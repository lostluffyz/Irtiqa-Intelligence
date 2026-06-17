from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import desc, select

from app.models.intelligence_score import IntelligenceScore
from app.repositories.base import BaseRepository


class IntelligenceScoreRepository(BaseRepository[IntelligenceScore]):
    model = IntelligenceScore

    def latest_for_company(self, company_id: str, *, organization_id: str) -> IntelligenceScore | None:
        statement = select(IntelligenceScore).where(IntelligenceScore.company_id == company_id)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalar_one_or_none(statement.order_by(desc(IntelligenceScore.scored_at)).limit(1))

    def latest_for_contact(self, contact_id: str, *, organization_id: str) -> IntelligenceScore | None:
        statement = select(IntelligenceScore).where(IntelligenceScore.contact_id == contact_id)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalar_one_or_none(statement.order_by(desc(IntelligenceScore.scored_at)).limit(1))

    def latest_for_target(self, *, company_id: str, organization_id: str, contact_id: str | None = None) -> IntelligenceScore | None:
        statement = select(IntelligenceScore).where(IntelligenceScore.company_id == company_id)
        if contact_id is None:
            statement = statement.where(IntelligenceScore.contact_id.is_(None))
        else:
            statement = statement.where(IntelligenceScore.contact_id == contact_id)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalar_one_or_none(statement.order_by(desc(IntelligenceScore.scored_at)).limit(1))

    def list_top_scores(self, *, organization_id: str | None = None, limit: int = 100) -> Sequence[IntelligenceScore]:
        """Org-scoped by default. Pass organization_id=None to get global top scores."""
        statement = select(IntelligenceScore).order_by(desc(IntelligenceScore.total_score))
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement.limit(limit))
