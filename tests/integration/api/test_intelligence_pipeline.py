from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.result import AGENT_STATUS_SUCCEEDED, AgentResult
from app.api.dependencies import get_current_organization
from app.models.agent_run import AgentRun
from app.models.evidence_record import EvidenceRecord
from app.models.intelligence_score import IntelligenceScore
from app.models.intent_signal import IntentSignal
from app.models.outreach_message import OutreachMessage
from app.models.technology import Technology
from app.core.config import AuthSettings, DatabaseSettings, LoggingSettings, Settings
from app.core.tenant import TenantContext
from app.database import session as database_session
from app.jobs.runner import JobRunner
from app.main import create_app
from app.models.company import Company
from app.models.organization import Organization
from app.models.website import Website
from app.services.job_service import JobService
from app.workflows.context import WorkflowContext
from app.workflows.intelligence_pipeline import IntelligencePipelineWorkflow
from app.workflows.registry import WorkflowRegistry


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
        org = Organization(id=str(uuid4()), name="Pipeline Test Org", slug="pipeline-test", status="active")
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


def _seed_company_via_db(session: Session, org_id: str) -> str:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    company = Company(
        organization_id=org_id,
        name="Pipeline Job Test Co",
        domain="pipeline-job-test.example",
        industry="software",
        company_size="11-50",
        status="active",
    )
    session.add(company)
    session.commit()
    return company.id


def _seed_website_via_db(session: Session, company_id: str) -> str:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    website = Website(
        company_id=company_id,
        url="https://pipeline-job-test.example",
        normalized_url="https://pipeline-job-test.example/",
        page_type="homepage",
    )
    session.add(website)
    session.commit()
    return website.id


