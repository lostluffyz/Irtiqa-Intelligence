from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.intent_signal import IntentSignal
    from app.models.technology import Technology


class Website(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "websites"
    __table_args__ = (
        Index("ix_websites_normalized_url", "normalized_url", unique=True),
        Index("ix_websites_company_id", "company_id"),
        Index("ix_websites_page_type", "page_type"),
        Index("ix_websites_http_status", "http_status"),
        Index("ix_websites_last_scraped_at", "last_scraped_at"),
    )

    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    page_type: Mapped[str | None] = mapped_column(String(100))
    http_status: Mapped[int | None] = mapped_column(Integer)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_html: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str | None] = mapped_column(Text)

    company: Mapped[Company] = relationship(back_populates="websites")
    technologies: Mapped[list[Technology]] = relationship(back_populates="website")
    intent_signals: Mapped[list[IntentSignal]] = relationship(back_populates="website")
