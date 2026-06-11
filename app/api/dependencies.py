from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import SessionLocal
from app.services import (
    AgentRunService,
    CompanyService,
    ContactService,
    EvidenceService,
    IntelligenceScoreService,
    IntentSignalService,
    JobService,
    OutreachMessageService,
    TechnologyService,
    WebsiteService,
)


def get_app_settings() -> Settings:
    return get_settings()


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_company_service() -> CompanyService:
    return CompanyService()


def get_contact_service() -> ContactService:
    return ContactService()


def get_website_service() -> WebsiteService:
    return WebsiteService()


def get_technology_service() -> TechnologyService:
    return TechnologyService()


def get_intent_signal_service() -> IntentSignalService:
    return IntentSignalService()


def get_intelligence_score_service() -> IntelligenceScoreService:
    return IntelligenceScoreService()


def get_outreach_message_service() -> OutreachMessageService:
    return OutreachMessageService()


def get_agent_run_service() -> AgentRunService:
    return AgentRunService()


def get_job_service() -> JobService:
    return JobService()


def get_evidence_service() -> EvidenceService:
    return EvidenceService()
