from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from app.core.errors import WorkflowError
from app.models.agent_run import AgentRun
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.intelligence_score import IntelligenceScore
from app.models.technology import Technology
from app.workflows.context import WorkflowContext
from app.workflows.score_refresh import ScoreRefreshWorkflow
from app.workflows.states import WorkflowStatus


COMPANY_ID = "00000000-0000-0000-0000-000000000001"
CONTACT_ID = "00000000-0000-0000-0000-000000000002"
AGENT_RUN_ID = "00000000-0000-0000-0000-000000000003"
SCORE_ID = "00000000-0000-0000-0000-000000000004"
TECHNOLOGY_ID = "00000000-0000-0000-0000-000000000005"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CompanyServiceDouble:
    def __init__(self, company: Company) -> None:
        self.company = company

    def get_required(self, entity_id: str) -> Company:
        if entity_id != self.company.id:
            raise WorkflowError("Company not found.", details={"entity_id": entity_id})
        return self.company


class ContactServiceDouble:
    def __init__(self, contact: Contact | None = None) -> None:
        self.contact = contact

    def get_required(self, entity_id: str) -> Contact:
        if self.contact is None or entity_id != self.contact.id:
            raise WorkflowError("Contact not found.", details={"entity_id": entity_id})
        return self.contact


class TechnologyServiceDouble:
    def __init__(self, technologies: list[Technology]) -> None:
        self.technologies = technologies

    def list_by_company(self, company_id: str) -> list[Technology]:
        return [technology for technology in self.technologies if technology.company_id == company_id]


class IntentSignalServiceDouble:
    def __init__(self, intent_signals: list[IntentSignal]) -> None:
        self.intent_signals = intent_signals

    def list_by_company(self, company_id: str) -> list[IntentSignal]:
        return [signal for signal in self.intent_signals if signal.company_id == company_id]

    def list_by_contact(self, contact_id: str) -> list[IntentSignal]:
        return [signal for signal in self.intent_signals if signal.contact_id == contact_id]


class IntelligenceScoreServiceDouble:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    def create(self, **values: Any) -> IntelligenceScore:
        self.created.append(values)
        return IntelligenceScore(id=SCORE_ID, **values)


class AgentRunServiceDouble:
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []
        self.succeeded: list[tuple[str, str | None]] = []
        self.failed: list[tuple[str, str]] = []

    def start_workflow_run(self, **values: Any) -> AgentRun:
        self.started.append(values)
        return AgentRun(
            id=AGENT_RUN_ID,
            status="running",
            started_at=utc_now(),
            **values,
        )

    def mark_succeeded(self, agent_run_id: str, *, output_summary: str | None = None) -> AgentRun:
        self.succeeded.append((agent_run_id, output_summary))
        return AgentRun(
            id=agent_run_id,
            agent_name="score_refresh_policy",
            workflow_name="score_refresh",
            status="succeeded",
            output_summary=output_summary,
            started_at=utc_now(),
            finished_at=utc_now(),
        )

    def mark_failed(self, agent_run_id: str, *, error_message: str) -> AgentRun:
        self.failed.append((agent_run_id, error_message))
        return AgentRun(
            id=agent_run_id,
            agent_name="score_refresh_policy",
            workflow_name="score_refresh",
            status="failed",
            error_message=error_message,
            started_at=utc_now(),
            finished_at=utc_now(),
        )


def make_company() -> Company:
    return Company(
        id=COMPANY_ID,
        name="Irtiqa Workflow Company",
        domain="workflow.example",
        industry="software",
        company_size="11-50",
        status="active",
    )


def make_contact(company: Company) -> Contact:
    return Contact(
        id=CONTACT_ID,
        company_id=company.id,
        full_name="Asha Rao",
        email="asha.rao@workflow.example",
        title="VP Revenue",
        department="sales",
        seniority="vp",
        status="active",
    )


def make_technology(company: Company) -> Technology:
    now = utc_now()
    return Technology(
        id=TECHNOLOGY_ID,
        company_id=company.id,
        name="HubSpot",
        category="crm",
        detection_method="html_signature",
        confidence=0.92,
        first_detected_at=now,
        last_detected_at=now,
    )


