from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import EntityConflictError
from app.models.contact import Contact
from app.repositories.contact_repository import ContactRepository
from app.services.base import BaseService


class ContactService(BaseService[Contact, ContactRepository]):
    model = Contact
    repository = ContactRepository

    def get_by_email(self, email: str) -> Contact | None:
        self._validate_identifier(email, field_name="email")

        def operation(session: Session) -> Contact | None:
            return self._repository(session).get_by_email(email)

        return self._run_in_transaction("get_by_email", operation)

    def list_by_company(self, company_id: str, *, limit: int = 100) -> Sequence[Contact]:
        self._validate_identifier(company_id, field_name="company_id")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[Contact]:
            return self._repository(session).list_by_company(company_id, limit=limit)

        return self._run_in_transaction("list_by_company", operation)

    def list_by_status(self, status: str, *, limit: int = 100) -> Sequence[Contact]:
        self._validate_identifier(status, field_name="status")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[Contact]:
            return self._repository(session).list_by_status(status, limit=limit)

        return self._run_in_transaction("list_by_status", operation)

    def _before_create(self, repository: ContactRepository, values: dict[str, Any]) -> None:
        email = values.get("email")
        if isinstance(email, str) and repository.get_by_email(email) is not None:
            raise EntityConflictError(
                "A contact with this email already exists.",
                details={"service": self.__class__.__name__, "email": email},
            )
