from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import session as database_session
from app.models.organization import Organization
from app.services import (
    CompanyService,
    IntelligenceScoreService,
    IntentSignalService,
    OutreachMessageService,
    TechnologyService,
)
from app.services.lead_retrieval_service import LeadRetrievalService


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
def service_database(service_session_factory: sessionmaker[Session]) -> sessionmaker[Session]:
    return service_session_factory


@pytest.fixture()
def org_id(service_session_factory: sessionmaker[Session]) -> str:
    _org_id = str(uuid4())
    with service_session_factory() as session:
        session.add(Organization(id=_org_id, name="Lead Test Org", slug="lead-test", status="active"))
        session.commit()
    return _org_id


@pytest.fixture()
def other_org_id(service_session_factory: sessionmaker[Session]) -> str:
    _org_id = str(uuid4())
    with service_session_factory() as session:
        session.add(Organization(id=_org_id, name="Other Test Org", slug="other-test", status="active"))
        session.commit()
    return _org_id


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_lead_data(
    *,
    org_id: str,
    domain: str,
    company_name: str,
) -> dict:
    """Seed a full lead (company + tech + signal + score + message) and return IDs."""
    company_svc = CompanyService()
    tech_svc = TechnologyService()
    signal_svc = IntentSignalService()
    score_svc = IntelligenceScoreService()
    msg_svc = OutreachMessageService()

    company = company_svc.create(
        organization_id=org_id,
        name=company_name,
        domain=domain,
        industry="software",
        status="active",
    )
    now = utc_now()

    tech = tech_svc.create(
        company_id=company.id,
        name="HubSpot",
        category="crm",
        vendor="HubSpot",
        detection_method="html_signature",
        confidence=0.92,
        first_detected_at=now,
        last_detected_at=now,
    )
    signal = signal_svc.create(
        organization_id=org_id,
        company_id=company.id,
        signal_type="technology_change",
        signal_name="CRM detected",
        signal_value="HubSpot detected",
        strength=0.75,
        confidence=0.88,
        observed_at=now,
    )
    score = score_svc.create(
        organization_id=org_id,
        company_id=company.id,
        fit_score=82.0,
        intent_score=76.0,
        technographic_score=91.0,
        engagement_score=70.0,
        total_score=81.4,
        confidence=0.86,
        score_version="test-v1",
        rationale="Strong fit.",
        scored_at=now,
    )
    msg = msg_svc.create(
        organization_id=org_id,
        company_id=company.id,
        channel="email",
        subject="Hello",
        message_body="Test outreach",
        personalization_angle="CRM",
        status="draft",
        confidence=0.81,
        generated_at=now,
    )
    return {
        "company_id": company.id,
        "tech_id": tech.id,
        "signal_id": signal.id,
        "score_id": score.id,
        "msg_id": msg.id,
    }


class TestLeadRetrievalServiceAggregation:
    """Verify that the service correctly aggregates all child entities."""

    def test_full_lead_aggregation(self, service_database: sessionmaker[Session], org_id: str) -> None:
        ids = _seed_lead_data(
            org_id=org_id,
            domain="agg.test",
            company_name="Aggregation Corp",
        )

        svc = LeadRetrievalService()
        result = svc.get_leads(organization_id=org_id, limit=100, offset=0)

        assert result.total == 1
        assert len(result.items) == 1

        lead = result.items[0]
        assert lead.company_id == ids["company_id"]
        assert lead.company_name == "Aggregation Corp"
        assert lead.domain == "agg.test"
        assert lead.industry == "software"
        assert lead.status == "active"

        # Technologies
        assert len(lead.technologies) == 1
        assert lead.technologies[0].name == "HubSpot"
        assert lead.technologies[0].category == "crm"

        # Intent signals
        assert len(lead.intent_signals) == 1
        assert lead.intent_signals[0].signal_type == "technology_change"
        assert lead.intent_signals[0].confidence == 0.88

        # Intelligence score
        assert lead.latest_intelligence_score is not None
        assert lead.latest_intelligence_score.total_score == 81.4
        assert lead.latest_intelligence_score.opportunity_score == 82.0
        assert lead.urgency_score == 76.0 if hasattr(lead, "urgency_score") else lead.latest_intelligence_score.urgency_score == 76.0

        # Outreach messages
        assert len(lead.outreach_messages) == 1
        assert lead.outreach_messages[0].channel == "email"
        assert lead.outreach_messages[0].subject == "Hello"

    def test_multiple_companies(self, service_database: sessionmaker[Session], org_id: str) -> None:
        _seed_lead_data(org_id=org_id, domain="multi1.test", company_name="Company One")
        _seed_lead_data(org_id=org_id, domain="multi2.test", company_name="Company Two")

        svc = LeadRetrievalService()
        result = svc.get_leads(organization_id=org_id, limit=100, offset=0)

        assert result.total == 2
        assert len(result.items) == 2
        names = {lead.company_name for lead in result.items}
        assert names == {"Company One", "Company Two"}

    def test_multiple_technologies(self, service_database: sessionmaker[Session], org_id: str) -> None:
        company_svc = CompanyService()
        tech_svc = TechnologyService()

        company = company_svc.create(
            organization_id=org_id,
            name="Multi Tech Corp",
            domain="multitech.test",
            industry="tech",
            status="active",
        )
        now = utc_now()
        tech_svc.create(
            company_id=company.id, name="HubSpot", category="crm",
            detection_method="html_signature", confidence=0.92,
            first_detected_at=now, last_detected_at=now,
        )
        tech_svc.create(
            company_id=company.id, name="React", category="frontend",
            detection_method="html_signature", confidence=0.85,
            first_detected_at=now, last_detected_at=now,
        )

        svc = LeadRetrievalService()
        result = svc.get_leads(organization_id=org_id, limit=100, offset=0)

        assert result.items[0].technologies is not None
        tech_names = {t.name for t in result.items[0].technologies}
        assert tech_names == {"HubSpot", "React"}

    def test_empty_organization(self, service_database: sessionmaker[Session], org_id: str) -> None:
        svc = LeadRetrievalService()
        result = svc.get_leads(organization_id=org_id, limit=100, offset=0)

        assert result.total == 0
        assert result.items == []


