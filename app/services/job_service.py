from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import EntityNotFoundError, ServiceError, ValidationError
from app.models.job import Job
from app.repositories.job_repository import JobRepository
from app.services.base import BaseService

if TYPE_CHECKING:
    from app.agents.context import AgentContext
    from app.workflows.context import WorkflowContext


class JobService(BaseService[Job, JobRepository]):
    model = Job
    repository = JobRepository

    def schedule_agent(
        self,
        name: str,
        context: AgentContext,
        *,
        scheduled_at: datetime | None = None,
        max_retries: int = 3,
    ) -> Job:
        if max_retries < 0:
            raise ValidationError("max_retries must be >= 0", details={"max_retries": max_retries})

        payload = {
            "company_id": context.company_id,
            "contact_id": context.contact_id,
            "organization_id": context.organization_id,
            "workflow_name": context.workflow_name,
            "correlation_id": context.correlation_id,
            "options": dict(context.options),
        }

        now = datetime.now(timezone.utc)
        effective_scheduled_at = scheduled_at or now

        return self.create(
            organization_id=context.organization_id,
            job_type="agent",
            target_name=name,
            payload=json.dumps(payload),
            status="pending",
            scheduled_at=effective_scheduled_at,
            max_retries=max_retries,
            retry_count=0,
            created_at=now,
            updated_at=now,
        )

    def schedule_workflow(
        self,
        name: str,
        context: WorkflowContext,
        *,
        scheduled_at: datetime | None = None,
        max_retries: int = 3,
    ) -> Job:
        if max_retries < 0:
            raise ValidationError("max_retries must be >= 0", details={"max_retries": max_retries})

        payload = {
            "company_id": context.company_id,
            "contact_id": context.contact_id,
            "organization_id": context.organization_id,
            "correlation_id": context.correlation_id,
            "requested_by": context.requested_by,
            "options": dict(context.options),
        }

        now = datetime.now(timezone.utc)
        effective_scheduled_at = scheduled_at or now

        return self.create(
            organization_id=context.organization_id,
            job_type="workflow",
            target_name=name,
            payload=json.dumps(payload),
            status="pending",
            scheduled_at=effective_scheduled_at,
            max_retries=max_retries,
            retry_count=0,
            created_at=now,
            updated_at=now,
        )

    def list_jobs(
        self,
        *,
        organization_id: str,
        status: str | None = None,
        target_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Job]:
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[Job]:
            repository = self._repository(session)
            statement = select(repository.model)

            statement = repository._apply_tenant_filter(statement, organization_id)

            if status:
                statement = statement.where(repository.model.status == status)
            if target_name:
                statement = statement.where(repository.model.target_name == target_name)

            statement = statement.order_by(repository.model.scheduled_at.desc()).offset(offset).limit(limit)
            return session.execute(statement).scalars().all()

        return self._run_in_transaction("list_jobs", operation)

    def cancel_job(self, job_id: str, *, organization_id: str) -> Job:
        self._validate_identifier(job_id, field_name="job_id")

        def operation(session: Session) -> Job:
            repository = self._repository(session)
            job = repository.get(job_id)
            if job is None:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": job_id,
                    }
                )
            if job.status != "pending":
                raise ServiceError(
                    "Only pending jobs can be cancelled.",
                    details={
                        "service": self.__class__.__name__,
                        "job_id": job_id,
                        "current_status": job.status,
                    },
                )
            now = datetime.now(timezone.utc)
            job.status = "cancelled"
            job.completed_at = now
            job.updated_at = now
            session.flush()
            return job

        return self._run_in_transaction("cancel_job", operation)

    def retry_job(self, job_id: str) -> Job:
        self._validate_identifier(job_id, field_name="job_id")

        def operation(session: Session) -> Job:
            job = self._repository(session).get(job_id)
            if job is None:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": job_id,
                    }
                )
            if job.status != "failed":
                raise ServiceError(
                    "Only failed jobs can be retried.",
                    details={
                        "service": self.__class__.__name__,
                        "job_id": job_id,
                        "current_status": job.status,
                    },
                )
            if job.retry_count >= job.max_retries:
                raise ServiceError(
                    "Job has exhausted maximum retries.",
                    details={
                        "service": self.__class__.__name__,
                        "job_id": job_id,
                        "retry_count": job.retry_count,
                        "max_retries": job.max_retries,
                    },
                )
            now = datetime.now(timezone.utc)
            job.status = "pending"
            job.retry_count += 1
            job.scheduled_at = now
            job.last_error = None
            job.updated_at = now
            session.flush()
            return job

        return self._run_in_transaction("retry_job", operation)

    def get_next_jobs(self, *, limit: int = 10) -> Sequence[Job]:
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[Job]:
            return self._repository(session).get_pending_jobs(limit=limit)

        return self._run_in_transaction("get_next_jobs", operation)

    def claim_job(self, job_id: str) -> Job | None:
        self._validate_identifier(job_id, field_name="job_id")

        def operation(session: Session) -> Job | None:
            now = datetime.now(timezone.utc)
            stmt = (
                update(Job)
                .where(Job.id == job_id, Job.status == "pending")
                .values(status="running", started_at=now, updated_at=now)
                .returning(Job)
            )
            result = session.execute(stmt)
            job = result.scalar_one_or_none()
            return job

        return self._run_in_transaction("claim_job", operation)