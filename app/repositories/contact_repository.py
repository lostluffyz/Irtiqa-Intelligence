from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.models.contact import Contact
from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    model = Contact

    def get_by_email(self, email: str) -> Contact | None:
        statement = select(Contact).where(Contact.email == email)
        return self.scalar_one_or_none(statement)

    def list_by_company(self, company_id: str, *, limit: int = 100) -> Sequence[Contact]:
        statement = select(Contact).where(Contact.company_id == company_id).limit(limit)
        return self.scalars(statement)

    def list_by_status(self, status: str, *, limit: int = 100) -> Sequence[Contact]:
        statement = select(Contact).where(Contact.status == status).limit(limit)
        return self.scalars(statement)
