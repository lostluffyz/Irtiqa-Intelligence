from __future__ import annotations

from types import MappingProxyType
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.base import IrtiqaSchema


class WorkflowContext(IrtiqaSchema):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
        str_strip_whitespace=True,
    )

    workflow_name: str = Field(min_length=1, max_length=150)
    company_id: str | None = Field(default=None, min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    organization_id: str | None = Field(default=None, min_length=36, max_length=36)  # NEW
    correlation_id: str | None = Field(default=None, min_length=1, max_length=100)
    requested_by: str | None = Field(default=None, min_length=1, max_length=150)
    options: MappingProxyType[str, Any] = Field(default_factory=lambda: MappingProxyType({}))

    @field_validator("options", mode="before")
    @classmethod
    def freeze_options(cls, value: Any) -> MappingProxyType[str, Any]:
        if value is None:
            return MappingProxyType({})
        if not isinstance(value, dict):
            raise ValueError("Workflow options must be a dictionary.")
        return MappingProxyType(dict(value))

    @model_validator(mode="after")
    def require_target(self) -> WorkflowContext:
        if self.organization_id is None and self.company_id is None and self.contact_id is None:
            raise ValueError("Workflow context requires organization_id, company_id, or contact_id.")
        return self
