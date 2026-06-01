from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.company import Company
    from app.models.intent_signal import IntentSignal
    from app.models.intelligence_score import IntelligenceScore
    from app.models.website import Website


class Technology(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "technologies"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="confidence_range",
        ),
        Index("uq_technologies_company_name_category", "company_id", "name", "category", unique=True),
        Index("ix_technologies_company_id", "company_id"),
        Index("ix_technologies_website_id", "website_id"),
        Index("ix_technologies_agent_run_id", "agent_run_id"),
        Index("ix_technologies_name", "name"),
        Index("ix_technologies_category", "category"),
        Index("ix_technologies_confidence", "confidence"),
        Index("ix_technologies_last_detected_at", "last_detected_at"),
    )

    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    website_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("websites.id", ondelete="SET NULL"),
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(150), nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(255))
    detection_method: Mapped[str] = mapped_column(String(150), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    company: Mapped[Company] = relationship(back_populates="technologies")
    website: Mapped[Website | None] = relationship(back_populates="technologies")
    agent_run: Mapped[AgentRun | None] = relationship(back_populates="technologies")
    intent_signals: Mapped[list[IntentSignal]] = relationship(back_populates="technology")
    intelligence_scores: Mapped[list[IntelligenceScore]] = relationship(
        back_populates="technology",
    )
