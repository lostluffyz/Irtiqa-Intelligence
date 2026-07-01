from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    model = Company

    def get_by_domain(self, domain: str, organization_id: str) -> Company | None:
        statement = select(Company).where(Company.domain == domain)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalar_one_or_none(statement)

    def get_existing_domains(self, domains: list[str], organization_id: str) -> set[str]:
        """Batch-check which domains already exist for the organization."""
        if not domains:
            return set()
        statement = select(Company.domain).where(Company.domain.in_(domains))
        statement = self._apply_tenant_filter(statement, organization_id)
        existing = self.session.execute(statement).scalars().all()
        return set(existing)

    def search_by_name(self, name: str, *, organization_id: str, limit: int = 50) -> Sequence[Company]:
        statement = select(Company).where(Company.name.ilike(f"%{name}%"))
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[Company]:
        statement = select(Company).where(Company.status == status)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))

    def count_by_organization(self, organization_id: str) -> int:
        """Count companies belonging to a specific organization."""
        statement = select(func.count()).select_from(Company)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.session.scalar(statement) or 0
