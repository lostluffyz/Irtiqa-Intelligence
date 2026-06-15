from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')",
            name="role",
        ),
        Index(
            "ix_memberships_user_org",
            "user_id",
            "organization_id",
            unique=True,
        ),
        Index("ix_memberships_organization_id", "organization_id"),
        Index("ix_memberships_user_id", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="member",
    )

    # back_populates on user will be added in Phase 2 when User.memberships
    # is introduced alongside auth integration.
    user: Mapped[User] = relationship()
    organization: Mapped[Organization] = relationship(back_populates="memberships")
