from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas import (
    AgentRunCreate,
    AgentRunList,
    AgentRunRead,
    AgentRunUpdate,
    CompanyCreate,
    CompanyList,
    CompanyRead,
    CompanyUpdate,
    ContactCreate,
    ContactList,
    ContactRead,
    ContactUpdate,
    IntentSignalCreate,
    IntentSignalList,
    IntentSignalRead,
    IntentSignalUpdate,
    IntelligenceScoreCreate,
    IntelligenceScoreList,
    IntelligenceScoreRead,
    IntelligenceScoreUpdate,
    OutreachMessageCreate,
    OutreachMessageList,
    OutreachMessageRead,
    OutreachMessageUpdate,
    TechnologyCreate,
    TechnologyList,
    TechnologyRead,
    TechnologyUpdate,
    WebsiteCreate,
    WebsiteList,
    WebsiteRead,
    WebsiteUpdate,
)


UUID_1 = "11111111-1111-1111-1111-111111111111"
UUID_2 = "22222222-2222-2222-2222-222222222222"
UUID_3 = "33333333-3333-3333-3333-333333333333"
UUID_4 = "44444444-4444-4444-4444-444444444444"
UUID_5 = "55555555-5555-5555-5555-555555555555"
NOW = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)


SCHEMA_CASES: tuple[
    tuple[type[BaseModel], type[BaseModel], type[BaseModel], type[BaseModel], dict[str, Any]],
    ...,
] = (
    (
        CompanyCreate,
        CompanyUpdate,
        CompanyRead,
        CompanyList,
        {
            "name": "Irtiqa Test Company",
            "domain": "irtiqa-test.example",
            "industry": "software",
            "company_size": "11-50",
            "headquarters": "Bengaluru, India",
            "description": "A production schema test company.",
            "linkedin_url": "https://linkedin.com/company/irtiqa-test",
            "status": "active",
        },
    ),
    (
        ContactCreate,
        ContactUpdate,
        ContactRead,
        ContactList,
        {
            "company_id": UUID_1,
            "first_name": "Asha",
            "last_name": "Rao",
            "full_name": "Asha Rao",
            "email": "asha.rao@irtiqa-test.example",
            "phone": "+91-555-0100",
            "title": "VP Revenue",
            "department": "sales",
            "seniority": "vp",
            "linkedin_url": "https://linkedin.com/in/asha-rao",
            "status": "active",
        },
    ),
    (
        WebsiteCreate,
        WebsiteUpdate,
        WebsiteRead,
        WebsiteList,
        {
            "company_id": UUID_1,
            "url": "https://irtiqa-test.example",
            "normalized_url": "https://irtiqa-test.example/",
            "page_type": "homepage",
            "http_status": 200,
            "last_scraped_at": NOW,
        },
    ),
    (
        TechnologyCreate,
        TechnologyUpdate,
        TechnologyRead,
        TechnologyList,
        {
            "company_id": UUID_1,
            "website_id": UUID_2,
            "agent_run_id": UUID_3,
            "name": "HubSpot",
            "category": "crm",
            "vendor": "HubSpot",
            "detection_method": "html_signature",
            "confidence": 0.92,
            "first_detected_at": NOW,
            "last_detected_at": NOW,
        },
    ),
    (
        IntentSignalCreate,
        IntentSignalUpdate,
        IntentSignalRead,
        IntentSignalList,
        {
            "company_id": UUID_1,
            "contact_id": UUID_2,
            "website_id": UUID_3,
            "technology_id": UUID_4,
            "agent_run_id": UUID_5,
            "signal_type": "technology_change",
            "signal_name": "CRM detected",
            "signal_value": "HubSpot detected on homepage",
            "strength": 0.75,
            "confidence": 0.88,
            "source_url": "https://irtiqa-test.example",
            "observed_at": NOW,
        },
    ),
    (
        IntelligenceScoreCreate,
        IntelligenceScoreUpdate,
        IntelligenceScoreRead,
        IntelligenceScoreList,
        {
            "company_id": UUID_1,
            "contact_id": UUID_2,
            "technology_id": UUID_3,
            "agent_run_id": UUID_4,
            "fit_score": 82.0,
            "intent_score": 76.0,
            "technographic_score": 91.0,
            "engagement_score": 70.0,
            "total_score": 81.4,
            "confidence": 0.86,
            "score_version": "schema-test-v1",
            "rationale": "Strong fit based on schema validation data.",
            "scored_at": NOW,
        },
    ),
    (
        OutreachMessageCreate,
        OutreachMessageUpdate,
        OutreachMessageRead,
        OutreachMessageList,
        {
            "company_id": UUID_1,
            "contact_id": UUID_2,
            "intelligence_score_id": UUID_3,
            "agent_run_id": UUID_4,
            "channel": "email",
            "subject": "Improving revenue workflow visibility",
            "message_body": "A focused schema test message body.",
            "personalization_angle": "CRM workflow detected",
            "call_to_action": "Book a discovery call",
            "status": "draft",
            "confidence": 0.81,
            "generated_at": NOW,
        },
    ),
    (
        AgentRunCreate,
        AgentRunUpdate,
        AgentRunRead,
        AgentRunList,
        {
            "company_id": UUID_1,
            "contact_id": UUID_2,
            "agent_name": "test_agent",
            "workflow_name": "test_workflow",
            "status": "succeeded",
            "input_summary": "schema test input",
            "output_summary": "schema test output",
            "error_message": None,
            "started_at": NOW,
            "finished_at": NOW,
        },
    ),
)


