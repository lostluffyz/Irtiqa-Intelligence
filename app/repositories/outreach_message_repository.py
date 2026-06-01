from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import desc, select

from app.models.outreach_message import OutreachMessage
from app.repositories.base import BaseRepository


class OutreachMessageRepository(BaseRepository[OutreachMessage]):
    model = OutreachMessage

    def list_by_company(self, company_id: str, *, limit: int = 100) -> Sequence[OutreachMessage]:
        statement = (
            select(OutreachMessage)
            .where(OutreachMessage.company_id == company_id)
            .order_by(desc(OutreachMessage.generated_at))
            .limit(limit)
        )
        return self.scalars(statement)

    def list_by_contact(self, contact_id: str, *, limit: int = 100) -> Sequence[OutreachMessage]:
        statement = (
            select(OutreachMessage)
            .where(OutreachMessage.contact_id == contact_id)
            .order_by(desc(OutreachMessage.generated_at))
            .limit(limit)
        )
        return self.scalars(statement)

    def list_by_status(self, status: str, *, limit: int = 100) -> Sequence[OutreachMessage]:
        statement = select(OutreachMessage).where(OutreachMessage.status == status).limit(limit)
        return self.scalars(statement)
