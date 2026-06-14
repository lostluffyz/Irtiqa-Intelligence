from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import EntityNotFoundError, ValidationError
from app.models.membership import Membership
from app.models.organization import Organization, generate_unique_slug
from app.repositories.membership_repository import MembershipRepository
from app.repositories.organization_repository import OrganizationRepository
from app.services.base import BaseService


class OrganizationService(BaseService[Organization, OrganizationRepository]):
    model = Organization
    repository = OrganizationRepository

    def create(self, name: str) -> Organization:
        self._validate_identifier(name, field_name="name")
        now = datetime.now(timezone.utc)

        def operation(session: Session) -> Organization:
            repo = self._repository(session)
            slug = generate_unique_slug(name, session)
            org = Organization(
                name=name,
                slug=slug,
                status="active",
                created_at=now,
                updated_at=now,
            )
            repo.add(org)
            session.flush()
            return org

        return self._run_in_transaction("create", operation)

    def create_with_owner(self, name: str, user_id: str) -> tuple[Organization, Membership]:
        """Create an organization and an owner membership atomically.

        The caller becomes the owner of the new organization.
        If either creation fails, the entire transaction is rolled back.
        """
        self._validate_identifier(name, field_name="name")
        self._validate_identifier(user_id, field_name="user_id")
        now = datetime.now(timezone.utc)

        def operation(session: Session) -> tuple[Organization, Membership]:
            org_repo = OrganizationRepository(session)
            mem_repo = MembershipRepository(session)

            slug = generate_unique_slug(name, session)
            org = Organization(
                name=name,
                slug=slug,
                status="active",
                created_at=now,
                updated_at=now,
            )
            org_repo.add(org)
            session.flush()

            membership = Membership(
                user_id=user_id,
                organization_id=org.id,
                role="owner",
                created_at=now,
                updated_at=now,
            )
            mem_repo.add(membership)
            session.flush()

            return org, membership

        return self._run_in_transaction("create_with_owner", operation)

    def get(self, organization_id: str) -> Organization | None:
        self._validate_identifier(organization_id, field_name="organization_id")

        def operation(session: Session) -> Organization | None:
            return self._repository(session).get_by_id(organization_id)

        return self._run_in_transaction("get", operation)

    def get_required(self, organization_id: str) -> Organization:
        org = self.get(organization_id)
        if org is None:
            raise EntityNotFoundError(
                details={
                    "service": self.__class__.__name__,
                    "model": self.model.__name__,
                    "entity_id": organization_id,
                }
            )
        return org

    def list_active(self, *, limit: int = 100, offset: int = 0) -> Sequence[Organization]:
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[Organization]:
            return self._repository(session).list_active(limit=limit, offset=offset)

        return self._run_in_transaction("list_active", operation)

    def update(self, organization_id: str, **values: Any) -> Organization:
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_update_values(values)

        allowed = {"name", "status"}
        invalid = set(values) - allowed
        if invalid:
            raise ValidationError(
                f"Invalid fields for organization update: {invalid}",
                details={"service": self.__class__.__name__, "invalid_fields": sorted(invalid)},
            )

        def operation(session: Session) -> Organization:
            repo = self._repository(session)
            org = repo.get_by_id(organization_id)
            if org is None:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": organization_id,
                    }
                )
            for field, value in values.items():
                setattr(org, field, value)
            org.updated_at = datetime.now(timezone.utc)
            session.flush()
            return org

        return self._run_in_transaction("update", operation)

    def deactivate(self, organization_id: str) -> Organization:
        return self.update(organization_id, status="suspended")
