from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import desc, select

from app.models.agent_run import AgentRun
from app.repositories.base import BaseRepository


class AgentRunRepository(BaseRepository[AgentRun]):
    model = AgentRun

    def list_by_agent(self, agent_name: str, *, limit: int = 100) -> Sequence[AgentRun]:
        statement = (
            select(AgentRun)
            .where(AgentRun.agent_name == agent_name)
            .order_by(desc(AgentRun.started_at))
            .limit(limit)
        )
        return self.scalars(statement)

    def list_by_status(self, status: str, *, limit: int = 100) -> Sequence[AgentRun]:
        statement = (
            select(AgentRun)
            .where(AgentRun.status == status)
            .order_by(desc(AgentRun.started_at))
            .limit(limit)
        )
        return self.scalars(statement)

    def list_by_workflow(self, workflow_name: str, *, limit: int = 100) -> Sequence[AgentRun]:
        statement = (
            select(AgentRun)
            .where(AgentRun.workflow_name == workflow_name)
            .order_by(desc(AgentRun.started_at))
            .limit(limit)
        )
        return self.scalars(statement)
