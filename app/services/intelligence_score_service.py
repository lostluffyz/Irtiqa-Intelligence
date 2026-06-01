from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.intelligence_score import IntelligenceScore
from app.repositories.intelligence_score_repository import IntelligenceScoreRepository
from app.services.base import BaseService


class IntelligenceScoreService(BaseService[IntelligenceScore, IntelligenceScoreRepository]):
    model = IntelligenceScore
    repository = IntelligenceScoreRepository

    def latest_for_company(self, company_id: str) -> IntelligenceScore | None:
        self._validate_identifier(company_id, field_name="company_id")

        def operation(session: Session) -> IntelligenceScore | None:
            return self._repository(session).latest_for_company(company_id)

        return self._run_in_transaction("latest_for_company", operation)

    def latest_for_contact(self, contact_id: str) -> IntelligenceScore | None:
        self._validate_identifier(contact_id, field_name="contact_id")

        def operation(session: Session) -> IntelligenceScore | None:
            return self._repository(session).latest_for_contact(contact_id)

        return self._run_in_transaction("latest_for_contact", operation)

    def latest_for_target(self, *, company_id: str, contact_id: str | None = None) -> IntelligenceScore | None:
        self._validate_identifier(company_id, field_name="company_id")
        if contact_id is not None:
            self._validate_identifier(contact_id, field_name="contact_id")

        def operation(session: Session) -> IntelligenceScore | None:
            return self._repository(session).latest_for_target(
                company_id=company_id,
                contact_id=contact_id,
            )

        return self._run_in_transaction("latest_for_target", operation)

    def list_top_scores(self, *, limit: int = 100) -> Sequence[IntelligenceScore]:
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[IntelligenceScore]:
            return self._repository(session).list_top_scores(limit=limit)

        return self._run_in_transaction("list_top_scores", operation)
