from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models.agent_run import AgentRun
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.intelligence_score import IntelligenceScore
from app.models.outreach_message import OutreachMessage
from app.models.technology import Technology
from app.models.website import Website


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def sqlite_database_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'irtiqa_test.db').as_posix()}"


@pytest.fixture()
def alembic_config(sqlite_database_url: str, monkeypatch: pytest.MonkeyPatch) -> Config:
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "database" / "migrations"))
    config.set_main_option("sqlalchemy.url", sqlite_database_url)
    return config


@pytest.fixture()
def migrated_engine(alembic_config: Config, sqlite_database_url: str) -> Iterator[Engine]:
    command.upgrade(alembic_config, "head")
    engine = create_engine(sqlite_database_url, future=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def session(migrated_engine: Engine) -> Iterator[Session]:
    session_factory = sessionmaker(
        bind=migrated_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture()
def company() -> Company:
    return Company(
        name="Irtiqa Test Company",
        domain="irtiqa-test.example",
        industry="software",
        company_size="11-50",
        headquarters="Bengaluru, India",
        status="active",
    )


@pytest.fixture()
def contact(company: Company) -> Contact:
    return Contact(
        company=company,
        first_name="Asha",
        last_name="Rao",
        full_name="Asha Rao",
        email="asha.rao@irtiqa-test.example",
        title="VP Revenue",
        department="sales",
        seniority="vp",
        status="active",
    )


@pytest.fixture()
def website(company: Company) -> Website:
    return Website(
        company=company,
        url="https://irtiqa-test.example",
        normalized_url="https://irtiqa-test.example/",
        page_type="homepage",
        http_status=200,
        last_scraped_at=utc_now(),
    )


@pytest.fixture()
def agent_run(company: Company, contact: Contact) -> AgentRun:
    return AgentRun(
        company=company,
        contact=contact,
        agent_name="test_agent",
        workflow_name="test_workflow",
        status="succeeded",
        input_summary="company and contact intelligence input",
        output_summary="test output",
        started_at=utc_now(),
        finished_at=utc_now(),
    )


@pytest.fixture()
def technology(company: Company, website: Website, agent_run: AgentRun) -> Technology:
    now = utc_now()
    return Technology(
        company=company,
        website=website,
        agent_run=agent_run,
        name="HubSpot",
        category="crm",
        vendor="HubSpot",
        detection_method="html_signature",
        confidence=0.92,
        first_detected_at=now,
        last_detected_at=now,
    )


@pytest.fixture()
def intent_signal(
    company: Company,
    contact: Contact,
    website: Website,
    technology: Technology,
    agent_run: AgentRun,
) -> IntentSignal:
    return IntentSignal(
        company=company,
        contact=contact,
        website=website,
        technology=technology,
        agent_run=agent_run,
        signal_type="technology_change",
        signal_name="CRM detected",
        signal_value="HubSpot detected on homepage",
        strength=0.75,
        confidence=0.88,
        source_url="https://irtiqa-test.example",
        observed_at=utc_now(),
    )


@pytest.fixture()
def intelligence_score(
    company: Company,
    contact: Contact,
    technology: Technology,
    agent_run: AgentRun,
) -> IntelligenceScore:
    return IntelligenceScore(
        company=company,
        contact=contact,
        technology=technology,
        agent_run=agent_run,
        fit_score=82.0,
        intent_score=76.0,
        technographic_score=91.0,
        engagement_score=70.0,
        total_score=81.4,
        confidence=0.86,
        score_version="test-v1",
        rationale="Strong test fit based on explicit fixtures.",
        scored_at=utc_now(),
    )


@pytest.fixture()
def outreach_message(
    company: Company,
    contact: Contact,
    intelligence_score: IntelligenceScore,
    agent_run: AgentRun,
) -> OutreachMessage:
    return OutreachMessage(
        company=company,
        contact=contact,
        intelligence_score=intelligence_score,
        agent_run=agent_run,
        channel="email",
        subject="Improving revenue workflow visibility",
        message_body="A focused test message body.",
        personalization_angle="CRM workflow detected",
        call_to_action="Book a discovery call",
        status="draft",
        confidence=0.81,
        generated_at=utc_now(),
    )


@pytest.fixture(autouse=True)
def restore_database_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    original = os.environ.get("DATABASE_URL")
    yield
    if original is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", original)
