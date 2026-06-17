from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    model = Company

    def get_by_domain(self, domain: str, organization_id: str) -> Company | None:
        statement = select(Company).where(Company.domain == domain)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalar_one_or_none(statement)

    def search_by_name(self, name: str, *, organization_id: str, limit: int = 50) -> Sequence[Company]:
        statement = select(Company).where(Company.name.ilike(f"%{name}%"))
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[Company]:
        statement = select(Company).where(Company.status == status)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))
