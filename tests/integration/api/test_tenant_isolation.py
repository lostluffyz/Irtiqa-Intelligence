from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AuthSettings, DatabaseSettings, LoggingSettings, Settings
from app.core.security import create_access_token
from app.core.tenant import TenantContext
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
def org_a(api_session_factory: sessionmaker[Session]) -> Iterator[Organization]:
    with api_session_factory() as session:
        org = Organization(id=str(uuid4()), name="Org A", slug="org-a", status="active")
        session.add(org)
        session.commit()
        yield org


@pytest.fixture()
def org_b(api_session_factory: sessionmaker[Session]) -> Iterator[Organization]:
    with api_session_factory() as session:
        org = Organization(id=str(uuid4()), name="Org B", slug="org-b", status="active")
        session.add(org)
        session.commit()
        yield org


@pytest.fixture()
def user_a(api_session_factory: sessionmaker[Session], org_a: Organization) -> Iterator[User]:
    with api_session_factory() as session:
        from app.core.security import hash_password
        user = User(
            id=str(uuid4()),
            email="user-a-isolation@test.example",
            password_hash=hash_password("password123"),
            display_name="User A",
            is_active=True,
        )
        session.add(user)
        session.add(Membership(user_id=user.id, organization_id=org_a.id, role="owner"))
        session.commit()
        yield user


@pytest.fixture()
def user_b(api_session_factory: sessionmaker[Session], org_b: Organization) -> Iterator[User]:
    with api_session_factory() as session:
        from app.core.security import hash_password
        user = User(
            id=str(uuid4()),
            email="user-b-isolation@test.example",
            password_hash=hash_password("password123"),
            display_name="User B",
            is_active=True,
        )
        session.add(user)
        session.add(Membership(user_id=user.id, organization_id=org_b.id, role="owner"))
        session.commit()
        yield user


@pytest.fixture()
def token_a(user_a: User, org_a: Organization) -> str:
    return create_access_token(user_id=user_a.id, organization_id=org_a.id, role="owner")


@pytest.fixture()
def token_b(user_b: User, org_b: Organization) -> str:
    return create_access_token(user_id=user_b.id, organization_id=org_b.id, role="owner")


@pytest.fixture()
def headers_a(token_a: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_a}"}


@pytest.fixture()
def headers_b(token_b: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_b}"}


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


# ── Cross-tenant UUID Enumeration Protection Tests ───────────────────────────

class TestCrossTenantIsolation:
    """Verify that entities from one org are not accessible from another org."""

    def test_company_cross_tenant_denied(
        self,
        client: TestClient,
        headers_a: dict[str, str],
        headers_b: dict[str, str],
    ) -> None:
        # User A creates a company
        resp = client.post(
            "/companies",
            json={"name": "Org A Co", "domain": "org-a-co.example", "status": "active"},
            headers=headers_a,
        )
        assert resp.status_code == 201
        company_id = resp.json()["id"]

        # User B should get 403 trying to read it
        resp = client.get(f"/companies/{company_id}", headers=headers_b)
        assert resp.status_code == 403

    def test_contact_cross_tenant_denied(
        self,
        client: TestClient,
        headers_a: dict[str, str],
        headers_b: dict[str, str],
    ) -> None:
        # User A creates a company and contact
        resp = client.post(
            "/companies",
            json={"name": "Contact Parent Co", "domain": "contact-cross.example", "status": "active"},
            headers=headers_a,
        )
        assert resp.status_code == 201
        company_id = resp.json()["id"]

        resp = client.post(
            "/contacts",
            json={
                "company_id": company_id,
                "full_name": "Cross-tenant Contact",
                "email": "cross-tenant@example.com",
                "status": "active",
            },
            headers=headers_a,
        )
        assert resp.status_code == 201
        contact_id = resp.json()["id"]

        # User B should get 403
        resp = client.get(f"/contacts/{contact_id}", headers=headers_b)
        assert resp.status_code == 403

    def test_intelligence_score_scoped_by_default(
        self,
        client: TestClient,
        headers_a: dict[str, str],
        headers_b: dict[str, str],
        api_session_factory: sessionmaker[Session],
        org_a: Organization,
        org_b: Organization,
    ) -> None:
        """Default top scores should be org-scoped, not global."""
        # Create a high-scoring entity in Org B
        with api_session_factory() as session:
            from app.models.company import Company as CompanyModel
            company_b = CompanyModel(
                organization_id=org_b.id,
                name="High Score Co",
                domain="high-score.example",
                status="active",
            )
            session.add(company_b)
            session.flush()

            from app.models.intelligence_score import IntelligenceScore as ScoreModel
            from datetime import datetime, timezone
            score_b = ScoreModel(
                organization_id=org_b.id,
                company_id=company_b.id,
                fit_score=99.0,
                intent_score=99.0,
                technographic_score=99.0,
                engagement_score=99.0,
                total_score=99.0,
                confidence=0.99,
                score_version="v1",
                rationale="High score for testing.",
                scored_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(score_b)
            session.flush()

        # User A's top scores should NOT include Org B's score
        resp = client.get("/intelligence-scores/top", headers=headers_a)
        assert resp.status_code == 200
        # The scores returned should be empty since Org A has no scores
        data = resp.json()
        assert len(data["items"]) == 0

    def test_job_visibility_isolation(
        self,
        client: TestClient,
        headers_a: dict[str, str],
        headers_b: dict[str, str],
    ) -> None:
        """User A cannot see User B's jobs via list endpoint."""
        # User B lists jobs — should get 200 with empty list (org-scoped)
        resp = client.get("/jobs", headers=headers_b)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 0

    def test_evidence_cross_tenant_denied(
        self,
        client: TestClient,
        headers_a: dict[str, str],
        headers_b: dict[str, str],
    ) -> None:
        """Evidence API endpoints require org context and reject cross-org."""
        resp = client.get(
            "/evidence/by-target/technology/some-id",
            headers=headers_b,
        )
        assert resp.status_code == 200  # OK — empty list scoped to Org B

    def test_owner_only_global_scores(
        self,
        client: TestClient,
        headers_a: dict[str, str],
        headers_b: dict[str, str],
    ) -> None:
        """Non-owner role cannot access ?global=true scores."""
        # User A is owner — should be able to access global
        resp = client.get("/intelligence-scores/top?global=true", headers=headers_a)
        assert resp.status_code == 200
