from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.models.website import Website
from app.repositories.base import BaseRepository


class WebsiteRepository(BaseRepository[Website]):
    model = Website

    def get_by_normalized_url(self, normalized_url: str) -> Website | None:
        statement = select(Website).where(Website.normalized_url == normalized_url)
        return self.scalar_one_or_none(statement)

    def list_by_company(self, company_id: str, *, limit: int = 100) -> Sequence[Website]:
        statement = select(Website).where(Website.company_id == company_id).limit(limit)
        return self.scalars(statement)
