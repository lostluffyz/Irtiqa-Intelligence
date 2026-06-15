from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AuthSettings, DatabaseSettings, LoggingSettings, Settings
from app.database import session as database_session
from app.main import create_app


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
def client(api_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("DEV_MODE", "true")
    app = create_app(_test_settings(dev_mode=True), configure_logging_on_startup=False)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    """Register and verify a user. Return Authorization headers."""
    r = client.post(
        "/auth/register",
        json={"email": "admin@test.com", "password": "password123", "display_name": "Admin"},
    )
    assert r.status_code == 201
    token = r.json()["message"].split("Token: ")[1].strip()
    client.post("/auth/verify-email", json={"token": token})
    r = client.post("/auth/login", json={"email": "admin@test.com", "password": "password123"})
    access = r.json()["access_token"]
    return {"Authorization": f"Bearer {access}"}


@pytest.fixture()
def second_user_headers(client: TestClient) -> dict[str, str]:
    """A second user for member testing."""
    r = client.post(
        "/auth/register",
        json={"email": "member@test.com", "password": "password123", "display_name": "Member"},
    )
    token = r.json()["message"].split("Token: ")[1].strip()
    client.post("/auth/verify-email", json={"token": token})
    r = client.post("/auth/login", json={"email": "member@test.com", "password": "password123"})
    access = r.json()["access_token"]
    return {"Authorization": f"Bearer {access}"}


# ── Organization API ─────────────────────────────────────────────────────────


class TestOrganizationAPI:
    def test_create_organization(self, client: TestClient, auth_headers: dict) -> None:
        r = client.post("/organizations", json={"name": "My Org"}, headers=auth_headers)
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "My Org"
        assert data["status"] == "active"
        assert "id" in data

    def test_creator_is_owner(self, client: TestClient, auth_headers: dict) -> None:
        r = client.post("/organizations", json={"name": "Owner Test"}, headers=auth_headers)
        org_id = r.json()["id"]
        # Creator can access the org (they're the owner)
        r2 = client.get(f"/organizations/{org_id}", headers=auth_headers)
        assert r2.status_code == 200

    def test_get_organization(self, client: TestClient, auth_headers: dict) -> None:
        r = client.post("/organizations", json={"name": "Get Test"}, headers=auth_headers)
        org_id = r.json()["id"]
        r2 = client.get(f"/organizations/{org_id}", headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json()["name"] == "Get Test"

    def test_get_organization_forbidden_for_non_member(
        self, client: TestClient, auth_headers: dict, second_user_headers: dict
    ) -> None:
        r = client.post("/organizations", json={"name": "NonMember Test"}, headers=auth_headers)
        org_id = r.json()["id"]
        r2 = client.get(f"/organizations/{org_id}", headers=second_user_headers)
        assert r2.status_code == 403

    def test_update_organization(self, client: TestClient, auth_headers: dict) -> None:
        r = client.post("/organizations", json={"name": "Update Test"}, headers=auth_headers)
        org_id = r.json()["id"]
        r2 = client.patch(f"/organizations/{org_id}", json={"name": "Updated"}, headers=auth_headers)
        assert r2.status_code == 200
        assert r2.json()["name"] == "Updated"

    def test_update_organization_forbidden_for_member(
        self, client: TestClient, auth_headers: dict, second_user_headers: dict
    ) -> None:
        # Creator (admin) creates org
        r = client.post("/organizations", json={"name": "Permission Test"}, headers=auth_headers)
        org_id = r.json()["id"]
        # Get creator's user_id from /auth/me
        r_me = client.get("/auth/me", headers=auth_headers)
        creator_id = r_me.json()["id"]
        # Add second user as member (not admin)
        client.post(
            f"/organizations/{org_id}/members",
            json={"user_id": creator_id, "role": "member"},
            headers=auth_headers,
        )
        # Second user tries to update — should be forbidden
        r3 = client.patch(f"/organizations/{org_id}", json={"name": "Hacked"}, headers=second_user_headers)
        assert r3.status_code == 403


# ── Membership API ───────────────────────────────────────────────────────────


class TestMembershipAPI:
    def test_add_member(self, client: TestClient, auth_headers: dict, second_user_headers: dict) -> None:
        r = client.post("/organizations", json={"name": "Member Test"}, headers=auth_headers)
        org_id = r.json()["id"]
        r_me2 = client.get("/auth/me", headers=second_user_headers)
        member_id = r_me2.json()["id"]
        r2 = client.post(
            f"/organizations/{org_id}/members",
            json={"user_id": member_id, "role": "member"},
            headers=auth_headers,
        )
        assert r2.status_code == 201
        assert r2.json()["role"] == "member"

    def test_list_members(self, client: TestClient, auth_headers: dict) -> None:
        r = client.post("/organizations", json={"name": "List Test"}, headers=auth_headers)
        org_id = r.json()["id"]
        r2 = client.get(f"/organizations/{org_id}/members", headers=auth_headers)
        assert r2.status_code == 200
        assert len(r2.json()["items"]) >= 1

    def test_list_members_forbidden_for_non_member(
        self, client: TestClient, auth_headers: dict, second_user_headers: dict
    ) -> None:
        r = client.post("/organizations", json={"name": "Members Only"}, headers=auth_headers)
        org_id = r.json()["id"]
        r2 = client.get(f"/organizations/{org_id}/members", headers=second_user_headers)
        assert r2.status_code == 403

    def test_change_member_role(self, client: TestClient, auth_headers: dict, second_user_headers: dict) -> None:
        r = client.post("/organizations", json={"name": "Role Test"}, headers=auth_headers)
        org_id = r.json()["id"]
        r_me2 = client.get("/auth/me", headers=second_user_headers)
        member_id = r_me2.json()["id"]
        # Add second user as member
        r2 = client.post(
            f"/organizations/{org_id}/members",
            json={"user_id": member_id, "role": "member"},
            headers=auth_headers,
        )
        mem_id = r2.json()["id"]
        # Change role to admin
        r3 = client.patch(
            f"/organizations/memberships/{mem_id}/role",
            json={"role": "admin"},
            headers=auth_headers,
        )
        assert r3.status_code == 200
        assert r3.json()["role"] == "admin"

    def test_transfer_ownership(self, client: TestClient, auth_headers: dict, second_user_headers: dict) -> None:
        r = client.post("/organizations", json={"name": "Transfer Test"}, headers=auth_headers)
        org_id = r.json()["id"]
        r_me = client.get("/auth/me", headers=auth_headers)
        creator_id = r_me.json()["id"]
        # Add second user as member
        r_me2 = client.get("/auth/me", headers=second_user_headers)
        member_id = r_me2.json()["id"]
        client.post(
            f"/organizations/{org_id}/members",
            json={"user_id": member_id, "role": "member"},
            headers=auth_headers,
        )
        # Transfer ownership
        r2 = client.post(
            f"/organizations/{org_id}/transfer",
            json={"new_owner_id": member_id},
            headers=auth_headers,
        )
        assert r2.status_code == 200
        assert r2.json()["user_id"] == member_id
        assert r2.json()["role"] == "owner"

    def test_unauthorized_access_returns_401(self, client: TestClient) -> None:
        r = client.get("/organizations/some-id")
        assert r.status_code == 401

    def test_add_member_forbidden_for_non_admin(
        self, client: TestClient, second_user_headers: dict
    ) -> None:
        r = client.post("/organizations/00000000-0000-0000-0000-000000000000/members",
                        json={"user_id": "a" * 36, "role": "member"},
                        headers=second_user_headers)
        assert r.status_code == 403


# ── Settings helper ──────────────────────────────────────────────────────────


def _test_settings(database_url: str = "sqlite:///:memory:", dev_mode: bool = False) -> Settings:
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
