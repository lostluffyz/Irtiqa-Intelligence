from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select

from app.models.discovery_search import DiscoverySearch
from app.repositories.base import BaseRepository


class DiscoverySearchRepository(BaseRepository[DiscoverySearch]):
    model = DiscoverySearch

    def list_by_organization(
        self,
        organization_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DiscoverySearch]:
        self.logger.debug(
            "Listing discovery searches by organization",
            extra={
                "model": self.model.__name__,
                "organization_id": organization_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(DiscoverySearch)
            .where(DiscoverySearch.organization_id == organization_id)
            .order_by(DiscoverySearch.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return self.scalars(statement)

    def get_active(
        self,
        organization_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DiscoverySearch]:
        self.logger.debug(
            "Listing active discovery searches",
            extra={
                "model": self.model.__name__,
                "organization_id": organization_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(DiscoverySearch)
            .where(
                DiscoverySearch.organization_id == organization_id,
                DiscoverySearch.status == "active",
            )
            .order_by(DiscoverySearch.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return self.scalars(statement)

    def count_by_organization(self, organization_id: str) -> int:
        self.logger.debug(
            "Counting discovery searches by organization",
            extra={
                "model": self.model.__name__,
                "organization_id": organization_id,
            },
        )
        statement = (
            select(func.count())
            .select_from(DiscoverySearch)
            .where(DiscoverySearch.organization_id == organization_id)
        )
        return self.session.scalar(statement) or 0
