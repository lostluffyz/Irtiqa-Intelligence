from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field

from app.schemas.base import IrtiqaSchema


AGENT_STATUS_SUCCEEDED = "succeeded"
AGENT_STATUS_FAILED = "failed"


class AgentResult(IrtiqaSchema):
    """Structured result returned by ``BaseAgent.execute()``.

    ``agent_run_id`` may be ``None`` if the run record could not be
    created (e.g. because of a validation failure before audit setup).
    ``error`` follows the ``IrtiqaError.to_dict()`` format when present.
    """

    agent_name: str = Field(min_length=1, max_length=150)
    agent_run_id: str | None = Field(default=None, min_length=36, max_length=36)
    status: str = Field(min_length=1, max_length=50)
    output_ids: dict[str, list[str]] = Field(default_factory=dict)
    summary: str = Field(min_length=1)
    error: dict[str, Any] | None = None
    duration_ms: float = Field(ge=0.0)
    stats: dict[str, Any] = Field(default_factory=dict)
    finished_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
