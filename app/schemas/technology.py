from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


class TechnologyCreate(IrtiqaSchema):
    company_id: str = Field(min_length=36, max_length=36)
    website_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=150)
    vendor: str | None = Field(default=None, max_length=255)
    detection_method: str = Field(min_length=1, max_length=150)
    confidence: float = Field(ge=0.0, le=1.0)
    first_detected_at: datetime
    last_detected_at: datetime


class TechnologyUpdate(IrtiqaSchema):
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    website_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=150)
    vendor: str | None = Field(default=None, max_length=255)
    detection_method: str | None = Field(default=None, min_length=1, max_length=150)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    first_detected_at: datetime | None = None
    last_detected_at: datetime | None = None

    @model_validator(mode="after")
    def require_update_values(self) -> TechnologyUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class TechnologyRead(TimestampedReadSchema):
    company_id: str
    website_id: str | None
    agent_run_id: str | None
    name: str
    category: str
    vendor: str | None
    detection_method: str
    confidence: float
    first_detected_at: datetime
    last_detected_at: datetime


class TechnologyList(ListSchema):
    items: list[TechnologyRead]
