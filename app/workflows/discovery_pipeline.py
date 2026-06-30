from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypeVar, cast

from app.agents.context import AgentContext
from app.agents.discovery.agent import DiscoveryAgent
from app.agents.result import AGENT_STATUS_SUCCEEDED
from app.core.errors import IrtiqaError, WorkflowError
from app.core.logging import get_logger
from app.services import AgentRunService, CompanyService, DiscoveryRunService, DiscoverySearchService
from app.workflows.base import Workflow
from app.workflows.context import WorkflowContext
from app.workflows.result import WorkflowResult, WorkflowStepResult
from app.workflows.states import WorkflowStatus


WORKFLOW_NAME = "discovery_pipeline"
DISCOVERY_AGENT_NAME = "discovery"

ServiceT = TypeVar("ServiceT")


class DiscoveryPipelineWorkflow(Workflow):
    name = WORKFLOW_NAME

    def __init__(self, **services: Any) -> None:
        super().__init__(**services)
        self.logger = get_logger(f"workflows.{self.name}")

    def execute(self, context: WorkflowContext) -> WorkflowResult:
        normalized_company_id = context.company_id
        normalized_contact_id = context.contact_id
        organization_id = self._organization_id(context)
        search_id = self._search_id(context)
        step_results: list[WorkflowStepResult] = []
        all_output_ids: dict[str, list[str]] = {}
        all_agent_run_ids: list[str] = []
        run_id: str | None = None

        try:
            self._service("agent_run_service", AgentRunService)
            search_service = self._service("discovery_search_service", DiscoverySearchService)
            run_service = self._service("discovery_run_service", DiscoveryRunService)
            self._service("company_service", CompanyService)

            search = search_service.get_for_organization(search_id, organization_id=organization_id)

            # Support resuming an existing run (Progress Token pattern)
            existing_run_id = context.options.get("discovery_run_id")
            if existing_run_id and isinstance(existing_run_id, str):
                run = run_service.get_run(existing_run_id, organization_id=organization_id)
                run_id = run.id
            else:
                run = run_service.start_run(organization_id=organization_id, search_id=search.id)
                run_id = run.id

            agent_context = AgentContext(
                agent_name=DISCOVERY_AGENT_NAME,
                company_id=normalized_company_id,
                contact_id=normalized_contact_id,
                organization_id=organization_id,
                workflow_name=WORKFLOW_NAME,
                options={
                    "discovery_search_id": search.id,
                    "discovery_run_id": run.id,
                    "criteria": search.criteria,
                },
            )
            discovery_agent = DiscoveryAgent(**self.services)
            agent_result = self._run_async(discovery_agent.execute(agent_context))

            if agent_result.status != AGENT_STATUS_SUCCEEDED:
                run_service.fail_run(
                    run.id,
                    organization_id=organization_id,
                    error_message=agent_result.summary,
                )
                raise WorkflowError(
                    f"Discovery agent failed: {agent_result.summary}",
                    details={
                        "workflow_name": self.name,
                        "organization_id": organization_id,
                        "search_id": search.id,
                        "run_id": run.id,
                        "agent_run_id": agent_result.agent_run_id,
                    },
                )

            created_company_ids = list(agent_result.output_ids.get("companies", []))
            stats = dict(agent_result.stats)
            sources_queried = self._stat_value(stats, "sources_queried", default=0)
            companies_found = self._stat_value(stats, "companies_found", default=len(created_company_ids))
            companies_created = self._stat_value(stats, "companies_created", default=len(created_company_ids))
            companies_skipped = self._stat_value(stats, "companies_skipped", default=0)

            search = search_service.update_for_organization(
                search.id,
                organization_id=organization_id,
                total_discovered=search.total_discovered + companies_created,
                last_run_at=datetime.now(timezone.utc),
            )

            run_service.complete_run(
                run.id,
                organization_id=organization_id,
                sources_queried=sources_queried,
                companies_found=companies_found,
                companies_created=companies_created,
                companies_skipped=companies_skipped,
            )

            all_output_ids["companies"] = created_company_ids
            all_output_ids["discovery_runs"] = [run.id]
            all_output_ids["discovery_searches"] = [search.id]
            if agent_result.agent_run_id:
                all_agent_run_ids.append(agent_result.agent_run_id)
            step_results.append(
                WorkflowStepResult(
                    step_name="discovery_agent",
                    status=WorkflowStatus.SUCCEEDED,
                    agent_run_id=agent_result.agent_run_id,
                    output_ids=agent_result.output_ids,
                )
            )

            self.logger.info(
                "Discovery pipeline completed",
                extra={
                    "workflow_name": self.name,
                    "organization_id": organization_id,
                    "search_id": search.id,
                    "run_id": run.id,
                    "companies_found": companies_found,
                    "companies_created": companies_created,
                    "companies_skipped": companies_skipped,
                    "sources_queried": sources_queried,
                },
            )

            return WorkflowResult(
                workflow_name=self.name,
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
            self._mark_failed(run_id, organization_id, exc)
            raise WorkflowError(
                "Discovery pipeline failed.",
                details={
                    "workflow_name": self.name,
                    "organization_id": organization_id,
                    "search_id": search_id,
                    "run_id": run_id,
                    "error_code": exc.code,
                },
                cause=exc,
            ) from exc
        except Exception as exc:
            error = WorkflowError(
                "Unexpected discovery pipeline failure.",
                details={
                    "workflow_name": self.name,
                    "organization_id": organization_id,
                    "search_id": search_id,
                    "run_id": run_id,
                },
                cause=exc,
            )
            self._mark_failed(run_id, organization_id, error)
            raise error from exc

    @staticmethod
    def _run_async(coro) -> Any:
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
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

    def _organization_id(self, context: WorkflowContext) -> str:
        if context.organization_id is None:
            raise WorkflowError(
                "Discovery pipeline requires organization_id.",
                details={"workflow_name": self.name},
            )
        return context.organization_id

    def _search_id(self, context: WorkflowContext) -> str:
        search_id = context.options.get("discovery_search_id")
        if not isinstance(search_id, str) or not search_id.strip():
            raise WorkflowError(
                "Discovery pipeline requires discovery_search_id in workflow options.",
                details={"workflow_name": self.name},
            )
        return search_id

    def _mark_failed(self, run_id: str | None, organization_id: str, error: IrtiqaError | WorkflowError) -> None:
        if run_id is None:
            return
        try:
            run_service = self._service("discovery_run_service", DiscoveryRunService)
            run_service.fail_run(run_id, organization_id=organization_id, error_message=str(error))
        except Exception:
            self.logger.warning(
                "Failed to mark discovery run as failed",
                extra={"workflow_name": self.name, "run_id": run_id},
                exc_info=True,
            )

    @staticmethod
    def _stat_value(stats: dict[str, Any], key: str, *, default: int) -> int:
        value = stats.get(key, default)
        if value is None:
            return default
        return int(value)