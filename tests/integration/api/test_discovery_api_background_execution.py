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
from app.services import DiscoverySearchService, JobService


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


def _create_org(factory: sessionmaker[Session], *, slug: str) -> Organization:
    with factory() as session:
        org = Organization(
            id=str(uuid4()),
            name=f"{slug} Organization",
            slug=slug,
            status="active",
        )
        session.add(org)
        session.commit()
        return org


@pytest.fixture()
def test_org(api_session_factory: sessionmaker[Session]) -> Organization:
    return _create_org(api_session_factory, slug="discovery-bg-org")


def _tenant_context(org_id: str, *, role: str = "owner") -> TenantContext:
    return TenantContext(
        organization_id=org_id,
        user_id=str(uuid4()),
        role=role,
        is_api_key=False,
    )


@pytest.fixture()
def app_client(api_session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app(_test_settings(), configure_logging_on_startup=False)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_organization, None)


@pytest.fixture()
def client(app_client: TestClient, test_org: Organization) -> Iterator[TestClient]:
    app_client.app.dependency_overrides[get_current_organization] = lambda: _tenant_context(
        test_org.id,
        role="owner",
    )
    yield app_client
    app_client.app.dependency_overrides.pop(get_current_organization, None)


def _criteria_payload() -> dict[str, object]:
    return {
        "industry": "fintech",
        "company_size_min": 10,
        "company_size_max": 500,
        "geography": "United States",
        "technologies": ["hubspot"],
        "keywords": ["Series A"],
        "exclude_domains": ["example.com"],
        "sources": ["sec_edgar"],
    }


def _seed_search(organization_id: str, *, name: str = "Background Test Search"):
    return DiscoverySearchService().create(
        organization_id=organization_id,
        name=name,
        description="Seeded for background execution test.",
        criteria=_criteria_payload(),
        status="active",
    )


def test_discovery_run_schedules_background_job(
    client: TestClient,
    test_org: Organization,
) -> None:
    """Verify that POST /discovery/searches/{id}/run creates both a run and a job."""
    search = _seed_search(test_org.id)

    # Trigger discovery run
    response = client.post(f"/discovery/searches/{search.id}/run")
    assert response.status_code == 202
    run = response.json()

    # Verify run is created immediately with "running" status
    assert run["search_id"] == search.id
    assert run["status"] == "running"
    assert run["sources_queried"] == 0
    assert run["companies_found"] == 0

    # Verify a background job was scheduled
    job_service = JobService()
    jobs = job_service.list_jobs(
        organization_id=test_org.id,
        target_name="discovery_pipeline",
        status="pending",
        limit=10,
    )
    assert len(jobs) == 1
    job = jobs[0]
    assert job.job_type == "workflow"
    assert job.target_name == "discovery_pipeline"
    assert job.status == "pending"

    # Verify job payload contains the run_id and search_id
    import json

    payload = json.loads(job.payload)
    assert payload["organization_id"] == test_org.id
    assert payload["options"]["discovery_search_id"] == search.id
    assert payload["options"]["discovery_run_id"] == run["id"]


def test_discovery_run_api_contract_unchanged(
    client: TestClient,
    test_org: Organization,
) -> None:
    """Verify that the API contract remains identical to Commit 6."""
    search = _seed_search(test_org.id)

    response = client.post(f"/discovery/searches/{search.id}/run")

    # API contract: HTTP 202 Accepted
    assert response.status_code == 202

    # API contract: returns DiscoveryRunRead with all expected fields
    run = response.json()
    assert "id" in run
    assert "search_id" in run
    assert "organization_id" in run
    assert "status" in run
    assert "sources_queried" in run
    assert "companies_found" in run
    assert "companies_created" in run
    assert "companies_skipped" in run
    assert "started_at" in run
    assert "finished_at" in run
    assert "error_message" in run

    # API contract: status is "running" immediately
    assert run["status"] == "running"

    # Client can immediately poll the run using the returned id
    poll_response = client.get(f"/discovery/runs/{run['id']}")
    assert poll_response.status_code == 200
    assert poll_response.json()["id"] == run["id"]


