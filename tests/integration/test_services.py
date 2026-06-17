from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from uuid import uuid4

from app.core.errors import EntityConflictError, EntityNotFoundError, ValidationError
from app.database import session as database_session
from app.models.company import Company
from app.models.organization import Organization
from app.services import (
    AgentRunService,
    CompanyService,
    ContactService,
    IntelligenceScoreService,
    IntentSignalService,
    OutreachMessageService,
    TechnologyService,
    WebsiteService,
)


@pytest.fixture()
def service_session_factory(
    migrated_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    factory = sessionmaker(
        bind=migrated_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    monkeypatch.setattr(database_session, "SessionLocal", factory)
    return factory


@pytest.fixture()
def service_database(service_session_factory: sessionmaker[Session]) -> Iterator[sessionmaker[Session]]:
    yield service_session_factory


@pytest.fixture()
def org_id(service_session_factory: sessionmaker[Session]) -> str:
    _org_id = str(uuid4())
    with service_session_factory() as session:
        session.add(Organization(id=_org_id, name="Service Test Org", slug="service-test", status="active"))
        session.commit()
    return _org_id


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_services_create_and_query_current_entities(service_database, org_id) -> None:
    company_service = CompanyService()
    contact_service = ContactService()
    website_service = WebsiteService()
    agent_run_service = AgentRunService()
    technology_service = TechnologyService()
    intent_signal_service = IntentSignalService()
    score_service = IntelligenceScoreService()
    outreach_service = OutreachMessageService()

    company = company_service.create(organization_id=org_id,
        name="Irtiqa Service Company",
        domain="irtiqa-service.example",
        industry="software",
        company_size="11-50",
        headquarters="Bengaluru, India",
        status="active",
    )
    contact = contact_service.create(organization_id=org_id, company_id=company.id,
        first_name="Asha",
        last_name="Rao",
        full_name="Asha Rao",
        email="asha.rao@irtiqa-service.example",
        title="VP Revenue",
        department="sales",
        seniority="vp",
        status="active",
    )
    website = website_service.create(company_id=company.id,
        url="https://irtiqa-service.example",
        normalized_url="https://irtiqa-service.example/",
        page_type="homepage",
        http_status=200,
        last_scraped_at=utc_now(),
    )
    agent_run = agent_run_service.create(organization_id=org_id, company_id=company.id,
        contact_id=contact.id,
        agent_name="test_agent",
        workflow_name="test_workflow",
        status="succeeded",
        input_summary="service test input",
        output_summary="service test output",
        started_at=utc_now(),
        finished_at=utc_now(),
    )
    technology = technology_service.create(company_id=company.id,
        website_id=website.id,
        agent_run_id=agent_run.id,
        name="HubSpot",
        category="crm",
        vendor="HubSpot",
        detection_method="html_signature",
        confidence=0.92,
        first_detected_at=utc_now(),
        last_detected_at=utc_now(),
    )
    intent_signal = intent_signal_service.create(organization_id=org_id, company_id=company.id,
        contact_id=contact.id,
        website_id=website.id,
        technology_id=technology.id,
        agent_run_id=agent_run.id,
        signal_type="technology_change",
        signal_name="CRM detected",
        signal_value="HubSpot detected on homepage",
        strength=0.75,
        confidence=0.88,
        source_url="https://irtiqa-service.example",
        observed_at=utc_now(),
    )
    score = score_service.create(organization_id=org_id, company_id=company.id,
        contact_id=contact.id,
        technology_id=technology.id,
        agent_run_id=agent_run.id,
        fit_score=82.0,
        intent_score=76.0,
        technographic_score=91.0,
        engagement_score=70.0,
        total_score=81.4,
        confidence=0.86,
        score_version="service-test-v1",
        rationale="Strong service test fit.",
        scored_at=utc_now(),
    )
    outreach_message = outreach_service.create(organization_id=org_id, company_id=company.id,
        contact_id=contact.id,
        intelligence_score_id=score.id,
        agent_run_id=agent_run.id,
        channel="email",
        subject="Improving revenue workflow visibility",
        message_body="A focused service test message body.",
        personalization_angle="CRM workflow detected",
        call_to_action="Book a discovery call",
        status="draft",
        confidence=0.81,
        generated_at=utc_now(),
    )

    required_company = company_service.get_required(company.id)
    matched_company = company_service.get_by_domain(company.domain, organization_id=org_id)
    matched_contact = contact_service.get_by_email(contact.email, organization_id=org_id)
    matched_website = website_service.get_by_normalized_url(website.normalized_url)
    assert required_company.domain == company.domain
    assert matched_company is not None
    assert matched_company.id == company.id
    assert [item.id for item in company_service.search_by_name("Service", organization_id=org_id)] == [company.id]
    assert [item.id for item in company_service.list_by_status("active", organization_id=org_id)] == [company.id]
    assert matched_contact is not None
    assert matched_contact.id == contact.id
    assert [item.id for item in contact_service.list_by_company(company.id, organization_id=org_id)] == [contact.id]
    assert matched_website is not None
    assert matched_website.id == website.id
    assert [item.id for item in website_service.list_by_company(company.id)] == [website.id]
    matched_technology = technology_service.get_company_technology(
        company_id=company.id,
        name=technology.name,
        category=technology.category,
    )
    assert matched_technology is not None
    assert matched_technology.id == technology.id
    assert [item.id for item in technology_service.list_by_category("crm")] == [technology.id]
    assert [item.id for item in intent_signal_service.list_by_type("technology_change", organization_id=org_id)] == [
        intent_signal.id
    ]
    latest_company_score = score_service.latest_for_company(company.id, organization_id=org_id)
    latest_contact_score = score_service.latest_for_contact(contact.id, organization_id=org_id)
    assert latest_company_score is not None
    assert latest_company_score.id == score.id
    assert latest_contact_score is not None
    assert latest_contact_score.id == score.id
    assert [item.id for item in outreach_service.list_by_status("draft", organization_id=org_id)] == [outreach_message.id]
    assert [item.id for item in agent_run_service.list_by_workflow("test_workflow", organization_id=org_id)] == [
        agent_run.id
    ]


def test_services_raise_structured_errors(service_database, org_id) -> None:
    service = CompanyService()
    service.create(organization_id=org_id, name="Conflict Company", domain="conflict.example", status="active")

    with pytest.raises(EntityConflictError) as conflict:
        service.create(organization_id=org_id, name="Duplicate Company", domain="conflict.example", status="active")

    with pytest.raises(EntityNotFoundError) as not_found:
        service.get_required("00000000-0000-0000-0000-000000000000")

    with pytest.raises(ValidationError) as validation:
        service.list(limit=0)

    assert conflict.value.code == "irtiqa.entity_conflict"
    assert not_found.value.code == "irtiqa.entity_not_found"
    assert validation.value.code == "irtiqa.validation_error"


def test_service_transaction_rolls_back_on_database_error(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    service = CompanyService()

    with pytest.raises(EntityConflictError):
        service.create(
            organization_id=org_id,
            name="Invalid Status Company",
            domain="invalid-status.example",
            status="unsupported",
        )

    with service_database() as session:
        persisted = session.query(Company).filter_by(domain="invalid-status.example").one_or_none()

    assert persisted is None
