from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.contact import Contact
    from app.models.discovery_search import DiscoverySearch
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
        CheckConstraint(
            "discovery_score >= 0.0 AND discovery_score <= 1.0",
            name="ck_companies_discovery_score",
        ),
        Index("ix_companies_name", "name"),
        Index("ix_companies_industry", "industry"),
        Index("ix_companies_status", "status"),
        Index("ix_companies_created_at", "created_at"),
        Index("ix_companies_organization_id", "organization_id"),
        Index("uq_companies_org_domain", "organization_id", "domain", unique=True),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk_companies_org"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str | None] = mapped_column(String(150))
    company_size: Mapped[str | None] = mapped_column(String(100))
    headquarters: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    discovered_via: Mapped[str | None] = mapped_column(String(100))
    discovery_search_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("discovery_searches.id", ondelete="SET NULL"),
        nullable=True,
    )
    discovery_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    discovery_search: Mapped[DiscoverySearch | None] = relationship(
        back_populates="companies",
        foreign_keys=[discovery_search_id],
    )
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
