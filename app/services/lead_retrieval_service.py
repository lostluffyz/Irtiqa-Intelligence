from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database import session as database_session
from app.models.company import Company
from app.models.intent_signal import IntentSignal
from app.models.intelligence_score import IntelligenceScore
from app.models.outreach_message import OutreachMessage
from app.models.technology import Technology
from app.repositories.company_repository import CompanyRepository
from app.schemas.lead import (
    LeadIntelligenceScoreResponse,
    LeadIntentSignalResponse,
    LeadListResponse,
    LeadOutreachMessageResponse,
    LeadResponse,
    LeadTechnologyResponse,
)


logger = get_logger("services.LeadRetrievalService")


class LeadRetrievalService:
    """Retrieves aggregated lead intelligence for companies within an organization.

    This service does not extend ``BaseService`` because it performs read-only
    aggregation queries across multiple tables rather than single-entity CRUD.
    It owns its own transaction boundary through ``session_scope()``.
    """

    def __init__(self) -> None:
        self.logger = logger

    def get_leads(
        self,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
        minimum_score: float | None = None,
    ) -> LeadListResponse:
        """Retrieve aggregated lead intelligence for the given organization.

        Returns companies along with their technologies, intent signals,
        latest intelligence score, and outreach messages.
        """
        self._validate_params(limit=limit, offset=offset, minimum_score=minimum_score)

        try:
            with database_session.session_scope() as session:
                self.logger.debug(
                    "Retrieving leads",
                    extra={
                        "organization_id": organization_id,
                        "limit": limit,
                        "offset": offset,
                        "minimum_score": minimum_score,
                    },
                )

                # 1. Get companies for this organization (paginated)
                company_repo = CompanyRepository(session)
                companies = company_repo.list(
                    organization_id=organization_id,
                    limit=limit,
                    offset=offset,
                )
                total = company_repo.count_by_organization(organization_id)

                if not companies:
                    return LeadListResponse(
                        items=[],
                        total=total,
                        limit=limit,
                        offset=offset,
                    )

                company_ids = [c.id for c in companies]

                # 2. Batch-fetch related entities for all companies in the page
                technologies_by_company = self._fetch_technologies(session, company_ids)
                intent_signals_by_company = self._fetch_intent_signals(session, company_ids)
                scores_by_company = self._fetch_latest_scores(session, company_ids)
                messages_by_company = self._fetch_outreach_messages(session, company_ids)

                # 3. Apply minimum_score filter (if specified) after fetching
                if minimum_score is not None:
                    companies = self._apply_score_filter(
                        companies, scores_by_company, minimum_score
                    )

                # 4. Build aggregated lead responses
                leads = []
                for company in companies:
                    lead = self._build_lead(
                        company=company,
                        technologies=technologies_by_company.get(company.id, []),
                        intent_signals=intent_signals_by_company.get(company.id, []),
                        score=scores_by_company.get(company.id),
                        outreach_messages=messages_by_company.get(company.id, []),
                    )
                    leads.append(lead)

                self.logger.debug(
                    "Retrieved leads",
                    extra={
                        "organization_id": organization_id,
                        "leads_count": len(leads),
                        "total": total,
                    },
                )

                return LeadListResponse(
                    items=leads,
                    total=total,
                    limit=limit,
                    offset=offset,
                )

        except Exception as exc:
            from app.core.errors import ServiceError

            error = ServiceError(
                "Failed to retrieve leads.",
                details={
                    "service": "LeadRetrievalService",
                    "operation": "get_leads",
                    "organization_id": organization_id,
                },
                cause=exc,
            )
            error.log(self.logger, include_traceback=True)
            raise error from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_technologies(
        self, session: Session, company_ids: list[str]
    ) -> dict[str, list[Technology]]:
        """Fetch technologies grouped by company_id in a single query."""
        statement = (
            select(Technology)
            .where(Technology.company_id.in_(company_ids))
            .order_by(Technology.name)
        )
        results = session.scalars(statement).all()

        grouped: dict[str, list[Technology]] = defaultdict(list)
        for tech in results:
            grouped[tech.company_id].append(tech)
        return dict(grouped)

    def _fetch_intent_signals(
        self, session: Session, company_ids: list[str]
    ) -> dict[str, list[IntentSignal]]:
        """Fetch intent signals grouped by company_id in a single query."""
        statement = (
            select(IntentSignal)
            .where(IntentSignal.company_id.in_(company_ids))
            .order_by(desc(IntentSignal.observed_at))
        )
        results = session.scalars(statement).all()

        grouped: dict[str, list[IntentSignal]] = defaultdict(list)
        for signal in results:
            grouped[signal.company_id].append(signal)
        return dict(grouped)

    def _fetch_latest_scores(
        self, session: Session, company_ids: list[str]
    ) -> dict[str, IntelligenceScore]:
        """Fetch the latest intelligence score for each company.

        Uses a subquery to find the max ``scored_at`` per company, then
        joins back to get the full row. This avoids N+1 while still
        returning only one score per company.
        """
        from sqlalchemy import func

        # Subquery: latest scored_at per company
        subq = (
            select(
                IntelligenceScore.company_id,
                func.max(IntelligenceScore.scored_at).label("latest_scored_at"),
            )
            .where(IntelligenceScore.company_id.in_(company_ids))
            .group_by(IntelligenceScore.company_id)
            .subquery()
        )

        # Join to get the full score row
        statement = (
            select(IntelligenceScore)
            .join(
                subq,
                (IntelligenceScore.company_id == subq.c.company_id)
                & (IntelligenceScore.scored_at == subq.c.latest_scored_at),
            )
            .where(IntelligenceScore.company_id.in_(company_ids))
        )

        results = session.scalars(statement).all()
        return {score.company_id: score for score in results}

    def _fetch_outreach_messages(
        self, session: Session, company_ids: list[str]
    ) -> dict[str, list[OutreachMessage]]:
        """Fetch outreach messages grouped by company_id in a single query."""
        statement = (
            select(OutreachMessage)
            .where(OutreachMessage.company_id.in_(company_ids))
            .order_by(desc(OutreachMessage.generated_at))
        )
        results = session.scalars(statement).all()

        grouped: dict[str, list[OutreachMessage]] = defaultdict(list)
        for message in results:
            grouped[message.company_id].append(message)
        return dict(grouped)

    def _apply_score_filter(
        self,
        companies: Sequence[Company],
        scores_by_company: dict[str, IntelligenceScore],
        minimum_score: float,
    ) -> list[Company]:
        """Filter companies to those with a score >= minimum_score.

        Companies without a score are excluded from the results.
        """
        filtered = []
        for company in companies:
            score = scores_by_company.get(company.id)
            if score is not None and score.total_score >= minimum_score:
                filtered.append(company)
        return filtered

    def _build_lead(
        self,
        company: Company,
        technologies: Sequence[Technology],
        intent_signals: Sequence[IntentSignal],
        score: IntelligenceScore | None,
        outreach_messages: Sequence[OutreachMessage],
    ) -> LeadResponse:
        """Build an aggregated LeadResponse from fetched entities."""
        tech_responses = [
            LeadTechnologyResponse(name=t.name, category=t.category)
            for t in technologies
        ]

        signal_responses = [
            LeadIntentSignalResponse(signal_type=s.signal_type, confidence=s.confidence)
            for s in intent_signals
        ]

        score_response = None
        if score is not None:
            score_response = LeadIntelligenceScoreResponse(
                total_score=score.total_score,
                opportunity_score=score.fit_score,
                urgency_score=score.intent_score,
            )

        message_responses = [
            LeadOutreachMessageResponse(
                channel=m.channel,
                subject=m.subject,
                message_body=m.message_body,
            )
            for m in outreach_messages
        ]

        # Use updated_at from the company record as the lead's updated_at
        updated_at = company.updated_at

        return LeadResponse(
            company_id=company.id,
            company_name=company.name,
            domain=company.domain,
            industry=company.industry,
            status=company.status,
            technologies=tech_responses,
            intent_signals=signal_responses,
            latest_intelligence_score=score_response,
            outreach_messages=message_responses,
            updated_at=updated_at,
        )

    def _validate_params(
        self,
        *,
        limit: int,
        offset: int,
        minimum_score: float | None,
    ) -> None:
        """Validate query parameters."""
        from app.core.errors import ValidationError

        if limit < 1 or limit > 500:
            raise ValidationError(
                "Limit must be between 1 and 500.",
                details={"service": "LeadRetrievalService", "limit": limit},
            )
        if offset < 0:
            raise ValidationError(
                "Offset must be greater than or equal to 0.",
                details={"service": "LeadRetrievalService", "offset": offset},
            )
        if minimum_score is not None and (minimum_score < 0.0 or minimum_score > 100.0):
            raise ValidationError(
                "minimum_score must be between 0.0 and 100.0.",
                details={"service": "LeadRetrievalService", "minimum_score": minimum_score},
            )
