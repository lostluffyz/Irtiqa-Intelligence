from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AuthSettings, DatabaseSettings, LoggingSettings, Settings
from app.core.security import decode_access_token
from app.database import session as database_session
from app.main import create_app
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User


# ── Fixtures ─────────────────────────────────────────────────────────────────


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
def client(
    api_session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DEV_MODE", "true")
    app = create_app(_test_settings(dev_mode=True), configure_logging_on_startup=False)
    with TestClient(app) as test_client:
        yield test_client


# ── Helpers ──────────────────────────────────────────────────────────────────


def _register(
    client: TestClient,
    email: str = "test@example.com",
    password: str = "password123",
) -> dict[str, Any]:
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": "Test User"},
    )
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    return resp.json()


def _verify(client: TestClient, msg: str, email: str = "test@example.com") -> None:
    """Extract and use the verification token from the registration message."""
    token = msg.split("Token: ")[1].strip()
    resp = client.post("/auth/verify-email", json={"token": token})
    assert resp.status_code == 200, f"Verify failed: {resp.text}"
    assert resp.json()["email"] == email


def _register_and_verify(
    client: TestClient,
    email: str = "test@example.com",
) -> dict[str, Any]:
    data = _register(client, email=email)
    _verify(client, data["message"], email=email)
    return data


def _login(
    client: TestClient,
    email: str = "test@example.com",
    password: str = "password123",
) -> dict[str, Any]:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()


def _test_settings(
    database_url: str = "sqlite:///:memory:",
    dev_mode: bool = False,
) -> Settings:
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
        auth=AuthSettings(dev_mode=dev_mode),
    )


# ── Multi-tenancy Auth Integration Tests ─────────────────────────────────────


class TestMultitenancyRegistration:
    """Tests for organization data in the registration flow."""

    def test_register_response_includes_org(
        self,
        client: TestClient,
    ) -> None:
        """POST /auth/register should include organization data in the response."""
        data = _register(client, email="reg-org@example.com")

        assert "organization" in data, "Register response should include organization"
        org = data["organization"]
        assert org is not None, "Organization should not be None"
        assert org["name"] == "Test User's Organization"
        assert "id" in org, "Organization should have an id"
        assert org["slug"] is not None, "Organization should have a slug"
        assert org["role"] == "owner", "Creator should have owner role"

    def test_register_creates_user_with_owner_membership(
        self,
        client: TestClient,
        api_session_factory: sessionmaker[Session],
    ) -> None:
        """The registered user should be able to access their organization."""
        data = _register(client, email="owner-mem@example.com")
        org_id = data["organization"]["id"]
        assert org_id is not None

        # Verify email and login
        _verify(client, data["message"], email="owner-mem@example.com")
        login_data = _login(client, email="owner-mem@example.com")
        access_token = login_data["access_token"]

        # User should be able to GET the organization they own
        resp = client.get(
            f"/organizations/{org_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200, f"Should access own org: {resp.text}"
        org_data = resp.json()
        assert org_data["id"] == org_id
        assert org_data["name"] == "Test User's Organization"


class TestMultitenancyLogin:
    """Tests for organization context in the login flow."""

    def test_login_response_includes_org(
        self,
        client: TestClient,
    ) -> None:
        """POST /auth/login should include organization and role in the response."""
        _register_and_verify(client, email="login-org@example.com")
        data = _login(client, email="login-org@example.com")

        assert "organization" in data, "Login response should include organization"
        org = data["organization"]
        assert org is not None, "Organization should not be None"
        assert org["name"] == "Test User's Organization"
        assert "id" in org
        assert "slug" in org
        assert org["role"] == "owner"

    def test_authenticated_user_can_access_org(
        self,
        client: TestClient,
    ) -> None:
        """After login, the user can access their organization's detail endpoint."""
        _register_and_verify(client, email="access-org@example.com")
        login_data = _login(client, email="access-org@example.com")

        org_summary = login_data["organization"]
        assert org_summary is not None
        org_id = org_summary["id"]
        access_token = login_data["access_token"]

        # GET the organization detail
        resp = client.get(
            f"/organizations/{org_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200, f"Should access own org: {resp.text}"

        # Verify JWT carries org and role claims
        payload = decode_access_token(access_token)
        assert "org" in payload
        assert "role" in payload
        assert payload["org"] == org_id
        assert payload["role"] == "owner"
