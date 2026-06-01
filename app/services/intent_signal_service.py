from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.intent_signal import IntentSignal
from app.repositories.intent_signal_repository import IntentSignalRepository
from app.services.base import BaseService


class IntentSignalService(BaseService[IntentSignal, IntentSignalRepository]):
    model = IntentSignal
    repository = IntentSignalRepository

    def list_by_company(self, company_id: str, *, limit: int = 100) -> Sequence[IntentSignal]:
        self._validate_identifier(company_id, field_name="company_id")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[IntentSignal]:
            return self._repository(session).list_by_company(company_id, limit=limit)

        return self._run_in_transaction("list_by_company", operation)

    def list_by_contact(self, contact_id: str, *, limit: int = 100) -> Sequence[IntentSignal]:
        self._validate_identifier(contact_id, field_name="contact_id")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[IntentSignal]:
            return self._repository(session).list_by_contact(contact_id, limit=limit)

        return self._run_in_transaction("list_by_contact", operation)

    def list_by_type(self, signal_type: str, *, limit: int = 100) -> Sequence[IntentSignal]:
        self._validate_identifier(signal_type, field_name="signal_type")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[IntentSignal]:
            return self._repository(session).list_by_type(signal_type, limit=limit)

        return self._run_in_transaction("list_by_type", operation)
