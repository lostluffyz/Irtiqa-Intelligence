from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


JobType = Literal["agent", "workflow"]
JobStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]


class JobCreate(IrtiqaSchema):
    job_type: JobType
    target_name: str = Field(min_length=1, max_length=128)
    payload: str = Field(min_length=1)
    status: JobStatus
    scheduled_at: datetime
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    last_error: str | None = None
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)


class JobRead(TimestampedReadSchema):
    job_type: JobType
    target_name: str
    payload: str
    status: JobStatus
    scheduled_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    retry_count: int
    max_retries: int
    last_error: str | None
    agent_run_id: str | None


class JobList(ListSchema):
    items: list[JobRead]


class JobScheduleAgentRequest(IrtiqaSchema):
    agent_name: str = Field(min_length=1, max_length=150)
    company_id: str = Field(min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    workflow_name: str | None = Field(default=None, max_length=150)
    correlation_id: str | None = Field(default=None, max_length=100)
    options: dict = Field(default_factory=dict)
    scheduled_at: datetime | None = None
    max_retries: int = Field(default=3, ge=0, le=10)


class JobScheduleWorkflowRequest(IrtiqaSchema):
    workflow_name: str = Field(min_length=1, max_length=150)
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    correlation_id: str | None = Field(default=None, max_length=100)
    requested_by: str | None = Field(default=None, max_length=150)
    options: dict = Field(default_factory=dict)
    scheduled_at: datetime | None = None
    max_retries: int = Field(default=3, ge=0, le=10)