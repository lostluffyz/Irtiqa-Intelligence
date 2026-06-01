from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


AgentRunStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class AgentRunCreate(IrtiqaSchema):
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_name: str = Field(min_length=1, max_length=150)
    workflow_name: str | None = Field(default=None, max_length=150)
    status: AgentRunStatus
    input_summary: str | None = None
    output_summary: str | None = None
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class AgentRunUpdate(IrtiqaSchema):
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_name: str | None = Field(default=None, min_length=1, max_length=150)
    workflow_name: str | None = Field(default=None, max_length=150)
    status: AgentRunStatus | None = None
    input_summary: str | None = None
    output_summary: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @model_validator(mode="after")
    def require_update_values(self) -> AgentRunUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class AgentRunRead(TimestampedReadSchema):
    company_id: str | None
    contact_id: str | None
    agent_name: str
    workflow_name: str | None
    status: AgentRunStatus
    input_summary: str | None
    output_summary: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class AgentRunList(ListSchema):
    items: list[AgentRunRead]
