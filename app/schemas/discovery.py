from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


DiscoverySearchStatus = Literal["active", "archived"]
DiscoveryRunStatus = Literal["running", "succeeded", "failed"]
DiscoverySource = Literal["sec_edgar", "google_news_rss", "opencorporates"]


def _parse_criteria(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("criteria must be valid JSON.") from exc
    return value


class DiscoverySearchCriteria(IrtiqaSchema):
    industry: str = Field(min_length=1, max_length=150)
    company_size_min: int | None = Field(default=None, ge=1)
    company_size_max: int | None = Field(default=None, ge=1)
    geography: str | None = Field(default=None, max_length=150)
    technologies: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(min_length=1)
    exclude_domains: list[str] = Field(default_factory=list)
    sources: list[DiscoverySource] = Field(
        default_factory=lambda: ["sec_edgar", "google_news_rss", "opencorporates"],
        min_length=1,
    )

    @field_validator("technologies", "keywords", "exclude_domains")
    @classmethod
    def reject_blank_list_values(cls, value: list[str]) -> list[str]:
        stripped_values = [item.strip() for item in value]
        if any(item == "" for item in stripped_values):
            raise ValueError("List values must not be blank.")
        return stripped_values

    @model_validator(mode="after")
    def validate_company_size_bounds(self) -> DiscoverySearchCriteria:
        if (
            self.company_size_min is not None
            and self.company_size_max is not None
            and self.company_size_min > self.company_size_max
        ):
            raise ValueError("company_size_min must be less than or equal to company_size_max.")
        return self


class DiscoverySearchCreate(IrtiqaSchema):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    criteria: DiscoverySearchCriteria
    status: DiscoverySearchStatus = "active"

    @field_validator("criteria", mode="before")
    @classmethod
    def parse_criteria_json(cls, value: Any) -> Any:
        return _parse_criteria(value)


class DiscoverySearchUpdate(IrtiqaSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    criteria: DiscoverySearchCriteria | None = None
    status: DiscoverySearchStatus | None = None

    @field_validator("criteria", mode="before")
    @classmethod
    def parse_criteria_json(cls, value: Any) -> Any:
        return _parse_criteria(value)

    @model_validator(mode="after")
    def require_update_values(self) -> DiscoverySearchUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class DiscoverySearchRead(TimestampedReadSchema):
    organization_id: str = Field(min_length=36, max_length=36)
    name: str
    description: str | None
    criteria: DiscoverySearchCriteria
    status: DiscoverySearchStatus
    last_run_at: datetime | None
    total_discovered: int = Field(ge=0)

    @field_validator("criteria", mode="before")
    @classmethod
    def parse_criteria_json(cls, value: Any) -> Any:
        return _parse_criteria(value)


class DiscoverySearchList(ListSchema):
    items: list[DiscoverySearchRead]


class DiscoverySearchQueryParams(IrtiqaSchema):
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    status: DiscoverySearchStatus | None = None


class DiscoveryRunCreate(IrtiqaSchema):
    organization_id: str = Field(min_length=36, max_length=36)
    search_id: str = Field(min_length=36, max_length=36)
    status: DiscoveryRunStatus = "running"
    sources_queried: int = Field(default=0, ge=0)
    companies_found: int = Field(default=0, ge=0)
    companies_created: int = Field(default=0, ge=0)
    companies_skipped: int = Field(default=0, ge=0)
    started_at: datetime
    finished_at: datetime | None = None
    error_message: str | None = None


class DiscoveryRunUpdate(IrtiqaSchema):
    status: DiscoveryRunStatus | None = None
    sources_queried: int | None = Field(default=None, ge=0)
    companies_found: int | None = Field(default=None, ge=0)
    companies_created: int | None = Field(default=None, ge=0)
    companies_skipped: int | None = Field(default=None, ge=0)
    finished_at: datetime | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def require_update_values(self) -> DiscoveryRunUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class DiscoveryRunRead(TimestampedReadSchema):
    organization_id: str = Field(min_length=36, max_length=36)
    search_id: str = Field(min_length=36, max_length=36)
    status: DiscoveryRunStatus
    sources_queried: int = Field(ge=0)
    companies_found: int = Field(ge=0)
    companies_created: int = Field(ge=0)
    companies_skipped: int = Field(ge=0)
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None


class DiscoveryRunList(ListSchema):
    items: list[DiscoveryRunRead]


class DiscoveryRunQueryParams(IrtiqaSchema):
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    search_id: str | None = Field(default=None, min_length=36, max_length=36)
    status: DiscoveryRunStatus | None = None
