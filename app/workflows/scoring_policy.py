from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.technology import Technology


SCORE_VERSION = "score_refresh.v1"
DEFAULT_INTENT_LOOKBACK_DAYS = 90


@dataclass(frozen=True)
class ScoreRefreshInput:
    company: Company
    contact: Contact | None
    technologies: Sequence[Technology]
    intent_signals: Sequence[IntentSignal]
    scored_at: datetime
    intent_lookback_days: int = DEFAULT_INTENT_LOOKBACK_DAYS


@dataclass(frozen=True)
class ScorePolicyResult:
    fit_score: float
    intent_score: float
    technographic_score: float
    engagement_score: float
    total_score: float
    confidence: float
    score_version: str
    rationale: str
    scored_at: datetime
    primary_technology_id: str | None


class DeterministicScoreRefreshPolicy:
    score_version = SCORE_VERSION

    def score(self, score_input: ScoreRefreshInput) -> ScorePolicyResult:
        fit_score = self._fit_score(score_input.company, score_input.contact)
        intent_score = self._intent_score(
            score_input.intent_signals,
            scored_at=score_input.scored_at,
            lookback_days=score_input.intent_lookback_days,
        )
        technographic_score = self._technographic_score(score_input.technologies)
        engagement_score = self._engagement_score(
            score_input.company,
            score_input.contact,
            score_input.technologies,
            score_input.intent_signals,
        )
        total_score = _round_score(
            (fit_score * 0.30)
            + (intent_score * 0.35)
            + (technographic_score * 0.25)
            + (engagement_score * 0.10)
        )
        confidence = self._confidence(
            score_input.company,
            score_input.contact,
            score_input.technologies,
            score_input.intent_signals,
        )
        primary_technology_id = self._primary_technology_id(score_input.technologies)
        rationale = self._rationale(
            company=score_input.company,
            contact=score_input.contact,
            technologies=score_input.technologies,
            intent_signals=score_input.intent_signals,
            fit_score=fit_score,
            intent_score=intent_score,
            technographic_score=technographic_score,
            engagement_score=engagement_score,
            total_score=total_score,
            confidence=confidence,
        )
        return ScorePolicyResult(
            fit_score=fit_score,
            intent_score=intent_score,
            technographic_score=technographic_score,
            engagement_score=engagement_score,
            total_score=total_score,
            confidence=confidence,
            score_version=self.score_version,
            rationale=rationale,
            scored_at=score_input.scored_at,
            primary_technology_id=primary_technology_id,
        )

    def _fit_score(self, company: Company, contact: Contact | None) -> float:
        score = 0.0
        score += 10.0 if _present(company.name) else 0.0
        score += 10.0 if _present(company.domain) else 0.0
        score += 10.0 if _present(company.industry) else 0.0
        score += 10.0 if _present(company.company_size) else 0.0
        score += 5.0 if _present(company.headquarters) else 0.0
        score += 10.0 if _present(company.description) else 0.0
        score += 5.0 if _present(company.linkedin_url) else 0.0

        if contact is not None:
            score += 10.0 if _present(contact.email) else 0.0
            score += 10.0 if _present(contact.title) else 0.0
            score += 8.0 if _present(contact.department) else 0.0
            score += 8.0 if _present(contact.seniority) else 0.0
            score += 4.0 if _present(contact.linkedin_url) else 0.0

        return _round_score(score)

    def _intent_score(
        self,
        intent_signals: Sequence[IntentSignal],
        *,
        scored_at: datetime,
        lookback_days: int,
    ) -> float:
        if not intent_signals:
            return 0.0

        contributions: list[float] = []
        for signal in intent_signals:
            age_days = max((_aware(scored_at) - _aware(signal.observed_at)).days, 0)
            if age_days > lookback_days:
                continue
            recency_weight = max(0.25, 1.0 - (age_days / max(lookback_days, 1)))
            contributions.append(signal.strength * signal.confidence * recency_weight)

        if not contributions:
            return 0.0

        signal_density = min(sum(contributions), 3.0) / 3.0
        return _round_score(signal_density * 100.0)

    def _technographic_score(self, technologies: Sequence[Technology]) -> float:
        if not technologies:
            return 0.0

        confidence_sum = sum(technology.confidence for technology in technologies)
        category_count = len({technology.category.strip().lower() for technology in technologies})
        confidence_component = min(confidence_sum, 4.0) / 4.0 * 75.0
        diversity_component = min(category_count, 5) / 5.0 * 25.0
        return _round_score(confidence_component + diversity_component)

    def _engagement_score(
        self,
        company: Company,
        contact: Contact | None,
        technologies: Sequence[Technology],
        intent_signals: Sequence[IntentSignal],
    ) -> float:
        score = 10.0 if _present(company.domain) else 0.0
        score += 15.0 if technologies else 0.0
        score += 20.0 if intent_signals else 0.0

        if contact is not None:
            score += 20.0 if _present(contact.email) else 0.0
            score += 15.0 if _present(contact.title) else 0.0
            score += 10.0 if _present(contact.department) else 0.0
            score += 10.0 if _present(contact.linkedin_url) else 0.0
        else:
            score += 15.0 if _present(company.linkedin_url) else 0.0

        return _round_score(min(score, 100.0))

    def _confidence(
        self,
        company: Company,
        contact: Contact | None,
        technologies: Sequence[Technology],
        intent_signals: Sequence[IntentSignal],
    ) -> float:
        evidence_points = 0.20
        evidence_points += 0.10 if _present(company.industry) else 0.0
        evidence_points += 0.10 if _present(company.company_size) else 0.0
        evidence_points += min(sum(technology.confidence for technology in technologies), 3.0) / 3.0 * 0.25
        evidence_points += min(
            sum(signal.strength * signal.confidence for signal in intent_signals),
            3.0,
        ) / 3.0 * 0.25
        if contact is not None:
            evidence_points += 0.05 if _present(contact.email) else 0.0
            evidence_points += 0.05 if _present(contact.title) else 0.0
        return round(min(evidence_points, 1.0), 4)

    def _primary_technology_id(self, technologies: Sequence[Technology]) -> str | None:
        if not technologies:
            return None
        return max(technologies, key=lambda technology: technology.confidence).id

    def _rationale(
        self,
        *,
        company: Company,
        contact: Contact | None,
        technologies: Sequence[Technology],
        intent_signals: Sequence[IntentSignal],
        fit_score: float,
        intent_score: float,
        technographic_score: float,
        engagement_score: float,
        total_score: float,
        confidence: float,
    ) -> str:
        target = f"company {company.id}"
        if contact is not None:
            target = f"contact {contact.id} at company {company.id}"
        return (
            f"score_refresh.v1 scored {target} using {len(technologies)} technologies "
            f"and {len(intent_signals)} intent signals. Components: fit={fit_score}, "
            f"intent={intent_score}, technographic={technographic_score}, "
            f"engagement={engagement_score}, total={total_score}, confidence={confidence}."
        )


def _present(value: str | None) -> bool:
    return bool(value and value.strip())


def _round_score(value: float) -> float:
    return round(max(0.0, min(value, 100.0)), 2)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
