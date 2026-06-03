from __future__ import annotations

from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


class WebsiteCreate(IrtiqaSchema):
    company_id: str = Field(min_length=36, max_length=36)
    url: str = Field(min_length=1, max_length=1000)
    normalized_url: str = Field(min_length=1, max_length=1000)
    page_type: str | None = Field(default=None, max_length=100)
    http_status: int | None = Field(default=None, ge=100, le=599)
    last_scraped_at: datetime | None = None
    raw_html: str | None = None
    extracted_text: str | None = None


class WebsiteUpdate(IrtiqaSchema):
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    url: str | None = Field(default=None, min_length=1, max_length=1000)
    normalized_url: str | None = Field(default=None, min_length=1, max_length=1000)
    page_type: str | None = Field(default=None, max_length=100)
    http_status: int | None = Field(default=None, ge=100, le=599)
    last_scraped_at: datetime | None = None
    raw_html: str | None = None
    extracted_text: str | None = None

    @model_validator(mode="after")
    def require_update_values(self) -> WebsiteUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class WebsiteRead(TimestampedReadSchema):
    company_id: str
    url: str
    normalized_url: str
    page_type: str | None
    http_status: int | None
    last_scraped_at: datetime | None
    raw_html: str | None = None
    extracted_text: str | None = None


class WebsiteList(ListSchema):
    items: list[WebsiteRead]
