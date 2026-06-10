from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
        CheckConstraint(
            "job_type IN ('agent', 'workflow')",
            name="ck_jobs_job_type",
        ),
        CheckConstraint(
            "retry_count <= max_retries",
            name="ck_jobs_retry_count",
        ),
        CheckConstraint(
            "max_retries >= 0",
            name="ck_jobs_max_retries",
        ),
        Index("ix_jobs_status_scheduled_at", "status", "scheduled_at"),
        Index("ix_jobs_target_name", "target_name"),
        Index("ix_jobs_agent_run_id", "agent_run_id"),
    )

    job_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_name: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(default=3, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    agent_run: Mapped[AgentRun | None] = relationship(back_populates="jobs")