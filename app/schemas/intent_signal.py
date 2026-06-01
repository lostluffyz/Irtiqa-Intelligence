from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


class IntentSignalCreate(IrtiqaSchema):
    company_id: str = Field(min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    website_id: str | None = Field(default=None, min_length=36, max_length=36)
    technology_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    signal_type: str = Field(min_length=1, max_length=150)
    signal_name: str = Field(min_length=1, max_length=255)
    signal_value: str | None = None
    strength: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    source_url: str | None = Field(default=None, max_length=1000)
    observed_at: datetime


class IntentSignalUpdate(IrtiqaSchema):
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    website_id: str | None = Field(default=None, min_length=36, max_length=36)
    technology_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    signal_type: str | None = Field(default=None, min_length=1, max_length=150)
    signal_name: str | None = Field(default=None, min_length=1, max_length=255)
    signal_value: str | None = None
    strength: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source_url: str | None = Field(default=None, max_length=1000)
    observed_at: datetime | None = None

    @model_validator(mode="after")
    def require_update_values(self) -> IntentSignalUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class IntentSignalRead(TimestampedReadSchema):
    company_id: str
    contact_id: str | None
    website_id: str | None
    technology_id: str | None
    agent_run_id: str | None
    signal_type: str
    signal_name: str
    signal_value: str | None
    strength: float
    confidence: float
    source_url: str | None
    observed_at: datetime


class IntentSignalList(ListSchema):
    items: list[IntentSignalRead]
