from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DatabaseSettings
from app.database import session as database_session
from app.database.engine import create_database_engine
from app.models import Base
from app.models.agent_run import AgentRun
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.intelligence_score import IntelligenceScore
from app.models.job import Job
from app.models.outreach_message import OutreachMessage
from app.models.technology import Technology
from app.models.website import Website
from app.repositories import (
    AgentRunRepository,
    CompanyRepository,
    ContactRepository,
    IntelligenceScoreRepository,
    IntentSignalRepository,
    OutreachMessageRepository,
    TechnologyRepository,
    WebsiteRepository,
)
from app.services import (
    AgentRunService,
    CompanyService,
    ContactService,
    IntelligenceScoreService,
    IntentSignalService,
    OutreachMessageService,
    TechnologyService,
    WebsiteService,
)
from tests.conftest import postgresql_required


EXPECTED_TABLES = {
    "agent_runs",
    "companies",
    "contacts",
    "intelligence_scores",
    "intent_signals",
    "jobs",
    "outreach_messages",
    "technologies",
    "websites",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Data cleanup ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_postgresql_data(postgresql_engine: Engine) -> None:
    with postgresql_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())


# ─── Engine ─────────────────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_engine_uses_queue_pool() -> None:
    database_url = "postgresql+psycopg://postgres:62869@localhost:5432/irtiqa_verify_20260610"
    engine = create_database_engine(DatabaseSettings(
        url=database_url,
        echo=False,
        pool_pre_ping=True,
        sqlite_foreign_keys=False,
        sqlite_journal_mode="",
        sqlite_busy_timeout_ms=0,
    ))
    try:
        assert engine.pool.__class__.__name__ == "QueuePool"
        assert engine.pool.size() == 5
        assert engine.pool._max_overflow == 10
    finally:
        engine.dispose()


@postgresql_required
def test_postgresql_engine_skips_sqlite_pragmas(postgresql_engine: Engine) -> None:
    with postgresql_engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1


# ─── Migrations ─────────────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_migration_creates_expected_tables(postgresql_engine: Engine) -> None:
    inspector = inspect(postgresql_engine)
    actual_tables = set(inspector.get_table_names())
    assert actual_tables >= EXPECTED_TABLES | {"alembic_version"}


@postgresql_required
def test_postgresql_migration_schema_matches_metadata(postgresql_engine: Engine) -> None:
    inspector = inspect(postgresql_engine)
    for table_name in EXPECTED_TABLES:
        db_cols = {c["name"] for c in inspector.get_columns(table_name)}
        model_cols = set(Base.metadata.tables[table_name].columns.keys())
        assert db_cols == model_cols, f"Mismatch in {table_name}: {db_cols.symmetric_difference(model_cols)}"


@postgresql_required
def test_postgresql_check_constraints_exist(postgresql_engine: Engine) -> None:
    inspector = inspect(postgresql_engine)
    expected = {
        "companies": {"ck_companies_status_allowed"},
        "contacts": {"ck_contacts_status_allowed"},
        "agent_runs": {"ck_agent_runs_status_allowed"},
        "technologies": {"ck_technologies_confidence_range"},
        "intent_signals": {"ck_intent_signals_strength_range", "ck_intent_signals_confidence_range"},
        "intelligence_scores": {
            "ck_intelligence_scores_fit_score_range",
            "ck_intelligence_scores_intent_score_range",
            "ck_intelligence_scores_technographic_score_range",
            "ck_intelligence_scores_engagement_score_range",
            "ck_intelligence_scores_total_score_range",
            "ck_intelligence_scores_confidence_range",
        },
        "outreach_messages": {"ck_outreach_messages_status_allowed", "ck_outreach_messages_confidence_range"},
        "jobs": {"ck_jobs_status", "ck_jobs_job_type", "ck_jobs_retry_count", "ck_jobs_max_retries"},
    }
    for table_name, expected_checks in expected.items():
        actual = {c["name"] for c in inspector.get_check_constraints(table_name)}
        missing = expected_checks - actual
        assert not missing, f"Missing check constraints on {table_name}: {missing}"


