from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.contact import Contact
    from app.models.intent_signal import IntentSignal
    from app.models.intelligence_score import IntelligenceScore
    from app.models.job import Job
    from app.models.outreach_message import OutreachMessage
    from app.models.technology import Technology


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="status_allowed",
        ),
        Index("ix_agent_runs_company_id", "company_id"),
        Index("ix_agent_runs_contact_id", "contact_id"),
        Index("ix_agent_runs_agent_name", "agent_name"),
        Index("ix_agent_runs_workflow_name", "workflow_name"),
        Index("ix_agent_runs_status", "status"),
        Index("ix_agent_runs_started_at", "started_at"),
        Index("ix_agent_runs_finished_at", "finished_at"),
        Index("ix_agent_runs_agent_name_status", "agent_name", "status"),
        Index("ix_agent_runs_workflow_name_status", "workflow_name", "status"),
    )

    company_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="SET NULL"),
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("contacts.id", ondelete="SET NULL"),
    )
    agent_name: Mapped[str] = mapped_column(String(150), nullable=False)
    workflow_name: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company | None] = relationship(back_populates="agent_runs")
    contact: Mapped[Contact | None] = relationship(back_populates="agent_runs")
    technologies: Mapped[list[Technology]] = relationship(back_populates="agent_run")
    intent_signals: Mapped[list[IntentSignal]] = relationship(back_populates="agent_run")
    intelligence_scores: Mapped[list[IntelligenceScore]] = relationship(
        back_populates="agent_run",
    )
    outreach_messages: Mapped[list[OutreachMessage]] = relationship(
        back_populates="agent_run",
    )
    jobs: Mapped[list[Job]] = relationship(back_populates="agent_run")
