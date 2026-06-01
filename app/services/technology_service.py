from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import EntityConflictError
from app.models.technology import Technology
from app.repositories.technology_repository import TechnologyRepository
from app.services.base import BaseService


class TechnologyService(BaseService[Technology, TechnologyRepository]):
    model = Technology
    repository = TechnologyRepository

    def list_by_company(self, company_id: str, *, limit: int = 100) -> Sequence[Technology]:
        self._validate_identifier(company_id, field_name="company_id")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[Technology]:
            return self._repository(session).list_by_company(company_id, limit=limit)

        return self._run_in_transaction("list_by_company", operation)

    def get_company_technology(
        self,
        *,
        company_id: str,
        name: str,
        category: str,
    ) -> Technology | None:
        self._validate_identifier(company_id, field_name="company_id")
        self._validate_identifier(name, field_name="name")
        self._validate_identifier(category, field_name="category")

        def operation(session: Session) -> Technology | None:
            return self._repository(session).get_company_technology(
                company_id=company_id,
                name=name,
                category=category,
            )

        return self._run_in_transaction("get_company_technology", operation)

    def list_by_category(self, category: str, *, limit: int = 100) -> Sequence[Technology]:
        self._validate_identifier(category, field_name="category")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[Technology]:
            return self._repository(session).list_by_category(category, limit=limit)

        return self._run_in_transaction("list_by_category", operation)

    def _before_create(self, repository: TechnologyRepository, values: dict[str, Any]) -> None:
        company_id = values.get("company_id")
        name = values.get("name")
        category = values.get("category")
        if (
            isinstance(company_id, str)
            and isinstance(name, str)
            and isinstance(category, str)
            and repository.get_company_technology(
                company_id=company_id,
                name=name,
                category=category,
            )
            is not None
        ):
            raise EntityConflictError(
                "A technology with this company, name, and category already exists.",
                details={
                    "service": self.__class__.__name__,
                    "company_id": company_id,
                    "name": name,
                    "category": category,
                },
            )
