from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.technology import Technology
from app.workflows.scoring_policy import (
    SCORE_VERSION,
    DeterministicScoreRefreshPolicy,
    ScoreRefreshInput,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_company(**overrides) -> Company:
    values = {
        "name": "Irtiqa Policy Company",
        "domain": "policy.example",
        "industry": "software",
        "company_size": "51-200",
        "headquarters": "Bengaluru, India",
        "description": "Revenue intelligence platform.",
        "linkedin_url": "https://linkedin.com/company/policy",
        "status": "active",
    }
    values.update(overrides)
    return Company(**values)


def make_contact(company: Company) -> Contact:
    return Contact(
        company=company,
        full_name="Asha Rao",
        email="asha.rao@policy.example",
        title="VP Revenue",
        department="sales",
        seniority="vp",
        linkedin_url="https://linkedin.com/in/asha-rao",
        status="active",
    )


def make_technology(company: Company, *, name: str = "HubSpot", category: str = "crm") -> Technology:
    now = utc_now()
    return Technology(
        company=company,
        name=name,
        category=category,
        detection_method="html_signature",
        confidence=0.9,
        first_detected_at=now,
        last_detected_at=now,
    )


def make_signal(company: Company, *, observed_at: datetime, strength: float = 0.8) -> IntentSignal:
    return IntentSignal(
        company=company,
        signal_type="technology_change",
        signal_name="CRM detected",
        strength=strength,
        confidence=0.9,
        observed_at=observed_at,
    )


def test_score_refresh_policy_returns_bounded_versioned_scores() -> None:
    company = make_company()
    contact = make_contact(company)
    now = utc_now()
    policy = DeterministicScoreRefreshPolicy()

    result = policy.score(
        ScoreRefreshInput(
            company=company,
            contact=contact,
            technologies=[make_technology(company), make_technology(company, name="Segment", category="cdp")],
            intent_signals=[make_signal(company, observed_at=now)],
            scored_at=now,
        )
    )

    assert result.score_version == SCORE_VERSION
    assert result.scored_at == now
    assert 0.0 <= result.fit_score <= 100.0
    assert 0.0 <= result.intent_score <= 100.0
    assert 0.0 <= result.technographic_score <= 100.0
    assert 0.0 <= result.engagement_score <= 100.0
    assert 0.0 <= result.total_score <= 100.0
    assert 0.0 <= result.confidence <= 1.0
    assert "score_refresh.v1" in result.rationale


def test_score_refresh_policy_rewards_persisted_evidence() -> None:
    sparse_company = make_company(industry=None, company_size=None, headquarters=None, description=None)
    rich_company = make_company()
    now = utc_now()
    policy = DeterministicScoreRefreshPolicy()

    sparse = policy.score(
        ScoreRefreshInput(
            company=sparse_company,
            contact=None,
            technologies=[],
            intent_signals=[],
            scored_at=now,
        )
    )
    rich = policy.score(
        ScoreRefreshInput(
            company=rich_company,
            contact=make_contact(rich_company),
            technologies=[make_technology(rich_company)],
            intent_signals=[make_signal(rich_company, observed_at=now)],
            scored_at=now,
        )
    )

    assert rich.total_score > sparse.total_score
    assert rich.confidence > sparse.confidence


def test_score_refresh_policy_applies_intent_recency_decay() -> None:
    company = make_company()
    now = utc_now()
    policy = DeterministicScoreRefreshPolicy()

    recent = policy.score(
        ScoreRefreshInput(
            company=company,
            contact=None,
            technologies=[],
            intent_signals=[make_signal(company, observed_at=now)],
            scored_at=now,
        )
    )
    stale = policy.score(
        ScoreRefreshInput(
            company=company,
            contact=None,
            technologies=[],
            intent_signals=[make_signal(company, observed_at=now - timedelta(days=180))],
            scored_at=now,
        )
    )

    assert recent.intent_score > stale.intent_score