# ─── Basic CRUD ─────────────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_create_and_read_company(postgresql_session: Session) -> None:
    company = Company(name="PG Test Co", domain="pg-test-1.example", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(company)
    postgresql_session.commit()

    saved = postgresql_session.get(Company, company.id)
    assert saved is not None
    assert saved.name == "PG Test Co"
    assert saved.domain == "pg-test-1.example"


@postgresql_required
def test_postgresql_unique_domain_enforced(postgresql_session: Session) -> None:
    c1 = Company(name="Unique Co", domain="unique-domain-1.example", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(c1)
    postgresql_session.commit()

    c2 = Company(name="Duplicate Co", domain="unique-domain-1.example", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(c2)
    with pytest.raises(IntegrityError):
        postgresql_session.commit()
    postgresql_session.rollback()


@postgresql_required
def test_postgresql_foreign_key_enforced(postgresql_session: Session) -> None:
    contact = Contact(company_id="00000000-0000-0000-0000-000000000000", full_name="Orphan Contact", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(contact)
    with pytest.raises(IntegrityError):
        postgresql_session.commit()
    postgresql_session.rollback()


@postgresql_required
def test_postgresql_status_constraint_enforced(postgresql_session: Session) -> None:
    company = Company(name="Bad Status", domain="bad-status-1.example", status="invalid_status", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(company)
    with pytest.raises(IntegrityError):
        postgresql_session.commit()
    postgresql_session.rollback()


@postgresql_required
def test_postgresql_confidence_constraint_enforced(postgresql_session: Session) -> None:
    company = Company(name="Conf Co", domain="conf-co-1.example", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(company)
    postgresql_session.commit()

    tech = Technology(
        company_id=company.id,
        name="BadConf",
        category="analytics",
        detection_method="html_signature",
        confidence=1.5,
        first_detected_at=utc_now(),
        last_detected_at=utc_now(),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    postgresql_session.add(tech)
    with pytest.raises(IntegrityError):
        postgresql_session.commit()
    postgresql_session.rollback()


# ─── Repositories ────────────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_company_repository(postgresql_session: Session) -> None:
    company = Company(name="Repo Co", domain="repo-co-1.example", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(company)
    postgresql_session.commit()

    repo = CompanyRepository(postgresql_session)
    assert repo.get(company.id) is not None
    assert repo.get_by_domain("repo-co-1.example") is not None
    assert repo.search_by_name("Repo") == [company]
    assert repo.list_by_status("active") == [company]


@postgresql_required
def test_postgresql_contact_repository(postgresql_session: Session) -> None:
    company = Company(name="Contact Parent", domain="contact-parent-pg-1.example", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(company)
    postgresql_session.commit()

    contact = Contact(company_id=company.id, full_name="PG Contact", email="pg-contact-1@example.com", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(contact)
    postgresql_session.commit()

    repo = ContactRepository(postgresql_session)
    assert repo.get_by_email("pg-contact-1@example.com") is not None
    assert repo.list_by_company(company.id) == [contact]
    assert repo.list_by_status("active") == [contact]


# ─── Services ────────────────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_company_service(postgresql_session: Session) -> None:
    _override_session(postgresql_session)
    service = CompanyService()
    company = service.create(name="Svc Co", domain="svc-co-pg-1.example", industry="software", status="active")
    company_id = company.id

    assert service.get(company_id) is not None
    assert service.get_by_domain("svc-co-pg-1.example") is not None
    results = service.search_by_name("Svc")
    assert len(results) == 1
    assert results[0].id == company_id


@postgresql_required
def test_postgresql_service_entity_conflict(postgresql_session: Session) -> None:
    _override_session(postgresql_session)
    service = CompanyService()
    service.create(name="Conflict Co", domain="conflict-pg-1.example", status="active")

    from app.core.errors import EntityConflictError
    with pytest.raises(EntityConflictError):
        service.create(name="Conflict Co 2", domain="conflict-pg-1.example", status="active")


@postgresql_required
def test_postgresql_service_entity_not_found(postgresql_session: Session) -> None:
    _override_session(postgresql_session)
    from app.core.errors import EntityNotFoundError
    with pytest.raises(EntityNotFoundError):
        CompanyService().get_required("00000000-0000-0000-0000-000000000000")


@postgresql_required
def test_postgresql_check_constraint_rejected_as_conflict(postgresql_session: Session) -> None:
    _override_session(postgresql_session)
    from app.core.errors import EntityConflictError
    with pytest.raises(EntityConflictError):
        CompanyService().create(name="Bad Status Co", domain="bad-status-svc-1.example", status="unsupported")


@postgresql_required
def test_postgresql_cascading_delete(postgresql_session: Session) -> None:
    company = Company(name="Cascade Co", domain="cascade-pg-1.example", status="active", created_at=utc_now(), updated_at=utc_now())
    contact = Contact(company=company, full_name="Cascade Contact", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(contact)
    postgresql_session.commit()

    postgresql_session.delete(company)
    postgresql_session.commit()

    orphan = postgresql_session.get(Contact, contact.id)
    assert orphan is None


@postgresql_required
def test_postgresql_set_null_on_delete_agent_run(postgresql_session: Session) -> None:
    company = Company(name="SetNull Co", domain="setnull-pg-1.example", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(company)
    postgresql_session.commit()

    agent_run = AgentRun(company_id=company.id, agent_name="setnull_agent", status="succeeded", started_at=utc_now(), finished_at=utc_now(), created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(agent_run)
    postgresql_session.commit()

    postgresql_session.delete(company)
    postgresql_session.commit()

    saved = postgresql_session.get(AgentRun, agent_run.id)
    assert saved is not None
    assert saved.company_id is None


# ─── DateTime Handling ──────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_timezone_aware_datetime_stored_and_retrieved(postgresql_session: Session) -> None:
    now = utc_now()
    company = Company(name="TZ Co", domain="tz-co-pg-1.example", status="active", created_at=now, updated_at=now)
    postgresql_session.add(company)
    postgresql_session.commit()

    saved = postgresql_session.get(Company, company.id)
    assert saved is not None
    assert saved.created_at.tzinfo is not None

    diff = abs((saved.created_at - now).total_seconds())
    assert diff < 1.0


@postgresql_required
def test_postgresql_naive_datetime_accepted(postgresql_session: Session) -> None:
    naive = datetime(2026, 1, 1, 12, 0, 0)
    company = Company(
        name="Naive Co", domain="naive-pg-1.example", status="active",
        created_at=naive,
        updated_at=naive,
    )
    postgresql_session.add(company)
    postgresql_session.commit()

    saved = postgresql_session.get(Company, company.id)
    assert saved is not None
    assert saved.created_at is not None


# ─── Session Scope ──────────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_service_transaction_rolls_back_on_error(postgresql_session: Session) -> None:
    _override_session(postgresql_session)
    from app.core.errors import EntityConflictError
    try:
        with pytest.raises(EntityConflictError):
            CompanyService().create(
                name="Invalid Status Company",
                domain="invalid-status-1.example",
                status="unsupported",
            )
    finally:
        pass

    found = CompanyService().get_by_domain("invalid-status-1.example")
    assert found is None


# ─── UUID Handling ───────────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_uuid_as_string(postgresql_session: Session) -> None:
    import uuid
    raw_uuid = str(uuid.uuid4())
    company = Company(id=raw_uuid, name="UUID Co", domain="uuid-pg-1.example", status="active", created_at=utc_now(), updated_at=utc_now())
    postgresql_session.add(company)
    postgresql_session.commit()

    saved = postgresql_session.get(Company, raw_uuid)
    assert saved is not None
    assert saved.id == raw_uuid


# ─── Full Entity Graph ───────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_full_entity_graph(postgresql_session: Session) -> None:
    now = utc_now()
    company = Company(name="Full Graph Co", domain="full-graph-pg-1.example", industry="software", status="active", created_at=now, updated_at=now)
    contact = Contact(company=company, full_name="Full Graph Contact", email="full-1@graph.example", status="active", created_at=now, updated_at=now)
    website = Website(company=company, url="https://full-graph-pg-1.example", normalized_url="https://full-graph-pg-1.example/", created_at=now, updated_at=now)
    agent_run = AgentRun(company=company, contact=contact, agent_name="full_graph_agent", status="succeeded", started_at=now, finished_at=now, created_at=now, updated_at=now)
    technology = Technology(company=company, website=website, agent_run=agent_run, name="FullGraphCRM", category="crm", detection_method="html_signature", confidence=0.9, first_detected_at=now, last_detected_at=now, created_at=now, updated_at=now)
    intent_signal = IntentSignal(company=company, contact=contact, website=website, technology=technology, agent_run=agent_run, signal_type="technology_change", signal_name="FullGraph CRM", strength=0.8, confidence=0.85, source_url="https://full-graph-pg-1.example", observed_at=now, created_at=now, updated_at=now)
    score = IntelligenceScore(company=company, contact=contact, technology=technology, agent_run=agent_run, fit_score=80.0, intent_score=70.0, technographic_score=90.0, engagement_score=75.0, total_score=80.5, confidence=0.88, score_version="pg-test-v1", rationale="Full graph test.", scored_at=now, created_at=now, updated_at=now)
    message = OutreachMessage(company=company, contact=contact, intelligence_score=score, agent_run=agent_run, channel="email", subject="Test", message_body="Full graph body.", personalization_angle="Full graph test", call_to_action="Book now", status="draft", confidence=0.8, generated_at=now, created_at=now, updated_at=now)

    postgresql_session.add(message)
    postgresql_session.commit()

    assert postgresql_session.get(Company, company.id) is not None
    assert postgresql_session.get(Contact, contact.id) is not None
    assert postgresql_session.get(Website, website.id) is not None
    assert postgresql_session.get(AgentRun, agent_run.id) is not None
    assert postgresql_session.get(Technology, technology.id) is not None
    assert postgresql_session.get(IntentSignal, intent_signal.id) is not None
    assert postgresql_session.get(IntelligenceScore, score.id) is not None
    assert postgresql_session.get(OutreachMessage, message.id) is not None

    assert len(company.contacts) == 1
    assert company.websites[0].normalized_url == "https://full-graph-pg-1.example/"


# ─── Job Tests ────────────────────────────────────────────────────────────────


@postgresql_required
def test_postgresql_job_create_and_query(postgresql_session: Session) -> None:
    _override_session(postgresql_session)
    from app.services.job_service import JobService
    from app.agents.context import AgentContext

    service = JobService()
    job = service.schedule_agent(
        name="pg_test_agent",
        context=AgentContext(agent_name="pg_test_agent", company_id="11111111-1111-1111-1111-111111111111"),
        max_retries=3,
    )
    assert job.status == "pending"
    assert job.retry_count == 0

    jobs = service.list_jobs(status="pending", limit=10, offset=0)
    assert len(jobs) >= 1
    assert any(j.id == job.id for j in jobs)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _override_session(postgresql_session: Session) -> None:
    factory = sessionmaker(
        bind=postgresql_session.get_bind(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    database_session.SessionLocal = factory
