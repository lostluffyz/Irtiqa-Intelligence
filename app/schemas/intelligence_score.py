from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


class IntelligenceScoreCreate(IrtiqaSchema):
    company_id: str = Field(min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    technology_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    fit_score: float = Field(ge=0.0, le=100.0)
    intent_score: float = Field(ge=0.0, le=100.0)
    technographic_score: float = Field(ge=0.0, le=100.0)
    engagement_score: float = Field(ge=0.0, le=100.0)
    total_score: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    score_version: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1)
    scored_at: datetime


class IntelligenceScoreUpdate(IrtiqaSchema):
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    technology_id: str | None = Field(default=None, min_length=36, max_length=36)
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    fit_score: float | None = Field(default=None, ge=0.0, le=100.0)
    intent_score: float | None = Field(default=None, ge=0.0, le=100.0)
    technographic_score: float | None = Field(default=None, ge=0.0, le=100.0)
    engagement_score: float | None = Field(default=None, ge=0.0, le=100.0)
    total_score: float | None = Field(default=None, ge=0.0, le=100.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    score_version: str | None = Field(default=None, min_length=1, max_length=100)
    rationale: str | None = Field(default=None, min_length=1)
    scored_at: datetime | None = None

    @model_validator(mode="after")
    def require_update_values(self) -> IntelligenceScoreUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class IntelligenceScoreRead(TimestampedReadSchema):
    company_id: str
    contact_id: str | None
    technology_id: str | None
    agent_run_id: str | None
    fit_score: float
    intent_score: float
    technographic_score: float
    engagement_score: float
    total_score: float
    confidence: float
    score_version: str
    rationale: str
    scored_at: datetime


class IntelligenceScoreList(ListSchema):
    items: list[IntelligenceScoreRead]
