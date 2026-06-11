from __future__ import annotations

from datetime import datetime
from typing import NotRequired, TypedDict

from pydantic import Field

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema


# ── Shared TypedDict (agent ↔ service contract) ─────────────────────────────


class EvidenceItem(TypedDict):
    """A single evidence record to be persisted.

    ``source_id`` is the UUID of the entity identified by ``source_type``
    (e.g. a website ID or agent run ID).

    ``company_id``, ``contact_id``, and ``agent_run_id`` are omitted here;
    they are injected by ``BaseAgent.execute()`` or
    ``EvidenceService.record_evidence_batch()``.
    """

    source_type: str
    source_id: str
    source_detail: str
    source_location_type: NotRequired[str | None]
    source_location_value: NotRequired[str | None]
    evidence_type: str
    evidence_value: str
    relationship_type: str
    target_type: str
    target_id: str
    confidence: float


# ── API schemas ─────────────────────────────────────────────────────────────


class EvidenceRead(TimestampedReadSchema):
    source_type: str
    source_id: str
    source_detail: str | None = None
    source_location_type: str | None = None
    source_location_value: str | None = None
    evidence_type: str
    evidence_value: str
    evidence_hash: str | None = None
    relationship_type: str
    target_type: str
    target_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    agent_run_id: str | None = None
    company_id: str | None = None
    contact_id: str | None = None


class EvidenceList(ListSchema):
    items: list[EvidenceRead]


class EvidenceSummary(IrtiqaSchema):
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=36, max_length=36)
    total_evidence: int = Field(ge=0)
    by_evidence_type: dict[str, int]
    by_relationship_type: dict[str, int]
    highest_confidence: float = Field(ge=0.0, le=1.0)
    lowest_confidence: float = Field(ge=0.0, le=1.0)
