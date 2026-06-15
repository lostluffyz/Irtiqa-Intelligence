from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import create_access_token, decode_access_token, hash_password
from app.database import session as database_session
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import OrganizationSummary
from app.services.auth_service import AuthService
from app.services.membership_service import MembershipService
from app.api.dependencies import get_current_organization


# ── Fixtures ─────────────────────────────────────────────────────────────────


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
def auth_service(service_session_factory: sessionmaker[Session]) -> AuthService:
    return AuthService()


@pytest.fixture()
def membership_service(
    service_session_factory: sessionmaker[Session],
) -> MembershipService:
    return MembershipService()


# ── Helpers ──────────────────────────────────────────────────────────────────


def _register_and_verify(
    auth_service: AuthService,
    email: str = "test@example.com",
    password: str = "password123",
    display_name: str = "Test User",
) -> tuple[User, str, str]:
    """Register a user, verify email, and login. Returns (user, access_token, refresh_token)."""
    user = auth_service.register(
        email=email,
        password=password,
        display_name=display_name,
    )
    token = auth_service.get_verification_token(user)
    auth_service.verify_email(token)

    user_obj, access_token, refresh_token, org_summary = auth_service.login(
        email=email,
        password=password,
        ip_address="127.0.0.1",
    )
    return user_obj, access_token, refresh_token


def _create_user_without_org(
    service_session_factory: sessionmaker[Session],
    email: str = "no-org@example.com",
    password: str = "password123",
    display_name: str = "No Org",
    *,
    verified: bool = True,
) -> User:
    """Create a User directly in the database without an organization or membership."""
    now = datetime.now(timezone.utc)
    hashed = hash_password(password)
    with service_session_factory() as session:
        repo = UserRepository(session)
        user = User(
            email=email,
            password_hash=hashed,
            display_name=display_name,
            is_active=verified,
            email_verified_at=now if verified else None,
            created_at=now,
            updated_at=now,
        )
        repo.add(user)
        session.commit()
        session.refresh(user)
        return user


# ── Registration Tests ───────────────────────────────────────────────────────


class TestRegisterOrg:
    """Tests that registration creates organization and owner membership."""

    def test_register_creates_org_and_membership(
        self,
        service_session_factory: sessionmaker[Session],
        auth_service: AuthService,
    ) -> None:
        user = auth_service.register(
            email="reg-org@example.com",
            password="password123",
            display_name="Org Creator",
        )

        # Verify organization was created
        with service_session_factory() as session:
            org = session.scalar(
                select(Organization).where(
                    Organization.name == "Org Creator's Organization",
                ),
            )
            assert org is not None, "Organization should have been created"
            assert org.status == "active"
            assert org.slug is not None

            # Verify membership was created with owner role
            membership = session.scalar(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.organization_id == org.id,
                ),
            )
            assert membership is not None, "Owner membership should have been created"
            assert membership.role == "owner"

    def test_register_org_has_correct_slug(
        self,
        service_session_factory: sessionmaker[Session],
        auth_service: AuthService,
    ) -> None:
        auth_service.register(
            email="slug-test@example.com",
            password="password123",
            display_name="Slug Test",
        )

        with service_session_factory() as session:
            org = session.scalar(
                select(Organization).where(
                    Organization.name == "Slug Test's Organization",
                ),
            )
            assert org is not None
            # generate_slug("Slug Test's Organization")
            #   → "slug-test-s-organization"
            assert org.slug == "slug-test-s-organization"


# ── Login Organization Context Tests ─────────────────────────────────────────


