from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, TypeVar, cast

from app.core.errors import IrtiqaError, WorkflowError
from app.models.agent_run import AgentRun
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.technology import Technology
from app.services import (
    AgentRunService,
    CompanyService,
    ContactService,
    IntelligenceScoreService,
    IntentSignalService,
    TechnologyService,
)
from app.workflows.base import Workflow
from app.workflows.context import WorkflowContext
from app.workflows.result import WorkflowResult, WorkflowStepResult
from app.workflows.scoring_policy import (
    DEFAULT_INTENT_LOOKBACK_DAYS,
    DeterministicScoreRefreshPolicy,
    ScoreRefreshInput,
)
from app.workflows.states import WorkflowStatus


SERVICE_AGENT_NAME = "score_refresh_policy"
WORKFLOW_NAME = "score_refresh"

ServiceT = TypeVar("ServiceT")


class ScoreRefreshWorkflow(Workflow):
    name = WORKFLOW_NAME

    def __init__(self, **services: Any) -> None:
        super().__init__(**services)
        self.policy = DeterministicScoreRefreshPolicy()

    def execute(self, context: WorkflowContext) -> WorkflowResult:
        agent_run: AgentRun | None = None
        normalized_company_id: str | None = context.company_id
        normalized_contact_id: str | None = context.contact_id

        try:
            company_service = self._service("company_service", CompanyService)
            contact_service = self._service("contact_service", ContactService)
            technology_service = self._service("technology_service", TechnologyService)
            intent_signal_service = self._service("intent_signal_service", IntentSignalService)
            score_service = self._service("intelligence_score_service", IntelligenceScoreService)
            agent_run_service = self._service("agent_run_service", AgentRunService)

            company, contact = self._load_target(
                context,
                company_service=company_service,
                contact_service=contact_service,
            )
            normalized_company_id = company.id
            normalized_contact_id = contact.id if contact is not None else None
            agent_run = agent_run_service.start_workflow_run(
                agent_name=SERVICE_AGENT_NAME,
                workflow_name=self.name,
                company_id=normalized_company_id,
                contact_id=normalized_contact_id,
                input_summary=self._input_summary(context),
            )
            technologies = technology_service.list_by_company(normalized_company_id)
            intent_signals = self._load_intent_signals(
                intent_signal_service,
                company_id=normalized_company_id,
                contact_id=normalized_contact_id,
            )
            scored_at = datetime.now(timezone.utc)
            policy_result = self.policy.score(
                ScoreRefreshInput(
                    company=company,
                    contact=contact,
                    technologies=technologies,
                    intent_signals=intent_signals,
                    scored_at=scored_at,
                    intent_lookback_days=self._intent_lookback_days(context),
                )
            )
            score = score_service.create(
                company_id=normalized_company_id,
                contact_id=normalized_contact_id,
                technology_id=policy_result.primary_technology_id,
                agent_run_id=agent_run.id,
                fit_score=policy_result.fit_score,
                intent_score=policy_result.intent_score,
                technographic_score=policy_result.technographic_score,
                engagement_score=policy_result.engagement_score,
                total_score=policy_result.total_score,
                confidence=policy_result.confidence,
                score_version=policy_result.score_version,
                rationale=policy_result.rationale,
                scored_at=policy_result.scored_at,
            )
            agent_run_service.mark_succeeded(
                agent_run.id,
                output_summary=f"Created intelligence score {score.id}.",
            )
            return WorkflowResult(
                workflow_name=self.name,
                status=WorkflowStatus.SUCCEEDED,
                company_id=normalized_company_id,
                contact_id=normalized_contact_id,
                agent_run_ids=[agent_run.id],
                output_ids={"intelligence_scores": [score.id]},
                steps=[
                    WorkflowStepResult(
                        step_name="score_refresh.v1",
                        status=WorkflowStatus.SUCCEEDED,
                        agent_run_id=agent_run.id,
                        output_ids={"intelligence_scores": [score.id]},
                    )
                ],
                finished_at=datetime.now(timezone.utc),
            )
        except IrtiqaError as exc:
            self._mark_failed(agent_run, exc)
            raise WorkflowError(
                "Score refresh workflow failed.",
                details={
                    "workflow_name": self.name,
                    "company_id": normalized_company_id,
                    "contact_id": normalized_contact_id,
                    "error_code": exc.code,
                },
                cause=exc,
            ) from exc
        except Exception as exc:
            error = WorkflowError(
                "Unexpected score refresh workflow failure.",
                details={
                    "workflow_name": self.name,
                    "company_id": normalized_company_id,
                    "contact_id": normalized_contact_id,
                },
                cause=exc,
            )
            self._mark_failed(agent_run, error)
            raise error from exc

    def _load_target(
        self,
        context: WorkflowContext,
        *,
        company_service: CompanyService,
        contact_service: ContactService,
    ) -> tuple[Company, Contact | None]:
        if context.contact_id is not None:
            contact = contact_service.get_required(context.contact_id)
            if context.company_id is not None and contact.company_id != context.company_id:
                raise WorkflowError(
                    "Workflow context company_id does not match contact company_id.",
                    details={
                        "workflow_name": self.name,
                        "company_id": context.company_id,
                        "contact_id": context.contact_id,
                        "contact_company_id": contact.company_id,
                    },
                )
            company = company_service.get_required(contact.company_id)
            return company, contact

        if context.company_id is None:
            raise WorkflowError(
                "Score refresh requires company_id or contact_id.",
                details={"workflow_name": self.name},
            )
        return company_service.get_required(context.company_id), None

    def _load_intent_signals(
        self,
        intent_signal_service: IntentSignalService,
        *,
        company_id: str,
        contact_id: str | None,
    ) -> Sequence[IntentSignal]:
        if contact_id is not None:
            return intent_signal_service.list_by_contact(contact_id)
        return intent_signal_service.list_by_company(company_id)

    def _mark_failed(self, agent_run: AgentRun | None, error: IrtiqaError) -> None:
        if agent_run is None:
            return
        try:
            agent_run_service = self._service("agent_run_service", AgentRunService)
            agent_run_service.mark_failed(agent_run.id, error_message=str(error))
        except IrtiqaError:
            return

    def _input_summary(self, context: WorkflowContext) -> str:
        return (
            f"score_refresh requested for company_id={context.company_id}, "
            f"contact_id={context.contact_id}, correlation_id={context.correlation_id}"
        )

    def _intent_lookback_days(self, context: WorkflowContext) -> int:
        raw_value = context.options.get("intent_lookback_days", DEFAULT_INTENT_LOOKBACK_DAYS)
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise WorkflowError(
                "intent_lookback_days workflow option must be an integer.",
                details={"workflow_name": self.name, "intent_lookback_days": raw_value},
            )
        if raw_value < 1 or raw_value > 3650:
            raise WorkflowError(
                "intent_lookback_days workflow option must be between 1 and 3650.",
                details={"workflow_name": self.name, "intent_lookback_days": raw_value},
            )
        return raw_value

    def _service(self, key: str, service_type: type[ServiceT]) -> ServiceT:
        service = self.services.get(key)
        if service is None:
            raise WorkflowError(
                "Workflow service dependency is missing or invalid.",
                details={
                    "workflow_name": self.name,
                    "service": key,
                    "expected_type": service_type.__name__,
                },
            )
        return cast(ServiceT, service)
