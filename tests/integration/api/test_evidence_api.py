from __future__ import annotations

from collections.abc import Iterator
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
from app.models.evidence_record import (
    EVIDENCE_TYPE_COMPUTED_METRIC,
    RELATIONSHIP_CONTRIBUTES_TO,
    SOURCE_TYPE_AGENT_RUN,
    SOURCE_TYPE_WEBSITE,
    TARGET_TYPE_INTELLIGENCE_SCORE,
    TARGET_TYPE_TECHNOLOGY,
    EvidenceRecord,
)
from app.models.organization import Organization
from app.services.evidence_service import EvidenceService


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
        org = Organization(id=str(uuid4()), name="Evidence Test Org", slug="evidence-test", status="active")
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


def _seed_evidence(service: EvidenceService, org_id: str) -> tuple[str, str, str]:
    score_id = "10000000-0000-0000-0000-000000000001"
    company_id = "20000000-0000-0000-0000-000000000001"
    agent_run_id = "30000000-0000-0000-0000-000000000001"

    service.record_evidence(
        organization_id=org_id,
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id=agent_run_id,
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="technology=tech1, confidence=0.92",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id=score_id,
        confidence=0.92,
        agent_run_id=None,
        company_id=company_id,
    )
    service.record_evidence(
        organization_id=org_id,
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id=agent_run_id,
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="signal=sig1, strength=0.75",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id=score_id,
        confidence=0.88,
        agent_run_id=None,
        company_id=company_id,
    )
    return score_id, company_id, agent_run_id


def test_evidence_api_list_by_target(client: TestClient, test_org: Organization) -> None:
    service = EvidenceService()
    score_id, _, _ = _seed_evidence(service, org_id=test_org.id)

    response = client.get(
        f"/evidence/by-target/{TARGET_TYPE_INTELLIGENCE_SCORE}/{score_id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2


def test_evidence_api_list_by_source(client: TestClient, test_org: Organization) -> None:
    service = EvidenceService()
    _, _, agent_run_id = _seed_evidence(service, org_id=test_org.id)

    response = client.get(
        f"/evidence/by-source/{SOURCE_TYPE_AGENT_RUN}/{agent_run_id}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2


def test_evidence_api_by_company(client: TestClient, test_org: Organization) -> None:
    service = EvidenceService()
    _, company_id, _ = _seed_evidence(service, org_id=test_org.id)

    response = client.get(f"/evidence/by-company/{company_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2


def test_evidence_api_by_company_with_type_filter(client: TestClient, test_org: Organization) -> None:
    service = EvidenceService()
    _, company_id, _ = _seed_evidence(service, org_id=test_org.id)

    response = client.get(
        f"/evidence/by-company/{company_id}",
        params={"target_type": TARGET_TYPE_INTELLIGENCE_SCORE},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2


def test_evidence_api_summary(client: TestClient, test_org: Organization) -> None:
    service = EvidenceService()
    score_id, _, _ = _seed_evidence(service, org_id=test_org.id)

    response = client.get(f"/evidence/summary/{TARGET_TYPE_INTELLIGENCE_SCORE}/{score_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total_evidence"] >= 2


def test_evidence_api_detail(client: TestClient, test_org: Organization) -> None:
    service = EvidenceService()
    score_id, _, _ = _seed_evidence(service, org_id=test_org.id)

    list_response = client.get(
        f"/evidence/by-target/{TARGET_TYPE_INTELLIGENCE_SCORE}/{score_id}"
    )
    evidence_id = list_response.json()["items"][0]["id"]

    response = client.get(f"/evidence/{evidence_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == evidence_id


def test_evidence_api_not_found(client: TestClient) -> None:
    response = client.get("/evidence/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_evidence_api_list_pagination(client: TestClient, test_org: Organization) -> None:
    service = EvidenceService()
    score_id, _, _ = _seed_evidence(service, org_id=test_org.id)

    response = client.get(
        f"/evidence/by-target/{TARGET_TYPE_INTELLIGENCE_SCORE}/{score_id}",
        params={"limit": 1, "offset": 0},
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_evidence_api_invalid_target_type_in_path(client: TestClient) -> None:
    response = client.get("/evidence/by-target/invalid_type/some-id")
    assert response.status_code in (200, 422)


def test_evidence_api_empty_list(client: TestClient) -> None:
    response = client.get(
        f"/evidence/by-target/{TARGET_TYPE_TECHNOLOGY}/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 200
    assert response.json()["total"] == 0


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
