from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import EntityConflictError, EntityNotFoundError, ValidationError
from app.models.membership import Membership
from app.repositories.membership_repository import MembershipRepository
from app.services.base import BaseService


VALID_ROLES = frozenset({"owner", "admin", "member", "viewer"})
LEVELS = {"viewer": 10, "member": 50, "admin": 80, "owner": 100}


class MembershipService(BaseService[Membership, MembershipRepository]):
    model = Membership
    repository = MembershipRepository

    def create(
        self,
        user_id: str,
        organization_id: str,
        role: str = "member",
    ) -> Membership:
        self._validate_identifier(user_id, field_name="user_id")
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_role(role)
        now = datetime.now(timezone.utc)

        def operation(session: Session) -> Membership:
            repo = self._repository(session)

            # Check for duplicate membership
            existing = repo.get_membership(user_id, organization_id)
            if existing is not None:
                raise EntityConflictError(
                    "User is already a member of this organization.",
                    details={
                        "service": self.__class__.__name__,
                        "user_id": user_id,
                        "organization_id": organization_id,
                    },
                )

            membership = Membership(
                user_id=user_id,
                organization_id=organization_id,
                role=role,
                created_at=now,
                updated_at=now,
            )
            repo.add(membership)
            session.flush()
            return membership

        return self._run_in_transaction("create", operation)

    def get(self, membership_id: str) -> Membership | None:
        self._validate_identifier(membership_id, field_name="membership_id")

        def operation(session: Session) -> Membership | None:
            return self._repository(session).get_by_id(membership_id)

        return self._run_in_transaction("get", operation)

    def get_membership(self, user_id: str, organization_id: str) -> Membership | None:
        self._validate_identifier(user_id, field_name="user_id")
        self._validate_identifier(organization_id, field_name="organization_id")

        def operation(session: Session) -> Membership | None:
            return self._repository(session).get_membership(user_id, organization_id)

        return self._run_in_transaction("get_membership", operation)

    def list_organization_members(
        self,
        organization_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Membership]:
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[Membership]:
            return self._repository(session).list_organization_members(
                organization_id, limit=limit, offset=offset,
            )

        return self._run_in_transaction("list_organization_members", operation)

    def list_user_memberships(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Membership]:
        self._validate_identifier(user_id, field_name="user_id")
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[Membership]:
            return self._repository(session).list_user_memberships(
                user_id, limit=limit, offset=offset,
            )

        return self._run_in_transaction("list_user_memberships", operation)

    def update_role(self, membership_id: str, new_role: str) -> Membership:
        self._validate_identifier(membership_id, field_name="membership_id")
        self._validate_role(new_role)

        def operation(session: Session) -> Membership:
            repo = self._repository(session)
            membership = repo.get_by_id(membership_id)
            if membership is None:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": membership_id,
                    }
                )

            # Owner protection: cannot downgrade the last owner
            if membership.role == "owner" and new_role != "owner":
                owner_count = repo.count_owners(membership.organization_id)
                if owner_count <= 1:
                    raise EntityConflictError(
                        "Cannot change the last owner's role. "
                        "Transfer ownership first.",
                        details={
                            "service": self.__class__.__name__,
                            "organization_id": membership.organization_id,
                            "membership_id": membership_id,
                        },
                    )

            membership.role = new_role
            membership.updated_at = datetime.now(timezone.utc)
            session.flush()
            return membership

        return self._run_in_transaction("update_role", operation)

    def remove(self, membership_id: str) -> None:
        self._validate_identifier(membership_id, field_name="membership_id")

        def operation(session: Session) -> None:
            repo = self._repository(session)
            membership = repo.get_by_id(membership_id)
            if membership is None:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": membership_id,
                    }
                )

            # Owner protection: cannot remove the last owner
            if membership.role == "owner":
                owner_count = repo.count_owners(membership.organization_id)
                if owner_count <= 1:
                    raise EntityConflictError(
                        "Cannot remove the last owner. "
                        "Transfer ownership first.",
                        details={
                            "service": self.__class__.__name__,
                            "organization_id": membership.organization_id,
                            "membership_id": membership_id,
                        },
                    )

            repo.delete(membership)
            session.flush()

        self._run_in_transaction("remove", operation)

    def transfer_ownership(
        self,
        organization_id: str,
        current_owner_id: str,
        new_owner_id: str,
    ) -> tuple[Membership, Membership]:
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_identifier(current_owner_id, field_name="current_owner_id")
        self._validate_identifier(new_owner_id, field_name="new_owner_id")

        def operation(session: Session) -> tuple[Membership, Membership]:
            repo = self._repository(session)

            current = repo.get_membership(current_owner_id, organization_id)
            if current is None or current.role != "owner":
                raise ValidationError(
                    "Current user is not an owner of this organization.",
                    details={
                        "service": self.__class__.__name__,
                        "organization_id": organization_id,
                        "user_id": current_owner_id,
                    },
                )

            new_owner = repo.get_membership(new_owner_id, organization_id)
            if new_owner is None:
                raise ValidationError(
                    "Target user is not a member of this organization.",
                    details={
                        "service": self.__class__.__name__,
                        "organization_id": organization_id,
                        "user_id": new_owner_id,
                    },
                )

            # Swap roles
            current.role = "admin"
            current.updated_at = datetime.now(timezone.utc)
            new_owner.role = "owner"
            new_owner.updated_at = datetime.now(timezone.utc)
            session.flush()

            return current, new_owner

        return self._run_in_transaction("transfer_ownership", operation)

    # ── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _validate_role(role: str) -> None:
        if role not in VALID_ROLES:
            raise ValidationError(
                f"Invalid role: '{role}'. Must be one of {sorted(VALID_ROLES)}.",
                details={
                    "service": "MembershipService",
                    "field": "role",
                    "value": role,
                    "valid_values": sorted(VALID_ROLES),
                },
            )
