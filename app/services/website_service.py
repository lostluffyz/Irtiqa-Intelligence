from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import EntityConflictError
from app.models.website import Website
from app.repositories.website_repository import WebsiteRepository
from app.services.base import BaseService


class WebsiteService(BaseService[Website, WebsiteRepository]):
    model = Website
    repository = WebsiteRepository

    def get_by_normalized_url(self, normalized_url: str) -> Website | None:
        self._validate_identifier(normalized_url, field_name="normalized_url")

        def operation(session: Session) -> Website | None:
            return self._repository(session).get_by_normalized_url(normalized_url)

        return self._run_in_transaction("get_by_normalized_url", operation)

    def list_by_company(self, company_id: str, *, limit: int = 100) -> Sequence[Website]:
        self._validate_identifier(company_id, field_name="company_id")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[Website]:
            return self._repository(session).list_by_company(company_id, limit=limit)

        return self._run_in_transaction("list_by_company", operation)

    def _before_create(self, repository: WebsiteRepository, values: dict[str, Any]) -> None:
        normalized_url = values.get("normalized_url")
        if (
            isinstance(normalized_url, str)
            and repository.get_by_normalized_url(normalized_url) is not None
        ):
            raise EntityConflictError(
                "A website with this normalized URL already exists.",
                details={"service": self.__class__.__name__, "normalized_url": normalized_url},
            )
