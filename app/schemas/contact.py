from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


ContactStatus = Literal["active", "unverified", "qualified", "disqualified", "archived"]


class ContactCreate(IrtiqaSchema):
    company_id: str = Field(min_length=36, max_length=36)
    first_name: str | None = Field(default=None, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    full_name: str = Field(min_length=1, max_length=300)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=100)
    seniority: str | None = Field(default=None, max_length=100)
    linkedin_url: str | None = Field(default=None, max_length=500)
    status: ContactStatus = "active"


class ContactUpdate(IrtiqaSchema):
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    first_name: str | None = Field(default=None, max_length=150)
    last_name: str | None = Field(default=None, max_length=150)
    full_name: str | None = Field(default=None, min_length=1, max_length=300)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    title: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=100)
    seniority: str | None = Field(default=None, max_length=100)
    linkedin_url: str | None = Field(default=None, max_length=500)
    status: ContactStatus | None = None

    @model_validator(mode="after")
    def require_update_values(self) -> ContactUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class ContactRead(TimestampedReadSchema):
    company_id: str
    first_name: str | None
    last_name: str | None
    full_name: str
    email: str | None
    phone: str | None
    title: str | None
    department: str | None
    seniority: str | None
    linkedin_url: str | None
    status: ContactStatus


class ContactList(ListSchema):
    items: list[ContactRead]
