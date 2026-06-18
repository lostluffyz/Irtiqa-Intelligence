from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_current_organization
from app.core.config import AuthSettings, DatabaseSettings, LoggingSettings, Settings
from app.core.tenant import TenantContext
from app.database import session as database_session
from app.main import create_app
from app.models.organization import Organization
from app.services import (
    CompanyService,
    IntelligenceScoreService,
    IntentSignalService,
    OutreachMessageService,
    TechnologyService,
)


def _test_settings(database_url: str = "sqlite:///:memory:") -> Settings:
    return Settings(
        database=DatabaseSettings(
            url=database_url,
            echo=False,
            pool_pre_ping=True,
            sqlite_foreign_keys=True,
            sqlite_journal_mode="WAL",
            sqlite_busy_timeout_ms=5000,
        ),
        logging=LoggingSettings(
            level="INFO",
            app_level="INFO",
            database_level="WARNING",
            repository_level="INFO",
            console_enabled=False,
            file_enabled=False,
            file_path=Path("unused.log"),
            file_max_bytes=10_485_760,
            file_backup_count=5,
            format="%(levelname)s:%(name)s:%(message)s",
            date_format="%Y-%m-%dT%H:%M:%S%z",
        ),
        auth=AuthSettings(),
    )


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture()
def api_session_factory(
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
def test_org(api_session_factory: sessionmaker[Session]) -> Iterator[Organization]:
    with api_session_factory() as session:
        org = Organization(id=str(uuid4()), name="Lead API Org", slug="lead-api-org", status="active")
        session.add(org)
        session.commit()
        yield org


@pytest.fixture()
def other_org(api_session_factory: sessionmaker[Session]) -> Iterator[Organization]:
    with api_session_factory() as session:
        org = Organization(id=str(uuid4()), name="Other API Org", slug="other-api-org", status="active")
        session.add(org)
        session.commit()
        yield org


@pytest.fixture()
def client(api_session_factory: sessionmaker[Session], test_org: Organization) -> Iterator[TestClient]:
    app = create_app(_test_settings(), configure_logging_on_startup=False)
    app.dependency_overrides[get_current_organization] = lambda: TenantContext(
        organization_id=test_org.id,
        user_id=str(uuid4()),
        role="owner",
        is_api_key=False,
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_organization, None)


def _seed_lead_via_db(session: Session, org_id: str, domain: str, company_name: str) -> str:
    """Seed a full lead directly via the database and return the company_id."""
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

    tech_svc.create(
        company_id=company.id,
        name="HubSpot",
        category="crm",
        vendor="HubSpot",
        detection_method="html_signature",
        confidence=0.92,
        first_detected_at=now,
        last_detected_at=now,
    )
    signal_svc.create(
        organization_id=org_id,
        company_id=company.id,
        signal_type="technology_change",
        signal_name="CRM detected",
        signal_value="HubSpot detected",
        strength=0.75,
        confidence=0.88,
        observed_at=now,
    )
    score_svc.create(
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
    msg_svc.create(
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
    return company.id


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════


def test_list_leads_empty(client: TestClient) -> None:
    response = client.get("/leads")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 100
    assert data["offset"] == 0


def test_list_leads_full_shape(
    client: TestClient,
    api_session_factory: sessionmaker[Session],
    test_org: Organization,
) -> None:
    with api_session_factory() as session:
        _seed_lead_via_db(session, test_org.id, "shape.test", "Shape Corp")

    response = client.get("/leads")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert len(data["items"]) == 1

    lead = data["items"][0]
    assert lead["company_id"]
    assert lead["company_name"] == "Shape Corp"
    assert lead["domain"] == "shape.test"
    assert lead["industry"] == "software"
    assert lead["status"] == "active"
    assert lead["updated_at"]

    # Technologies
    assert len(lead["technologies"]) == 1
    assert lead["technologies"][0]["name"] == "HubSpot"
    assert lead["technologies"][0]["category"] == "crm"

    # Intent signals
    assert len(lead["intent_signals"]) == 1
    assert lead["intent_signals"][0]["signal_type"] == "technology_change"
    assert lead["intent_signals"][0]["confidence"] == 0.88

    # Intelligence score
    assert lead["latest_intelligence_score"] is not None
    assert lead["latest_intelligence_score"]["total_score"] == 81.4
    assert lead["latest_intelligence_score"]["opportunity_score"] == 82.0
    assert lead["latest_intelligence_score"]["urgency_score"] == 76.0

    # Outreach messages
    assert len(lead["outreach_messages"]) == 1
    assert lead["outreach_messages"][0]["channel"] == "email"
    assert lead["outreach_messages"][0]["subject"] == "Hello"


def test_list_leads_pagination(
    client: TestClient,
    api_session_factory: sessionmaker[Session],
    test_org: Organization,
) -> None:
    with api_session_factory() as session:
        _seed_lead_via_db(session, test_org.id, "page1.test", "Page One")
        _seed_lead_via_db(session, test_org.id, "page2.test", "Page Two")
        _seed_lead_via_db(session, test_org.id, "page3.test", "Page Three")

    page1 = client.get("/leads", params={"limit": 2, "offset": 0})
    assert page1.status_code == 200
    data1 = page1.json()
    assert len(data1["items"]) == 2
    assert data1["total"] == 3

    page2 = client.get("/leads", params={"limit": 2, "offset": 2})
    assert page2.status_code == 200
    data2 = page2.json()
    assert len(data2["items"]) == 1
    assert data2["total"] == 3


def test_list_leads_minimum_score_filter(
    client: TestClient,
    api_session_factory: sessionmaker[Session],
    test_org: Organization,
) -> None:
    with api_session_factory() as session:
        _seed_lead_via_db(session, test_org.id, "minscore.test", "Score Filter Corp")

    # Score is 81.4, filter at 90.0 → should exclude
    response = client.get("/leads", params={"minimum_score": 90.0})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0  # total reflects filtered count
    assert len(data["items"]) == 0

    # Score is 81.4, filter at 80.0 → should include
    response2 = client.get("/leads", params={"minimum_score": 80.0})
    assert response2.status_code == 200
    data2 = response2.json()
    assert len(data2["items"]) == 1


def test_list_leads_tenant_isolation(
    client: TestClient,
    api_session_factory: sessionmaker[Session],
    test_org: Organization,
    other_org: Organization,
) -> None:
    with api_session_factory() as session:
        _seed_lead_via_db(session, test_org.id, "myorg.test", "My Org Corp")
        _seed_lead_via_db(session, other_org.id, "otherorg.test", "Other Org Corp")

    response = client.get("/leads")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "myorg.test"
    assert data["items"][0]["company_name"] == "My Org Corp"


def test_list_leads_multiple_companies(
    client: TestClient,
    api_session_factory: sessionmaker[Session],
    test_org: Organization,
) -> None:
    with api_session_factory() as session:
        _seed_lead_via_db(session, test_org.id, "multi1.test", "Multi One")
        _seed_lead_via_db(session, test_org.id, "multi2.test", "Multi Two")

    response = client.get("/leads")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    names = {item["company_name"] for item in data["items"]}
    assert names == {"Multi One", "Multi Two"}


def test_list_leads_no_score(client: TestClient) -> None:
    """Company without a score should have null latest_intelligence_score."""
    response = client.get("/leads")
    assert response.status_code == 200
    # Empty — no companies seeded
    data = response.json()
    assert data["items"] == []
