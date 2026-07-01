from __future__ import annotations

import re
import secrets
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session
from sqlalchemy import select

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.discovery_run import DiscoveryRun
    from app.models.discovery_search import DiscoverySearch
    from app.models.membership import Membership


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'suspended', 'cancelled')",
            name="status",
        ),
        Index("ix_organizations_slug", "slug", unique=True),
        Index("ix_organizations_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active",
    )

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    discovery_searches: Mapped[list[DiscoverySearch]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    discovery_runs: Mapped[list[DiscoveryRun]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


# -- Slug generation ---------------------------------------------------------


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from an organization name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        slug = "org"
    return slug


def generate_unique_slug(name: str, session: Session) -> str:
    """Generate a unique slug, appending a random suffix on collision."""
    base = generate_slug(name)
    candidate = base
    for _ in range(10):
        existing = session.scalar(
            select(Organization).where(Organization.slug == candidate)
        )
        if existing is None:
            return candidate
        suffix = secrets.token_hex(4)
        candidate = f"{base}-{suffix}"
    return f"{base}-{secrets.token_hex(8)}"
