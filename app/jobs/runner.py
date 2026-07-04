from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any

from app.agents.context import AgentContext
from app.agents.registry import AgentRegistry
from app.core.logging import get_logger
from app.jobs.errors import JobExecutionError, JobSchedulingError
from app.jobs.retry_policy import compute_next_scheduled_at
from app.models.job import Job
from app.services.job_service import JobService
from app.workflows.context import WorkflowContext
from app.workflows.registry import WorkflowRegistry
from app.workflows.runner import WorkflowRunner


class JobRunner:
    def __init__(
        self,
        job_service: JobService,
        agent_registry: AgentRegistry | None = None,
        workflow_registry: WorkflowRegistry | None = None,
        workflow_services: dict[str, Any] | None = None,
        *,
        poll_interval: float = 5.0,
    ) -> None:
        self.job_service = job_service
        self.agent_registry = agent_registry
        self.workflow_registry = workflow_registry
        self.workflow_services = workflow_services or {}
        self.poll_interval = poll_interval
        self.logger = get_logger("jobs.runner")
        self._shutdown = False

    async def start(self) -> None:
        self.logger.info("JobRunner started", extra={"poll_interval": self.poll_interval})

    async def stop(self) -> None:
        self.logger.info("JobRunner stopping...")
        self._shutdown = True

    async def _poll_once(self) -> None:
        jobs = self.job_service.get_next_jobs(limit=10)
        if not jobs:
            return

        for job in jobs:
            if self._shutdown:
                break
            await self._run_job(job)

    async def _run_job(self, job: Job) -> None:
        claimed = self.job_service.claim_job(job.id)
        if claimed is None:
            self.logger.debug(
                "Job was already claimed by another worker",
                extra={"job_id": job.id},
            )
            return

        self.logger.info(
            "Job claimed for execution",
            extra={
                "job_id": job.id,
                "job_type": job.job_type,
                "target_name": job.target_name,
            },
        )

        try:
            payload = json.loads(job.payload)
            if job.job_type == "agent":
                await self._run_agent_job(job, payload)
            elif job.job_type == "workflow":
                await self._run_workflow_job(job, payload)
            else:
                raise JobSchedulingError(
                    f"Unknown job type: {job.job_type}",
                    details={"job_id": job.id, "job_type": job.job_type},
                )
        except Exception as exc:
            self.logger.error(
                "Job execution failed",
                extra={
                    "job_id": job.id,
                    "job_type": job.job_type,
                    "target_name": job.target_name,
                    "error": str(exc),
                },
                exc_info=True,
            )
            await self._handle_job_failure(job, exc)

    async def _run_agent_job(self, job: Job, payload: dict[str, Any]) -> None:
        if self.agent_registry is None:
            raise JobSchedulingError(
                "AgentRegistry not configured",
                details={"job_id": job.id, "target_name": job.target_name},
            )

        agent_cls = self.agent_registry.get(job.target_name)
        agent = agent_cls()

        context = AgentContext(
            agent_name=job.target_name,
            company_id=payload["company_id"],
            contact_id=payload.get("contact_id"),
            organization_id=payload.get("organization_id"),
            workflow_name=payload.get("workflow_name"),
            correlation_id=payload.get("correlation_id"),
            options=payload.get("options", {}),
        )

        result = await agent.execute(context)

        if result.agent_run_id:
            self.job_service.update(
                job.id,
                status="succeeded",
                completed_at=datetime.now(timezone.utc),
                agent_run_id=result.agent_run_id,
            )
        else:
            self.job_service.update(
                job.id,
                status="succeeded",
                completed_at=datetime.now(timezone.utc),
            )

        self.logger.info(
            "Agent job completed successfully",
            extra={
                "job_id": job.id,
                "agent_run_id": result.agent_run_id,
                "output_ids": result.output_ids,
            },
        )

    async def _run_workflow_job(self, job: Job, payload: dict[str, Any]) -> None:
        if self.workflow_registry is None:
            raise JobSchedulingError(
                "WorkflowRegistry not configured",
                details={"job_id": job.id, "target_name": job.target_name},
            )

        runner = WorkflowRunner(self.workflow_registry, **self.workflow_services)

        context = WorkflowContext(
            workflow_name=job.target_name,
            company_id=payload.get("company_id"),
            contact_id=payload.get("contact_id"),
            organization_id=payload.get("organization_id"),
            correlation_id=payload.get("correlation_id"),
            requested_by=payload.get("requested_by"),
            options=payload.get("options", {}),
        )

        result = await runner.run(context)

        from app.workflows.states import WorkflowStatus as WfStatus

        if result.status == WfStatus.FAILED:
            error_message = str(result.error) if result.error else "Workflow returned failed status"
            self.job_service.update(
                job.id,
                status="failed",
                completed_at=datetime.now(timezone.utc),
                last_error=error_message,
            )
            self.logger.error(
                "Workflow job failed",
                extra={
                    "job_id": job.id,
                    "workflow_name": job.target_name,
                    "error": error_message,
                },
            )
            return

        # Use the first agent_run_id from the workflow result.
        # WorkflowResult stores multiple agent_run_ids; the job FK stores one.
        primary_agent_run_id = result.agent_run_ids[0] if result.agent_run_ids else None
        if primary_agent_run_id:
            self.job_service.update(
                job.id,
                status="succeeded",
                completed_at=datetime.now(timezone.utc),
                agent_run_id=primary_agent_run_id,
            )
        else:
            self.job_service.update(
                job.id,
                status="succeeded",
                completed_at=datetime.now(timezone.utc),
            )

        self.logger.info(
            "Workflow job completed successfully",
            extra={
                "job_id": job.id,
                "workflow_name": job.target_name,
                "output_ids": result.output_ids,
                "status": result.status.value,
            },
        )

    async def _handle_job_failure(self, job: Job, exc: Exception) -> None:
        error_details = {
            "job_id": job.id,
            "job_type": job.job_type,
            "target_name": job.target_name,
            "exception_type": type(exc).__name__,
        }
        if hasattr(exc, "details"):
            error_details.update(exc.details)

        error_message = str(exc)

        if job.retry_count < job.max_retries:
            next_scheduled = compute_next_scheduled_at(job.retry_count)
            self.job_service.update(
                job.id,
                status="pending",
                retry_count=job.retry_count + 1,
                scheduled_at=next_scheduled,
                last_error=error_message,
            )
            self.logger.warning(
                "Job failed, scheduled for retry",
                extra={
                    **error_details,
                    "retry_count": job.retry_count + 1,
                    "max_retries": job.max_retries,
                    "next_scheduled_at": next_scheduled.isoformat(),
                },
            )
        else:
            self.job_service.update(
                job.id,
                status="failed",
                completed_at=datetime.now(timezone.utc),
                last_error=error_message,
            )
            self.logger.error(
                "Job failed permanently, max retries exhausted",
                extra={
                    **error_details,
                    "retry_count": job.retry_count,
                    "max_retries": job.max_retries,
                },
            )