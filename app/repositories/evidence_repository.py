from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.evidence_record import EvidenceRecord
from app.repositories.base import BaseRepository


class EvidenceRepository(BaseRepository[EvidenceRecord]):
    model = EvidenceRecord

    def add_all(self, entities: list[EvidenceRecord]) -> list[EvidenceRecord]:
        self.logger.debug(
            "Adding evidence records",
            extra={"model": self.model.__name__, "count": len(entities)},
        )
        self.session.add_all(entities)
        return entities

    def list_by_target(
        self,
        target_type: str,
        target_id: str,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EvidenceRecord]:
        self.logger.debug(
            "Listing evidence by target",
            extra={
                "model": self.model.__name__,
                "target_type": target_type,
                "target_id": target_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(EvidenceRecord)
            .where(
                EvidenceRecord.target_type == target_type,
                EvidenceRecord.target_id == target_id,
            )
            .order_by(EvidenceRecord.evidence_type, EvidenceRecord.created_at)
            .offset(offset)
            .limit(limit)
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement)

    def list_by_source(
        self,
        source_type: str,
        source_id: str,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EvidenceRecord]:
        self.logger.debug(
            "Listing evidence by source",
            extra={
                "model": self.model.__name__,
                "source_type": source_type,
                "source_id": source_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(EvidenceRecord)
            .where(
                EvidenceRecord.source_type == source_type,
                EvidenceRecord.source_id == source_id,
            )
            .order_by(EvidenceRecord.created_at)
            .offset(offset)
            .limit(limit)
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement)

    def list_by_agent_run(
        self,
        agent_run_id: str,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EvidenceRecord]:
        self.logger.debug(
            "Listing evidence by agent run",
            extra={
                "model": self.model.__name__,
                "agent_run_id": agent_run_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(EvidenceRecord)
            .where(EvidenceRecord.agent_run_id == agent_run_id)
            .order_by(EvidenceRecord.created_at)
            .offset(offset)
            .limit(limit)
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement)

    def list_by_company(
        self,
        company_id: str,
        *,
        organization_id: str,
        target_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EvidenceRecord]:
        self.logger.debug(
            "Listing evidence by company",
            extra={
                "model": self.model.__name__,
                "company_id": company_id,
                "target_type": target_type,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = select(EvidenceRecord).where(
            EvidenceRecord.company_id == company_id,
        )
        if target_type is not None:
            statement = statement.where(EvidenceRecord.target_type == target_type)
        statement = statement.order_by(EvidenceRecord.created_at).offset(offset).limit(limit)
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement)

    def list_by_entity_type(
        self,
        target_type: str,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[EvidenceRecord]:
        self.logger.debug(
            "Listing evidence by entity type",
            extra={
                "model": self.model.__name__,
                "target_type": target_type,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(EvidenceRecord)
            .where(EvidenceRecord.target_type == target_type)
            .order_by(EvidenceRecord.created_at)
            .offset(offset)
            .limit(limit)
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.scalars(statement)

    def count_by_target(self, target_type: str, target_id: str, *, organization_id: str) -> int:
        self.logger.debug(
            "Counting evidence by target",
            extra={
                "model": self.model.__name__,
                "target_type": target_type,
                "target_id": target_id,
            },
        )
        statement = (
            select(func.count())
            .select_from(EvidenceRecord)
            .where(
                EvidenceRecord.target_type == target_type,
                EvidenceRecord.target_id == target_id,
            )
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        return self.session.scalar(statement) or 0

    def delete_by_target(self, target_type: str, target_id: str, *, organization_id: str) -> int:
        self.logger.debug(
            "Deleting evidence by target",
            extra={
                "model": self.model.__name__,
                "target_type": target_type,
                "target_id": target_id,
            },
        )
        statement = (
            select(EvidenceRecord)
            .where(
                EvidenceRecord.target_type == target_type,
                EvidenceRecord.target_id == target_id,
            )
        )
        statement = self._apply_tenant_filter(statement, organization_id)
        entities = self.session.scalars(statement).all()
        count = 0
        for entity in entities:
            self.session.delete(entity)
            count += 1
        return count
