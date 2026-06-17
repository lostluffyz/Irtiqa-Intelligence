from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.company import Company
    from app.models.intent_signal import IntentSignal
    from app.models.intelligence_score import IntelligenceScore
    from app.models.outreach_message import OutreachMessage


class Contact(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'unverified', 'qualified', 'disqualified', 'archived')",
            name="status_allowed",
        ),
        Index("ix_contacts_company_id", "company_id"),
        Index("ix_contacts_linkedin_url", "linkedin_url"),
        Index("ix_contacts_department", "department"),
        Index("ix_contacts_seniority", "seniority"),
        Index("ix_contacts_status", "status"),
        Index("ix_contacts_organization_id", "organization_id"),
        Index("uq_contacts_org_email", "organization_id", "email", unique=True),
    )

    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE", name="fk_contacts_org"),
        nullable=False,
    )
    first_name: Mapped[str | None] = mapped_column(String(150))
    last_name: Mapped[str | None] = mapped_column(String(150))
    full_name: Mapped[str] = mapped_column(String(300), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(100))
    seniority: Mapped[str | None] = mapped_column(String(100))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    company: Mapped[Company] = relationship(back_populates="contacts")
    intent_signals: Mapped[list[IntentSignal]] = relationship(
        back_populates="contact",
    )
    intelligence_scores: Mapped[list[IntelligenceScore]] = relationship(
        back_populates="contact",
    )
    outreach_messages: Mapped[list[OutreachMessage]] = relationship(
        back_populates="contact",
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(back_populates="contact")
