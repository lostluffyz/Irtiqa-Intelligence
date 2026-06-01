from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from app.schemas.base import IrtiqaSchema
from app.workflows.states import WorkflowStatus


class WorkflowStepResult(IrtiqaSchema):
    step_name: str = Field(min_length=1, max_length=150)
    status: WorkflowStatus
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    output_ids: dict[str, list[str]] = Field(default_factory=dict)
    error: dict[str, Any] | None = None


class WorkflowResult(IrtiqaSchema):
    workflow_name: str = Field(min_length=1, max_length=150)
    status: WorkflowStatus
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_run_ids: list[str] = Field(default_factory=list)
    output_ids: dict[str, list[str]] = Field(default_factory=dict)
    steps: list[WorkflowStepResult] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

    def finish(self, status: WorkflowStatus, *, error: dict[str, Any] | None = None) -> WorkflowResult:
        return self.model_copy(
            update={
                "status": status,
                "error": error,
                "finished_at": datetime.now(timezone.utc),
            }
        )
