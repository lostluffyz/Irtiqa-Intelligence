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
from app.models.organization import Organization
from app.services.job_service import JobService


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
        org = Organization(id=str(uuid4()), name="Job API Test Org", slug="job-api-test", status="active")
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


@pytest.fixture
def job_service() -> JobService:
    return JobService()


def test_schedule_agent_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "workflow_name": None,
            "correlation_id": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["job_type"] == "agent"
    assert data["target_name"] == "test_agent"
    assert data["status"] == "pending"
    assert data["retry_count"] == 0
    assert data["max_retries"] == 3


def test_schedule_workflow_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-workflow",
        json={
            "workflow_name": "test_workflow",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "correlation_id": None,
            "requested_by": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["job_type"] == "workflow"
    assert data["target_name"] == "test_workflow"
    assert data["status"] == "pending"


def test_get_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "workflow_name": None,
            "correlation_id": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["id"] == job_id


def test_list_jobs_endpoint(client: TestClient) -> None:
    client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "workflow_name": None,
            "correlation_id": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    response = client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1


def test_cancel_pending_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "workflow_name": None,
            "correlation_id": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    response = client.post(f"/jobs/{job_id}/cancel")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"


def test_cancel_running_job_endpoint_fails(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "workflow_name": None,
            "correlation_id": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    assert response.status_code == 201
    job_id = response.json()["id"]
    JobService().update(job_id, status="running")

    response = client.post(f"/jobs/{job_id}/cancel")
    assert response.status_code == 409


def test_retry_failed_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "workflow_name": None,
            "correlation_id": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    assert response.status_code == 201
    job_id = response.json()["id"]
    JobService().update(job_id, status="failed")

    response = client.post(f"/jobs/{job_id}/retry")
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_retry_non_failed_job_endpoint_fails(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "workflow_name": None,
            "correlation_id": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    assert response.status_code == 201
    job_id = response.json()["id"]

    response = client.post(f"/jobs/{job_id}/retry")
    assert response.status_code == 409


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
