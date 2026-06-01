from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import desc, select

from app.models.intelligence_score import IntelligenceScore
from app.repositories.base import BaseRepository


class IntelligenceScoreRepository(BaseRepository[IntelligenceScore]):
    model = IntelligenceScore

    def latest_for_company(self, company_id: str) -> IntelligenceScore | None:
        statement = (
            select(IntelligenceScore)
            .where(IntelligenceScore.company_id == company_id)
            .order_by(desc(IntelligenceScore.scored_at))
            .limit(1)
        )
        return self.scalar_one_or_none(statement)

    def latest_for_contact(self, contact_id: str) -> IntelligenceScore | None:
        statement = (
            select(IntelligenceScore)
            .where(IntelligenceScore.contact_id == contact_id)
            .order_by(desc(IntelligenceScore.scored_at))
            .limit(1)
        )
        return self.scalar_one_or_none(statement)

    def latest_for_target(self, *, company_id: str, contact_id: str | None = None) -> IntelligenceScore | None:
        statement = select(IntelligenceScore).where(IntelligenceScore.company_id == company_id)
        if contact_id is None:
            statement = statement.where(IntelligenceScore.contact_id.is_(None))
        else:
            statement = statement.where(IntelligenceScore.contact_id == contact_id)
        statement = statement.order_by(desc(IntelligenceScore.scored_at)).limit(1)
        return self.scalar_one_or_none(statement)

    def list_top_scores(self, *, limit: int = 100) -> Sequence[IntelligenceScore]:
        statement = select(IntelligenceScore).order_by(desc(IntelligenceScore.total_score)).limit(limit)
        return self.scalars(statement)
