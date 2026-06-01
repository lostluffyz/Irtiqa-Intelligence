from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import session as database_session
from app.models.agent_run import AgentRun
from app.models.intelligence_score import IntelligenceScore
from app.services import (
    AgentRunService,
    CompanyService,
    ContactService,
    IntelligenceScoreService,
    IntentSignalService,
    TechnologyService,
)
from app.workflows.context import WorkflowContext
from app.workflows.registry import WorkflowRegistry
from app.workflows.runner import WorkflowRunner
from app.workflows.score_refresh import ScoreRefreshWorkflow
from app.workflows.states import WorkflowStatus


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
def service_database(service_session_factory: sessionmaker[Session]) -> Iterator[sessionmaker[Session]]:
    yield service_session_factory


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_score_refresh_workflow_persists_score_and_agent_run(
    service_database: sessionmaker[Session],
) -> None:
    company_service = CompanyService()
    contact_service = ContactService()
    technology_service = TechnologyService()
    intent_signal_service = IntentSignalService()
    score_service = IntelligenceScoreService()
    agent_run_service = AgentRunService()

    company = company_service.create(
        name="Irtiqa Score Refresh Company",
        domain="score-refresh.example",
        industry="software",
        company_size="51-200",
        headquarters="Bengaluru, India",
        description="Revenue intelligence workflows.",
        linkedin_url="https://linkedin.com/company/score-refresh",
        status="active",
    )
    contact = contact_service.create(
        company_id=company.id,
        full_name="Asha Rao",
        email="asha.rao@score-refresh.example",
        title="VP Revenue",
        department="sales",
        seniority="vp",
        linkedin_url="https://linkedin.com/in/asha-score-refresh",
        status="active",
    )
    technology = technology_service.create(
        company_id=company.id,
        name="HubSpot",
        category="crm",
        detection_method="html_signature",
        confidence=0.92,
        first_detected_at=utc_now(),
        last_detected_at=utc_now(),
    )
    intent_signal_service.create(
        company_id=company.id,
        contact_id=contact.id,
        technology_id=technology.id,
        signal_type="technology_change",
        signal_name="CRM detected",
        signal_value="HubSpot detected on homepage",
        strength=0.75,
        confidence=0.88,
        source_url="https://score-refresh.example",
        observed_at=utc_now(),
    )
    registry = WorkflowRegistry()
    registry.register(ScoreRefreshWorkflow)
    runner = WorkflowRunner(
        registry,
        company_service=company_service,
        contact_service=contact_service,
        technology_service=technology_service,
        intent_signal_service=intent_signal_service,
        intelligence_score_service=score_service,
        agent_run_service=agent_run_service,
    )

    first_result = runner.run(
        WorkflowContext(
            workflow_name="score_refresh",
            company_id=company.id,
            contact_id=contact.id,
        )
    )
    second_result = runner.run(
        WorkflowContext(
            workflow_name="score_refresh",
            company_id=company.id,
            contact_id=contact.id,
        )
    )

    assert first_result.status == WorkflowStatus.SUCCEEDED
    assert second_result.status == WorkflowStatus.SUCCEEDED
    assert first_result.output_ids["intelligence_scores"] != second_result.output_ids["intelligence_scores"]

    with service_database() as session:
        scores = session.query(IntelligenceScore).order_by(IntelligenceScore.scored_at).all()
        agent_runs = session.query(AgentRun).order_by(AgentRun.started_at).all()

    assert len(scores) == 2
    assert {score.score_version for score in scores} == {"score_refresh.v1"}
    assert all(score.company_id == company.id for score in scores)
    assert all(score.contact_id == contact.id for score in scores)
    assert all(score.agent_run_id is not None for score in scores)
    assert len(agent_runs) == 2
    assert {run.agent_name for run in agent_runs} == {"score_refresh_policy"}
    assert {run.workflow_name for run in agent_runs} == {"score_refresh"}
    assert {run.status for run in agent_runs} == {"succeeded"}
    assert all(run.finished_at is not None for run in agent_runs)


def test_score_refresh_workflow_returns_structured_failure_for_missing_target(
    service_database: sessionmaker[Session],
) -> None:
    registry = WorkflowRegistry()
    registry.register(ScoreRefreshWorkflow)
    runner = WorkflowRunner(
        registry,
        company_service=CompanyService(),
        contact_service=ContactService(),
        technology_service=TechnologyService(),
        intent_signal_service=IntentSignalService(),
        intelligence_score_service=IntelligenceScoreService(),
        agent_run_service=AgentRunService(),
    )

    result = runner.run(
        WorkflowContext(
            workflow_name="score_refresh",
            company_id="00000000-0000-0000-0000-000000000000",
        )
    )

    assert result.status == WorkflowStatus.FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.workflow_error"
    assert result.error["details"]["workflow_name"] == "score_refresh"
