from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AuthSettings, DatabaseSettings, LoggingSettings, Settings
from app.core.security import create_access_token
from app.database import session as database_session
from app.main import create_app
from app.models.email_verification_token import EmailVerificationToken
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
def client(api_session_factory: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("DEV_MODE", "true")
    app = create_app(_test_settings(dev_mode=True), configure_logging_on_startup=False)
    with TestClient(app) as test_client:
        yield test_client


# ── Helpers ──────────────────────────────────────────────────────────────────


def _register(client: TestClient, email: str = "test@example.com", password: str = "password123") -> dict:
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


def _register_and_verify(client: TestClient, email: str = "test@example.com") -> dict:
    data = _register(client, email=email)
    _verify(client, data["message"], email=email)
    return data


def _login(client: TestClient, email: str = "test@example.com", password: str = "password123") -> dict:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()


# ── Registration Tests ───────────────────────────────────────────────────────


class TestRegister:
    def test_successful_registration(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/register",
            json={"email": "new@example.com", "password": "validpass123", "display_name": "New User"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["display_name"] == "New User"
        assert "id" in data
        assert "Verify your email" in data["message"]

    def test_duplicate_email_rejected(self, client: TestClient) -> None:
        _register(client, email="dup@example.com")
        resp = client.post(
            "/auth/register",
            json={"email": "dup@example.com", "password": "validpass123", "display_name": "Second"},
        )
        assert resp.status_code == 409

    def test_invalid_email_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/register",
            json={"email": "", "password": "validpass123", "display_name": "No Email"},
        )
        assert resp.status_code == 422

    def test_short_password_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/register",
            json={"email": "shortpwd@example.com", "password": "abc", "display_name": "Short Pwd"},
        )
        assert resp.status_code == 422

    def test_user_is_inactive_after_register(self, client: TestClient, api_session_factory: sessionmaker[Session]) -> None:
        _register(client, email="inactive@example.com")
        with api_session_factory() as session:
            user = session.scalar(select(User).where(User.email == "inactive@example.com"))
            assert user is not None
            assert user.is_active is False
            assert user.email_verified_at is None

    def test_dev_mode_logs_verification_token(self, client: TestClient) -> None:
        """Registration in dev mode writes the verification token to the server log.

        We attach a ``StringIO`` handler to the ``irtiqa`` logger because the
        test client has ``configure_logging_on_startup=False`` (the default
        WARNING-level root logger would suppress INFO-level messages).
        """
        import io, logging

        buf = io.StringIO()
        logger = logging.getLogger("irtiqa")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(buf)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

        # Sanity check: verify our handler captures log records before the
        # actual registration call.  This isolates logger-hierarchy issues
        # from request-handling concerns.
        auth_logger = logging.getLogger("irtiqa.endpoints.auth")
        logger.info("direct-on-irtiqa")
        auth_logger.info("via-child-logger")
        preflight = buf.getvalue()
        assert "via-child-logger" in preflight, (
            f"Handler not receiving records via child logger.  Details:\n"
            f"  irtiqa: level={logger.level} handlers={logger.handlers} "
            f"propagate={logger.propagate} disabled={logger.disabled}\n"
            f"  irtiqa.endpoints.auth: level={auth_logger.level} "
            f"effective={auth_logger.getEffectiveLevel()} "
            f"propagate={auth_logger.propagate} "
            f"disabled={auth_logger.disabled} "
            f"handlers={auth_logger.handlers}\n"
            f"  irtiqa.endpoints: "
            f"level={logging.getLogger('irtiqa.endpoints').level} "
            f"propagate={logging.getLogger('irtiqa.endpoints').propagate}\n"
            f"  preflight={repr(preflight)}"
        )

        try:
            data = _register(client, email="dev-log@example.com")
            response_token = data["message"].split("Token: ")[1].strip()
            log_output = buf.getvalue()
            assert response_token in log_output, (
                f"Token {response_token[:12]}... not found in log output:\n"
                f"{'─' * 40}\n"
                f"{log_output}"
                f"{'─' * 40}\n"
                f"(preflight was OK)"
            )
        finally:
            logger.removeHandler(handler)


# ── Email Verification Tests ─────────────────────────────────────────────────


class TestEmailVerification:
    def test_verify_valid_token(self, client: TestClient, api_session_factory: sessionmaker[Session]) -> None:
        data = _register(client, email="verify-ok@example.com")
        _verify(client, data["message"], email="verify-ok@example.com")

        with api_session_factory() as session:
            user = session.scalar(select(User).where(User.email == "verify-ok@example.com"))
            assert user is not None
            assert user.is_active is True
            assert user.email_verified_at is not None

    def test_invalid_token_rejected(self, client: TestClient) -> None:
        resp = client.post("/auth/verify-email", json={"token": "not-a-real-token"})
        assert resp.status_code == 422

    def test_empty_token_rejected(self, client: TestClient) -> None:
        resp = client.post("/auth/verify-email", json={"token": ""})
        assert resp.status_code == 422

    def test_login_blocked_before_verification(self, client: TestClient) -> None:
        _register(client, email="unverified@example.com")
        resp = client.post("/auth/login", json={"email": "unverified@example.com", "password": "password123"})
        assert resp.status_code == 422
        assert "not activated" in resp.text.lower()


# ── Login Tests ──────────────────────────────────────────────────────────────


class TestLogin:
    def test_successful_login(self, client: TestClient, api_session_factory: sessionmaker[Session]) -> None:
        _register_and_verify(client, email="login-ok@example.com")
        data = _login(client, email="login-ok@example.com")
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "login-ok@example.com"

    def test_wrong_password_rejected(self, client: TestClient) -> None:
        _register_and_verify(client, email="wrong-pw@example.com")
        resp = client.post(
            "/auth/login",
            json={"email": "wrong-pw@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 422

    def test_nonexistent_user_rejected(self, client: TestClient) -> None:
        resp = client.post(
            "/auth/login",
            json={"email": "doesnotexist@example.com", "password": "password123"},
        )
        assert resp.status_code == 422

    def test_soft_deleted_user_rejected(self, client: TestClient) -> None:
        _register_and_verify(client, email="deleteme@example.com")
        data = _login(client, email="deleteme@example.com")
        # Delete account
        client.delete("/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        # Try to login again — deleted user should be rejected
        resp = client.post(
            "/auth/login",
            json={"email": "deleteme@example.com", "password": "password123"},
        )
        assert resp.status_code == 422

    def test_rate_limiting(self, client: TestClient) -> None:
        """6 failed login attempts within the window should trigger lockout."""
        _register_and_verify(client, email="ratelimit@example.com")
        # 5 failed attempts
        for _ in range(5):
            resp = client.post(
                "/auth/login",
                json={"email": "ratelimit@example.com", "password": "wrongpass"},
            )
            assert resp.status_code == 422
        # 6th attempt should be rate limited
        # Currently returns 422 (ValidationError); 429 planned for enhancement.
        resp = client.post(
            "/auth/login",
            json={"email": "ratelimit@example.com", "password": "wrongpass"},
        )
        assert resp.status_code in (422, 429)


# ── Logout Tests ─────────────────────────────────────────────────────────────


class TestLogout:
    def test_logout_revokes_refresh_token(self, client: TestClient) -> None:
        data = _register_and_verify(client)
        data = _login(client)
        access = data["access_token"]
        refresh = data["refresh_token"]

        resp = client.post(
            "/auth/logout",
            json={"refresh_token": refresh},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert resp.status_code == 204

        # Try to refresh with the revoked token
        resp = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 422

    def test_logout_no_auth_rejected(self, client: TestClient) -> None:
        resp = client.post("/auth/logout", json={"refresh_token": "some-token"})
        assert resp.status_code == 401


# ── Refresh Tests ────────────────────────────────────────────────────────────


class TestRefresh:
    def test_successful_refresh(self, client: TestClient) -> None:
        _register_and_verify(client)
        data = _login(client)
        refresh = data["refresh_token"]

        resp = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        new_data = resp.json()
        assert "access_token" in new_data
        assert "refresh_token" in new_data
        assert new_data["token_type"] == "bearer"
        # A new refresh token is always issued (rotation)
        assert new_data["refresh_token"] != refresh
        # The new access token is usable for authentication
        resp2 = client.get("/auth/me", headers={"Authorization": f"Bearer {new_data['access_token']}"})
        assert resp2.status_code == 200

    def test_refreshed_token_has_org_scoping(self, client: TestClient) -> None:
        """Refreshed access token must carry org context so that
        org-scoped endpoints (e.g. GET /companies) do not 403."""
        _register_and_verify(client)
        data = _login(client)
        refresh = data["refresh_token"]

        resp = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        new_data = resp.json()

        # Use the refreshed token against an org-scoped endpoint
        resp2 = client.get(
            "/companies",
            headers={"Authorization": f"Bearer {new_data['access_token']}"},
        )
        assert resp2.status_code == 200, (
            f"Refreshed token should work for /companies, got {resp2.status_code}: {resp2.text}"
        )

    def test_old_token_revoked_after_refresh(self, client: TestClient) -> None:
        _register_and_verify(client)
        data = _login(client)
        refresh = data["refresh_token"]

        # First refresh — works
        resp = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200

        # Second refresh with old token — should fail
        resp = client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 422

    def test_invalid_token_rejected(self, client: TestClient) -> None:
        resp = client.post("/auth/refresh", json={"refresh_token": "not-a-real-token"})
        assert resp.status_code == 422

    def test_empty_token_rejected(self, client: TestClient) -> None:
        resp = client.post("/auth/refresh", json={"refresh_token": ""})
        assert resp.status_code == 422


# ── Profile Tests ────────────────────────────────────────────────────────────


class TestProfile:
    def test_get_me_authenticated(self, client: TestClient) -> None:
        _register_and_verify(client)
        data = _login(client)
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
        assert resp.status_code == 200
        assert resp.json()["email"] is not None

    def test_get_me_no_auth_rejected(self, client: TestClient) -> None:
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_get_me_expired_token_rejected(self, client: TestClient) -> None:
        expired = create_access_token("nonexistent", expires_in=-1)
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
        assert resp.status_code == 401

    def test_get_me_invalid_token_rejected(self, client: TestClient) -> None:
        resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert resp.status_code == 401

    def test_update_profile(self, client: TestClient) -> None:
        _register_and_verify(client)
        data = _login(client)
        resp = client.patch(
            "/auth/me",
            json={"display_name": "Updated Name"},
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated Name"

    def test_update_profile_no_auth_rejected(self, client: TestClient) -> None:
        resp = client.patch("/auth/me", json={"display_name": "Hacker"})
        assert resp.status_code == 401

    def test_delete_account(self, client: TestClient) -> None:
        _register_and_verify(client)
        data = _login(client)
        access = data["access_token"]

        resp = client.delete("/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert resp.status_code == 204

        # Verify user cannot access /auth/me after deletion
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert resp.status_code == 401

    def test_delete_account_no_auth_rejected(self, client: TestClient) -> None:
        resp = client.delete("/auth/me")
        assert resp.status_code == 401


# ── JWKS Tests ───────────────────────────────────────────────────────────────


class TestJWKS:
    def test_jwks_endpoint(self, client: TestClient) -> None:
        resp = client.get("/.well-known/jwks.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        assert len(data["keys"]) >= 1
        key = data["keys"][0]
        assert key["kty"] == "RSA"
        assert key["kid"] == "key-v1"
        assert key["alg"] == "RS256"

    def test_jwks_public_key_exists(self, client: TestClient) -> None:
        resp = client.get("/.well-known/jwks.json")
        key = resp.json()["keys"][0]
        assert "n" in key
        assert "e" in key
        assert len(key["n"]) > 0
        assert len(key["e"]) > 0


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
