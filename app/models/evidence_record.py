from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun


# ── Evidence types ──────────────────────────────────────

EVIDENCE_TYPE_HTML_SNIPPET = "html_snippet"
EVIDENCE_TYPE_TEXT_EXCERPT = "text_excerpt"
EVIDENCE_TYPE_URL_MATCH = "url_match"
EVIDENCE_TYPE_SIGNATURE_MATCH = "signature_match"
EVIDENCE_TYPE_COMPUTED_METRIC = "computed_metric"
EVIDENCE_TYPE_AGENT_SUMMARY = "agent_summary"

VALID_EVIDENCE_TYPES = frozenset({
    EVIDENCE_TYPE_HTML_SNIPPET,
    EVIDENCE_TYPE_TEXT_EXCERPT,
    EVIDENCE_TYPE_URL_MATCH,
    EVIDENCE_TYPE_SIGNATURE_MATCH,
    EVIDENCE_TYPE_COMPUTED_METRIC,
    EVIDENCE_TYPE_AGENT_SUMMARY,
})

# ── Relationship types ──────────────────────────────────

RELATIONSHIP_SUPPORTS = "supports"
RELATIONSHIP_CONTRADICTS = "contradicts"
RELATIONSHIP_CONTRIBUTES_TO = "contributes_to"
RELATIONSHIP_GENERATES = "generates"

VALID_RELATIONSHIP_TYPES = frozenset({
    RELATIONSHIP_SUPPORTS,
    RELATIONSHIP_CONTRADICTS,
    RELATIONSHIP_CONTRIBUTES_TO,
    RELATIONSHIP_GENERATES,
})

# ── Source entity types ─────────────────────────────────

SOURCE_TYPE_WEBSITE = "website"
SOURCE_TYPE_AGENT_RUN = "agent_run"
SOURCE_TYPE_JOB = "job"

VALID_SOURCE_TYPES = frozenset({
    SOURCE_TYPE_WEBSITE,
    SOURCE_TYPE_AGENT_RUN,
    SOURCE_TYPE_JOB,
})

# ── Target entity types ─────────────────────────────────

TARGET_TYPE_TECHNOLOGY = "technology"
TARGET_TYPE_INTENT_SIGNAL = "intent_signal"
TARGET_TYPE_INTELLIGENCE_SCORE = "intelligence_score"
TARGET_TYPE_OUTREACH_MESSAGE = "outreach_message"

VALID_TARGET_TYPES = frozenset({
    TARGET_TYPE_TECHNOLOGY,
    TARGET_TYPE_INTENT_SIGNAL,
    TARGET_TYPE_INTELLIGENCE_SCORE,
    TARGET_TYPE_OUTREACH_MESSAGE,
})

# ── Evidence value maximum length (characters) ──────────

EVIDENCE_VALUE_MAX_LENGTH = 5000


class EvidenceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evidence_records"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ("
            "'html_snippet', 'text_excerpt', 'url_match', "
            "'signature_match', 'computed_metric', 'agent_summary'"
            ")",
            name="evidence_type",
        ),
        CheckConstraint(
            "relationship_type IN ("
            "'supports', 'contradicts', 'contributes_to', 'generates'"
            ")",
            name="relationship_type",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="confidence",
        ),
        Index("ix_evidence_target", "target_type", "target_id"),
        Index("ix_evidence_source", "source_type", "source_id"),
        Index("ix_evidence_type", "evidence_type"),
        Index("ix_evidence_relationship", "relationship_type"),
        Index("ix_evidence_agent_run", "agent_run_id"),
        Index("ix_evidence_company", "company_id"),
        Index("ix_evidence_contact", "contact_id"),
        Index("ix_evidence_hash", "evidence_hash"),
        Index("ix_evidence_target_type", "target_type"),
        Index("ix_evidence_created_at", "created_at"),
        Index("ix_evidence_source_location", "source_location_type", "source_location_value"),
        Index("ix_evidence_organization_id", "organization_id"),
        Index("ix_evidence_org_target", "organization_id", "target_type", "target_id"),
        Index("ix_evidence_org_source", "organization_id", "source_type", "source_id"),
    )

    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_detail: Mapped[str | None] = mapped_column(Text)
    source_location_type: Mapped[str | None] = mapped_column(String(50))
    source_location_value: Mapped[str | None] = mapped_column(String(500))
    evidence_type: Mapped[str] = mapped_column(String(150), nullable=False)
    evidence_value: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_hash: Mapped[str | None] = mapped_column(String(64))
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk_evidence_records_org"),
        nullable=False,
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
    )
    company_id: Mapped[str | None] = mapped_column(String(36))
    contact_id: Mapped[str | None] = mapped_column(String(36))

    # Relationships
    # agent_run_id has a declarative FK, so this relationship uses standard join resolution.
    agent_run: Mapped[AgentRun | None] = relationship(back_populates="evidence_records")
    # company_id and contact_id are denormalized query shortcuts without declarative FKs.
    # They are queried via the indexed columns directly, not through ORM relationships.
