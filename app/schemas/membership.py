from __future__ import annotations

from pydantic import Field

from app.schemas.base import IrtiqaSchema, ListSchema, TimestampedReadSchema


class MembershipCreate(IrtiqaSchema):
    user_id: str = Field(min_length=36, max_length=36)
    role: str = Field(default="member", min_length=1, max_length=50)


class MembershipUpdateRole(IrtiqaSchema):
    role: str = Field(min_length=1, max_length=50)


class MembershipRead(TimestampedReadSchema):
    user_id: str
    organization_id: str
    role: str


class MembershipList(ListSchema):
    items: list[MembershipRead]


class TransferOwnershipRequest(IrtiqaSchema):
    new_owner_id: str = Field(min_length=36, max_length=36)
