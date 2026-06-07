from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.agents.base import AgentRunOutput, BaseAgent
from app.agents.context import AgentContext
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.technology import Technology
from app.services.company_service import CompanyService
from app.services.contact_service import ContactService
from app.services.intelligence_score_service import IntelligenceScoreService
from app.services.intent_signal_service import IntentSignalService
from app.services.technology_service import TechnologyService
from app.schemas.intelligence_score import IntelligenceScoreCreate
from app.workflows.scoring_policy import DeterministicScoreRefreshPolicy, ScoreRefreshInput

logger = logging.getLogger("irtiqa.agents.intelligence_scoring")


class IntelligenceScoringAgent(BaseAgent):
    """
    Agent that aggregates data from Company, Contact, Technologies, and Intent Signals
    and computes an Intelligence Score using the deterministic scoring policy.
    """

    name = "intelligence_scoring_agent"
    version = "1.0.0"

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        logger.info(
            "IntelligenceScoringAgent started",
            extra={"company_id": context.company_id, "contact_id": context.contact_id},
        )

        # 1. Resolve Services
        company_service = self._service("company_service", CompanyService)
        contact_service = self._service("contact_service", ContactService)
        technology_service = self._service("technology_service", TechnologyService)
        intent_signal_service = self._service("intent_signal_service", IntentSignalService)
        intelligence_score_service = self._service("intelligence_score_service", IntelligenceScoreService)

        # 2. Fetch Data
        company: Company | None = company_service.get(context.company_id)
        if not company:
            raise ValueError(f"Company {context.company_id} not found.")

        contact: Contact | None = None
        if context.contact_id:
            contact = contact_service.get(context.contact_id)
            if not contact:
                raise ValueError(f"Contact {context.contact_id} not found.")

        technologies: list[Technology] = technology_service.list_by_company(context.company_id)
        
        # We fetch intent signals for the company. If contact_id is present, we could filter by it,
        # but the scoring policy typically uses all intent signals for the company/contact context.
        intent_signals: list[IntentSignal] = intent_signal_service.list_by_company(context.company_id)
        if contact:
            # Optionally, we might merge contact-specific signals here if the service structure allowed,
            # but list_by_company gets the company level. Let's get contact level signals too if they exist.
            contact_signals = intent_signal_service.list_by_contact(context.contact_id)
            # Deduplicate by ID
            seen_ids = {s.id for s in intent_signals}
            for s in contact_signals:
                if s.id not in seen_ids:
                    intent_signals.append(s)
                    seen_ids.add(s.id)

        # 3. Score
        policy = DeterministicScoreRefreshPolicy()
        score_input = ScoreRefreshInput(
            company=company,
            contact=contact,
            technologies=technologies,
            intent_signals=intent_signals,
            scored_at=datetime.now(timezone.utc),
        )
        result = policy.score(score_input)

        # 4. Persist
        create_schema = IntelligenceScoreCreate(
            company_id=context.company_id,
            contact_id=context.contact_id,
            fit_score=result.fit_score,
            intent_score=result.intent_score,
            technographic_score=result.technographic_score,
            engagement_score=result.engagement_score,
            total_score=result.total_score,
            confidence=result.confidence,
            score_version=result.score_version,
            primary_technology_id=result.primary_technology_id,
            rationale=result.rationale,
            scored_at=result.scored_at,
        )
        score = intelligence_score_service.create(create_schema)

        # 5. Return mapped output IDs
        logger.info(
            "IntelligenceScoringAgent completed successfully",
            extra={"score_id": score.id, "total_score": score.total_score},
        )
        return {"intelligence_scores": [score.id]}
