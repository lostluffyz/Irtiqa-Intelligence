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
    from app.models.technology import Technology
    from app.models.website import Website


class IntentSignal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "intent_signals"
    __table_args__ = (
        CheckConstraint(
            "strength >= 0.0 AND strength <= 1.0",
            name="strength_range",
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="confidence_range",
        ),
        Index("ix_intent_signals_company_id", "company_id"),
        Index("ix_intent_signals_contact_id", "contact_id"),
        Index("ix_intent_signals_website_id", "website_id"),
        Index("ix_intent_signals_technology_id", "technology_id"),
        Index("ix_intent_signals_agent_run_id", "agent_run_id"),
        Index("ix_intent_signals_signal_type", "signal_type"),
        Index("ix_intent_signals_strength", "strength"),
        Index("ix_intent_signals_confidence", "confidence"),
        Index("ix_intent_signals_observed_at", "observed_at"),
        Index("ix_intent_signals_company_type_observed", "company_id", "signal_type", "observed_at"),
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
    website_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("websites.id", ondelete="SET NULL"),
    )
    technology_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("technologies.id", ondelete="SET NULL"),
    )
    agent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
    )
    signal_type: Mapped[str] = mapped_column(String(150), nullable=False)
    signal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    signal_value: Mapped[str | None] = mapped_column(Text)
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    company: Mapped[Company] = relationship(back_populates="intent_signals")
    contact: Mapped[Contact | None] = relationship(back_populates="intent_signals")
    website: Mapped[Website | None] = relationship(back_populates="intent_signals")
    technology: Mapped[Technology | None] = relationship(back_populates="intent_signals")
    agent_run: Mapped[AgentRun | None] = relationship(back_populates="intent_signals")