class TestLoginOrg:
    """Tests that login returns organization context."""

    def test_login_returns_org_context(
        self,
        auth_service: AuthService,
    ) -> None:
        user = auth_service.register(
            email="login-ctx@example.com",
            password="password123",
            display_name="Login Ctx",
        )
        token = auth_service.get_verification_token(user)
        auth_service.verify_email(token)

        result = auth_service.login(
            email="login-ctx@example.com",
            password="password123",
            ip_address="127.0.0.1",
        )
        _, _, _, org_summary = result

        assert org_summary is not None, "Login should return org context"
        assert isinstance(org_summary, OrganizationSummary)
        assert org_summary.role == "owner"
        assert org_summary.name == "Login Ctx's Organization"
        assert org_summary.slug is not None

    def test_login_jwt_contains_org_claim(
        self,
        auth_service: AuthService,
    ) -> None:
        user = auth_service.register(
            email="jwt-claim@example.com",
            password="password123",
            display_name="JWT Tester",
        )
        token = auth_service.get_verification_token(user)
        auth_service.verify_email(token)

        _, access_token, _, org_summary = auth_service.login(
            email="jwt-claim@example.com",
            password="password123",
            ip_address="127.0.0.1",
        )

        assert org_summary is not None
        payload = decode_access_token(access_token)
        assert "org" in payload, "JWT should contain org claim"
        assert "role" in payload, "JWT should contain role claim"
        assert payload["org"] == org_summary.id
        assert payload["role"] == "owner"

    def test_login_returns_correct_role(
        self,
        auth_service: AuthService,
    ) -> None:
        user = auth_service.register(
            email="login-role@example.com",
            password="password123",
            display_name="Role Tester",
        )
        token = auth_service.get_verification_token(user)
        auth_service.verify_email(token)

        _, access_token, _, org_summary = auth_service.login(
            email="login-role@example.com",
            password="password123",
            ip_address="127.0.0.1",
        )

        # The registered user is the owner of the auto-created org
        assert org_summary is not None
        assert org_summary.role == "owner"

        payload = decode_access_token(access_token)
        assert payload["role"] == "owner"

    def test_login_no_org_fallback(
        self,
        service_session_factory: sessionmaker[Session],
        auth_service: AuthService,
    ) -> None:
        """A user without any memberships should get None as org context."""
        _create_user_without_org(
            service_session_factory,
            email="no-org-login@example.com",
            password="password123",
        )

        user_obj, access_token, refresh_token, org_summary = auth_service.login(
            email="no-org-login@example.com",
            password="password123",
            ip_address="127.0.0.1",
        )

        # No memberships → no org context
        assert org_summary is None, "User without org should get None org context"

        # JWT should have no org/role claims
        payload = decode_access_token(access_token)
        assert payload.get("org") is None
        assert payload.get("role") is None


# ── get_current_organization Tests ───────────────────────────────────────────


class TestGetCurrentOrganization:
    """Tests for the get_current_organization FastAPI dependency."""

    def test_get_current_organization_valid(
        self,
        service_session_factory: sessionmaker[Session],
        auth_service: AuthService,
        membership_service: MembershipService,
    ) -> None:
        user = auth_service.register(
            email="valid-org@example.com",
            password="password123",
            display_name="Valid Org",
        )
        token = auth_service.get_verification_token(user)
        auth_service.verify_email(token)

        _, access_token, _, org_summary = auth_service.login(
            email="valid-org@example.com",
            password="password123",
            ip_address="127.0.0.1",
        )
        assert org_summary is not None

        ctx = get_current_organization(
            authorization=f"Bearer {access_token}",
            auth_service=auth_service,
            membership_service=membership_service,
        )

        assert ctx is not None
        assert ctx.organization_id == org_summary.id
        assert ctx.user_id == user.id
        assert ctx.role == "owner"
        assert ctx.is_api_key is False

    def test_get_current_organization_revoked(
        self,
        service_session_factory: sessionmaker[Session],
        auth_service: AuthService,
        membership_service: MembershipService,
    ) -> None:
        """A deleted/revoked membership should cause a 403."""
        user = auth_service.register(
            email="revoked@example.com",
            password="password123",
            display_name="Revoked User",
        )
        token = auth_service.get_verification_token(user)
        auth_service.verify_email(token)

        _, access_token, _, org_summary = auth_service.login(
            email="revoked@example.com",
            password="password123",
            ip_address="127.0.0.1",
        )
        assert org_summary is not None

        # Delete the membership from the database
        with service_session_factory() as session:
            stmt = select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == org_summary.id,
            )
            membership = session.scalar(stmt)
            assert membership is not None
            session.delete(membership)
            session.commit()

        # Now get_current_organization should fail with 403
        # because MembershipService.get_membership() returns None
        with pytest.raises(HTTPException) as exc_info:
            get_current_organization(
                authorization=f"Bearer {access_token}",
                auth_service=auth_service,
                membership_service=membership_service,
            )
        assert exc_info.value.status_code == 403
        assert "not a member" in exc_info.value.detail.lower()

    def test_get_current_organization_no_org(
        self,
        service_session_factory: sessionmaker[Session],
        auth_service: AuthService,
        membership_service: MembershipService,
    ) -> None:
        """A JWT without an org claim should cause a 403."""
        user = _create_user_without_org(
            service_session_factory,
            email="no-org-ctx@example.com",
        )

        # Create a token WITHOUT org/role claims
        token = create_access_token(user_id=user.id)

        with pytest.raises(HTTPException) as exc_info:
            get_current_organization(
                authorization=f"Bearer {token}",
                auth_service=auth_service,
                membership_service=membership_service,
            )
        assert exc_info.value.status_code == 403
        assert "no organization context" in exc_info.value.detail.lower()
