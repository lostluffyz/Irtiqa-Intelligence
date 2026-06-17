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
        org = Organization(id=str(uuid4()), name="CRUD Test Org", slug="crud-test-org", status="active")
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


# ═══════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════


def test_company_crud_endpoints(client: TestClient) -> None:
    created = client.post(
        "/companies",
        json={
            "name": "Irtiqa API Company",
            "domain": "irtiqa-api.example",
            "industry": "software",
            "status": "active",
        },
    )
    assert created.status_code == 201
    company = created.json()
    assert company["id"]
    assert company["domain"] == "irtiqa-api.example"

    listed = client.get("/companies", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    fetched = client.get(f"/companies/{company['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Irtiqa API Company"

    updated = client.patch(
        f"/companies/{company['id']}",
        json={"status": "needs_review", "headquarters": "Bengaluru, India"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "needs_review"
    assert updated.json()["headquarters"] == "Bengaluru, India"

    deleted = client.delete(f"/companies/{company['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/companies/{company['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def test_contact_crud_endpoints(client: TestClient) -> None:
    company = _create_company(client, domain="contact-parent.example")

    created = client.post(
        "/contacts",
        json={
            "company_id": company["id"],
            "first_name": "Asha",
            "last_name": "Rao",
            "full_name": "Asha Rao",
            "email": "asha.rao@contact-parent.example",
            "title": "VP Revenue",
            "status": "active",
        },
    )
    assert created.status_code == 201
    contact = created.json()
    assert contact["company_id"] == company["id"]
    assert contact["email"] == "asha.rao@contact-parent.example"

    listed = client.get("/contacts", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    fetched = client.get(f"/contacts/{contact['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["full_name"] == "Asha Rao"

    updated = client.patch(f"/contacts/{contact['id']}", json={"status": "qualified"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "qualified"

    deleted = client.delete(f"/contacts/{contact['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/contacts/{contact['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def test_website_crud_endpoints(client: TestClient) -> None:
    company = _create_company(client, domain="website-parent.example")

    created = client.post(
        "/websites",
        json={
            "company_id": company["id"],
            "url": "https://website-parent.example",
            "normalized_url": "https://website-parent.example/",
            "page_type": "homepage",
            "http_status": 200,
        },
    )
    assert created.status_code == 201
    website = created.json()
    assert website["company_id"] == company["id"]
    assert website["normalized_url"] == "https://website-parent.example/"

    listed = client.get("/websites", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    fetched = client.get(f"/websites/{website['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["url"] == "https://website-parent.example"

    updated = client.patch(f"/websites/{website['id']}", json={"http_status": 204})
    assert updated.status_code == 200
    assert updated.json()["http_status"] == 204

    deleted = client.delete(f"/websites/{website['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/websites/{website['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def test_crud_error_responses_are_structured(client: TestClient) -> None:
    company = _create_company(client, domain="structured-errors.example")

    conflict = client.post(
        "/companies",
        json={"name": "Duplicate", "domain": company["domain"], "status": "active"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "irtiqa.entity_conflict"

    invalid_payload = client.post(
        "/contacts",
        json={"company_id": company["id"], "full_name": "", "status": "active"},
    )
    assert invalid_payload.status_code == 422
    assert invalid_payload.json()["error"]["code"] == "irtiqa.request_validation_error"

    invalid_pagination = client.get("/websites", params={"limit": 0})
    assert invalid_pagination.status_code == 422
    assert invalid_pagination.json()["error"]["code"] == "irtiqa.request_validation_error"

    missing = client.delete("/companies/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def _create_company(client: TestClient, *, domain: str) -> dict[str, object]:
    response = client.post(
        "/companies",
        json={"name": "Parent Company", "domain": domain, "status": "active"},
    )
    assert response.status_code == 201
    return response.json()


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
