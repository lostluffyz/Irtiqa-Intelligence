from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


OutreachMessageStatus = Literal["draft", "ready_for_review", "approved", "sent", "archived"]


class OutreachMessageCreate(IrtiqaSchema):
    company_id: str = Field(min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    intelligence_score_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    channel: str = Field(min_length=1, max_length=100)
    subject: str | None = Field(default=None, max_length=255)
    message_body: str = Field(min_length=1)
    personalization_angle: str = Field(min_length=1)
    call_to_action: str | None = None
    status: OutreachMessageStatus = "draft"
    confidence: float = Field(ge=0.0, le=1.0)
    generated_at: datetime


class OutreachMessageUpdate(IrtiqaSchema):
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    intelligence_score_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    channel: str | None = Field(default=None, min_length=1, max_length=100)
    subject: str | None = Field(default=None, max_length=255)
    message_body: str | None = Field(default=None, min_length=1)
    personalization_angle: str | None = Field(default=None, min_length=1)
    call_to_action: str | None = None
    status: OutreachMessageStatus | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    generated_at: datetime | None = None

    @model_validator(mode="after")
    def require_update_values(self) -> OutreachMessageUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class OutreachMessageRead(TimestampedReadSchema):
    company_id: str
    contact_id: str | None
    intelligence_score_id: str | None
    agent_run_id: str | None
    channel: str
    subject: str | None
    message_body: str
    personalization_angle: str
    call_to_action: str | None
    status: OutreachMessageStatus
    confidence: float
    generated_at: datetime


class OutreachMessageList(ListSchema):
    items: list[OutreachMessageRead]
