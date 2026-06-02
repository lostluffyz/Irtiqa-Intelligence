from __future__ import annotations

from types import MappingProxyType
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.schemas.base import IrtiqaSchema


class AgentContext(IrtiqaSchema):
    """Immutable execution context passed to agents.

    Follows the same frozen-options pattern as ``WorkflowContext``.
    ``company_id`` is always required because every agent operates
    within the scope of a target company.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        frozen=True,
        str_strip_whitespace=True,
    )

    agent_name: str = Field(min_length=1, max_length=150)
    company_id: str = Field(min_length=36, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    workflow_name: str | None = Field(default=None, min_length=1, max_length=150)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=100)
    options: MappingProxyType[str, Any] = Field(default_factory=lambda: MappingProxyType({}))

    @field_validator("options", mode="before")
    @classmethod
    def freeze_options(cls, value: Any) -> MappingProxyType[str, Any]:
        if value is None:
            return MappingProxyType({})
        if not isinstance(value, dict):
            raise ValueError("Agent options must be a dictionary.")
        return MappingProxyType(dict(value))

    @model_validator(mode="after")
    def require_company(self) -> AgentContext:
        if not self.company_id or not self.company_id.strip():
            raise ValueError("Agent context requires a non-blank company_id.")
        return self
