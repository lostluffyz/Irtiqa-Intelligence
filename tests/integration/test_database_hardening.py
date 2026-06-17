from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import DatabaseSettings
from app.database.engine import create_database_engine
from app.models.agent_run import AgentRun
from app.models.organization import Organization
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.intelligence_score import IntelligenceScore
from app.models.outreach_message import OutreachMessage
from app.models.technology import Technology
from app.models.website import Website


EXPECTED_CHECK_CONSTRAINTS = {
    "companies": {"ck_companies_status_allowed"},
    "contacts": {"ck_contacts_status_allowed"},
    "agent_runs": {"ck_agent_runs_status_allowed"},
    "technologies": {"ck_technologies_confidence_range"},
    "intent_signals": {
        "ck_intent_signals_strength_range",
        "ck_intent_signals_confidence_range",
    },
    "intelligence_scores": {
        "ck_intelligence_scores_fit_score_range",
        "ck_intelligence_scores_intent_score_range",
        "ck_intelligence_scores_technographic_score_range",
        "ck_intelligence_scores_engagement_score_range",
        "ck_intelligence_scores_total_score_range",
        "ck_intelligence_scores_confidence_range",
    },
    "outreach_messages": {
        "ck_outreach_messages_status_allowed",
        "ck_outreach_messages_confidence_range",
    },
}


def now() -> datetime:
    return datetime.now(timezone.utc)


def add_valid_graph(session: Session) -> dict[str, object]:
    from uuid import uuid4
    org_id = str(uuid4())
    org = Organization(id=org_id, name="Constraint Test Org", slug="constraint-test", status="active", created_at=now(), updated_at=now())
    session.add(org)
    session.flush()
    company = Company(organization_id=org_id, name="Constraint Company", domain="constraint.example", status="active")
    contact = Contact(organization_id=org_id, company=company, full_name="Constraint Contact", status="active")
    website = Website(
        company=company,
        url="https://constraint.example",
        normalized_url="https://constraint.example/",
    )
    agent_run = AgentRun(
        organization_id=org_id,
        company=company,
        contact=contact,
        agent_name="constraint_agent",
        workflow_name="constraint_workflow",
        status="succeeded",
        started_at=now(),
        finished_at=now(),
    )
    technology = Technology(
        company=company,
        website=website,
        agent_run=agent_run,
        name="Constraint CRM",
        category="crm",
        detection_method="html_signature",
        confidence=0.8,
        first_detected_at=now(),
        last_detected_at=now(),
    )
    score = IntelligenceScore(
        organization_id=org_id,
        company=company,
        contact=contact,
        technology=technology,
        agent_run=agent_run,
        fit_score=50.0,
        intent_score=50.0,
        technographic_score=50.0,
        engagement_score=50.0,
        total_score=50.0,
        confidence=0.5,
        score_version="constraints-v1",
        rationale="Valid baseline score.",
        scored_at=now(),
    )
    session.add(score)
    session.commit()
    return {
        "org_id": org_id,
        "company": company,
        "contact": contact,
        "website": website,
        "agent_run": agent_run,
        "technology": technology,
        "score": score,
    }


def expect_integrity_error(session: Session, entity: object) -> None:
    session.add(entity)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_sqlite_engine_sets_foreign_keys_wal_and_busy_timeout(tmp_path: Path) -> None:
    database_path = tmp_path / "hardening.db"
    settings = DatabaseSettings(
        url=f"sqlite:///{database_path.as_posix()}",
        echo=False,
        pool_pre_ping=True,
        sqlite_foreign_keys=True,
        sqlite_journal_mode="WAL",
        sqlite_busy_timeout_ms=7000,
    )
    engine = create_database_engine(settings)

    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
            assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() == 7000
    finally:
        engine.dispose()


def test_migrated_schema_contains_all_check_constraints(migrated_engine) -> None:
    inspector = inspect(migrated_engine)

    for table_name, expected_constraints in EXPECTED_CHECK_CONSTRAINTS.items():
        actual_constraints = {
            constraint["name"] for constraint in inspector.get_check_constraints(table_name)
        }
        assert expected_constraints <= actual_constraints


