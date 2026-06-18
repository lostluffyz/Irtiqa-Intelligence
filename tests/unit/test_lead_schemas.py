from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.lead import (
    LeadIntelligenceScoreResponse,
    LeadIntentSignalResponse,
    LeadListResponse,
    LeadOutreachMessageResponse,
    LeadResponse,
    LeadTechnologyResponse,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_lead_technology_response_serializes() -> None:
    data = LeadTechnologyResponse(name="HubSpot", category="crm")
    assert data.name == "HubSpot"
    assert data.category == "crm"


def test_lead_intent_signal_response_serializes() -> None:
    data = LeadIntentSignalResponse(signal_type="technology_change", confidence=0.88)
    assert data.signal_type == "technology_change"
    assert data.confidence == 0.88


def test_lead_intelligence_score_response_serializes() -> None:
    data = LeadIntelligenceScoreResponse(total_score=81.4, opportunity_score=82.0, urgency_score=76.0)
    assert data.total_score == 81.4
    assert data.opportunity_score == 82.0
    assert data.urgency_score == 76.0


def test_lead_outreach_message_response_serializes() -> None:
    data = LeadOutreachMessageResponse(
        channel="email",
        subject="Hello",
        message_body="Test message",
    )
    assert data.channel == "email"
    assert data.subject == "Hello"
    assert data.message_body == "Test message"


def test_lead_outreach_message_response_optional_subject() -> None:
    data = LeadOutreachMessageResponse(
        channel="linkedin",
        subject=None,
        message_body="Direct message",
    )
    assert data.subject is None


def test_lead_response_serializes_full() -> None:
    now = _utc_now()
    data = LeadResponse(
        company_id="c1",
        company_name="Acme Corp",
        domain="acme.com",
        industry="software",
        status="active",
        technologies=[LeadTechnologyResponse(name="HubSpot", category="crm")],
        intent_signals=[LeadIntentSignalResponse(signal_type="hiring", confidence=0.7)],
        latest_intelligence_score=LeadIntelligenceScoreResponse(
            total_score=75.0,
            opportunity_score=80.0,
            urgency_score=65.0,
        ),
        outreach_messages=[LeadOutreachMessageResponse(
            channel="email",
            subject="Hi",
            message_body="Body",
        )],
        updated_at=now,
    )
    assert data.company_id == "c1"
    assert len(data.technologies) == 1
    assert len(data.intent_signals) == 1
    assert data.latest_intelligence_score is not None
    assert len(data.outreach_messages) == 1


def test_lead_response_without_score() -> None:
    now = _utc_now()
    data = LeadResponse(
        company_id="c2",
        company_name="No Score Inc",
        domain="noscore.com",
        industry=None,
        status="needs_review",
        technologies=[],
        intent_signals=[],
        latest_intelligence_score=None,
        outreach_messages=[],
        updated_at=now,
    )
    assert data.latest_intelligence_score is None
    assert data.technologies == []
    assert data.intent_signals == []
    assert data.outreach_messages == []


def test_lead_list_response_serializes() -> None:
    now = _utc_now()
    lead = LeadResponse(
        company_id="c3",
        company_name="List Test",
        domain="list.test",
        industry="tech",
        status="active",
        technologies=[],
        intent_signals=[],
        latest_intelligence_score=None,
        outreach_messages=[],
        updated_at=now,
    )
    response = LeadListResponse(
        items=[lead],
        total=1,
        limit=100,
        offset=0,
    )
    assert len(response.items) == 1
    assert response.total == 1
    assert response.limit == 100
    assert response.offset == 0


def test_lead_list_response_empty() -> None:
    response = LeadListResponse(items=[], total=0, limit=100, offset=0)
    assert response.items == []
    assert response.total == 0
