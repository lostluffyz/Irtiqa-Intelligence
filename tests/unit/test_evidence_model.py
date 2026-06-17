from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from app.models.organization import Organization

from app.models.evidence_record import (
    EVIDENCE_TYPE_COMPUTED_METRIC,
    EVIDENCE_VALUE_MAX_LENGTH,
    RELATIONSHIP_CONTRIBUTES_TO,
    SOURCE_TYPE_AGENT_RUN,
    TARGET_TYPE_INTELLIGENCE_SCORE,
    VALID_EVIDENCE_TYPES,
    VALID_RELATIONSHIP_TYPES,
    VALID_SOURCE_TYPES,
    VALID_TARGET_TYPES,
    EvidenceRecord,
)


def test_evidence_model_columns() -> None:
    record = EvidenceRecord(
        id="10000000-0000-0000-0000-000000000001",
        organization_id="70000000-0000-0000-0000-000000000007",
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id="20000000-0000-0000-0000-000000000002",
        source_detail="Test evidence detail",
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="technology=abc123, confidence=0.92",
        evidence_hash="abc123def456",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id="30000000-0000-0000-0000-000000000003",
        confidence=0.92,
        agent_run_id=None,
        company_id="40000000-0000-0000-0000-000000000004",
        contact_id="50000000-0000-0000-0000-000000000005",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert record.id == "10000000-0000-0000-0000-000000000001"
    assert len(record.id) == 36
    assert record.source_type == SOURCE_TYPE_AGENT_RUN
    assert record.source_id == "20000000-0000-0000-0000-000000000002"
    assert record.evidence_type == EVIDENCE_TYPE_COMPUTED_METRIC
    assert record.evidence_value == "technology=abc123, confidence=0.92"
    assert record.evidence_hash == "abc123def456"
    assert record.relationship_type == RELATIONSHIP_CONTRIBUTES_TO
    assert record.target_type == TARGET_TYPE_INTELLIGENCE_SCORE
    assert record.target_id == "30000000-0000-0000-0000-000000000003"
    assert record.confidence == 0.92
    assert record.agent_run_id is None
    assert record.company_id == "40000000-0000-0000-0000-000000000004"
    assert record.contact_id == "50000000-0000-0000-0000-000000000005"


def test_evidence_model_defaults() -> None:
    record = EvidenceRecord(
        id="60000000-0000-0000-0000-000000000006",
        organization_id="80000000-0000-0000-0000-000000000008",
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id="a" * 36,
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="test",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id="b" * 36,
        confidence=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert record.id == "60000000-0000-0000-0000-000000000006"
    assert record.source_detail is None
    assert record.source_location_type is None
    assert record.source_location_value is None
    assert record.evidence_hash is None
    assert record.agent_run_id is None
    assert record.company_id is None
    assert record.contact_id is None
    assert record.created_at is not None
    assert record.updated_at is not None


def test_evidence_model_uuid_generated(session) -> None:
    org_id = str(uuid4())
    session.add(Organization(id=org_id, name="Test Org", slug="test-org-evid", status="active"))
    session.flush()
    r1 = EvidenceRecord(
        organization_id=org_id,
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id="a" * 36,
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="test1",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id="b" * 36,
        confidence=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    r2 = EvidenceRecord(
        organization_id=org_id,
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id="a" * 36,
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="test2",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id="b" * 36,
        confidence=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(r1)
    session.add(r2)
    session.flush()
    assert r1.id is not None
    assert r2.id is not None
    assert r1.id != r2.id


def test_evidence_model_table_name() -> None:
    assert EvidenceRecord.__tablename__ == "evidence_records"


def test_evidence_model_indexes() -> None:
    table = EvidenceRecord.__table__
    index_names = {idx.name for idx in table.indexes}
    assert "ix_evidence_target" in index_names
    assert "ix_evidence_source" in index_names
    assert "ix_evidence_type" in index_names
    assert "ix_evidence_agent_run" in index_names
    assert "ix_evidence_company" in index_names
    assert "ix_evidence_hash" in index_names


def test_evidence_model_associates_with_session(session) -> None:
    org_id = str(uuid4())
    session.add(Organization(id=org_id, name="Session Test Org", slug="session-test-evid", status="active"))
    session.flush()
    record = EvidenceRecord(
        organization_id=org_id,
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id="a" * 36,
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="session test",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id="b" * 36,
        confidence=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(record)
    session.flush()
    assert record.id is not None
    saved = session.get(EvidenceRecord, record.id)
    assert saved is not None
    assert saved.evidence_value == "session test"


def test_evidence_model_constant_sets() -> None:
    assert isinstance(VALID_EVIDENCE_TYPES, frozenset)
    assert isinstance(VALID_RELATIONSHIP_TYPES, frozenset)
    assert isinstance(VALID_SOURCE_TYPES, frozenset)
    assert isinstance(VALID_TARGET_TYPES, frozenset)
    assert len(VALID_EVIDENCE_TYPES) == 6
    assert len(VALID_RELATIONSHIP_TYPES) == 4
    assert len(VALID_SOURCE_TYPES) == 3
    assert len(VALID_TARGET_TYPES) == 4


def test_evidence_model_max_length_constant() -> None:
    assert EVIDENCE_VALUE_MAX_LENGTH == 5000


def test_evidence_model_relationships_declared() -> None:
    relationships = inspect(EvidenceRecord).relationships
    assert "agent_run" in relationships
