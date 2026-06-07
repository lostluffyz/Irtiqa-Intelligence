"""Scoring helpers for intent signal candidates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


MAX_CONTEXT_COMPONENT = 0.2


@dataclass(frozen=True, slots=True)
class SignalScore:
    """Computed intent signal score pair."""

    confidence: float
    strength: float


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    """Clamp a score into the database-supported range."""
    return max(minimum, min(value, maximum))


def normalize_context_component(value: float) -> float:
    """Cap a context component at 0.2 and normalize it to 0.0-1.0."""
    capped = min(max(value, 0.0), MAX_CONTEXT_COMPONENT)
    return capped / MAX_CONTEXT_COMPONENT


def compute_confidence(
    *,
    matched_pattern_weights: list[float],
    page_context_score: float,
    technology_context_score: float,
) -> float:
    """Compute confidence exactly from the approved design formula."""
    pattern_score = min(sum(matched_pattern_weights), 1.0)
    page_context_score_normalized = normalize_context_component(page_context_score)
    technology_context_score_normalized = normalize_context_component(
        technology_context_score,
    )

    confidence = (
        0.65 * pattern_score
        + 0.20 * page_context_score_normalized
        + 0.15 * technology_context_score_normalized
    )
    return round(clamp(confidence), 4)


def compute_recency_factor(
    observed_at: datetime | None,
    *,
    current_time: datetime | None = None,
) -> float:
    """Reduce strength for stale scraped content."""
    if observed_at is None:
        return 1.0

    now = current_time or datetime.now(timezone.utc)
    observed = observed_at
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)

    age_days = max((now - observed).days, 0)
    if age_days <= 90:
        return 1.0
    if age_days <= 180:
        return 0.85
    if age_days <= 365:
        return 0.7
    return 0.55


def compute_strength(
    *,
    base_strength: float,
    specificity_boost: float,
    technology_boost: float,
    recency_factor: float,
) -> float:
    """Compute commercial signal strength from the approved design formula."""
    strength = (base_strength + specificity_boost + technology_boost) * recency_factor
    return round(clamp(strength), 4)


def compute_signal_score(
    *,
    matched_pattern_weights: list[float],
    page_context_score: float,
    technology_context_score: float,
    base_strength: float,
    specificity_boost: float,
    technology_boost: float,
    recency_factor: float,
) -> SignalScore:
    """Compute both confidence and strength for a signal candidate."""
    return SignalScore(
        confidence=compute_confidence(
            matched_pattern_weights=matched_pattern_weights,
            page_context_score=page_context_score,
            technology_context_score=technology_context_score,
        ),
        strength=compute_strength(
            base_strength=base_strength,
            specificity_boost=specificity_boost,
            technology_boost=technology_boost,
            recency_factor=recency_factor,
        ),
    )
