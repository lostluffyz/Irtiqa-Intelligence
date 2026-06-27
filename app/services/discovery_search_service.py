from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.orm import Session

from app.core.errors import EntityNotFoundError, ValidationError
from app.models.discovery_search import DiscoverySearch
from app.repositories.discovery_search_repository import DiscoverySearchRepository
from app.schemas.discovery import DiscoverySearchCriteria
from app.services.base import BaseService


DISCOVERY_SEARCH_STATUSES = {"active", "archived"}


class DiscoverySearchService(BaseService[DiscoverySearch, DiscoverySearchRepository]):
    """CRUD service for saved discovery search definitions."""

    model = DiscoverySearch
    repository = DiscoverySearchRepository

    def create(self, organization_id: str, **values: Any) -> DiscoverySearch:
        self._validate_identifier(organization_id, field_name="organization_id")
        return super().create(organization_id=organization_id, **values)

    def list(
        self,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DiscoverySearch]:
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[DiscoverySearch]:
            return self._repository(session).list_by_organization(
                organization_id,
                limit=limit,
                offset=offset,
            )

        return self._run_in_transaction("list", operation)

    def list_active(
        self,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DiscoverySearch]:
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[DiscoverySearch]:
            return self._repository(session).get_active(
                organization_id,
                limit=limit,
                offset=offset,
            )

        return self._run_in_transaction("list_active", operation)

    def count_by_organization(self, organization_id: str) -> int:
        self._validate_identifier(organization_id, field_name="organization_id")

        def operation(session: Session) -> int:
            return self._repository(session).count_by_organization(organization_id)

        return self._run_in_transaction("count_by_organization", operation)

    def get_for_organization(self, search_id: str, *, organization_id: str) -> DiscoverySearch:
        self._validate_identifier(search_id, field_name="search_id")
        self._validate_identifier(organization_id, field_name="organization_id")

        def operation(session: Session) -> DiscoverySearch:
            search = self._repository(session).get(search_id)
            if search is None or search.organization_id != organization_id:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": search_id,
                    }
                )
            return search

        return self._run_in_transaction("get_for_organization", operation)

    def update_for_organization(
        self,
        search_id: str,
        *,
        organization_id: str,
        **values: Any,
    ) -> DiscoverySearch:
        self._validate_identifier(search_id, field_name="search_id")
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_update_values(values)
        self._prepare_values(values)

        def operation(session: Session) -> DiscoverySearch:
            search = self._repository(session).get(search_id)
            if search is None or search.organization_id != organization_id:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": search_id,
                    }
                )
            for field, value in values.items():
                setattr(search, field, value)
            session.flush()
            return search

        return self._run_in_transaction("update_for_organization", operation)

    def delete_for_organization(self, search_id: str, *, organization_id: str) -> None:
        self._validate_identifier(search_id, field_name="search_id")
        self._validate_identifier(organization_id, field_name="organization_id")

        def operation(session: Session) -> None:
            repository = self._repository(session)
            search = repository.get(search_id)
            if search is None or search.organization_id != organization_id:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": search_id,
                    }
                )
            repository.delete(search)
            session.flush()

        self._run_in_transaction("delete_for_organization", operation)

    def update(self, entity_id: str, **values: Any) -> DiscoverySearch:
        self._prepare_values(values)
        return super().update(entity_id, **values)

    def _before_create(
        self,
        repository: DiscoverySearchRepository,
        values: dict[str, Any],
    ) -> None:
        self._prepare_values(values)

    def _prepare_values(self, values: dict[str, Any]) -> None:
        if "criteria" in values:
            values["criteria"] = self._normalize_criteria_json(values["criteria"])
        if "status" in values:
            self._validate_status(values["status"])

    def _normalize_criteria_json(self, criteria: Any) -> str:
        if criteria is None:
            raise ValidationError(
                "criteria is required.",
                details={"service": self.__class__.__name__, "field": "criteria"},
            )

        try:
            if isinstance(criteria, DiscoverySearchCriteria):
                criteria_model = criteria
            elif isinstance(criteria, str):
                criteria_model = DiscoverySearchCriteria.model_validate(json.loads(criteria))
            else:
                criteria_model = DiscoverySearchCriteria.model_validate(criteria)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                "criteria must be valid JSON.",
                details={"service": self.__class__.__name__, "field": "criteria"},
                cause=exc,
            ) from exc
        except PydanticValidationError as exc:
            raise ValidationError(
                "criteria does not match the discovery criteria schema.",
                details={"service": self.__class__.__name__, "field": "criteria"},
                cause=exc,
            ) from exc

        return json.dumps(criteria_model.model_dump(exclude_none=True), sort_keys=True)

    def _validate_status(self, status: Any) -> None:
        if status not in DISCOVERY_SEARCH_STATUSES:
            raise ValidationError(
                "Discovery search status must be active or archived.",
                details={
                    "service": self.__class__.__name__,
                    "field": "status",
                    "status": status,
                },
            )
