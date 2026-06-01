from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.contact import Contact
    from app.models.intent_signal import IntentSignal
    from app.models.intelligence_score import IntelligenceScore
    from app.models.outreach_message import OutreachMessage
    from app.models.technology import Technology
    from app.models.website import Website


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'needs_review', 'archived')",
            name="status_allowed",
        ),
        Index("ix_companies_domain", "domain", unique=True),
        Index("ix_companies_name", "name"),
        Index("ix_companies_industry", "industry"),
        Index("ix_companies_status", "status"),
        Index("ix_companies_created_at", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(150))
    company_size: Mapped[str | None] = mapped_column(String(100))
    headquarters: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    contacts: Mapped[list[Contact]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    websites: Mapped[list[Website]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    technologies: Mapped[list[Technology]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    intent_signals: Mapped[list[IntentSignal]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    intelligence_scores: Mapped[list[IntelligenceScore]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    outreach_messages: Mapped[list[OutreachMessage]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="company",
    )
