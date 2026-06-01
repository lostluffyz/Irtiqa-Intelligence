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
    from app.models.outreach_message import OutreachMessage
    from app.models.technology import Technology


class IntelligenceScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "intelligence_scores"
    __table_args__ = (
        CheckConstraint(
            "fit_score >= 0.0 AND fit_score <= 100.0",
            name="fit_score_range",
        ),
        CheckConstraint(
            "intent_score >= 0.0 AND intent_score <= 100.0",
            name="intent_score_range",
        ),
        CheckConstraint(
            "technographic_score >= 0.0 AND technographic_score <= 100.0",
            name="technographic_score_range",
        ),
        CheckConstraint(
            "engagement_score >= 0.0 AND engagement_score <= 100.0",
            name="engagement_score_range",
        ),
        CheckConstraint(
            "total_score >= 0.0 AND total_score <= 100.0",
            name="total_score_range",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="confidence_range",
        ),
        Index("ix_intelligence_scores_company_id", "company_id"),
        Index("ix_intelligence_scores_contact_id", "contact_id"),
        Index("ix_intelligence_scores_technology_id", "technology_id"),
        Index("ix_intelligence_scores_agent_run_id", "agent_run_id"),
        Index("ix_intelligence_scores_total_score", "total_score"),
        Index("ix_intelligence_scores_confidence", "confidence"),
        Index("ix_intelligence_scores_score_version", "score_version"),
        Index("ix_intelligence_scores_scored_at", "scored_at"),
        Index("ix_intelligence_scores_company_total", "company_id", "total_score"),
        Index("ix_intelligence_scores_contact_total", "contact_id", "total_score"),
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
    technology_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("technologies.id", ondelete="SET NULL"),
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
    )
    fit_score: Mapped[float] = mapped_column(Float, nullable=False)
    intent_score: Mapped[float] = mapped_column(Float, nullable=False)
    technographic_score: Mapped[float] = mapped_column(Float, nullable=False)
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    score_version: Mapped[str] = mapped_column(String(100), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    company: Mapped[Company] = relationship(back_populates="intelligence_scores")
    contact: Mapped[Contact | None] = relationship(back_populates="intelligence_scores")
    technology: Mapped[Technology | None] = relationship(back_populates="intelligence_scores")
    agent_run: Mapped[AgentRun | None] = relationship(back_populates="intelligence_scores")
    outreach_messages: Mapped[list[OutreachMessage]] = relationship(
        back_populates="intelligence_score",
    )
