from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import create_access_token
from app.database import session as database_session
from app.models.company import Company
from app.models.contact import Contact
from app.models.organization import Organization
from app.models.user import User
from app.repositories import (
    AgentRunRepository,
    CompanyRepository,
    ContactRepository,
    IntelligenceScoreRepository,
    IntentSignalRepository,
    OutreachMessageRepository,
)
from app.repositories.evidence_repository import EvidenceRepository
from app.services.company_service import CompanyService
from app.services.contact_service import ContactService
from app.api.dependencies import get_current_organization
from app.services.membership_service import MembershipService
from app.services.auth_service import AuthService


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
def org_a(service_session_factory: sessionmaker[Session]) -> Organization:
    with service_session_factory() as session:
        org = Organization(
            id=str(uuid4()),
            name="Organization A",
            slug="org-a",
            status="active",
        )
        session.add(org)
        session.commit()
        return org


@pytest.fixture()
def org_b(service_session_factory: sessionmaker[Session]) -> Organization:
    with service_session_factory() as session:
        org = Organization(
            id=str(uuid4()),
            name="Organization B",
            slug="org-b",
            status="active",
        )
        session.add(org)
        session.commit()
        return org


@pytest.fixture()
def user_a(service_session_factory: sessionmaker[Session], org_a: Organization) -> User:
    with service_session_factory() as session:
        from app.core.security import hash_password
        from app.models.membership import Membership
        user = User(
            id=str(uuid4()),
            email="user-a@test.example",
            password_hash=hash_password("password123"),
            display_name="User A",
            is_active=True,
        )
        session.add(user)
        session.add(Membership(user_id=user.id, organization_id=org_a.id, role="owner"))
        session.commit()
        return user


# ── Repository Tenant Isolation Tests ────────────────────────────────────────


def test_repository_company_tenant_filter(
    service_session_factory: sessionmaker[Session],
    org_a: Organization,
    org_b: Organization,
) -> None:
    """Company created in Org A is not visible when querying via Org B."""
    with service_session_factory() as session:
        repo = CompanyRepository(session)
        company = Company(
            organization_id=org_a.id,
            name="Org A Company",
            domain="org-a-company.example",
            status="active",
        )
        repo.add(company)
        session.flush()

        # Should be visible in Org A
        result = repo.get_by_domain("org-a-company.example", organization_id=org_a.id)
        assert result is not None
        assert result.name == "Org A Company"

        # Should NOT be visible in Org B
        result = repo.get_by_domain("org-a-company.example", organization_id=org_b.id)
        assert result is None

        # list_by_status should respect org boundary
        results = repo.list_by_status("active", organization_id=org_b.id)
        assert len(results) == 0


def test_repository_contact_tenant_filter(
    service_session_factory: sessionmaker[Session],
    org_a: Organization,
    org_b: Organization,
) -> None:
    """Contact created in Org A is not visible when querying via Org B."""
    with service_session_factory() as session:
        repo = CompanyRepository(session)
        company = Company(
            organization_id=org_a.id,
            name="Org A Co",
            domain="org-a-co.example",
            status="active",
        )
        repo.add(company)
        session.flush()

        contact_repo = ContactRepository(session)
        contact = Contact(
            organization_id=org_a.id,
            company_id=company.id,
            full_name="Org A Contact",
            email="contact-orga@example.com",
            status="active",
        )
        contact_repo.add(contact)
        session.flush()

        # Should be visible in Org A
        result = contact_repo.get_by_email("contact-orga@example.com", organization_id=org_a.id)
        assert result is not None

        # Should NOT be visible in Org B
        result = contact_repo.get_by_email("contact-orga@example.com", organization_id=org_b.id)
        assert result is None


# ── Service Tenant Isolation Tests ───────────────────────────────────────────


def test_service_cross_org_company_isolation(
    service_session_factory: sessionmaker[Session],
    org_a: Organization,
    org_b: Organization,
) -> None:
    """CompanyService.get_by_domain should not return companies from other orgs."""
    svc = CompanyService()

    # Create in Org A
    company = svc.create(
        organization_id=org_a.id,
        name="Cross-org Test Co",
        domain="cross-org-test.example",
        status="active",
    )

    # Lookup by Org A — should find
    found = svc.get_by_domain("cross-org-test.example", organization_id=org_a.id)
    assert found is not None
    assert found.id == company.id

    # Lookup by Org B — should NOT find (different org)
    found = svc.get_by_domain("cross-org-test.example", organization_id=org_b.id)
    assert found is None


def test_service_cross_org_contact_isolation(
    service_session_factory: sessionmaker[Session],
    org_a: Organization,
    org_b: Organization,
) -> None:
    """ContactService.get_by_email should not return contacts from other orgs."""
    company_svc = CompanyService()
    contact_svc = ContactService()

    company = company_svc.create(
        organization_id=org_a.id,
        name="Contact Parent Co",
        domain="contact-parent.example",
        status="active",
    )

    contact = contact_svc.create(
        organization_id=org_a.id,
        company_id=company.id,
        full_name="Isolated Contact",
        email="isolated@example.com",
        status="active",
    )

    # Same org — should find
    found = contact_svc.get_by_email("isolated@example.com", organization_id=org_a.id)
    assert found is not None

    # Different org — should NOT find
    found = contact_svc.get_by_email("isolated@example.com", organization_id=org_b.id)
    assert found is None


# ── get_current_organization Dependency Tests ────────────────────────────────


def test_get_current_organization_no_org_claim(
    service_session_factory: sessionmaker[Session],
    user_a: User,
) -> None:
    """JWT without org claim raises 403."""
    from app.api.dependencies import get_current_organization
    from app.services.auth_service import AuthService
    from app.services.membership_service import MembershipService

    auth_svc = AuthService()
    mem_svc = MembershipService()

    # Token WITHOUT org claim
    token = create_access_token(user_id=user_a.id)

    with pytest.raises(HTTPException) as exc:
        get_current_organization(
            authorization=f"Bearer {token}",
            auth_service=auth_svc,
            membership_service=mem_svc,
        )
    assert exc.value.status_code == 403


def test_get_current_organization_revoked(
    service_session_factory: sessionmaker[Session],
    org_a: Organization,
    user_a: User,
) -> None:
    """Deleted membership raises 403."""
    from app.services.auth_service import AuthService
    from app.services.membership_service import MembershipService

    auth_svc = AuthService()
    mem_svc = MembershipService()

    token = create_access_token(
        user_id=user_a.id,
        organization_id=org_a.id,
        role="owner",
    )

    # Delete the membership
    with service_session_factory() as session:
        from app.models.membership import Membership
        stmt = select(Membership).where(
            Membership.user_id == user_a.id,
            Membership.organization_id == org_a.id,
        )
        membership = session.scalar(stmt)
        if membership:
            session.delete(membership)
            session.commit()

    with pytest.raises(HTTPException) as exc:
        get_current_organization(
            authorization=f"Bearer {token}",
            auth_service=auth_svc,
            membership_service=mem_svc,
        )
    assert exc.value.status_code == 403
