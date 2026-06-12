from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, TypeVar, cast

from app.agents.context import AgentContext
from app.agents.deep_scraper import DeepScraperAgent
from app.agents.intelligence_scoring import IntelligenceScoringAgent
from app.agents.intent_signal import IntentSignalAgent
from app.agents.personalization import PersonalizationAgent
from app.agents.result import AGENT_STATUS_SUCCEEDED
from app.agents.technographic import TechnographicAgent
from app.core.errors import IrtiqaError, WorkflowError
from app.core.logging import get_logger
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
from app.workflows.base import Workflow
from app.workflows.context import WorkflowContext
from app.workflows.result import WorkflowResult, WorkflowStepResult
from app.workflows.states import WorkflowStatus


WORKFLOW_NAME = "intelligence_pipeline"

ServiceT = TypeVar("ServiceT")


class IntelligencePipelineWorkflow(Workflow):
    name = WORKFLOW_NAME

    def __init__(self, **services: Any) -> None:
        super().__init__(**services)
        self.logger = get_logger(f"workflows.{self.name}")

    def execute(self, context: WorkflowContext) -> WorkflowResult:
        normalized_company_id: str | None = context.company_id
        normalized_contact_id: str | None = context.contact_id
        step_results: list[WorkflowStepResult] = []
        all_output_ids: dict[str, list[str]] = {}
        all_agent_run_ids: list[str] = []

        try:
            company_service = self._service("company_service", CompanyService)

            # Validate company exists
            if context.company_id is None:
                raise WorkflowError(
                    "Intelligence pipeline requires a company_id.",
                    details={"workflow_name": self.name},
                )
            company_service.get_required(context.company_id)

            # ── Step 1: Deep Scraper Agent ────────────────────────────────
            deep_context = AgentContext(
                agent_name="deep_scraper",
                company_id=normalized_company_id,
                workflow_name=WORKFLOW_NAME,
                options=dict(
                    crawl_depth=context.options.get("crawl_depth", 2),
                    max_pages=context.options.get("max_pages", 50),
                    page_limit=context.options.get("page_limit", 50),
                ),
            )
            scraper = DeepScraperAgent(**self.services)
            scraper_result = self._run_async(scraper.execute(deep_context))
            if scraper_result.status != AGENT_STATUS_SUCCEEDED:
                raise WorkflowError(
                    f"Deep Scraper Agent failed: {scraper_result.summary}",
                    details={"workflow_name": self.name, "agent_run_id": scraper_result.agent_run_id},
                )
            all_output_ids["websites"] = scraper_result.output_ids.get("websites", [])
            if scraper_result.agent_run_id:
                all_agent_run_ids.append(scraper_result.agent_run_id)
            step_results.append(
                WorkflowStepResult(
                    step_name="deep_scraper",
                    status=WorkflowStatus.SUCCEEDED,
                    agent_run_id=scraper_result.agent_run_id,
                    output_ids=scraper_result.output_ids,
                )
            )
            self.logger.info(
                "Pipeline step 1 complete: deep_scraper",
                extra={"websites": len(all_output_ids.get("websites", []))},
            )

            # ── Step 2: Technographic Agent ──────────────────────────────
            tech_context = AgentContext(
                agent_name="technographic",
                company_id=normalized_company_id,
                workflow_name=WORKFLOW_NAME,
                options=dict(context.options),
            )
            technographic = TechnographicAgent(**self.services)
            technographic_result = self._run_async(technographic.execute(tech_context))
            if technographic_result.status != AGENT_STATUS_SUCCEEDED:
                raise WorkflowError(
                    f"Technographic Agent failed: {technographic_result.summary}",
                    details={"workflow_name": self.name, "agent_run_id": technographic_result.agent_run_id},
                )
            all_output_ids["technologies"] = technographic_result.output_ids.get("technologies", [])
            if technographic_result.agent_run_id:
                all_agent_run_ids.append(technographic_result.agent_run_id)
            step_results.append(
                WorkflowStepResult(
                    step_name="technographic",
                    status=WorkflowStatus.SUCCEEDED,
                    agent_run_id=technographic_result.agent_run_id,
                    output_ids=technographic_result.output_ids,
                )
            )
            self.logger.info(
                "Pipeline step 2 complete: technographic",
                extra={"technologies": len(all_output_ids.get("technologies", []))},
            )

            # ── Step 3: Intent Signal Agent ──────────────────────────────
            signal_context = AgentContext(
                agent_name="intent_signal",
                company_id=normalized_company_id,
                workflow_name=WORKFLOW_NAME,
                options=dict(context.options),
            )
            intent_signal = IntentSignalAgent(**self.services)
            signal_result = self._run_async(intent_signal.execute(signal_context))
            if signal_result.status != AGENT_STATUS_SUCCEEDED:
                raise WorkflowError(
                    f"Intent Signal Agent failed: {signal_result.summary}",
                    details={"workflow_name": self.name, "agent_run_id": signal_result.agent_run_id},
                )
            all_output_ids["intent_signals"] = signal_result.output_ids.get("intent_signals", [])
            if signal_result.agent_run_id:
                all_agent_run_ids.append(signal_result.agent_run_id)
            step_results.append(
                WorkflowStepResult(
                    step_name="intent_signal",
                    status=WorkflowStatus.SUCCEEDED,
                    agent_run_id=signal_result.agent_run_id,
                    output_ids=signal_result.output_ids,
                )
            )
            self.logger.info(
                "Pipeline step 3 complete: intent_signal",
                extra={"signals": len(all_output_ids.get("intent_signals", []))},
            )

            # ── Step 4: Intelligence Scoring Agent ───────────────────────
            score_context = AgentContext(
                agent_name="intelligence_scoring_agent",
                company_id=normalized_company_id,
                contact_id=normalized_contact_id,
                workflow_name=WORKFLOW_NAME,
                options=dict(context.options),
            )
            scoring = IntelligenceScoringAgent(**self.services)
            score_result = self._run_async(scoring.execute(score_context))
            if score_result.status != AGENT_STATUS_SUCCEEDED:
                raise WorkflowError(
                    f"Intelligence Scoring Agent failed: {score_result.summary}",
                    details={"workflow_name": self.name, "agent_run_id": score_result.agent_run_id},
                )
            all_output_ids["intelligence_scores"] = score_result.output_ids.get("intelligence_scores", [])
            if score_result.agent_run_id:
                all_agent_run_ids.append(score_result.agent_run_id)
            step_results.append(
                WorkflowStepResult(
                    step_name="intelligence_scoring",
                    status=WorkflowStatus.SUCCEEDED,
                    agent_run_id=score_result.agent_run_id,
                    output_ids=score_result.output_ids,
                )
            )
            self.logger.info(
                "Pipeline step 4 complete: intelligence_scoring",
                extra={"scores": len(all_output_ids.get("intelligence_scores", []))},
            )

            # ── Step 5: Personalization Agent ────────────────────────────
            pers_context = AgentContext(
                agent_name="personalization_agent",
                company_id=normalized_company_id,
                contact_id=normalized_contact_id,
                workflow_name=WORKFLOW_NAME,
                options=dict(context.options),
            )
            personalization = PersonalizationAgent(**self.services)
            pers_result = self._run_async(personalization.execute(pers_context))
            if pers_result.status != AGENT_STATUS_SUCCEEDED:
                raise WorkflowError(
                    f"Personalization Agent failed: {pers_result.summary}",
                    details={"workflow_name": self.name, "agent_run_id": pers_result.agent_run_id},
                )
            all_output_ids["outreach_messages"] = pers_result.output_ids.get("outreach_messages", [])
            if pers_result.agent_run_id:
                all_agent_run_ids.append(pers_result.agent_run_id)
            step_results.append(
                WorkflowStepResult(
                    step_name="personalization",
                    status=WorkflowStatus.SUCCEEDED,
                    agent_run_id=pers_result.agent_run_id,
                    output_ids=pers_result.output_ids,
                )
            )
            self.logger.info(
                "Pipeline step 5 complete: personalization",
                extra={"messages": len(all_output_ids.get("outreach_messages", []))},
            )

            return WorkflowResult(
                workflow_name=WORKFLOW_NAME,
                status=WorkflowStatus.SUCCEEDED,
                company_id=normalized_company_id,
                contact_id=normalized_contact_id,
                agent_run_ids=all_agent_run_ids,
                output_ids=all_output_ids,
                steps=step_results,
                finished_at=datetime.now(timezone.utc),
            )

        except WorkflowError:
            raise
        except IrtiqaError as exc:
            raise WorkflowError(
                "Intelligence pipeline failed.",
                details={
                    "workflow_name": self.name,
                    "company_id": normalized_company_id,
                    "contact_id": normalized_contact_id,
                    "error_code": exc.code,
                },
                cause=exc,
            ) from exc
        except Exception as exc:
            raise WorkflowError(
                "Unexpected intelligence pipeline failure.",
                details={
                    "workflow_name": self.name,
                    "company_id": normalized_company_id,
                    "contact_id": normalized_contact_id,
                },
                cause=exc,
            ) from exc

    @staticmethod
    def _run_async(coro) -> Any:
        """Run a coroutine synchronously.

        When called outside a running event loop (the common production
        path where WorkflowRunner.execute() is called synchronously),
        uses ``asyncio.run()``.

        When called inside a running event loop (e.g. from a
        ``JobRunner`` test that uses ``asyncio.run()``), creates an
        isolated ``asyncio.Runner`` to avoid the nested-loop restriction.
        ``asyncio.Runner`` (Python 3.11+) properly cancels pending tasks
        and shuts down async generators before closing the loop.
        """
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        # Running inside an event loop — use an isolated Runner.
        with asyncio.Runner() as runner:
            return runner.run(coro)

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
