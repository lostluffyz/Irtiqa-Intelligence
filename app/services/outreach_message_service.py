from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.outreach_message import OutreachMessage
from app.repositories.outreach_message_repository import OutreachMessageRepository
from app.services.base import BaseService


class OutreachMessageService(BaseService[OutreachMessage, OutreachMessageRepository]):
    model = OutreachMessage
    repository = OutreachMessageRepository

    def create(self, organization_id: str, **values: Any) -> OutreachMessage:
        return super().create(organization_id=organization_id, **values)

    def list_by_company(self, company_id: str, *, organization_id: str, limit: int = 100) -> Sequence[OutreachMessage]:
        self._validate_identifier(company_id, field_name="company_id")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[OutreachMessage]:
            return self._repository(session).list_by_company(company_id, organization_id=organization_id, limit=limit)

        return self._run_in_transaction("list_by_company", operation)

    def list_by_contact(self, contact_id: str, *, organization_id: str, limit: int = 100) -> Sequence[OutreachMessage]:
        self._validate_identifier(contact_id, field_name="contact_id")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[OutreachMessage]:
            return self._repository(session).list_by_contact(contact_id, organization_id=organization_id, limit=limit)

        return self._run_in_transaction("list_by_contact", operation)

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[OutreachMessage]:
        self._validate_identifier(status, field_name="status")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[OutreachMessage]:
            return self._repository(session).list_by_status(status, organization_id=organization_id, limit=limit)

        return self._run_in_transaction("list_by_status", operation)
