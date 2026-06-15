from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, func

from app.models.organization import Organization
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    model = Organization

    def get_by_id(self, organization_id: str) -> Organization | None:
        self.logger.debug(
            "Fetching organization by id",
            extra={"model": self.model.__name__, "organization_id": organization_id},
        )
        return self.session.get(self.model, organization_id)

    def get_by_slug(self, slug: str) -> Organization | None:
        self.logger.debug(
            "Fetching organization by slug",
            extra={"model": self.model.__name__, "slug": slug},
        )
        statement = select(Organization).where(Organization.slug == slug)
        return self.scalar_one_or_none(statement)

    def list_active(self, *, limit: int = 100, offset: int = 0) -> Sequence[Organization]:
        self.logger.debug(
            "Listing active organizations",
            extra={"model": self.model.__name__, "limit": limit, "offset": offset},
        )
        statement = (
            select(Organization)
            .where(Organization.status == "active")
            .offset(offset)
            .limit(limit)
        )
        return self.scalars(statement)

    def slug_exists(self, slug: str) -> bool:
        self.logger.debug(
            "Checking slug existence",
            extra={"model": self.model.__name__, "slug": slug},
        )
        statement = select(func.count()).select_from(Organization).where(
            Organization.slug == slug,
        )
        count = self.session.scalar(statement) or 0
        return count > 0
