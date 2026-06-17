from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.company import Company
    from app.models.contact import Contact
    from app.models.intelligence_score import IntelligenceScore


class OutreachMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outreach_messages"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'ready_for_review', 'approved', 'sent', 'archived')",
            name="status_allowed",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="confidence_range",
        ),
        Index("ix_outreach_messages_organization_id", "organization_id"),
        Index("ix_outreach_messages_company_id", "company_id"),
        Index("ix_outreach_messages_contact_id", "contact_id"),
        Index("ix_outreach_messages_intelligence_score_id", "intelligence_score_id"),
        Index("ix_outreach_messages_agent_run_id", "agent_run_id"),
        Index("ix_outreach_messages_channel", "channel"),
        Index("ix_outreach_messages_status", "status"),
        Index("ix_outreach_messages_confidence", "confidence"),
        Index("ix_outreach_messages_generated_at", "generated_at"),
        Index("ix_outreach_messages_org_company", "organization_id", "company_id"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk_outreach_messages_org"),
        nullable=False,
    )
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("contacts.id", ondelete="SET NULL"),
    )
    intelligence_score_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("intelligence_scores.id", ondelete="SET NULL"),
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
    )
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255))
    message_body: Mapped[str] = mapped_column(Text, nullable=False)
    personalization_angle: Mapped[str] = mapped_column(Text, nullable=False)
    call_to_action: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    company: Mapped[Company] = relationship(back_populates="outreach_messages")
    contact: Mapped[Contact | None] = relationship(back_populates="outreach_messages")
    intelligence_score: Mapped[IntelligenceScore | None] = relationship(
        back_populates="outreach_messages",
    )
    agent_run: Mapped[AgentRun | None] = relationship(back_populates="outreach_messages")