def make_signal(company: Company, contact: Contact) -> IntentSignal:
    return IntentSignal(
        company_id=company.id,
        contact_id=contact.id,
        signal_type="technology_change",
        signal_name="CRM detected",
        strength=0.75,
        confidence=0.88,
        observed_at=utc_now(),
    )


def make_workflow(**overrides: Any) -> tuple[ScoreRefreshWorkflow, AgentRunServiceDouble, IntelligenceScoreServiceDouble]:
    company = make_company()
    contact = make_contact(company)
    agent_run_service = AgentRunServiceDouble()
    score_service = IntelligenceScoreServiceDouble()
    services: dict[str, Any] = {
        "company_service": CompanyServiceDouble(company),
        "contact_service": ContactServiceDouble(contact),
        "technology_service": TechnologyServiceDouble([make_technology(company)]),
        "intent_signal_service": IntentSignalServiceDouble([make_signal(company, contact)]),
        "intelligence_score_service": score_service,
        "agent_run_service": agent_run_service,
    }
    services.update(overrides)
    return ScoreRefreshWorkflow(**services), agent_run_service, score_service


def test_score_refresh_workflow_creates_append_only_score_and_result_ids() -> None:
    workflow, agent_run_service, score_service = make_workflow()
    context = WorkflowContext(workflow_name="score_refresh", company_id=COMPANY_ID, contact_id=CONTACT_ID)

    result = workflow.execute(context)

    assert result.status == WorkflowStatus.SUCCEEDED
    assert result.company_id == COMPANY_ID
    assert result.contact_id == CONTACT_ID
    assert result.agent_run_ids == [AGENT_RUN_ID]
    assert result.output_ids == {"intelligence_scores": [SCORE_ID]}
    assert result.steps[0].step_name == "score_refresh.v1"
    assert result.steps[0].output_ids == {"intelligence_scores": [SCORE_ID]}
    assert agent_run_service.started[0]["agent_name"] == "score_refresh_policy"
    assert agent_run_service.started[0]["workflow_name"] == "score_refresh"
    assert agent_run_service.succeeded[0][0] == AGENT_RUN_ID
    assert score_service.created[0]["score_version"] == "score_refresh.v1"
    assert score_service.created[0]["agent_run_id"] == AGENT_RUN_ID
    assert score_service.created[0]["technology_id"] == TECHNOLOGY_ID


def test_score_refresh_workflow_can_score_company_only_target() -> None:
    workflow, _, score_service = make_workflow()
    context = WorkflowContext(workflow_name="score_refresh", company_id=COMPANY_ID)

    result = workflow.execute(context)

    assert result.status == WorkflowStatus.SUCCEEDED
    assert result.company_id == COMPANY_ID
    assert result.contact_id is None
    assert score_service.created[0]["contact_id"] is None


def test_score_refresh_workflow_marks_agent_run_failed_for_scoring_error() -> None:
    workflow, agent_run_service, _ = make_workflow(
        technology_service=TechnologyServiceDouble([]),
        intent_signal_service=IntentSignalServiceDouble([]),
    )
    context = WorkflowContext(
        workflow_name="score_refresh",
        company_id=COMPANY_ID,
        options={"intent_lookback_days": "invalid"},
    )

    with pytest.raises(WorkflowError) as exc:
        workflow.execute(context)

    assert exc.value.code == "irtiqa.workflow_error"
    assert agent_run_service.failed[0][0] == AGENT_RUN_ID
    assert "intent_lookback_days" in agent_run_service.failed[0][1]


def test_score_refresh_workflow_rejects_mismatched_company_and_contact() -> None:
    workflow, agent_run_service, _ = make_workflow()
    context = WorkflowContext(
        workflow_name="score_refresh",
        company_id="00000000-0000-0000-0000-000000000999",
        contact_id=CONTACT_ID,
    )

    with pytest.raises(WorkflowError) as exc:
        workflow.execute(context)

    assert exc.value.details["workflow_name"] == "score_refresh"
    assert agent_run_service.failed == []
