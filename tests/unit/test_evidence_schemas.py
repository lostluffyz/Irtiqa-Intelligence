from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.evidence import EvidenceList, EvidenceRead, EvidenceSummary


def test_evidence_read_serialization() -> None:
    now = datetime.now(timezone.utc)
    data = {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "source_type": "agent_run",
        "source_id": "650e8400-e29b-41d4-a716-446655440001",
        "source_detail": "Test source detail",
        "source_location_type": None,
        "source_location_value": None,
        "evidence_type": "computed_metric",
        "evidence_value": "technology=abc, confidence=0.92",
        "evidence_hash": "abc123def456",
        "relationship_type": "contributes_to",
        "target_type": "intelligence_score",
        "target_id": "750e8400-e29b-41d4-a716-446655440002",
        "confidence": 0.92,
        "agent_run_id": "850e8400-e29b-41d4-a716-446655440003",
        "company_id": "950e8400-e29b-41d4-a716-446655440004",
        "contact_id": None,
        "created_at": now,
        "updated_at": now,
    }
    schema = EvidenceRead(**data)
    assert schema.id == data["id"]
    assert schema.evidence_type == "computed_metric"
    assert schema.confidence == 0.92
    assert schema.agent_run_id == "850e8400-e29b-41d4-a716-446655440003"


def test_evidence_list_pagination() -> None:
    record = EvidenceRead(
        id="550e8400-e29b-41d4-a716-446655440000",
        source_type="agent_run",
        source_id="a" * 36,
        evidence_type="computed_metric",
        evidence_value="test",
        relationship_type="contributes_to",
        target_type="intelligence_score",
        target_id="b" * 36,
        confidence=0.5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    schema = EvidenceList(items=[record], total=25, limit=10, offset=0)
    assert len(schema.items) == 1
    assert schema.total == 25
    assert schema.limit == 10
    assert schema.offset == 0


def test_evidence_summary_schema() -> None:
    schema = EvidenceSummary(
        target_type="intelligence_score",
        target_id="550e8400-e29b-41d4-a716-446655440000",
        total_evidence=5,
        by_evidence_type={"computed_metric": 3, "signature_match": 2},
        by_relationship_type={"contributes_to": 5},
        highest_confidence=0.95,
        lowest_confidence=0.42,
    )
    assert schema.total_evidence == 5
    assert schema.by_evidence_type["computed_metric"] == 3
    assert schema.highest_confidence == 0.95
    assert schema.lowest_confidence == 0.42