class TestLeadRetrievalServiceTenantIsolation:
    """Verify that tenant isolation is enforced."""

    def test_org_a_cannot_see_org_b_leads(
        self,
        service_database: sessionmaker[Session],
        org_id: str,
        other_org_id: str,
    ) -> None:
        _seed_lead_data(org_id=org_id, domain="orga.test", company_name="Org A Company")
        _seed_lead_data(org_id=other_org_id, domain="orgb.test", company_name="Org B Company")

        svc = LeadRetrievalService()
        result_a = svc.get_leads(organization_id=org_id, limit=100, offset=0)
        result_b = svc.get_leads(organization_id=other_org_id, limit=100, offset=0)

        assert result_a.total == 1
        assert result_a.items[0].company_name == "Org A Company"
        assert result_b.total == 1
        assert result_b.items[0].company_name == "Org B Company"

    def test_total_count_is_org_scoped(
        self,
        service_database: sessionmaker[Session],
        org_id: str,
        other_org_id: str,
    ) -> None:
        _seed_lead_data(org_id=org_id, domain="count1.test", company_name="Count One")
        _seed_lead_data(org_id=other_org_id, domain="count2.test", company_name="Count Two")

        svc = LeadRetrievalService()
        result = svc.get_leads(organization_id=org_id, limit=100, offset=0)
        assert result.total == 1


class TestLeadRetrievalServiceMinimumScore:
    """Verify minimum_score filtering."""

    def test_filters_below_minimum(self, service_database: sessionmaker[Session], org_id: str) -> None:
        _seed_lead_data(org_id=org_id, domain="high.test", company_name="High Score")
        # This company gets score 81.4

        svc = LeadRetrievalService()
        result = svc.get_leads(organization_id=org_id, limit=100, offset=0, minimum_score=90.0)
        # 81.4 < 90.0, so filtered out
        assert result.total == 1  # total companies count is unaffected
        assert len(result.items) == 0  # but items list is filtered

    def test_keeps_above_minimum(self, service_database: sessionmaker[Session], org_id: str) -> None:
        _seed_lead_data(org_id=org_id, domain="above.test", company_name="Above Min")

        svc = LeadRetrievalService()
        result = svc.get_leads(organization_id=org_id, limit=100, offset=0, minimum_score=81.0)
        assert len(result.items) == 1

    def test_company_without_score_excluded_by_minimum(
        self, service_database: sessionmaker[Session], org_id: str
    ) -> None:
        company_svc = CompanyService()
        company_svc.create(
            organization_id=org_id,
            name="No Score Corp",
            domain="noscore.test",
            industry="tech",
            status="active",
        )

        svc = LeadRetrievalService()
        result = svc.get_leads(organization_id=org_id, limit=100, offset=0, minimum_score=0.0)
        assert len(result.items) == 0


class TestLeadRetrievalServicePagination:
    """Verify limit and offset behavior."""

    def test_limit_offset(self, service_database: sessionmaker[Session], org_id: str) -> None:
        _seed_lead_data(org_id=org_id, domain="page1.test", company_name="Page One")
        _seed_lead_data(org_id=org_id, domain="page2.test", company_name="Page Two")
        _seed_lead_data(org_id=org_id, domain="page3.test", company_name="Page Three")

        svc = LeadRetrievalService()
        page1 = svc.get_leads(organization_id=org_id, limit=2, offset=0)
        assert len(page1.items) == 2
        assert page1.total == 3

        page2 = svc.get_leads(organization_id=org_id, limit=2, offset=2)
        assert len(page2.items) == 1
        assert page2.total == 3
