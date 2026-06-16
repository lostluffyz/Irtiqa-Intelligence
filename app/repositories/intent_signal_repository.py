from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import desc, select

from app.models.intent_signal import IntentSignal
from app.repositories.base import BaseRepository


class IntentSignalRepository(BaseRepository[IntentSignal]):
    model = IntentSignal

    def list_by_company(self, company_id: str, *, organization_id: str, limit: int = 100) -> Sequence[IntentSignal]:
        statement = (
            select(IntentSignal)
            .where(IntentSignal.company_id == company_id)
            .order_by(desc(IntentSignal.observed_at))
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_contact(self, contact_id: str, *, organization_id: str, limit: int = 100) -> Sequence[IntentSignal]:
        statement = (
            select(IntentSignal)
            .where(IntentSignal.contact_id == contact_id)
            .order_by(desc(IntentSignal.observed_at))
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_type(self, signal_type: str, *, organization_id: str, limit: int = 100) -> Sequence[IntentSignal]:
        statement = (
            select(IntentSignal)
            .where(IntentSignal.signal_type == signal_type)
            .order_by(desc(IntentSignal.observed_at))
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))