def test_status_constraints_are_enforced(session: Session) -> None:
    graph = add_valid_graph(session)

    expect_integrity_error(
        session,
        Company(organization_id=graph["org_id"], name="Invalid Company", domain="invalid-company.example", status="deleted"),
    )
    expect_integrity_error(
        session,
        Contact(organization_id=graph["org_id"], company=graph["company"], full_name="Invalid Contact", status="deleted"),
    )
    expect_integrity_error(
        session,
        AgentRun(
            organization_id=graph["org_id"],
            company=graph["company"],
            contact=graph["contact"],
            agent_name="bad_agent",
            status="done",
            started_at=now(),
        ),
    )
    expect_integrity_error(
        session,
        OutreachMessage(
            organization_id=graph["org_id"],
            company=graph["company"],
            contact=graph["contact"],
            intelligence_score=graph["score"],
            agent_run=graph["agent_run"],
            channel="email",
            message_body="Invalid status message.",
            personalization_angle="Constraint test",
            status="queued",
            confidence=0.5,
            generated_at=now(),
        ),
    )


def test_confidence_and_strength_constraints_are_enforced(session: Session) -> None:
    graph = add_valid_graph(session)

    expect_integrity_error(
        session,
        Technology(
            company=graph["company"],
            website=graph["website"],
            agent_run=graph["agent_run"],
            name="Invalid Confidence",
            category="analytics",
            detection_method="script_src",
            confidence=1.1,
            first_detected_at=now(),
            last_detected_at=now(),
        ),
    )
    expect_integrity_error(
        session,
        IntentSignal(
            organization_id=graph["org_id"],
            company=graph["company"],
            contact=graph["contact"],
            website=graph["website"],
            technology=graph["technology"],
            agent_run=graph["agent_run"],
            signal_type="growth",
            signal_name="Invalid strength",
            strength=-0.1,
            confidence=0.5,
            observed_at=now(),
        ),
    )
    expect_integrity_error(
        session,
        IntentSignal(
            organization_id=graph["org_id"],
            company=graph["company"],
            contact=graph["contact"],
            website=graph["website"],
            technology=graph["technology"],
            agent_run=graph["agent_run"],
            signal_type="growth",
            signal_name="Invalid confidence",
            strength=0.5,
            confidence=1.1,
            observed_at=now(),
        ),
    )
    expect_integrity_error(
        session,
        OutreachMessage(
            organization_id=graph["org_id"],
            company=graph["company"],
            contact=graph["contact"],
            intelligence_score=graph["score"],
            agent_run=graph["agent_run"],
            channel="email",
            message_body="Invalid confidence message.",
            personalization_angle="Constraint test",
            status="draft",
            confidence=-0.1,
            generated_at=now(),
        ),
    )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("fit_score", -0.1),
        ("intent_score", 100.1),
        ("technographic_score", -0.1),
        ("engagement_score", 100.1),
        ("total_score", 101.0),
        ("confidence", 1.1),
    ],
)
def test_intelligence_score_range_constraints_are_enforced(
    session: Session,
    field_name: str,
    invalid_value: float,
) -> None:
    graph = add_valid_graph(session)
    values = {
        "fit_score": 50.0,
        "intent_score": 50.0,
        "technographic_score": 50.0,
        "engagement_score": 50.0,
        "total_score": 50.0,
        "confidence": 0.5,
    }
    values[field_name] = invalid_value

    expect_integrity_error(
        session,
        IntelligenceScore(
            organization_id=graph["org_id"],
            company=graph["company"],
            contact=graph["contact"],
            technology=graph["technology"],
            agent_run=graph["agent_run"],
            score_version=f"invalid-{field_name}",
            rationale="Invalid score constraint test.",
            scored_at=now(),
            **values,
        ),
    )
