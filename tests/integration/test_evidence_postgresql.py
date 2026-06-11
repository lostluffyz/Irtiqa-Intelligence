from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, text

from app.models import Base
from app.models.evidence_record import (
    EVIDENCE_TYPE_COMPUTED_METRIC,
    RELATIONSHIP_CONTRIBUTES_TO,
    SOURCE_TYPE_AGENT_RUN,
    TARGET_TYPE_INTELLIGENCE_SCORE,
    EvidenceRecord,
)
from app.repositories.evidence_repository import EvidenceRepository
from tests.conftest import postgresql_required


EXPECTED_TABLES = {
    "agent_runs",
    "companies",
    "contacts",
    "evidence_records",
    "intelligence_scores",
    "intent_signals",
    "jobs",
    "outreach_messages",
    "technologies",
    "websites",
}


@postgresql_required
def test_evidence_postgresql_migration(postgresql_engine) -> None:
    inspector = inspect(postgresql_engine)
    actual_tables = set(inspector.get_table_names())
    assert actual_tables >= EXPECTED_TABLES | {"alembic_version"}


@postgresql_required
def test_evidence_postgresql_crud(postgresql_session) -> None:
    now = datetime.now(timezone.utc)
    record = EvidenceRecord(
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id="a" * 36,
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="pg test value",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id="b" * 36,
        confidence=0.85,
        created_at=now,
        updated_at=now,
    )
    postgresql_session.add(record)
    postgresql_session.commit()

    saved = postgresql_session.get(EvidenceRecord, record.id)
    assert saved is not None
    assert saved.evidence_value == "pg test value"
    assert saved.confidence == 0.85

    repo = EvidenceRepository(postgresql_session)
    results = repo.list_by_target(
        TARGET_TYPE_INTELLIGENCE_SCORE, "b" * 36,
    )
    assert len(results) >= 1


@postgresql_required
def test_evidence_postgresql_fk_agent_run(postgresql_session) -> None:
    now = datetime.now(timezone.utc)
    record = EvidenceRecord(
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id="a" * 36,
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="fk test",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id="b" * 36,
        confidence=0.5,
        agent_run_id="nonexistent-0000-0000-0000-000000000000",
        created_at=now,
        updated_at=now,
    )
    # ForeignKey on agent_run_id is SET NULL, not CASCADE or RESTRICT,
    # so inserting with a nonexistent FK should fail
    postgresql_session.add(record)
    with pytest.raises(Exception):
        postgresql_session.commit()
    postgresql_session.rollback()
