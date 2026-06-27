from __future__ import annotations

from sqlalchemy import inspect

from app.models import Base
from app.models.agent_run import AgentRun
from app.models.company import Company
from app.models.contact import Contact
from app.models.discovery_run import DiscoveryRun
from app.models.discovery_search import DiscoverySearch
from app.models.email_verification_token import EmailVerificationToken
from app.models.evidence_record import EvidenceRecord
from app.models.failed_login_attempt import FailedLoginAttempt
from app.models.intent_signal import IntentSignal
from app.models.intelligence_score import IntelligenceScore
from app.models.job import Job
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.outreach_message import OutreachMessage
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.technology import Technology
from app.models.user import User
from app.models.website import Website


def test_model_metadata_contains_current_schema_tables() -> None:
    assert set(Base.metadata.tables.keys()) == {
        "agent_runs",
        "companies",
        "contacts",
        "discovery_runs",
        "discovery_searches",
        "email_verification_tokens",
        "evidence_records",
        "failed_login_attempts",
        "intelligence_scores",
        "intent_signals",
        "jobs",
        "memberships",
        "organizations",
        "outreach_messages",
        "password_reset_tokens",
        "refresh_tokens",
        "technologies",
        "users",
        "websites",
    }


def test_models_have_primary_key_and_timestamps() -> None:
    for model in (
        AgentRun,
        Company,
        Contact,
        DiscoveryRun,
        DiscoverySearch,
        EvidenceRecord,
        IntentSignal,
        IntelligenceScore,
        Membership,
        Organization,
        OutreachMessage,
        Technology,
        User,
        Website,
    ):
        columns = model.__table__.columns
        assert "id" in columns
        assert "created_at" in columns
        assert "updated_at" in columns
        assert columns["id"].primary_key


def test_company_relationships_are_declared() -> None:
    relationships = inspect(Company).relationships

    assert set(relationships.keys()) == {
        "agent_runs",
        "contacts",
        "discovery_search",
        "intent_signals",
        "intelligence_scores",
        "outreach_messages",
        "technologies",
        "websites",
    }


def test_relationships_persist_and_load(
    session,
    organization,
    company,
    contact,
    website,
    agent_run,
    technology,
    intent_signal,
    intelligence_score,
    outreach_message,
) -> None:
    session.add(organization)
    session.flush()
    session.add(company)
    session.flush()
    session.add(outreach_message)
    session.add(intent_signal)
    session.commit()

    saved_company = session.get(Company, company.id)
    saved_contact = session.get(Contact, contact.id)
    saved_score = session.get(IntelligenceScore, intelligence_score.id)

    assert saved_company is not None
    assert len(saved_company.contacts) == 1
    assert len(saved_company.websites) == 1
    assert len(saved_company.technologies) == 1
    assert len(saved_company.intent_signals) == 1
    assert len(saved_company.intelligence_scores) == 1
    assert len(saved_company.outreach_messages) == 1
    assert len(saved_company.agent_runs) == 1
    assert saved_contact is not None
    assert saved_contact.company == saved_company
    assert saved_score is not None
    assert saved_score.outreach_messages == [outreach_message]
