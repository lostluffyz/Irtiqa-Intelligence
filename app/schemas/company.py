from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


CompanyStatus = Literal["active", "needs_review", "archived"]


class CompanyCreate(IrtiqaSchema):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=150)
    company_size: str | None = Field(default=None, max_length=100)
    headquarters: str | None = Field(default=None, max_length=255)
    description: str | None = None
    linkedin_url: str | None = Field(default=None, max_length=500)
    status: CompanyStatus = "active"


class CompanyUpdate(IrtiqaSchema):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, max_length=150)
    company_size: str | None = Field(default=None, max_length=100)
    headquarters: str | None = Field(default=None, max_length=255)
    description: str | None = None
    linkedin_url: str | None = Field(default=None, max_length=500)
    status: CompanyStatus | None = None

    @model_validator(mode="after")
    def require_update_values(self) -> CompanyUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class CompanyRead(TimestampedReadSchema):
    name: str
    domain: str
    industry: str | None
    company_size: str | None
    headquarters: str | None
    description: str | None
    linkedin_url: str | None
    status: CompanyStatus


class CompanyList(ListSchema):
    items: list[CompanyRead]
