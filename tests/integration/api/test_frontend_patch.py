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


OBSERVED_AT = "2026-06-01T10:00:00Z"


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
        org = Organization(
            id=str(uuid4()), name="Frontend Patch Org", slug="frontend-patch", status="active"
        )
        session.add(org)
        session.commit()
        yield org


@pytest.fixture()
def other_org(api_session_factory: sessionmaker[Session]) -> Iterator[Organization]:
    with api_session_factory() as session:
        org = Organization(
            id=str(uuid4()), name="Other Org", slug="other-org", status="active"
        )
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
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_organization, None)


@pytest.fixture()
def other_org_client(
    api_session_factory: sessionmaker[Session],
    other_org: Organization,
) -> Iterator[TestClient]:
    app = create_app(_test_settings(), configure_logging_on_startup=False)
    app.dependency_overrides[get_current_organization] = lambda: TenantContext(
        organization_id=other_org.id,
        user_id=str(uuid4()),
        role="owner",
        is_api_key=False,
    )
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_organization, None)


# ---------------------------------------------------------------------------
# CORS Tests
# ---------------------------------------------------------------------------


class TestCORS:
    def test_preflight_auth_login_allowed_origin(self) -> None:
        app = create_app(_test_settings(), configure_logging_on_startup=False)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.options(
                "/auth/login",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Authorization,Content-Type",
                },
            )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert resp.headers.get("access-control-allow-credentials") == "true"
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods
        allow_headers = resp.headers.get("access-control-allow-headers", "")
        assert "Authorization" in allow_headers
        assert "Content-Type" in allow_headers

    def test_preflight_companies_allowed_origin(self) -> None:
        app = create_app(_test_settings(), configure_logging_on_startup=False)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.options(
                "/companies",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert resp.headers.get("access-control-allow-credentials") == "true"

    def test_preflight_disallowed_origin(self) -> None:
        app = create_app(_test_settings(), configure_logging_on_startup=False)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.options(
                "/auth/login",
                headers={
                    "Origin": "https://evil.example.com",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Authorization",
                },
            )
        # Disallowed origin must NOT get Access-Control-Allow-Origin back
        assert resp.headers.get("access-control-allow-origin") != "https://evil.example.com"


# ---------------------------------------------------------------------------
# Helper to create companies for filter tests
# ---------------------------------------------------------------------------


def _create_company(client: TestClient, *, domain: str, name: str = "Test Company") -> dict:
    resp = client.post(
        "/companies",
        json={"name": name, "domain": domain, "status": "active"},
    )
    assert resp.status_code == 201
    return resp.json()


def _create_website(client: TestClient, *, company_id: str) -> dict:
    resp = client.post(
        "/websites",
        json={
            "company_id": company_id,
            "url": f"https://{company_id}.example",
            "normalized_url": f"https://{company_id}.example/",
            "page_type": "homepage",
            "http_status": 200,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_technology(client: TestClient, *, company_id: str, website_id: str, name: str = "HubSpot") -> dict:
    resp = client.post(
        "/technologies",
        json={
            "company_id": company_id,
            "website_id": website_id,
            "name": name,
            "category": "crm",
            "vendor": "HubSpot",
            "detection_method": "html_signature",
            "confidence": 0.92,
            "first_detected_at": OBSERVED_AT,
            "last_detected_at": OBSERVED_AT,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_intent_signal(client: TestClient, *, company_id: str, website_id: str, technology_id: str) -> dict:
    resp = client.post(
        "/intent-signals",
        json={
            "company_id": company_id,
            "website_id": website_id,
            "technology_id": technology_id,
            "signal_type": "technology_change",
            "signal_name": "CRM detected",
            "signal_value": "HubSpot on homepage",
            "strength": 0.75,
            "confidence": 0.88,
            "source_url": "https://example.com",
            "observed_at": OBSERVED_AT,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_intelligence_score(
    client: TestClient, *, company_id: str, technology_id: str
) -> dict:
    resp = client.post(
        "/intelligence-scores",
        json={
            "company_id": company_id,
            "technology_id": technology_id,
            "fit_score": 82.0,
            "intent_score": 76.0,
            "technographic_score": 91.0,
            "engagement_score": 70.0,
            "total_score": 81.4,
            "confidence": 0.86,
            "score_version": "filter-test-v1",
            "rationale": "Test filter rationale.",
            "scored_at": OBSERVED_AT,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _create_outreach_message(
    client: TestClient, *, company_id: str, intelligence_score_id: str
) -> dict:
    resp = client.post(
        "/outreach-messages",
        json={
            "company_id": company_id,
            "intelligence_score_id": intelligence_score_id,
            "channel": "email",
            "subject": "Filter test outreach",
            "message_body": "Test message body for filter tests.",
            "personalization_angle": "Test angle",
            "call_to_action": "Book a call",
            "status": "draft",
            "confidence": 0.80,
            "generated_at": OBSERVED_AT,
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# Technology company_id filter tests
# ---------------------------------------------------------------------------


class TestTechnologyCompanyFilter:
    def _setup(self, client: TestClient) -> tuple[dict, dict]:
        c1 = _create_company(client, domain="tech-filter-a.example", name="Company A")
        c2 = _create_company(client, domain="tech-filter-b.example", name="Company B")
        w1 = _create_website(client, company_id=c1["id"])
        w2 = _create_website(client, company_id=c2["id"])
        _create_technology(client, company_id=c1["id"], website_id=w1["id"], name="HubSpot")
        _create_technology(client, company_id=c1["id"], website_id=w1["id"], name="Salesforce")
        _create_technology(client, company_id=c2["id"], website_id=w2["id"], name="Stripe")
        return c1, c2

    def test_unfiltered_returns_all(self, client: TestClient) -> None:
        self._setup(client)
        resp = client.get("/technologies", params={"limit": 100, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3
        assert len(body["items"]) >= 3
        # Verify envelope
        assert "items" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body

    def test_filtered_returns_only_company_records(self, client: TestClient) -> None:
        c1, c2 = self._setup(client)
        resp = client.get("/technologies", params={"company_id": c1["id"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        for item in body["items"]:
            assert item["company_id"] == c1["id"]

    def test_filtered_total_matches_items(self, client: TestClient) -> None:
        c1, _ = self._setup(client)
        resp = client.get("/technologies", params={"company_id": c1["id"], "limit": 1, "offset": 0})
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 1
        assert body["limit"] == 1
        assert body["offset"] == 0

    def test_pagination_with_filter(self, client: TestClient) -> None:
        c1, _ = self._setup(client)
        page1 = client.get("/technologies", params={"company_id": c1["id"], "limit": 1, "offset": 0})
        page2 = client.get("/technologies", params={"company_id": c1["id"], "limit": 1, "offset": 1})
        assert page1.json()["items"][0]["id"] != page2.json()["items"][0]["id"]
        assert page1.json()["total"] == page2.json()["total"]

    def test_nonexistent_company_id_returns_empty(self, client: TestClient) -> None:
        self._setup(client)
        resp = client.get(
            "/technologies",
            params={"company_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_other_org_company_id_returns_visible(self, client: TestClient, other_org_client: TestClient) -> None:
        # NOTE: /technologies has no org scoping (existing behavior — no auth dependency on list).
        # A company_id from another org still matches because technology has no org_id column.
        c_other = _create_company(
            other_org_client, domain="other-org-tech.example", name="Other Org Company"
        )
        w_other = _create_website(other_org_client, company_id=c_other["id"])
        _create_technology(other_org_client, company_id=c_other["id"], website_id=w_other["id"])

        resp = client.get("/technologies", params={"company_id": c_other["id"]})
        assert resp.status_code == 200
        body = resp.json()
        # Technologies are NOT org-scoped; result is non-empty (existing behavior).
        assert body["total"] == 1


# ---------------------------------------------------------------------------
# Intent Signal company_id filter tests
# ---------------------------------------------------------------------------


class TestIntentSignalCompanyFilter:
    def _setup(self, client: TestClient) -> tuple[dict, dict]:
        c1 = _create_company(client, domain="signal-filter-a.example", name="Signal Co A")
        c2 = _create_company(client, domain="signal-filter-b.example", name="Signal Co B")
        w1 = _create_website(client, company_id=c1["id"])
        w2 = _create_website(client, company_id=c2["id"])
        t1 = _create_technology(client, company_id=c1["id"], website_id=w1["id"], name="TechA")
        t2 = _create_technology(client, company_id=c2["id"], website_id=w2["id"], name="TechB")
        _create_intent_signal(client, company_id=c1["id"], website_id=w1["id"], technology_id=t1["id"])
        _create_intent_signal(client, company_id=c1["id"], website_id=w1["id"], technology_id=t1["id"])
        _create_intent_signal(client, company_id=c2["id"], website_id=w2["id"], technology_id=t2["id"])
        return c1, c2

    def test_unfiltered_returns_all(self, client: TestClient) -> None:
        self._setup(client)
        resp = client.get("/intent-signals", params={"limit": 100, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3
        assert len(body["items"]) >= 3

    def test_filtered_returns_only_company_records(self, client: TestClient) -> None:
        c1, c2 = self._setup(client)
        resp = client.get("/intent-signals", params={"company_id": c1["id"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        for item in body["items"]:
            assert item["company_id"] == c1["id"]

    def test_filtered_total_correct(self, client: TestClient) -> None:
        c1, _ = self._setup(client)
        resp = client.get("/intent-signals", params={"company_id": c1["id"], "limit": 10})
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_nonexistent_company_id_returns_empty(self, client: TestClient) -> None:
        self._setup(client)
        resp = client.get(
            "/intent-signals",
            params={"company_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []

    def test_other_org_company_id_returns_empty(self, client: TestClient, other_org_client: TestClient) -> None:
        c_other = _create_company(other_org_client, domain="other-org-signal.example")
        w_other = _create_website(other_org_client, company_id=c_other["id"])
        t_other = _create_technology(other_org_client, company_id=c_other["id"], website_id=w_other["id"])
        _create_intent_signal(other_org_client, company_id=c_other["id"], website_id=w_other["id"], technology_id=t_other["id"])

        resp = client.get("/intent-signals", params={"company_id": c_other["id"]})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []


# ---------------------------------------------------------------------------
# Intelligence Score company_id filter tests
# ---------------------------------------------------------------------------


class TestIntelligenceScoreCompanyFilter:
    def _setup(self, client: TestClient) -> tuple[dict, dict]:
        c1 = _create_company(client, domain="score-filter-a.example", name="Score Co A")
        c2 = _create_company(client, domain="score-filter-b.example", name="Score Co B")
        w1 = _create_website(client, company_id=c1["id"])
        w2 = _create_website(client, company_id=c2["id"])
        t1 = _create_technology(client, company_id=c1["id"], website_id=w1["id"], name="ScoreTechA")
        t2 = _create_technology(client, company_id=c2["id"], website_id=w2["id"], name="ScoreTechB")
        _create_intelligence_score(client, company_id=c1["id"], technology_id=t1["id"])
        _create_intelligence_score(client, company_id=c1["id"], technology_id=t1["id"])
        _create_intelligence_score(client, company_id=c2["id"], technology_id=t2["id"])
        return c1, c2

    def test_unfiltered_returns_all(self, client: TestClient) -> None:
        self._setup(client)
        resp = client.get("/intelligence-scores", params={"limit": 100, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3

    def test_filtered_returns_only_company_records(self, client: TestClient) -> None:
        c1, c2 = self._setup(client)
        resp = client.get("/intelligence-scores", params={"company_id": c1["id"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        for item in body["items"]:
            assert item["company_id"] == c1["id"]

    def test_filtered_total_correct(self, client: TestClient) -> None:
        c1, _ = self._setup(client)
        resp = client.get("/intelligence-scores", params={"company_id": c1["id"], "limit": 1})
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 1

    def test_pagination_with_filter(self, client: TestClient) -> None:
        c1, _ = self._setup(client)
        page1 = client.get("/intelligence-scores", params={"company_id": c1["id"], "limit": 1, "offset": 0})
        page2 = client.get("/intelligence-scores", params={"company_id": c1["id"], "limit": 1, "offset": 1})
        assert page1.json()["items"][0]["id"] != page2.json()["items"][0]["id"]
        assert page1.json()["total"] == page2.json()["total"]

    def test_nonexistent_company_id_returns_empty(self, client: TestClient) -> None:
        self._setup(client)
        resp = client.get(
            "/intelligence-scores",
            params={"company_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_other_org_company_id_returns_empty(self, client: TestClient, other_org_client: TestClient) -> None:
        c_other = _create_company(other_org_client, domain="other-org-score.example")
        w_other = _create_website(other_org_client, company_id=c_other["id"])
        t_other = _create_technology(other_org_client, company_id=c_other["id"], website_id=w_other["id"])
        _create_intelligence_score(other_org_client, company_id=c_other["id"], technology_id=t_other["id"])

        resp = client.get("/intelligence-scores", params={"company_id": c_other["id"]})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []


# ---------------------------------------------------------------------------
# Outreach Message company_id filter tests
# ---------------------------------------------------------------------------


class TestOutreachMessageCompanyFilter:
    def _setup(self, client: TestClient) -> tuple[dict, dict]:
        c1 = _create_company(client, domain="outreach-filter-a.example", name="Outreach Co A")
        c2 = _create_company(client, domain="outreach-filter-b.example", name="Outreach Co B")
        w1 = _create_website(client, company_id=c1["id"])
        w2 = _create_website(client, company_id=c2["id"])
        t1 = _create_technology(client, company_id=c1["id"], website_id=w1["id"], name="OutTechA")
        t2 = _create_technology(client, company_id=c2["id"], website_id=w2["id"], name="OutTechB")
        s1 = _create_intelligence_score(client, company_id=c1["id"], technology_id=t1["id"])
        s2 = _create_intelligence_score(client, company_id=c2["id"], technology_id=t2["id"])
        _create_outreach_message(client, company_id=c1["id"], intelligence_score_id=s1["id"])
        _create_outreach_message(client, company_id=c1["id"], intelligence_score_id=s1["id"])
        _create_outreach_message(client, company_id=c2["id"], intelligence_score_id=s2["id"])
        return c1, c2

    def test_unfiltered_returns_all(self, client: TestClient) -> None:
        self._setup(client)
        resp = client.get("/outreach-messages", params={"limit": 100, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 3

    def test_filtered_returns_only_company_records(self, client: TestClient) -> None:
        c1, c2 = self._setup(client)
        resp = client.get("/outreach-messages", params={"company_id": c1["id"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 2
        for item in body["items"]:
            assert item["company_id"] == c1["id"]

    def test_filtered_total_correct(self, client: TestClient) -> None:
        c1, _ = self._setup(client)
        resp = client.get("/outreach-messages", params={"company_id": c1["id"], "limit": 1})
        body = resp.json()
        assert body["total"] == 2
        assert len(body["items"]) == 1

    def test_pagination_with_filter(self, client: TestClient) -> None:
        c1, _ = self._setup(client)
        page1 = client.get("/outreach-messages", params={"company_id": c1["id"], "limit": 1, "offset": 0})
        page2 = client.get("/outreach-messages", params={"company_id": c1["id"], "limit": 1, "offset": 1})
        assert page1.json()["items"][0]["id"] != page2.json()["items"][0]["id"]
        assert page1.json()["total"] == page2.json()["total"]

    def test_nonexistent_company_id_returns_empty(self, client: TestClient) -> None:
        self._setup(client)
        resp = client.get(
            "/outreach-messages",
            params={"company_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_other_org_company_id_returns_empty(self, client: TestClient, other_org_client: TestClient) -> None:
        c_other = _create_company(other_org_client, domain="other-org-outreach.example")
        w_other = _create_website(other_org_client, company_id=c_other["id"])
        t_other = _create_technology(other_org_client, company_id=c_other["id"], website_id=w_other["id"])
        s_other = _create_intelligence_score(other_org_client, company_id=c_other["id"], technology_id=t_other["id"])
        _create_outreach_message(other_org_client, company_id=c_other["id"], intelligence_score_id=s_other["id"])

        resp = client.get("/outreach-messages", params={"company_id": c_other["id"]})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["items"] == []


# ---------------------------------------------------------------------------
# Settings helper
# ---------------------------------------------------------------------------


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
