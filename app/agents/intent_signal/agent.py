"""Intent Signal Agent.

Detects commercial buying signals from ``websites.extracted_text`` and
correlates them with technologies produced by the Technographic Agent.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.agents.base import AgentRunOutput, BaseAgent
from app.agents.context import AgentContext
from app.agents.intent_signal.normalization import (
    build_signal_key,
    normalize_label,
    normalize_signal_value,
)
from app.agents.intent_signal.rules import (
    SUPPORTED_SIGNAL_TYPES,
    IntentSignalRule,
    RuleMatch,
    TechnologyBoost,
    match_rule,
    rules_for_signal_types,
)
from app.agents.intent_signal.scoring import compute_recency_factor, compute_signal_score
from app.core.errors import AgentValidationError
from app.services import IntentSignalService, TechnologyService, WebsiteService


DEFAULT_MIN_CONFIDENCE = 0.35
DEFAULT_MIN_STRENGTH = 0.25
DEFAULT_MAX_SIGNALS_PER_TYPE = 5
MAX_SIGNALS_PER_TYPE = 25


@dataclass(frozen=True, slots=True)
class TechnologyContext:
    """Technology data used for signal correlation."""

    id: str
    name: str
    category: str
    confidence: float


@dataclass(frozen=True, slots=True)
class SignalCandidate:
    """Normalized intent signal candidate before persistence."""

    company_id: str
    contact_id: str | None
    website_id: str | None
    technology_id: str | None
    signal_type: str
    signal_name: str
    signal_value: str | None
    strength: float
    confidence: float
    source_url: str | None
    observed_at: datetime


class IntentSignalAgent(BaseAgent):
    """Detects evidence-backed business intent signals."""

    name = "intent_signal"
    version = "1.0.0"

    async def _validate_context(self, context: AgentContext) -> None:
        """Validate base context and agent-specific options."""
        await super()._validate_context(context)

        options = dict(context.options)

        min_confidence = options.get("min_confidence", DEFAULT_MIN_CONFIDENCE)
        if (
            not isinstance(min_confidence, (int, float))
            or min_confidence < 0.0
            or min_confidence > 1.0
        ):
            raise AgentValidationError(
                "min_confidence must be a number between 0.0 and 1.0.",
                details={"min_confidence": min_confidence},
            )

        min_strength = options.get("min_strength", DEFAULT_MIN_STRENGTH)
        if (
            not isinstance(min_strength, (int, float))
            or min_strength < 0.0
            or min_strength > 1.0
        ):
            raise AgentValidationError(
                "min_strength must be a number between 0.0 and 1.0.",
                details={"min_strength": min_strength},
            )

        max_signals = options.get("max_signals_per_type", DEFAULT_MAX_SIGNALS_PER_TYPE)
        if (
            not isinstance(max_signals, int)
            or max_signals < 1
            or max_signals > MAX_SIGNALS_PER_TYPE
        ):
            raise AgentValidationError(
                f"max_signals_per_type must be an integer between 1 and {MAX_SIGNALS_PER_TYPE}.",
                details={"max_signals_per_type": max_signals},
            )

        require_source_url = options.get("require_source_url", True)
        if not isinstance(require_source_url, bool):
            raise AgentValidationError(
                "require_source_url must be a boolean.",
                details={"require_source_url": require_source_url},
            )

        signal_types = options.get("signal_types")
        if signal_types is not None:
            if not isinstance(signal_types, list) or not all(
                isinstance(item, str) for item in signal_types
            ):
                raise AgentValidationError(
                    "signal_types must be a list of strings.",
                    details={"signal_types": signal_types},
                )
            invalid = set(signal_types) - SUPPORTED_SIGNAL_TYPES
            if invalid:
                raise AgentValidationError(
                    f"Invalid signal_types: {sorted(invalid)}.",
                    details={"invalid_signal_types": sorted(invalid)},
                )

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        """Execute intent signal detection and persistence."""
        options = dict(context.options)
        min_confidence: float = float(options.get("min_confidence", DEFAULT_MIN_CONFIDENCE))
        min_strength: float = float(options.get("min_strength", DEFAULT_MIN_STRENGTH))
        max_signals_per_type: int = int(
            options.get("max_signals_per_type", DEFAULT_MAX_SIGNALS_PER_TYPE),
        )
        require_source_url: bool = bool(options.get("require_source_url", True))
        signal_types: list[str] | None = options.get("signal_types")

        website_service = self._service("website_service", WebsiteService)
        technology_service = self._service("technology_service", TechnologyService)
        intent_signal_service = self._service("intent_signal_service", IntentSignalService)

        websites = website_service.list_by_company(context.company_id, limit=500)
        technologies = technology_service.list_by_company(context.company_id, limit=500)
        existing_signals = intent_signal_service.list_by_company(context.company_id, limit=500)
        rules = rules_for_signal_types(signal_types)
        technology_contexts = [
            TechnologyContext(
                id=technology.id,
                name=technology.name,
                category=technology.category,
                confidence=technology.confidence,
            )
            for technology in technologies
        ]

        self.logger.info(
            "Starting intent signal analysis",
            extra={
                "company_id": context.company_id,
                "total_websites": len(websites),
                "total_technologies": len(technology_contexts),
                "total_rules": len(rules),
            },
        )

        pages_scanned = 0
        pages_skipped_no_text = 0
        candidate_signals_detected = 0
        signals_below_threshold = 0
        signals_deduplicated = 0

        candidates: list[SignalCandidate] = []
        seen_keys = {
            build_signal_key(
                company_id=signal.company_id,
                signal_type=signal.signal_type,
                signal_name=signal.signal_name,
                website_id=signal.website_id,
                technology_id=signal.technology_id,
            )
            for signal in existing_signals
        }

        for website in websites:
            extracted_text = getattr(website, "extracted_text", None)
            if not extracted_text:
                pages_skipped_no_text += 1
                self.logger.debug(
                    "Skipping website without extracted_text",
                    extra={"website_id": getattr(website, "id", None)},
                )
                continue

            pages_scanned += 1
            page_candidates = self._detect_page_candidates(
                context=context,
                website=website,
                text=extracted_text,
                rules=rules,
                technology_contexts=technology_contexts,
            )
            candidate_signals_detected += len(page_candidates)

            for candidate in page_candidates:
                if candidate.confidence < min_confidence or candidate.strength < min_strength:
                    signals_below_threshold += 1
                    continue
                if require_source_url and not candidate.source_url:
                    signals_below_threshold += 1
                    continue

                key = build_signal_key(
                    company_id=candidate.company_id,
                    signal_type=candidate.signal_type,
                    signal_name=candidate.signal_name,
                    website_id=candidate.website_id,
                    technology_id=candidate.technology_id,
                )
                if key in seen_keys:
                    signals_deduplicated += 1
                    continue
                seen_keys.add(key)
                candidates.append(candidate)

        selected_candidates = self._limit_by_signal_type(
            candidates,
            max_signals_per_type=max_signals_per_type,
        )
        signals_deduplicated += len(candidates) - len(selected_candidates)

        intent_signal_ids: list[str] = []
        for candidate in selected_candidates:
            created = intent_signal_service.create(
                company_id=candidate.company_id,
                contact_id=candidate.contact_id,
                website_id=candidate.website_id,
                technology_id=candidate.technology_id,
                agent_run_id=None,
                signal_type=candidate.signal_type,
                signal_name=candidate.signal_name,
                signal_value=candidate.signal_value,
                strength=candidate.strength,
                confidence=candidate.confidence,
                source_url=candidate.source_url,
                observed_at=candidate.observed_at,
            )
            intent_signal_ids.append(created.id)

        summary = (
            f"Detected {len(intent_signal_ids)} intent signal(s) across"
            f" {pages_scanned} page(s)."
            f" {signals_below_threshold} below threshold."
            f" {signals_deduplicated} duplicate candidate(s) skipped."
            f" {pages_skipped_no_text} page(s) skipped (no text)."
        )

        self.logger.info(
            "Intent signal analysis completed",
            extra={
                "company_id": context.company_id,
                "signals_persisted": len(intent_signal_ids),
                "pages_scanned": pages_scanned,
                "signals_deduplicated": signals_deduplicated,
            },
        )

        return AgentRunOutput(
            output_ids={"intent_signals": intent_signal_ids},
            summary=summary,
            stats={
                "pages_considered": len(websites),
                "pages_scanned": pages_scanned,
                "pages_skipped_no_text": pages_skipped_no_text,
                "technologies_considered": len(technology_contexts),
                "candidate_signals_detected": candidate_signals_detected,
                "signals_persisted": len(intent_signal_ids),
                "signals_below_threshold": signals_below_threshold,
                "signals_deduplicated": signals_deduplicated,
                "min_confidence": min_confidence,
                "min_strength": min_strength,
            },
        )

    def _detect_page_candidates(
        self,
        *,
        context: AgentContext,
        website: Any,
        text: str,
        rules: tuple[IntentSignalRule, ...],
        technology_contexts: list[TechnologyContext],
    ) -> list[SignalCandidate]:
        """Detect normalized candidates from one website's extracted text."""
        candidates: list[SignalCandidate] = []
        page_type = getattr(website, "page_type", None)
        page_type_key = str(page_type) if page_type else ""
        source_url = getattr(website, "url", None)
        website_id = getattr(website, "id", None)
        observed_at = getattr(website, "last_scraped_at", None) or datetime.now(timezone.utc)
        recency_factor = compute_recency_factor(observed_at)

        for rule in rules:
            rule_match = match_rule(rule, text)
            if rule_match is None:
                continue

            best_technology, technology_context_score = self._best_technology_match(
                rule_match.rule.technology_boosts,
                technology_contexts,
            )
            technology_boost = technology_context_score
            page_context_score = min(rule.page_type_boosts.get(page_type_key, 0.0), 0.2)

            score = compute_signal_score(
                matched_pattern_weights=rule_match.pattern_weights,
                page_context_score=page_context_score,
                technology_context_score=technology_context_score,
                base_strength=rule.base_strength,
                specificity_boost=rule_match.specificity_boost,
                technology_boost=technology_boost,
                recency_factor=recency_factor,
            )

            candidates.append(
                SignalCandidate(
                    company_id=context.company_id,
                    contact_id=context.contact_id,
                    website_id=website_id,
                    technology_id=best_technology.id if best_technology else None,
                    signal_type=normalize_label(rule.signal_type),
                    signal_name=normalize_label(rule.signal_name),
                    signal_value=self._build_signal_value(rule_match),
                    strength=score.strength,
                    confidence=score.confidence,
                    source_url=source_url,
                    observed_at=observed_at,
                ),
            )

        return candidates

    def _best_technology_match(
        self,
        boosts: tuple[TechnologyBoost, ...],
        technologies: list[TechnologyContext],
    ) -> tuple[TechnologyContext | None, float]:
        """Find the strongest technology correlation for a rule."""
        best_technology: TechnologyContext | None = None
        best_score = 0.0

        for boost in boosts:
            for technology in technologies:
                if not boost.matches(
                    technology_name=technology.name,
                    technology_category=technology.category,
                ):
                    continue
                score = min(technology.confidence * boost.weight, 0.2)
                if score > best_score:
                    best_score = score
                    best_technology = technology

        return best_technology, best_score

    def _build_signal_value(self, rule_match: RuleMatch) -> str | None:
        """Build a normalized persisted evidence summary."""
        if rule_match.signal_value:
            return normalize_signal_value(rule_match.signal_value)
        return normalize_signal_value(rule_match.rule.signal_name)

    def _limit_by_signal_type(
        self,
        candidates: list[SignalCandidate],
        *,
        max_signals_per_type: int,
    ) -> list[SignalCandidate]:
        """Limit noisy outputs by keeping strongest candidates per type."""
        grouped: dict[str, list[SignalCandidate]] = defaultdict(list)
        for candidate in candidates:
            grouped[candidate.signal_type].append(candidate)

        selected: list[SignalCandidate] = []
        for signal_type in sorted(grouped):
            ranked = sorted(
                grouped[signal_type],
                key=lambda candidate: (candidate.strength, candidate.confidence),
                reverse=True,
            )
            selected.extend(ranked[:max_signals_per_type])
        return selected
