"""Rule registry for deterministic intent signal detection."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal

from app.agents.intent_signal.normalization import extract_evidence_snippet, normalize_text


SIGNAL_HIRING_ACTIVITY = "hiring_activity"
SIGNAL_GROWTH_ACTIVITY = "growth_activity"
SIGNAL_EXPANSION_ACTIVITY = "expansion_activity"
SIGNAL_FUNDING_INDICATOR = "funding_indicator"
SIGNAL_PRODUCT_LAUNCH_INDICATOR = "product_launch_indicator"
SIGNAL_PARTNERSHIP_INDICATOR = "partnership_indicator"
SIGNAL_ENTERPRISE_READINESS = "enterprise_readiness"
SIGNAL_DIGITAL_TRANSFORMATION = "digital_transformation"

SUPPORTED_SIGNAL_TYPES = frozenset(
    {
        SIGNAL_HIRING_ACTIVITY,
        SIGNAL_GROWTH_ACTIVITY,
        SIGNAL_EXPANSION_ACTIVITY,
        SIGNAL_FUNDING_INDICATOR,
        SIGNAL_PRODUCT_LAUNCH_INDICATOR,
        SIGNAL_PARTNERSHIP_INDICATOR,
        SIGNAL_ENTERPRISE_READINESS,
        SIGNAL_DIGITAL_TRANSFORMATION,
    }
)

TechnologyMatchMode = Literal["category", "name"]


@dataclass(frozen=True, slots=True)
class TextPattern:
    """Pattern used to detect intent evidence in cleaned page text."""

    pattern: str
    weight: float
    is_regex: bool = False
    evidence_window_chars: int = 120

    def matches(self, normalized_text: str) -> bool:
        """Return whether the pattern matches normalized text."""
        normalized_text = normalize_text(normalized_text)
        if self.is_regex:
            return re.search(self.pattern, normalized_text, re.IGNORECASE) is not None
        return self.pattern.lower() in normalized_text

    def snippet_from(self, original_text: str) -> str | None:
        """Extract a source snippet for this pattern."""
        return extract_evidence_snippet(
            original_text,
            self.pattern,
            is_regex=self.is_regex,
            window_chars=self.evidence_window_chars,
        )


@dataclass(frozen=True, slots=True)
class TechnologyBoost:
    """Technology correlation that can strengthen a signal."""

    mode: TechnologyMatchMode
    value: str
    weight: float

    def matches(self, *, technology_name: str, technology_category: str) -> bool:
        """Return whether a technology matches this boost."""
        expected = normalize_text(self.value)
        if self.mode == "category":
            return normalize_text(technology_category) == expected
        return expected in normalize_text(technology_name)


@dataclass(frozen=True, slots=True)
class IntentSignalRule:
    """Deterministic rule for one commercial intent signal."""

    signal_type: str
    signal_name: str
    patterns: tuple[TextPattern, ...]
    page_type_boosts: dict[str, float]
    technology_boosts: tuple[TechnologyBoost, ...]
    base_strength: float
    base_confidence: float


@dataclass(frozen=True, slots=True)
class RuleMatch:
    """Matched rule evidence on a single page."""

    rule: IntentSignalRule
    matched_patterns: tuple[TextPattern, ...]
    signal_value: str | None
    specificity_boost: float

    @property
    def pattern_weights(self) -> list[float]:
        return [pattern.weight for pattern in self.matched_patterns]


def calculate_specificity_boost(text: str) -> float:
    """Score specific evidence such as counts, roles, compliance labels, or geographies."""
    normalized = normalize_text(text)
    boost = 0.0
    if re.search(r"\b\d+(\+| percent|%)?\b", normalized):
        boost += 0.05
    if re.search(r"\b(engineer|sales|revops|customer success|director|vp|enterprise)\b", normalized):
        boost += 0.05
    if re.search(r"\b(soc 2|sso|sla|gdpr|hipaa|iso 27001)\b", normalized):
        boost += 0.05
    if re.search(r"\b(north america|europe|apac|international|global|new york|london)\b", normalized):
        boost += 0.05
    return min(boost, 0.2)


def match_rule(rule: IntentSignalRule, text: str) -> RuleMatch | None:
    """Match a rule against original page text."""
    normalized = normalize_text(text)
    matched = tuple(pattern for pattern in rule.patterns if pattern.matches(normalized))
    if not matched:
        return None

    snippet = next(
        (pattern.snippet_from(text) for pattern in matched if pattern.snippet_from(text)),
        None,
    )
    return RuleMatch(
        rule=rule,
        matched_patterns=matched,
        signal_value=snippet,
        specificity_boost=calculate_specificity_boost(snippet or text),
    )


def _p(pattern: str, weight: float, *, regex: bool = False) -> TextPattern:
    return TextPattern(pattern=pattern, weight=weight, is_regex=regex)


RULE_REGISTRY: tuple[IntentSignalRule, ...] = (
    IntentSignalRule(
        signal_type=SIGNAL_HIRING_ACTIVITY,
        signal_name="Hiring for growth roles",
        patterns=(
            _p("we are hiring", 0.35),
            _p("join our team", 0.3),
            _p(r"\b(open roles|open positions|job openings)\b", 0.35, regex=True),
            _p(r"\b(hiring|recruiting) (sales|engineers|engineering|revops|customer success)\b", 0.45, regex=True),
        ),
        page_type_boosts={"careers": 0.2, "about": 0.05},
        technology_boosts=(
            TechnologyBoost("category", "analytics", 0.08),
            TechnologyBoost("category", "chat_widget", 0.06),
            TechnologyBoost("name", "HubSpot", 0.1),
        ),
        base_strength=0.45,
        base_confidence=0.35,
    ),
    IntentSignalRule(
        signal_type=SIGNAL_GROWTH_ACTIVITY,
        signal_name="Business growth momentum",
        patterns=(
            _p("rapid growth", 0.35),
            _p("fast growing", 0.3),
            _p(r"\b(revenue|customer|user|team) growth\b", 0.4, regex=True),
            _p(r"\b\d+% growth\b", 0.45, regex=True),
        ),
        page_type_boosts={"about": 0.08, "blog": 0.08, "case_study": 0.1},
        technology_boosts=(
            TechnologyBoost("category", "analytics", 0.08),
            TechnologyBoost("category", "marketing_pixel", 0.06),
            TechnologyBoost("category", "ecommerce", 0.08),
        ),
        base_strength=0.5,
        base_confidence=0.35,
    ),
    IntentSignalRule(
        signal_type=SIGNAL_EXPANSION_ACTIVITY,
        signal_name="Market or segment expansion",
        patterns=(
            _p("new market", 0.3),
            _p("new office", 0.3),
            _p("international expansion", 0.45),
            _p(r"\b(expanding|expanded) (into|across|our presence)\b", 0.4, regex=True),
            _p("enterprise segment", 0.35),
        ),
        page_type_boosts={"about": 0.08, "blog": 0.1, "news": 0.12},
        technology_boosts=(
            TechnologyBoost("category", "cdn", 0.05),
            TechnologyBoost("category", "hosting", 0.06),
            TechnologyBoost("category", "ecommerce", 0.08),
        ),
        base_strength=0.52,
        base_confidence=0.35,
    ),
    IntentSignalRule(
        signal_type=SIGNAL_FUNDING_INDICATOR,
        signal_name="Funding or investor-backed growth",
        patterns=(
            _p("raised", 0.25),
            _p("funding round", 0.4),
            _p(r"\bseries [a-e]\b", 0.45, regex=True),
            _p("backed by", 0.35),
            _p("investors include", 0.4),
        ),
        page_type_boosts={"about": 0.08, "blog": 0.12, "news": 0.15},
        technology_boosts=(
            TechnologyBoost("category", "analytics", 0.05),
            TechnologyBoost("category", "hosting", 0.05),
        ),
        base_strength=0.65,
        base_confidence=0.4,
    ),
    IntentSignalRule(
        signal_type=SIGNAL_PRODUCT_LAUNCH_INDICATOR,
        signal_name="Product or feature launch",
        patterns=(
            _p("new product", 0.35),
            _p("new feature", 0.3),
            _p("beta launch", 0.35),
            _p("platform rollout", 0.4),
            _p(r"\b(launched|introducing|announcing) (our )?(new )?(product|feature|platform)\b", 0.45, regex=True),
        ),
        page_type_boosts={"blog": 0.15, "product": 0.12, "docs": 0.08},
        technology_boosts=(
            TechnologyBoost("category", "frontend_framework", 0.08),
            TechnologyBoost("category", "hosting", 0.06),
            TechnologyBoost("category", "cdn", 0.05),
        ),
        base_strength=0.55,
        base_confidence=0.35,
    ),
    IntentSignalRule(
        signal_type=SIGNAL_PARTNERSHIP_INDICATOR,
        signal_name="Partnership or ecosystem motion",
        patterns=(
            _p("strategic partnership", 0.45),
            _p("partnered with", 0.4),
            _p("integration partner", 0.35),
            _p("marketplace listing", 0.35),
            _p("channel partner", 0.35),
        ),
        page_type_boosts={"partners": 0.2, "integrations": 0.15, "blog": 0.1},
        technology_boosts=(
            TechnologyBoost("category", "ecommerce", 0.06),
            TechnologyBoost("name", "Stripe", 0.08),
            TechnologyBoost("name", "HubSpot", 0.08),
        ),
        base_strength=0.5,
        base_confidence=0.35,
    ),
    IntentSignalRule(
        signal_type=SIGNAL_ENTERPRISE_READINESS,
        signal_name="Enterprise readiness",
        patterns=(
            _p("soc 2", 0.45),
            _p("single sign-on", 0.35),
            _p("sso", 0.3),
            _p("service level agreement", 0.35),
            _p("enterprise pricing", 0.4),
            _p("sla", 0.25),
        ),
        page_type_boosts={"pricing": 0.15, "security": 0.2, "docs": 0.08},
        technology_boosts=(
            TechnologyBoost("category", "hosting", 0.05),
            TechnologyBoost("category", "cdn", 0.04),
            TechnologyBoost("name", "Cloudflare", 0.06),
        ),
        base_strength=0.58,
        base_confidence=0.4,
    ),
    IntentSignalRule(
        signal_type=SIGNAL_DIGITAL_TRANSFORMATION,
        signal_name="Digital transformation initiative",
        patterns=(
            _p("digital transformation", 0.45),
            _p("cloud migration", 0.4),
            _p("automation initiative", 0.35),
            _p("ai adoption", 0.35),
            _p("data platform", 0.35),
            _p(r"\b(modernizing|automating|migrating) (our )?(operations|workflows|platform|infrastructure)\b", 0.45, regex=True),
        ),
        page_type_boosts={"blog": 0.1, "docs": 0.08, "product": 0.1},
        technology_boosts=(
            TechnologyBoost("category", "analytics", 0.08),
            TechnologyBoost("category", "hosting", 0.08),
            TechnologyBoost("category", "frontend_framework", 0.05),
        ),
        base_strength=0.52,
        base_confidence=0.35,
    ),
)


def rules_for_signal_types(signal_types: list[str] | None) -> tuple[IntentSignalRule, ...]:
    """Return the active rule set for an optional signal type filter."""
    if signal_types is None:
        return RULE_REGISTRY
    allowed = frozenset(signal_types)
    return tuple(rule for rule in RULE_REGISTRY if rule.signal_type in allowed)
