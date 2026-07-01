from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import EntityConflictError
from app.models.company import Company
from app.repositories.company_repository import CompanyRepository
from app.services.base import BaseService


class CompanyService(BaseService[Company, CompanyRepository]):
    model = Company
    repository = CompanyRepository

    def create(self, organization_id: str, **values: Any) -> Company:
        return super().create(organization_id=organization_id, **values)

    def get_by_domain(self, domain: str, organization_id: str) -> Company | None:
        self._validate_identifier(domain, field_name="domain")

        def operation(session: Session) -> Company | None:
            return self._repository(session).get_by_domain(domain, organization_id=organization_id)

        return self._run_in_transaction("get_by_domain", operation)

    def get_existing_domains(self, domains: list[str], organization_id: str) -> set[str]:
        """Batch-check which domains already exist for the organization."""
        self._validate_identifier(organization_id, field_name="organization_id")

        def operation(session: Session) -> set[str]:
            return self._repository(session).get_existing_domains(domains, organization_id)

        return self._run_in_transaction("get_existing_domains", operation)

    def search_by_name(self, name: str, *, organization_id: str, limit: int = 50) -> Sequence[Company]:
        self._validate_identifier(name, field_name="name")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[Company]:
            return self._repository(session).search_by_name(name, organization_id=organization_id, limit=limit)

        return self._run_in_transaction("search_by_name", operation)

    def list_by_status(self, status: str, *, organization_id: str, limit: int = 100) -> Sequence[Company]:
        self._validate_identifier(status, field_name="status")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[Company]:
            return self._repository(session).list_by_status(status, organization_id=organization_id, limit=limit)

        return self._run_in_transaction("list_by_status", operation)

    def _before_create(self, repository: CompanyRepository, values: dict[str, Any]) -> None:
        domain = values.get("domain")
        org_id = values.get("organization_id", "")
        if isinstance(domain, str) and repository.get_by_domain(domain, organization_id=org_id) is not None:
            raise EntityConflictError(
                "A company with this domain already exists in this organization.",
                details={"service": self.__class__.__name__, "domain": domain},
            )