def test_discovery_run_idempotency_no_duplicate_runs(
    client: TestClient,
    test_org: Organization,
) -> None:
    """Verify that triggering a run multiple times creates separate runs (expected behavior)."""
    search = _seed_search(test_org.id)

    # Trigger first run
    response1 = client.post(f"/discovery/searches/{search.id}/run")
    assert response1.status_code == 202
    run1 = response1.json()

    # Trigger second run (should create a new run, not reuse the first)
    response2 = client.post(f"/discovery/searches/{search.id}/run")
    assert response2.status_code == 202
    run2 = response2.json()

    # Two distinct runs
    assert run1["id"] != run2["id"]
    assert run1["search_id"] == run2["search_id"] == search.id

    # Both runs are independent
    assert run1["status"] == "running"
    assert run2["status"] == "running"


def test_discovery_run_archived_search_validation(
    client: TestClient,
    test_org: Organization,
) -> None:
    """Verify that archived searches cannot be run."""
    search = _seed_search(test_org.id, name="Archived Search")

    # Archive the search
    DiscoverySearchService().update_for_organization(
        search.id,
        organization_id=test_org.id,
        status="archived",
    )

    # Attempt to run archived search
    response = client.post(f"/discovery/searches/{search.id}/run")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "irtiqa.validation_error"
    assert "archived" in response.json()["error"]["message"].lower()


def test_discovery_run_job_payload_structure(
    client: TestClient,
    test_org: Organization,
) -> None:
    """Verify that the scheduled job has the correct payload structure."""
    search = _seed_search(test_org.id)

    response = client.post(f"/discovery/searches/{search.id}/run")
    assert response.status_code == 202
    run = response.json()

    # Retrieve the scheduled job
    job_service = JobService()
    jobs = job_service.list_jobs(
        organization_id=test_org.id,
        target_name="discovery_pipeline",
        limit=10,
    )
    assert len(jobs) >= 1
    job = jobs[0]

    # Verify payload structure
    import json

    payload = json.loads(job.payload)
    assert payload["company_id"] is None
    assert payload["contact_id"] is None
    assert payload["organization_id"] == test_org.id
    assert payload["correlation_id"] is None
    assert payload["requested_by"] is None
    assert "options" in payload
    assert payload["options"]["discovery_search_id"] == search.id
    assert payload["options"]["discovery_run_id"] == run["id"]


def test_discovery_run_multiple_searches_independent_jobs(
    client: TestClient,
    test_org: Organization,
) -> None:
    """Verify that multiple searches create independent jobs."""
    search1 = _seed_search(test_org.id, name="Search 1")
    search2 = _seed_search(test_org.id, name="Search 2")

    # Trigger runs for both searches
    run1_response = client.post(f"/discovery/searches/{search1.id}/run")
    run2_response = client.post(f"/discovery/searches/{search2.id}/run")

    assert run1_response.status_code == 202
    assert run2_response.status_code == 202

    run1 = run1_response.json()
    run2 = run2_response.json()

    # Verify both jobs were scheduled
    job_service = JobService()
    jobs = job_service.list_jobs(
        organization_id=test_org.id,
        target_name="discovery_pipeline",
        status="pending",
        limit=10,
    )
    assert len(jobs) >= 2

    # Verify jobs reference the correct runs and searches
    import json

    job_payloads = [json.loads(job.payload) for job in jobs]
    run_ids = {payload["options"]["discovery_run_id"] for payload in job_payloads}
    search_ids = {payload["options"]["discovery_search_id"] for payload in job_payloads}

    assert run1["id"] in run_ids
    assert run2["id"] in run_ids
    assert search1.id in search_ids
    assert search2.id in search_ids
