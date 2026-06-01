from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    model = Company

    def get_by_domain(self, domain: str) -> Company | None:
        statement = select(Company).where(Company.domain == domain)
        return self.scalar_one_or_none(statement)

    def search_by_name(self, name: str, *, limit: int = 50) -> Sequence[Company]:
        statement = select(Company).where(Company.name.ilike(f"%{name}%")).limit(limit)
        return self.scalars(statement)

    def list_by_status(self, status: str, *, limit: int = 100) -> Sequence[Company]:
        statement = select(Company).where(Company.status == status).limit(limit)
        return self.scalars(statement)
