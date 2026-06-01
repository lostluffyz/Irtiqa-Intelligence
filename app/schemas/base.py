from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IrtiqaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    @field_validator("*", mode="after")
    @classmethod
    def reject_blank_strings(cls, value: Any) -> Any:
        if isinstance(value, str) and value == "":
            raise ValueError("String fields must not be blank.")
        return value


class TimestampedReadSchema(IrtiqaSchema):
    id: str = Field(min_length=36, max_length=36)
    created_at: datetime
    updated_at: datetime


class ListSchema(IrtiqaSchema):
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)


def has_update_values(schema: BaseModel) -> bool:
    return bool(schema.model_dump(exclude_unset=True))
