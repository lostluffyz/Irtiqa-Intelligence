from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun
from app.repositories.agent_run_repository import AgentRunRepository
from app.services.base import BaseService


class AgentRunService(BaseService[AgentRun, AgentRunRepository]):
    model = AgentRun
    repository = AgentRunRepository

    def create(self, organization_id: str, **values: Any) -> AgentRun:
        return super().create(organization_id=organization_id, **values)

    def list_by_agent(self, agent_name: str, *, organization_id: str, limit: int = 100) -> Sequence[AgentRun]:
        self._validate_identifier(agent_name, field_name="agent_name")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[AgentRun]:
            return self._repository(session).list_by_agent(agent_name, organization_id=organization_id, limit=limit)

        return self._run_in_transaction("list_by_agent", operation)

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[AgentRun]:
        self._validate_identifier(status, field_name="status")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[AgentRun]:
            return self._repository(session).list_by_status(status, organization_id=organization_id, limit=limit)

        return self._run_in_transaction("list_by_status", operation)

    def list_by_workflow(self, workflow_name: str, *, organization_id: str, limit: int = 100) -> Sequence[AgentRun]:
        self._validate_identifier(workflow_name, field_name="workflow_name")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[AgentRun]:
            return self._repository(session).list_by_workflow(workflow_name, organization_id=organization_id, limit=limit)

        return self._run_in_transaction("list_by_workflow", operation)

    def start_workflow_run(
        self,
        *,
        organization_id: str,
        agent_name: str,
        workflow_name: str,
        company_id: str | None = None,
        contact_id: str | None = None,
        input_summary: str | None = None,
    ) -> AgentRun:
        self._validate_identifier(agent_name, field_name="agent_name")
        self._validate_identifier(workflow_name, field_name="workflow_name")

        return self.create(
            organization_id=organization_id,
            company_id=company_id,
            contact_id=contact_id,
            agent_name=agent_name,
            workflow_name=workflow_name,
            status="running",
            input_summary=input_summary,
            started_at=datetime.now(timezone.utc),
        )

    def mark_succeeded(self, agent_run_id: str, *, output_summary: str | None = None) -> AgentRun:
        self._validate_identifier(agent_run_id, field_name="agent_run_id")

        return self.update(
            agent_run_id,
            status="succeeded",
            output_summary=output_summary,
            finished_at=datetime.now(timezone.utc),
        )

    def mark_failed(self, agent_run_id: str, *, error_message: str) -> AgentRun:
        self._validate_identifier(agent_run_id, field_name="agent_run_id")
        self._validate_identifier(error_message, field_name="error_message")

        return self.update(
            agent_run_id,
            status="failed",
            error_message=error_message,
            finished_at=datetime.now(timezone.utc),
        )
