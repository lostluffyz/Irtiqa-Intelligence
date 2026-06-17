from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.agents.result import AGENT_STATUS_SUCCEEDED, AgentResult
from app.api.dependencies import get_current_organization
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
