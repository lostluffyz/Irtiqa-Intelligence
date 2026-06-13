from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, func

from app.models.membership import Membership
from app.repositories.base import BaseRepository


class MembershipRepository(BaseRepository[Membership]):
    model = Membership

    def get_by_id(self, membership_id: str) -> Membership | None:
        self.logger.debug(
            "Fetching membership by id",
            extra={"model": self.model.__name__, "membership_id": membership_id},
        )
        return self.session.get(self.model, membership_id)

    def get_membership(self, user_id: str, organization_id: str) -> Membership | None:
        self.logger.debug(
            "Fetching membership by user and organization",
            extra={
                "model": self.model.__name__,
                "user_id": user_id,
                "organization_id": organization_id,
            },
        )
        statement = select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
        )
        return self.scalar_one_or_none(statement)

    def list_organization_members(
        self,
        organization_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Membership]:
        self.logger.debug(
            "Listing memberships by organization",
            extra={
                "model": self.model.__name__,
                "organization_id": organization_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(Membership)
            .where(Membership.organization_id == organization_id)
            .offset(offset)
            .limit(limit)
        )
        return self.scalars(statement)

    def list_user_memberships(
        self,
        user_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Membership]:
        self.logger.debug(
            "Listing memberships by user",
            extra={
                "model": self.model.__name__,
                "user_id": user_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(Membership)
            .where(Membership.user_id == user_id)
            .offset(offset)
            .limit(limit)
        )
        return self.scalars(statement)

    def count_owners(self, organization_id: str) -> int:
        self.logger.debug(
            "Counting owners in organization",
            extra={"model": self.model.__name__, "organization_id": organization_id},
        )
        statement = (
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == organization_id,
                Membership.role == "owner",
            )
        )
        return self.session.scalar(statement) or 0
