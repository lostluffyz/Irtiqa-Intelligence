from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.job import Job
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    model = Job

    def get_pending_jobs(self, *, limit: int = 10) -> Sequence[Job]:
        now = datetime.now(timezone.utc)
        statement = (
            select(Job)
            .where(Job.status == "pending", Job.scheduled_at <= now)
            .order_by(Job.scheduled_at.asc())
            .limit(limit)
        )
        return self.scalars(statement)

    def get_job_by_agent_run_id(self, agent_run_id: str, *, organization_id: str | None = None) -> Job | None:
        statement = select(Job).where(Job.agent_run_id == agent_run_id)
        if organization_id is not None:
            statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalar_one_or_none(statement)