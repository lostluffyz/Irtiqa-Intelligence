from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.agents.base import AgentRunOutput, BaseAgent
from app.agents.context import AgentContext
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.intelligence_score import IntelligenceScore
from app.models.technology import Technology
from app.schemas.outreach_message import OutreachMessageCreate
from app.services.company_service import CompanyService
from app.services.contact_service import ContactService
from app.services.intelligence_score_service import IntelligenceScoreService
from app.services.intent_signal_service import IntentSignalService
from app.services.outreach_message_service import OutreachMessageService
from app.services.technology_service import TechnologyService

from app.agents.personalization.templates import (
    TemplateContext,
    get_template_for_angle,
    render_template,
)

logger = logging.getLogger("irtiqa.agents.personalization")


class PersonalizationAgent(BaseAgent):
    """
    Agent that aggregates data from Company, Contact, Technologies, Intent Signals,
    and Intelligence Scores to generate tailored outreach message variants.
    """

    name = "personalization_agent"
    version = "1.0.0"

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        logger.info(
            "PersonalizationAgent started",
            extra={"company_id": context.company_id, "contact_id": context.contact_id},
        )

        # 1. Resolve Services
        company_service = self._service("company_service", CompanyService)
        contact_service = self._service("contact_service", ContactService)
        technology_service = self._service("technology_service", TechnologyService)
        intent_signal_service = self._service("intent_signal_service", IntentSignalService)
        intelligence_score_service = self._service("intelligence_score_service", IntelligenceScoreService)
        outreach_message_service = self._service("outreach_message_service", OutreachMessageService)

        # 2. Fetch Data
        company: Company | None = company_service.get(context.company_id)
        if not company:
            raise ValueError(f"Company {context.company_id} not found.")

        contact: Contact | None = None
        if context.contact_id:
            contact = contact_service.get(context.contact_id)

        technologies: list[Technology] = technology_service.list_by_company(context.company_id)
        intent_signals: list[IntentSignal] = intent_signal_service.list_by_company(context.company_id, organization_id=context.organization_id)
        if contact:
            contact_signals = intent_signal_service.list_by_contact(contact.id, organization_id=context.organization_id)
            seen_ids = {s.id for s in intent_signals}
            for s in contact_signals:
                if s.id not in seen_ids:
                    intent_signals.append(s)
                    seen_ids.add(s.id)

        # Fetch latest intelligence score
        latest_score: IntelligenceScore | None = intelligence_score_service.latest_for_company(
            context.company_id, organization_id=context.organization_id,
        )

        # 3. Angle Selector
        primary_angle = "fit_driven"
        secondary_angle = "fit_driven"
        confidence = 0.5
        score_id = None

        if latest_score:
            score_id = latest_score.id
            confidence = latest_score.confidence
            
            intent_val = latest_score.intent_score
            tech_val = latest_score.technographic_score
            fit_val = latest_score.fit_score
            
            # Determine primary angle
            if intent_val >= tech_val and intent_val >= fit_val and intent_val > 0:
                primary_angle = "intent_driven"
                secondary_angle = "tech_driven" if tech_val > fit_val else "fit_driven"
            elif tech_val >= intent_val and tech_val >= fit_val and tech_val > 0:
                primary_angle = "tech_driven"
                secondary_angle = "intent_driven" if intent_val > fit_val else "fit_driven"
            else:
                primary_angle = "fit_driven"
                secondary_angle = "intent_driven" if intent_val > tech_val else "tech_driven"

        # Safe fallbacks if data is missing despite the angle
        if primary_angle == "intent_driven" and not intent_signals:
            primary_angle = "fit_driven"
        if primary_angle == "tech_driven" and not technologies:
            primary_angle = "fit_driven"
        if secondary_angle == "intent_driven" and not intent_signals:
            secondary_angle = "fit_driven"
        if secondary_angle == "tech_driven" and not technologies:
            secondary_angle = "fit_driven"

        # 4. Map Context Data
        top_tech = technologies[0] if technologies else None
        top_intent = intent_signals[0] if intent_signals else None

        template_context: TemplateContext = {
            "company_name": company.name,
            "contact_first_name": contact.first_name if contact and contact.first_name else "there",
            "industry": company.industry if company.industry else "your industry",
            "domain": company.domain,
            "technology_name": top_tech.name if top_tech else "your current stack",
            "intent_signal_summary": top_intent.signal_type if top_intent else "recent positive momentum",
        }

        # 5. Generate Variants
        variants_to_generate = [
            ("email", primary_angle, "Primary"),
            ("email", secondary_angle, "Secondary"),
            ("linkedin", "fit_driven", "LinkedIn"), # Default LinkedIn to fit_driven or primary? Let's use primary.
        ]
        
        # Override LinkedIn to use the primary angle to stay relevant
        variants_to_generate[2] = ("linkedin", primary_angle, "LinkedIn")

        output_ids = []
        now = datetime.now(timezone.utc)

        for channel, angle, variant_name in variants_to_generate:
            raw_template = get_template_for_angle(angle, channel)
            rendered = render_template(raw_template, template_context)

            create_schema = OutreachMessageCreate(
                company_id=company.id,
                contact_id=contact.id if contact else None,
                intelligence_score_id=score_id,
                channel=channel,
                subject=rendered.get("subject"),
                message_body=rendered["message_body"],
                personalization_angle=f"{angle}_{variant_name.lower()}",
                call_to_action=rendered.get("call_to_action"),
                status="draft",
                confidence=confidence,
                generated_at=now,
            )
            
            created_message = outreach_message_service.create(organization_id=context.organization_id, **create_schema.model_dump())
            output_ids.append(created_message.id)

        # 6. Return mapped output IDs
        logger.info(
            "PersonalizationAgent completed successfully",
            extra={"outreach_messages_count": len(output_ids)},
        )
        return AgentRunOutput(
            output_ids={"outreach_messages": output_ids},
            summary=f"Generated {len(output_ids)} personalization variants.",
            stats={
                "primary_angle": primary_angle,
                "secondary_angle": secondary_angle,
                "variants_created": len(output_ids),
            },
        )
