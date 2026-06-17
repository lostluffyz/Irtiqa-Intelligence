from __future__ import annotations

import hashlib
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.errors import ValidationError
from app.models.evidence_record import (
    EVIDENCE_VALUE_MAX_LENGTH,
    VALID_EVIDENCE_TYPES,
    VALID_RELATIONSHIP_TYPES,
    VALID_SOURCE_TYPES,
    VALID_TARGET_TYPES,
    EvidenceRecord,
)
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.evidence import EvidenceItem, EvidenceSummary
from app.services.base import BaseService


class EvidenceService(BaseService[EvidenceRecord, EvidenceRepository]):
    model = EvidenceRecord
    repository = EvidenceRepository

    # ── Recording ──────────────────────────────────────────────────────────

    def record_evidence(
        self,
        *,
        organization_id: str,
        source_type: str,
        source_id: str,
        source_detail: str | None = None,
        source_location_type: str | None = None,
        source_location_value: str | None = None,
        evidence_type: str,
        evidence_value: str,
        relationship_type: str,
        target_type: str,
        target_id: str,
        confidence: float,
        agent_run_id: str | None = None,
        company_id: str | None = None,
        contact_id: str | None = None,
    ) -> EvidenceRecord:
        self._validate_discriminator("source_type", source_type, VALID_SOURCE_TYPES)
        self._validate_discriminator("evidence_type", evidence_type, VALID_EVIDENCE_TYPES)
        self._validate_discriminator("relationship_type", relationship_type, VALID_RELATIONSHIP_TYPES)
        self._validate_discriminator("target_type", target_type, VALID_TARGET_TYPES)
        self._validate_confidence(confidence)
        evidence_value = self._truncate_evidence_value(evidence_value)
        evidence_hash = self._compute_hash(evidence_value)

        def operation(session: Session) -> EvidenceRecord:
            repository = self._repository(session)
            entity = EvidenceRecord(
                source_type=source_type,
                source_id=source_id,
                source_detail=source_detail,
                source_location_type=source_location_type,
                source_location_value=source_location_value,
                evidence_type=evidence_type,
                evidence_value=evidence_value,
                evidence_hash=evidence_hash,
                relationship_type=relationship_type,
                target_type=target_type,
                target_id=target_id,
                confidence=confidence,
                agent_run_id=agent_run_id,
                company_id=company_id,
                contact_id=contact_id,
                organization_id=organization_id,
            )
            return repository.add(entity)

        return self._run_in_transaction("record_evidence", operation)

    def record_evidence_batch(
        self,
        items: list[EvidenceItem],
        *,
        organization_id: str,
        agent_run_id: str | None = None,
        company_id: str | None = None,
        contact_id: str | None = None,
    ) -> list[EvidenceRecord]:
        if not items:
            return []

        def operation(session: Session) -> list[EvidenceRecord]:
            repository = self._repository(session)
            entities: list[EvidenceRecord] = []

            for item in items:
                self._validate_discriminator("source_type", item["source_type"], VALID_SOURCE_TYPES)
                self._validate_discriminator("evidence_type", item["evidence_type"], VALID_EVIDENCE_TYPES)
                self._validate_discriminator("relationship_type", item["relationship_type"], VALID_RELATIONSHIP_TYPES)
                self._validate_discriminator("target_type", item["target_type"], VALID_TARGET_TYPES)
                self._validate_confidence(item["confidence"])

                evidence_value = self._truncate_evidence_value(item["evidence_value"])
                evidence_hash = self._compute_hash(evidence_value)

                # Dedup: skip if same hash + target already exists
                existing_count = repository.count_by_target(
                    item["target_type"], item["target_id"], organization_id=organization_id,
                )
                if existing_count > 0:
                    existing = repository.list_by_target(
                        item["target_type"], item["target_id"], organization_id=organization_id, limit=500,
                    )
                    if any(e.evidence_hash == evidence_hash for e in existing):
                        self.logger.debug(
                            "Skipping duplicate evidence",
                            extra={"evidence_hash": evidence_hash},
                        )
                        continue

                entity = EvidenceRecord(
                    source_type=item["source_type"],
                    source_id=item["source_id"],
                    source_detail=item.get("source_detail"),
                    source_location_type=item.get("source_location_type"),
                    source_location_value=item.get("source_location_value"),
                    evidence_type=item["evidence_type"],
                    evidence_value=evidence_value,
                    evidence_hash=evidence_hash,
                    relationship_type=item["relationship_type"],
                    target_type=item["target_type"],
                    target_id=item["target_id"],
                    confidence=item["confidence"],
                    agent_run_id=agent_run_id,
                    company_id=company_id,
                    contact_id=contact_id,
                    organization_id=organization_id,
                )
                entities.append(entity)

            if entities:
                repository.add_all(entities)
                session.flush()

            return entities

        return self._run_in_transaction("record_evidence_batch", operation)

    # ── Queries ────────────────────────────────────────────────────────────

    def get_target_evidence(
        self,
        target_type: str,
        target_id: str,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EvidenceRecord]:
        self._validate_identifier(target_type, field_name="target_type")
        self._validate_identifier(target_id, field_name="target_id")
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[EvidenceRecord]:
            return self._repository(session).list_by_target(
                target_type, target_id, organization_id=organization_id, limit=limit, offset=offset,
            )

        return self._run_in_transaction("get_target_evidence", operation)

    def get_source_targets(
        self,
        source_type: str,
        source_id: str,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EvidenceRecord]:
        self._validate_identifier(source_type, field_name="source_type")
        self._validate_identifier(source_id, field_name="source_id")
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[EvidenceRecord]:
            return self._repository(session).list_by_source(
                source_type, source_id, organization_id=organization_id, limit=limit, offset=offset,
            )

        return self._run_in_transaction("get_source_targets", operation)

    def get_company_evidence(
        self,
        company_id: str,
        *,
        organization_id: str,
        target_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EvidenceRecord]:
        self._validate_identifier(company_id, field_name="company_id")
        self._validate_limit(limit)
        self._validate_offset(offset)
        if target_type is not None:
            self._validate_discriminator("target_type", target_type, VALID_TARGET_TYPES)

        def operation(session: Session) -> Sequence[EvidenceRecord]:
            return self._repository(session).list_by_company(
                company_id, organization_id=organization_id, target_type=target_type, limit=limit, offset=offset,
            )

        return self._run_in_transaction("get_company_evidence", operation)

    def get_agent_run_evidence(
        self,
        agent_run_id: str,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EvidenceRecord]:
        self._validate_identifier(agent_run_id, field_name="agent_run_id")
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[EvidenceRecord]:
            return self._repository(session).list_by_agent_run(
                agent_run_id, organization_id=organization_id, limit=limit, offset=offset,
            )

        return self._run_in_transaction("get_agent_run_evidence", operation)

    def get_evidence_summary(self, target_type: str, target_id: str, *, organization_id: str) -> EvidenceSummary:
        self._validate_identifier(target_type, field_name="target_type")
        self._validate_identifier(target_id, field_name="target_id")

        def operation(session: Session) -> EvidenceSummary:
            repository = self._repository(session)
            records = repository.list_by_target(target_type, target_id, organization_id=organization_id, limit=10000)

            by_evidence_type: dict[str, int] = {}
            by_relationship: dict[str, int] = {}
            highest = 0.0
            lowest = 1.0

            for record in records:
                by_evidence_type[record.evidence_type] = by_evidence_type.get(record.evidence_type, 0) + 1
                by_relationship[record.relationship_type] = by_relationship.get(record.relationship_type, 0) + 1
                if record.confidence > highest:
                    highest = record.confidence
                if record.confidence < lowest:
                    lowest = record.confidence

            return EvidenceSummary(
                target_type=target_type,
                target_id=target_id,
                total_evidence=len(records),
                by_evidence_type=by_evidence_type,
                by_relationship_type=by_relationship,
                highest_confidence=highest,
                lowest_confidence=lowest if records else 0.0,
            )

        return self._run_in_transaction("get_evidence_summary", operation)

    # ── Deletion ───────────────────────────────────────────────────────────

    def delete_target_evidence(self, target_type: str, target_id: str, *, organization_id: str) -> int:
        self._validate_identifier(target_type, field_name="target_type")
        self._validate_identifier(target_id, field_name="target_id")

        def operation(session: Session) -> int:
            return self._repository(session).delete_by_target(target_type, target_id, organization_id=organization_id)

        return self._run_in_transaction("delete_target_evidence", operation)

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _compute_hash(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _truncate_evidence_value(value: str) -> str:
        if len(value) > EVIDENCE_VALUE_MAX_LENGTH:
            return value[:EVIDENCE_VALUE_MAX_LENGTH] + "...[truncated]"
        return value

    @staticmethod
    def _validate_discriminator(
        field_name: str,
        value: str,
        valid_set: frozenset[str],
    ) -> None:
        if value not in valid_set:
            raise ValidationError(
                f"Invalid {field_name}: '{value}'. Must be one of {sorted(valid_set)}.",
                details={
                    "service": "EvidenceService",
                    "field": field_name,
                    "value": value,
                    "valid_values": sorted(valid_set),
                },
            )

    @staticmethod
    def _validate_confidence(value: float) -> None:
        if not (0.0 <= value <= 1.0):
            raise ValidationError(
                f"Invalid confidence: {value}. Must be between 0.0 and 1.0.",
                details={
                    "service": "EvidenceService",
                    "field": "confidence",
                    "value": value,
                },
            )
