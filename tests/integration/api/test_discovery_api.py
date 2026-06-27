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
from app.services import DiscoverySearchService


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
    return _create_org(api_session_factory, slug="discovery-api-org")


@pytest.fixture()
def other_org(api_session_factory: sessionmaker[Session]) -> Organization:
    return _create_org(api_session_factory, slug="other-discovery-api-org")


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
        "technologies": ["hubspot", "salesforce"],
        "keywords": ["Series A", "hiring engineer"],
        "exclude_domains": ["example.com"],
        "sources": ["sec_edgar", "google_news_rss", "opencorporates"],
    }


def _search_payload(name: str = "Fintech Series A") -> dict[str, object]:
    return {
        "name": name,
        "description": "Find recently funded fintech companies.",
        "criteria": _criteria_payload(),
        "status": "active",
    }


def _create_search(client: TestClient, *, name: str = "Fintech Series A") -> dict[str, object]:
    response = client.post("/discovery/searches", json=_search_payload(name))
    assert response.status_code == 201, response.text
    return response.json()


def _seed_search(organization_id: str, *, name: str = "Seeded Search", status: str = "active"):
    return DiscoverySearchService().create(
        organization_id=organization_id,
        name=name,
        description="Seeded for API test.",
        criteria=_criteria_payload(),
        status=status,
    )


def test_discovery_search_crud_endpoints(client: TestClient) -> None:
    created = _create_search(client)
    search_id = created["id"]

    assert created["name"] == "Fintech Series A"
    assert created["criteria"]["industry"] == "fintech"

    listed = client.get("/discovery/searches", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    fetched = client.get(f"/discovery/searches/{search_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == search_id

    updated = client.patch(
        f"/discovery/searches/{search_id}",
        json={"status": "archived", "description": "Archived search."},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "archived"
    assert updated.json()["description"] == "Archived search."

    deleted = client.delete(f"/discovery/searches/{search_id}")
    assert deleted.status_code == 204

    missing = client.get(f"/discovery/searches/{search_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def test_discovery_search_tenant_isolation(
    app_client: TestClient,
    test_org: Organization,
    other_org: Organization,
) -> None:
    own_search = _seed_search(test_org.id, name="Own Search")
    other_search = _seed_search(other_org.id, name="Other Search")

    app_client.app.dependency_overrides[get_current_organization] = lambda: _tenant_context(
        test_org.id,
        role="owner",
    )

    listed = app_client.get("/discovery/searches")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [own_search.id]

    hidden = app_client.get(f"/discovery/searches/{other_search.id}")
    assert hidden.status_code == 404

    hidden_update = app_client.patch(
        f"/discovery/searches/{other_search.id}",
        json={"name": "Should Not Update"},
    )
    assert hidden_update.status_code == 404


def test_discovery_search_validation_errors(client: TestClient) -> None:
    invalid_payload = client.post(
        "/discovery/searches",
        json={"name": "Invalid", "criteria": {"industry": "fintech"}},
    )
    assert invalid_payload.status_code == 422
    assert invalid_payload.json()["error"]["code"] == "irtiqa.request_validation_error"

    invalid_update = client.patch("/discovery/searches/not-found", json={"status": "running"})
    assert invalid_update.status_code == 422

    invalid_pagination = client.get("/discovery/searches", params={"limit": 0})
    assert invalid_pagination.status_code == 422


def test_discovery_run_creation_retrieval_and_listing(client: TestClient) -> None:
    search = _create_search(client)
    search_id = search["id"]

    triggered = client.post(f"/discovery/searches/{search_id}/run")
    assert triggered.status_code == 202
    run = triggered.json()
    assert run["search_id"] == search_id
    assert run["status"] == "running"
    assert run["sources_queried"] == 0

    fetched = client.get(f"/discovery/runs/{run['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == run["id"]

    listed = client.get(f"/discovery/searches/{search_id}/runs")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == run["id"]


def test_discovery_run_tenant_isolation(
    app_client: TestClient,
    test_org: Organization,
    other_org: Organization,
) -> None:
    own_search = _seed_search(test_org.id, name="Own Search")
    other_search = _seed_search(other_org.id, name="Other Search")

    app_client.app.dependency_overrides[get_current_organization] = lambda: _tenant_context(
        other_org.id,
        role="owner",
    )
    other_run = app_client.post(f"/discovery/searches/{other_search.id}/run").json()

    app_client.app.dependency_overrides[get_current_organization] = lambda: _tenant_context(
        test_org.id,
        role="owner",
    )

    cannot_run_other = app_client.post(f"/discovery/searches/{other_search.id}/run")
    assert cannot_run_other.status_code == 404

    cannot_get_other_run = app_client.get(f"/discovery/runs/{other_run['id']}")
    assert cannot_get_other_run.status_code == 404

    cannot_list_other_runs = app_client.get(f"/discovery/searches/{other_search.id}/runs")
    assert cannot_list_other_runs.status_code == 404

    own_run = app_client.post(f"/discovery/searches/{own_search.id}/run")
    assert own_run.status_code == 202


def test_discovery_run_404_handling(client: TestClient) -> None:
    missing_search_run = client.post("/discovery/searches/00000000-0000-0000-0000-000000000000/run")
    assert missing_search_run.status_code == 404
    assert missing_search_run.json()["error"]["code"] == "irtiqa.entity_not_found"

    missing_run = client.get("/discovery/runs/00000000-0000-0000-0000-000000000000")
    assert missing_run.status_code == 404

    missing_run_list = client.get(
        "/discovery/searches/00000000-0000-0000-0000-000000000000/runs"
    )
    assert missing_run_list.status_code == 404


def test_discovery_authorization_roles(
    app_client: TestClient,
    test_org: Organization,
) -> None:
    app_client.app.dependency_overrides[get_current_organization] = lambda: _tenant_context(
        test_org.id,
        role="viewer",
    )

    viewer_create = app_client.post("/discovery/searches", json=_search_payload())
    assert viewer_create.status_code == 403

    seeded_search = _seed_search(test_org.id)
    viewer_list = app_client.get("/discovery/searches")
    assert viewer_list.status_code == 200

    viewer_run = app_client.post(f"/discovery/searches/{seeded_search.id}/run")
    assert viewer_run.status_code == 403

    app_client.app.dependency_overrides[get_current_organization] = lambda: _tenant_context(
        test_org.id,
        role="member",
    )
    member_delete = app_client.delete(f"/discovery/searches/{seeded_search.id}")
    assert member_delete.status_code == 403


def test_discovery_requires_authentication(app_client: TestClient) -> None:
    response = app_client.get("/discovery/searches")

    assert response.status_code == 401
