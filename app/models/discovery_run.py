from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.discovery_search import DiscoverySearch
    from app.models.organization import Organization


class DiscoveryRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "discovery_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_discovery_runs_status",
        ),
        Index("ix_discovery_runs_organization_id", "organization_id"),
        Index("ix_discovery_runs_search_id", "search_id"),
        Index("ix_discovery_runs_status", "status"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_discovery_runs_org",
        ),
        nullable=False,
    )
    search_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "discovery_searches.id",
            ondelete="CASCADE",
            name="fk_discovery_runs_search",
        ),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="running",
        nullable=False,
    )
    sources_queried: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    companies_found: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    companies_created: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    companies_skipped: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    organization: Mapped[Organization] = relationship(
        back_populates="discovery_runs",
        foreign_keys=[organization_id],
    )
    search: Mapped[DiscoverySearch] = relationship(
        back_populates="discovery_runs",
        foreign_keys=[search_id],
    )
