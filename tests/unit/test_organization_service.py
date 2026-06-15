from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import session as database_session
from app.models.base import Base
from app.models.user import User
from app.services.organization_service import OrganizationService
from app.services.membership_service import MembershipService


@pytest.fixture(autouse=True)
def _session_override(monkeypatch: pytest.MonkeyPatch) -> sessionmaker:
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database_session, "SessionLocal", factory)
    return factory


def _create_user(session_factory: sessionmaker) -> str:
    session = session_factory()
    uid = str(uuid.uuid4())
    session.add(
        User(id=uid, email=f"{uid[:8]}@test.com", password_hash="pw", display_name="Test", is_active=True)
    )
    session.commit()
    session.close()
    return uid


class TestOrganizationCreate:
    def test_creates_org_with_slug(self, _session_override: sessionmaker) -> None:
        svc = OrganizationService()
        org = svc.create("My Org")
        assert org.name == "My Org"
        assert org.slug == "my-org"
        assert org.status == "active"

    def test_generates_unique_slug_on_collision(self, _session_override: sessionmaker) -> None:
        svc = OrganizationService()
        org1 = svc.create("Test Org")
        org2 = svc.create("Test Org")
        assert org1.slug == "test-org"
        assert org2.slug != org1.slug
        assert org2.slug.startswith("test-org")

    def test_empty_name_rejected(self) -> None:
        from app.core.errors import ValidationError
        svc = OrganizationService()
        with pytest.raises(ValidationError):
            svc.create("")


class TestOrganizationCreateWithOwner:
    def test_creates_org_and_owner(self, _session_override: sessionmaker) -> None:
        uid = _create_user(_session_override)
        svc = OrganizationService()
        org, membership = svc.create_with_owner("My Org", uid)
        assert org.name == "My Org"
        assert membership.user_id == uid
        assert membership.role == "owner"

    def test_creator_is_owner(self, _session_override: sessionmaker) -> None:
        uid = _create_user(_session_override)
        svc = OrganizationService()
        org, _ = svc.create_with_owner("My Org", uid)
        mem_svc = MembershipService()
        membership = mem_svc.get_membership(uid, org.id)
        assert membership is not None
        assert membership.role == "owner"


class TestOrganizationUpdate:
    def test_updates_name(self, _session_override: sessionmaker) -> None:
        uid = _create_user(_session_override)
        svc = OrganizationService()
        org, _ = svc.create_with_owner("Original", uid)
        updated = svc.update(org.id, name="Updated")
        assert updated.name == "Updated"

    def test_deactivates_org(self, _session_override: sessionmaker) -> None:
        uid = _create_user(_session_override)
        svc = OrganizationService()
        org, _ = svc.create_with_owner("Active Org", uid)
        deactivated = svc.deactivate(org.id)
        assert deactivated.status == "suspended"

    def test_list_active_excludes_deactivated(self, _session_override: sessionmaker) -> None:
        uid = _create_user(_session_override)
        svc = OrganizationService()
        org, _ = svc.create_with_owner("To Deactivate", uid)
        svc.deactivate(org.id)
        active = svc.list_active()
        assert all(o.status == "active" for o in active)
