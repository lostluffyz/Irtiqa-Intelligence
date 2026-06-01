from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.models.technology import Technology
from app.repositories.base import BaseRepository


class TechnologyRepository(BaseRepository[Technology]):
    model = Technology

    def list_by_company(self, company_id: str, *, limit: int = 100) -> Sequence[Technology]:
        statement = select(Technology).where(Technology.company_id == company_id).limit(limit)
        return self.scalars(statement)

    def get_company_technology(
        self,
        *,
        company_id: str,
        name: str,
        category: str,
    ) -> Technology | None:
        statement = select(Technology).where(
            Technology.company_id == company_id,
            Technology.name == name,
            Technology.category == category,
        )
        return self.scalar_one_or_none(statement)

    def list_by_category(self, category: str, *, limit: int = 100) -> Sequence[Technology]:
        statement = select(Technology).where(Technology.category == category).limit(limit)
        return self.scalars(statement)