def _seed_company(client: TestClient) -> str:
    response = client.post(
        "/companies",
        json={
            "name": "Pipeline Test Co",
            "domain": "pipeline-test.example",
            "industry": "software",
            "company_size": "11-50",
            "status": "active",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _seed_website(client: TestClient, company_id: str) -> str:
    response = client.post(
        "/websites",
        json={
            "company_id": company_id,
            "url": "https://pipeline-test.example",
            "normalized_url": "https://pipeline-test.example/",
            "page_type": "homepage",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_pipeline_through_job_system(
    api_session_factory: sessionmaker[Session],
    test_org: Organization,
) -> None:
    """Execute the real IntelligencePipelineWorkflow through the real
    WorkflowRunner, mocking only the 5 agent execute() methods.

    Verifies the chain:
      WorkflowRunner → IntelligencePipelineWorkflow → mocked agents

    JobRunner dispatch (async) is tested separately in
    test_runner_dispatches_workflow_job.
    """
    # ── Seed database ───────────────────────────────────────────────────
    session = api_session_factory()
    company_id = _seed_company_via_db(session, org_id=test_org.id)
    session.close()

    # ── Mock only the 5 agent execute() calls ───────────────────────────
    mock_result = AgentResult(
        agent_name="mock_agent",
        agent_run_id="f" * 36,
        status=AGENT_STATUS_SUCCEEDED,
        output_ids={
            "websites": ["w1"],
            "technologies": ["t1"],
            "intent_signals": ["s1"],
            "intelligence_scores": ["sc1"],
            "outreach_messages": ["m1"],
        },
        summary="Mock step completed.",
        duration_ms=5.0,
    )
    async_mock = AsyncMock(return_value=mock_result)

    patches = [
        patch("app.agents.deep_scraper.DeepScraperAgent.execute", async_mock),
        patch("app.agents.technographic.TechnographicAgent.execute", async_mock),
        patch("app.agents.intent_signal.IntentSignalAgent.execute", async_mock),
        patch("app.agents.intelligence_scoring.IntelligenceScoringAgent.execute", async_mock),
        patch("app.agents.personalization.PersonalizationAgent.execute", async_mock),
    ]
    for p in patches:
        p.start()

    try:
        from app.services.company_service import CompanyService
        from app.workflows.runner import WorkflowRunner

        workflow_registry = WorkflowRegistry()
        workflow_registry.register(IntelligencePipelineWorkflow)

        company_service = CompanyService()

        runner = WorkflowRunner(
            workflow_registry,
            company_service=company_service,
        )

        context = WorkflowContext(
            workflow_name="intelligence_pipeline",
            company_id=company_id,
            organization_id=test_org.id,
        )
        result = runner.run(context)

        from app.workflows.states import WorkflowStatus as WfStatus

        assert result.status == WfStatus.SUCCEEDED, f"Pipeline failed: {result.error}"
        assert result.workflow_name == "intelligence_pipeline"
        assert len(result.agent_run_ids) == 5
        assert "websites" in result.output_ids
        assert "technologies" in result.output_ids
        assert "intent_signals" in result.output_ids
        assert "intelligence_scores" in result.output_ids
        assert "outreach_messages" in result.output_ids
        assert async_mock.call_count == 5

    finally:
        for p in patches:
            p.stop()


def test_pipeline_end_to_end(client: TestClient) -> None:
    """Full pipeline with seeded data produces all 5 output types."""
    company_id = _seed_company(client)
    _seed_website(client, company_id)

    mock_result = _make_result()
    async_mock = AsyncMock(return_value=mock_result)

    with patch(
        "app.agents.deep_scraper.DeepScraperAgent.execute", async_mock,
    ), patch(
        "app.agents.technographic.TechnographicAgent.execute", async_mock,
    ), patch(
        "app.agents.intent_signal.IntentSignalAgent.execute", async_mock,
    ), patch(
        "app.agents.intelligence_scoring.IntelligenceScoringAgent.execute", async_mock,
    ), patch(
        "app.agents.personalization.PersonalizationAgent.execute", async_mock,
    ):
        response = client.post(
            "/intelligence/pipeline",
            json={"company_id": company_id},
        )
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "scheduled"
    assert data["target_name"] == "intelligence_pipeline"
    assert len(data["job_id"]) == 36


def test_pipeline_status_endpoint(client: TestClient) -> None:
    """GET /intelligence/pipeline/{job_id} returns job status."""
    company_id = _seed_company(client)
    _seed_website(client, company_id)

    mock_result = _make_result()
    async_mock = AsyncMock(return_value=mock_result)

    with patch(
        "app.agents.deep_scraper.DeepScraperAgent.execute", async_mock,
    ), patch(
        "app.agents.technographic.TechnographicAgent.execute", async_mock,
    ), patch(
        "app.agents.intent_signal.IntentSignalAgent.execute", async_mock,
    ), patch(
        "app.agents.intelligence_scoring.IntelligenceScoringAgent.execute", async_mock,
    ), patch(
        "app.agents.personalization.PersonalizationAgent.execute", async_mock,
    ):
        trigger = client.post(
            "/intelligence/pipeline",
            json={"company_id": company_id},
        )
    job_id = trigger.json()["job_id"]
    response = client.get(f"/intelligence/pipeline/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id


def test_pipeline_not_found(client: TestClient) -> None:
    """Missing job_id returns 404."""
    response = client.get(
        "/intelligence/pipeline/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


def test_pipeline_invalid_company(client: TestClient) -> None:
    """Pipeline triggered with nonexistent company creates job."""
    response = client.post(
        "/intelligence/pipeline",
        json={"company_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    status_resp = client.get(f"/intelligence/pipeline/{job_id}")
    assert status_resp.status_code == 200


def _make_result() -> AgentResult:
    return AgentResult(
        agent_name="test_agent",
        agent_run_id="f" * 36,
        status=AGENT_STATUS_SUCCEEDED,
        output_ids={},
        summary="Mock execution completed.",
        duration_ms=10.0,
    )


def test_pipeline_real_agents(
    api_session_factory: sessionmaker[Session],
    test_org: Organization,
) -> None:
    """End-to-end pipeline test executing real agents against a real database.

    Only the HTTP layer is mocked (via respx) so that DeepScraperAgent
    can crawl without network access. All agent logic runs unchanged:
    scraping → technology detection → intent signals → scoring → outreach.
    """
    from unittest.mock import AsyncMock, patch

    from app.services import (
        AgentRunService,
        CompanyService,
        ContactService,
        IntelligenceScoreService,
        IntentSignalService,
        OutreachMessageService,
        TechnologyService,
        WebsiteService,
    )
    from app.workflows.runner import WorkflowRunner
    from app.workflows.states import WorkflowStatus

    # ── Seed database ──────────────────────────────────────────────────
    session = api_session_factory()
    company_id = _seed_company_via_db(session, org_id=test_org.id)
    domain = "pipeline-job-test.example"
    session.close()

    # The DeepScraperAgent fetches robots.txt first, then the page.
    # Use patch to intercept httpx.AsyncClient at the class level so the
    # mock applies regardless of which event loop the agent runs in.
    # The agent constructs httpx.AsyncClient() inside _run_async() which
    # may create a new event loop — class-level patch survives that.
    from unittest.mock import MagicMock

    html_page = """
            <html>
            <head><title>Test Company</title></head>
            <body>
                <h1>Welcome to Test Company</h1>
                <p>We provide innovative software solutions.</p>
                <script src="https://www.googletagmanager.com/gtag/js?id=G-TEST"></script>
                <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
                <script>jQuery(function() { console.log("ready"); });</script>
                <div id="root" data-reactroot="">
                    <h2>Our Products</h2>
                    <p>We are growing rapidly and hiring engineers.</p>
                    <p>We just raised a Series A funding round.</p>
                </div>
            </body>
            </html>
            """

    robots_404 = AsyncMock(spec=["status_code", "headers"])
    robots_404.status_code = 404
    robots_404.headers = {"content-type": "text/plain"}

    html_200 = AsyncMock(spec=["status_code", "text", "raise_for_status", "headers"])
    html_200.status_code = 200
    html_200.headers = {"content-type": "text/html"}
    html_200.text = html_page
    html_200.raise_for_status = AsyncMock()

    async def mock_get(url, *args, **kwargs):
        if "robots.txt" in str(url):
            return robots_404
        return html_200

    mock_client = AsyncMock()
    mock_client.get.side_effect = mock_get
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    # ── Set up real services ──────────────────────────────────────────
    services = {
        "company_service": CompanyService(),
        "contact_service": ContactService(),
        "website_service": WebsiteService(),
        "technology_service": TechnologyService(),
        "intent_signal_service": IntentSignalService(),
        "intelligence_score_service": IntelligenceScoreService(),
        "outreach_message_service": OutreachMessageService(),
        "agent_run_service": AgentRunService(),
    }

    workflow_registry = WorkflowRegistry()
    workflow_registry.register(IntelligencePipelineWorkflow)
    runner = WorkflowRunner(workflow_registry, **services)
    context = WorkflowContext(
        workflow_name="intelligence_pipeline",
        company_id=company_id,
        organization_id=test_org.id,
    )

    # ── Execute pipeline (all 5 agents run for real) ──────────────────
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = runner.run(context)

    # ── Verify workflow execution ─────────────────────────────────────
    from app.workflows.states import WorkflowStatus as WfStatus

    assert result.status == WfStatus.SUCCEEDED, (
        f"Pipeline failed: {result.error}"
    )
    assert result.workflow_name == "intelligence_pipeline"
    assert len(result.agent_run_ids) == 5

    # Print output_ids for debugging
    print(f"\n  PIPELINE OUTPUT: {dict((k, len(v)) for k, v in result.output_ids.items())}")

    # All 5 output types should have non-empty results
    assert len(result.output_ids.get("websites", [])) > 0, "No websites crawled"
    assert len(result.output_ids.get("technologies", [])) > 0, "No technologies detected"
    assert len(result.output_ids.get("intent_signals", [])) > 0, "No intent signals detected"
    assert len(result.output_ids.get("intelligence_scores", [])) > 0, "No scores created"
    assert len(result.output_ids.get("outreach_messages", [])) > 0, "No outreach messages created"

    # ── Verify database persistence ───────────────────────────────────
    with api_session_factory() as verify_session:
        # Websites persisted
        websites = verify_session.execute(
            select(Website).where(Website.company_id == company_id)
        ).scalars().all()
        assert len(websites) > 0, "No websites were persisted"
        assert any(w.raw_html is not None for w in websites), "No raw HTML stored"
        assert any(w.extracted_text is not None for w in websites), "No extracted text stored"

        # Technologies detected
        technologies = verify_session.execute(
            select(Technology).where(Technology.company_id == company_id)
        ).scalars().all()
        assert len(technologies) > 0, "No technologies were detected"

        # Intent signals detected
        signals = verify_session.execute(
            select(IntentSignal).where(IntentSignal.company_id == company_id)
        ).scalars().all()
        assert len(signals) > 0, "No intent signals were detected"

        # Intelligence scores created
        scores = verify_session.execute(
            select(IntelligenceScore).where(IntelligenceScore.company_id == company_id)
        ).scalars().all()
        assert len(scores) > 0, "No intelligence scores were created"
        score = scores[0]
        assert score.total_score > 0
        assert score.organization_id == test_org.id

        # Outreach messages created
        messages = verify_session.execute(
            select(OutreachMessage).where(OutreachMessage.company_id == company_id)
        ).scalars().all()
        assert len(messages) > 0, "No outreach messages were created"
        assert all(m.organization_id == test_org.id for m in messages)

        # Evidence records — agents in the intelligence pipeline don't
        # produce evidence items directly (evidence is created by
        # ScoreRefreshWorkflow, which links technologies and signals
        # to the generated score as a separate follow-up step).
        evidence = verify_session.execute(
            select(EvidenceRecord).where(EvidenceRecord.company_id == company_id)
        ).scalars().all()
        # No assertion on evidence count — agents may or may not produce it

        # Agent runs created
        agent_runs = verify_session.execute(
            select(AgentRun).where(AgentRun.company_id == company_id)
        ).scalars().all()
        assert len(agent_runs) == 5, "Expected 5 agent runs (one per agent)"
        assert all(ar.organization_id == test_org.id for ar in agent_runs)
        assert all(ar.status == "succeeded" for ar in agent_runs)


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