@pytest.mark.parametrize(("create_schema", "update_schema", "_read_schema", "_list_schema", "payload"), SCHEMA_CASES)
def test_create_and_update_schemas_validate_service_payloads(
    create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    _read_schema: type[BaseModel],
    _list_schema: type[BaseModel],
    payload: dict[str, Any],
) -> None:
    create_model = create_schema.model_validate(payload)
    update_field, update_value = next(iter(create_model.model_dump().items()))

    assert create_model.model_dump(exclude_none=True)[update_field] == update_value
    assert update_schema.model_validate({update_field: update_value}).model_dump(exclude_unset=True) == {
        update_field: update_value
    }


@pytest.mark.parametrize(("_create_schema", "update_schema", "_read_schema", "_list_schema", "_payload"), SCHEMA_CASES)
def test_update_schemas_reject_empty_payloads(
    _create_schema: type[BaseModel],
    update_schema: type[BaseModel],
    _read_schema: type[BaseModel],
    _list_schema: type[BaseModel],
    _payload: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        update_schema.model_validate({})


@pytest.mark.parametrize(("_create_schema", "_update_schema", "read_schema", "list_schema", "payload"), SCHEMA_CASES)
def test_read_and_list_schemas_serialize_from_attributes(
    _create_schema: type[BaseModel],
    _update_schema: type[BaseModel],
    read_schema: type[BaseModel],
    list_schema: type[BaseModel],
    payload: dict[str, Any],
) -> None:
    source = SimpleNamespace(id=UUID_1, created_at=NOW, updated_at=NOW, **payload)
    read_model = read_schema.model_validate(source)
    list_model = list_schema.model_validate(
        {"items": [read_model], "total": 1, "limit": 100, "offset": 0}
    )

    assert read_model.model_dump(mode="json")["id"] == UUID_1
    assert list_model.model_dump(mode="json")["items"][0]["id"] == UUID_1
    assert list_model.model_dump()["total"] == 1


def test_status_schemas_reject_unknown_status_values() -> None:
    with pytest.raises(ValidationError):
        CompanyCreate(name="Invalid", domain="invalid.example", status="unknown")

    with pytest.raises(ValidationError):
        ContactCreate(company_id=UUID_1, full_name="Invalid Contact", status="unknown")

    with pytest.raises(ValidationError):
        OutreachMessageCreate(
            company_id=UUID_1,
            channel="email",
            message_body="Body",
            personalization_angle="Angle",
            status="unknown",
            confidence=0.8,
            generated_at=NOW,
        )

    with pytest.raises(ValidationError):
        AgentRunCreate(agent_name="agent", status="unknown", started_at=NOW)


def test_numeric_range_validation_matches_database_constraints() -> None:
    with pytest.raises(ValidationError):
        TechnologyCreate(
            company_id=UUID_1,
            name="HubSpot",
            category="crm",
            detection_method="html_signature",
            confidence=1.1,
            first_detected_at=NOW,
            last_detected_at=NOW,
        )

    with pytest.raises(ValidationError):
        IntentSignalCreate(
            company_id=UUID_1,
            signal_type="growth",
            signal_name="Hiring",
            strength=-0.1,
            confidence=0.5,
            observed_at=NOW,
        )

    with pytest.raises(ValidationError):
        IntelligenceScoreCreate(
            company_id=UUID_1,
            fit_score=101.0,
            intent_score=76.0,
            technographic_score=91.0,
            engagement_score=70.0,
            total_score=81.4,
            confidence=0.86,
            score_version="schema-test-v1",
            rationale="Invalid score test.",
            scored_at=NOW,
        )


def test_blank_strings_are_rejected_after_trimming() -> None:
    with pytest.raises(ValidationError):
        CompanyCreate(name="   ", domain="blank.example")

    with pytest.raises(ValidationError):
        AgentRunCreate(agent_name="agent", workflow_name="   ", status="pending", started_at=NOW)
