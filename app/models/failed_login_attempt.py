from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin


class FailedLoginAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "failed_login_attempts"
    __table_args__ = (
        Index("ix_failed_login_attempts_email_attempted", "email", "attempted_at"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
