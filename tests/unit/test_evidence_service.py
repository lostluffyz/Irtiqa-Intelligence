from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import ValidationError
from app.database import session as database_session
from app.models.evidence_record import (
    EVIDENCE_TYPE_COMPUTED_METRIC,
    RELATIONSHIP_CONTRIBUTES_TO,
    SOURCE_TYPE_AGENT_RUN,
    TARGET_TYPE_INTELLIGENCE_SCORE,
)
from app.schemas.evidence import EvidenceItem
from app.services.evidence_service import EvidenceService


@pytest.fixture()
def _session_override(
    migrated_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[sessionmaker[Session]]:
    factory = sessionmaker(
        bind=migrated_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    monkeypatch.setattr(database_session, "SessionLocal", factory)
    yield factory


def _evidence_item(**overrides: str | float | None) -> EvidenceItem:
    base: dict = {
        "source_type": SOURCE_TYPE_AGENT_RUN,
        "source_id": "a" * 36,
        "source_detail": "Test evidence",
        "evidence_type": EVIDENCE_TYPE_COMPUTED_METRIC,
        "evidence_value": "test value",
        "relationship_type": RELATIONSHIP_CONTRIBUTES_TO,
        "target_type": TARGET_TYPE_INTELLIGENCE_SCORE,
        "target_id": "b" * 36,
        "confidence": 0.85,
    }
    base.update(overrides)
    return EvidenceItem(**base)


def test_record_evidence_creates_record(_session_override: object) -> None:
    service = EvidenceService()
    record = service.record_evidence(
        source_type=SOURCE_TYPE_AGENT_RUN,
        source_id="a" * 36,
        source_detail="Direct record test",
        evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
        evidence_value="direct test value",
        relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
        target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
        target_id="b" * 36,
        confidence=0.75,
    )
    assert record.id is not None
    assert record.evidence_value == "direct test value"
    assert record.evidence_hash is not None
    assert len(record.evidence_hash) == 64


def test_record_evidence_validates_invalid_evidence_type(_session_override: object) -> None:
    service = EvidenceService()
    with pytest.raises(ValidationError):
        service.record_evidence(
            source_type=SOURCE_TYPE_AGENT_RUN,
            source_id="a" * 36,
            evidence_type="invalid_type",
            evidence_value="test",
            relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
            target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
            target_id="b" * 36,
            confidence=0.5,
        )


def test_record_evidence_validates_invalid_confidence(_session_override: object) -> None:
    service = EvidenceService()
    with pytest.raises(ValidationError):
        service.record_evidence(
            source_type=SOURCE_TYPE_AGENT_RUN,
            source_id="a" * 36,
            evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
            evidence_value="test",
            relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
            target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
            target_id="b" * 36,
            confidence=1.5,
        )


def test_record_evidence_batch_creates_multiple(_session_override: object) -> None:
    service = EvidenceService()
    items = [
        _evidence_item(evidence_value="v1", confidence=0.9),
        _evidence_item(evidence_value="v2", confidence=0.8),
    ]
    records = service.record_evidence_batch(
        items=items,
        agent_run_id=None,
        company_id="d" * 36,
        contact_id="e" * 36,
    )
    assert len(records) == 2
    for record in records:
        assert record.company_id == "d" * 36
        assert record.contact_id == "e" * 36


def test_record_evidence_batch_returns_empty_for_empty_input() -> None:
    service = EvidenceService()
    records = service.record_evidence_batch(items=[])
    assert records == []


def test_record_evidence_batch_deduplicates_across_batches(_session_override: object) -> None:
    service = EvidenceService()
    items = [
        _evidence_item(evidence_value="unique dedup test", target_id="t_dedup", confidence=0.9),
    ]
    # First batch
    first = service.record_evidence_batch(items=items, agent_run_id=None)
    assert len(first) == 1

    # Second batch with same content — should be skipped
    second = service.record_evidence_batch(items=items, agent_run_id=None)
    assert len(second) == 0


def test_record_evidence_batch_accepts_same_hash_different_target(_session_override: object) -> None:
    service = EvidenceService()
    items = [
        _evidence_item(evidence_value="same content", target_id="target_a", confidence=0.9),
        _evidence_item(evidence_value="same content", target_id="target_b", confidence=0.9),
    ]
    records = service.record_evidence_batch(items=items, agent_run_id=None)
    assert len(records) == 2
