from datetime import datetime, timedelta, timezone

from app.agents.intent_signal.scoring import (
    compute_confidence,
    compute_recency_factor,
    compute_signal_score,
    compute_strength,
    normalize_context_component,
)


def test_normalize_context_component_caps_and_normalizes() -> None:
    assert normalize_context_component(0.0) == 0.0
    assert normalize_context_component(0.1) == 0.5
    assert normalize_context_component(0.2) == 1.0
    assert normalize_context_component(0.5) == 1.0


def test_compute_confidence_uses_approved_formula() -> None:
    confidence = compute_confidence(
        matched_pattern_weights=[0.5],
        page_context_score=0.2,
        technology_context_score=0.2,
    )
    assert confidence == 0.675


def test_compute_confidence_caps_pattern_score() -> None:
    confidence = compute_confidence(
        matched_pattern_weights=[0.8, 0.7],
        page_context_score=0.2,
        technology_context_score=0.2,
    )
    assert confidence == 1.0


def test_compute_strength_uses_approved_formula() -> None:
    strength = compute_strength(
        base_strength=0.5,
        specificity_boost=0.1,
        technology_boost=0.05,
        recency_factor=0.85,
    )
    assert strength == 0.5525


def test_compute_recency_factor_reduces_stale_content() -> None:
    now = datetime(2026, 6, 7, tzinfo=timezone.utc)
    assert compute_recency_factor(now - timedelta(days=30), current_time=now) == 1.0
    assert compute_recency_factor(now - timedelta(days=120), current_time=now) == 0.85
    assert compute_recency_factor(now - timedelta(days=250), current_time=now) == 0.7
    assert compute_recency_factor(now - timedelta(days=500), current_time=now) == 0.55


def test_compute_signal_score_returns_bounded_pair() -> None:
    score = compute_signal_score(
        matched_pattern_weights=[1.0],
        page_context_score=0.2,
        technology_context_score=0.2,
        base_strength=0.9,
        specificity_boost=0.2,
        technology_boost=0.2,
        recency_factor=1.0,
    )

    assert score.confidence == 1.0
    assert score.strength == 1.0
