from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.discovery_run import DiscoveryRun
    from app.models.organization import Organization


class DiscoverySearch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "discovery_searches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="ck_discovery_searches_status",
        ),
        Index("ix_discovery_searches_organization_id", "organization_id"),
    )

    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "organizations.id",
            ondelete="CASCADE",
            name="fk_discovery_searches_org",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    criteria: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    total_discovered: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    organization: Mapped[Organization] = relationship(
        back_populates="discovery_searches",
        foreign_keys=[organization_id],
    )
    discovery_runs: Mapped[list[DiscoveryRun]] = relationship(
        back_populates="search",
        cascade="all, delete-orphan",
    )
    companies: Mapped[list[Company]] = relationship(
        back_populates="discovery_search",
    )
