from __future__ import annotations

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema, has_update_values


class OrganizationCreate(IrtiqaSchema):
    name: str = Field(min_length=1, max_length=200)


class OrganizationUpdate(IrtiqaSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_update_values(self) -> OrganizationUpdate:
        if not has_update_values(self):
            raise ValueError("At least one field must be provided for update.")
        return self


class OrganizationRead(TimestampedReadSchema):
    name: str
    slug: str
    status: str


class OrganizationList(ListSchema):
    items: list[OrganizationRead]
