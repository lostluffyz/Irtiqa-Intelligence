from __future__ import annotations

import pytest

from app.models.evidence_record import (
    TARGET_TYPE_INTELLIGENCE_SCORE,
)
from app.repositories.evidence_repository import EvidenceRepository
from app.services.evidence_service import EvidenceService
from app.workflows.context import WorkflowContext
from app.workflows.score_refresh import ScoreRefreshWorkflow
from app.workflows.states import WorkflowStatus


def test_score_refresh_creates_evidence(session) -> None:
    """Score refresh workflow creates evidence records linking the score
    to contributing technologies and intent signals."""
    # Seed: need a company with technologies and intent signals
    from app.models.company import Company
    from app.models.contact import Contact
    from app.models.technology import Technology
    from app.models.intent_signal import IntentSignal
    from app.models.agent_run import AgentRun
    from app.models.website import Website
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    company = Company(
        name="Evidence Test Co",
        domain="evidence-test.example",
        industry="software",
        company_size="11-50",
        status="active",
    )
    session.add(company)
    session.flush()

    contact = Contact(
        company_id=company.id,
        full_name="Evidence Contact",
        email="evidence@test.example",
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(contact)
    session.flush()

    website = Website(
        company_id=company.id,
        url="https://evidence-test.example",
        normalized_url="https://evidence-test.example/",
        page_type="homepage",
        http_status=200,
        last_scraped_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(website)
    session.flush()
    website_id = website.id
    agent_run_ref = AgentRun(
        company_id=company.id,
        contact_id=contact.id,
        agent_name="test_setup",
        status="succeeded",
        started_at=now,
        finished_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(agent_run_ref)
    session.flush()

    tech = Technology(
        company_id=company.id,
        website_id=website_id,
        agent_run_id=agent_run_ref.id,
        name="TestCRM",
        category="crm",
        detection_method="html_signature",
        confidence=0.92,
        first_detected_at=now,
        last_detected_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(tech)
    session.flush()

    signal = IntentSignal(
        company_id=company.id,
        contact_id=contact.id,
        website_id=website_id,
        technology_id=tech.id,
        agent_run_id=agent_run_ref.id,
        signal_type="technology_change",
        signal_name="CRM detected",
        strength=0.75,
        confidence=0.88,
        source_url="https://test.example",
        observed_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(signal)
    session.commit()

    # Run score_refresh workflow
    workflow = ScoreRefreshWorkflow(
        company_service=None,
        contact_service=None,
        technology_service=None,
        intent_signal_service=None,
        intelligence_score_service=None,
        agent_run_service=None,
    )

    # The workflow needs proper service instances
    from app.services.company_service import CompanyService
    from app.services.contact_service import ContactService
    from app.services.technology_service import TechnologyService
    from app.services.intent_signal_service import IntentSignalService
    from app.services.intelligence_score_service import IntelligenceScoreService
    from app.services.agent_run_service import AgentRunService

    # Override SessionLocal for service layer
    from sqlalchemy.orm import sessionmaker
    from app.database import session as database_session

    SessionClass = sessionmaker(
        bind=session.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=type(session),
    )
    original_factory = database_session.SessionLocal
    database_session.SessionLocal = SessionClass

    try:
        workflow = ScoreRefreshWorkflow(
            company_service=CompanyService(),
            contact_service=ContactService(),
            technology_service=TechnologyService(),
            intent_signal_service=IntentSignalService(),
            intelligence_score_service=IntelligenceScoreService(),
            agent_run_service=AgentRunService(),
        )
        context = WorkflowContext(
            workflow_name="score_refresh",
            company_id=company.id,
            contact_id=contact.id,
            options={"intent_lookback_days": 365},
        )
        result = workflow.execute(context)

        assert result.status == WorkflowStatus.SUCCEEDED
        assert "intelligence_scores" in result.output_ids
        score_id = result.output_ids["intelligence_scores"][0]

        # Verify evidence was created for the score
        evidence_service = EvidenceService()
        evidence_records = evidence_service.get_target_evidence(
            TARGET_TYPE_INTELLIGENCE_SCORE, score_id,
        )
        assert len(evidence_records) >= 2, (
            f"Expected at least 2 evidence records (technology + signal), "
            f"got {len(evidence_records)}"
        )

        evidence_types = {r.evidence_type for r in evidence_records}
        assert "computed_metric" in evidence_types
    finally:
        database_session.SessionLocal = original_factory
