from __future__ import annotations

import uuid

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.database import session as database_session
from app.models.base import Base
from app.models.user import User
from app.services.membership_service import MembershipService
from app.services.organization_service import OrganizationService


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


def _create_org_with_owner(session_factory: sessionmaker) -> tuple[str, str]:
    uid = _create_user(session_factory)
    svc = OrganizationService()
    org, _ = svc.create_with_owner("Test Org", uid)
    return org.id, uid


class TestMembershipCreate:
    def test_adds_member(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        uid2 = _create_user(_session_override)
        svc = MembershipService()
        mem = svc.create(uid2, org_id, "member")
        assert mem.user_id == uid2
        assert mem.organization_id == org_id
        assert mem.role == "member"

    def test_duplicate_membership_rejected(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        svc = MembershipService()
        with pytest.raises(Exception):
            svc.create(owner_id, org_id, "member")


class TestMembershipQuery:
    def test_get_membership(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        svc = MembershipService()
        mem = svc.get_membership(owner_id, org_id)
        assert mem is not None
        assert mem.role == "owner"

    def test_get_membership_returns_none(self, _session_override: sessionmaker) -> None:
        uid = _create_user(_session_override)
        svc = MembershipService()
        mem = svc.get_membership(uid, "00000000-0000-0000-0000-000000000000")
        assert mem is None

    def test_list_organization_members(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        svc = MembershipService()
        members = svc.list_organization_members(org_id)
        assert len(members) == 1

    def test_list_user_memberships(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        svc = MembershipService()
        memberships = svc.list_user_memberships(owner_id)
        assert len(memberships) == 1


class TestMembershipUpdateRole:
    def test_updates_role(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        uid2 = _create_user(_session_override)
        svc = MembershipService()
        mem = svc.create(uid2, org_id, "member")
        updated = svc.update_role(mem.id, "admin")
        assert updated.role == "admin"

    def test_invalid_role_rejected(self, _session_override: sessionmaker) -> None:
        from app.core.errors import ValidationError
        svc = MembershipService()
        with pytest.raises(ValidationError):
            svc.create(_create_user(_session_override), "x" * 36, "superadmin")  # type: ignore[arg-type]

    def test_cannot_downgrade_last_owner(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        svc = MembershipService()
        mem = svc.get_membership(owner_id, org_id)
        assert mem is not None
        with pytest.raises(Exception):
            svc.update_role(mem.id, "member")


class TestMembershipRemove:
    def test_removes_member(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        uid2 = _create_user(_session_override)
        svc = MembershipService()
        mem = svc.create(uid2, org_id, "member")
        svc.remove(mem.id)
        assert svc.get(mem.id) is None

    def test_cannot_remove_last_owner(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        svc = MembershipService()
        mem = svc.get_membership(owner_id, org_id)
        assert mem is not None
        with pytest.raises(Exception):
            svc.remove(mem.id)


class TestOwnershipTransfer:
    def test_transfers_ownership(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        uid2 = _create_user(_session_override)
        svc = MembershipService()
        svc.create(uid2, org_id, "member")
        old, new = svc.transfer_ownership(org_id, owner_id, uid2)
        assert old.role == "admin"
        assert new.role == "owner"

    def test_can_remove_former_owner_after_transfer(self, _session_override: sessionmaker) -> None:
        org_id, owner_id = _create_org_with_owner(_session_override)
        uid2 = _create_user(_session_override)
        svc = MembershipService()
        svc.create(uid2, org_id, "member")
        old, _ = svc.transfer_ownership(org_id, owner_id, uid2)
        # Old owner is now admin — can be removed
        svc.remove(old.id)
        assert svc.get(old.id) is None
