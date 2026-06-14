from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import (
    get_current_user,
    get_membership_service,
    get_organization_service,
)
from app.schemas.membership import (
    MembershipCreate,
    MembershipList,
    MembershipRead,
    MembershipUpdateRole,
    TransferOwnershipRequest,
)
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationList,
    OrganizationRead,
    OrganizationUpdate,
)
from app.services.membership_service import MembershipService
from app.services.organization_service import OrganizationService


router = APIRouter(prefix="/organizations", tags=["organizations"])


# ── Organization endpoints ───────────────────────────────────────────────────


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current_user: dict = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
) -> OrganizationRead:
    org = org_service.create(name=payload.name)
    return OrganizationRead.model_validate(org)


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_organization(
    organization_id: str,
    current_user: dict = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
    mem_service: MembershipService = Depends(get_membership_service),
) -> OrganizationRead:
    # Verify caller is a member of this organization (viewer+)
    membership = mem_service.get_membership(current_user["id"], organization_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization.",
        )
    org = org_service.get_required(organization_id)
    return OrganizationRead.model_validate(org)


@router.patch("/{organization_id}", response_model=OrganizationRead)
def update_organization(
    organization_id: str,
    payload: OrganizationUpdate,
    current_user: dict = Depends(get_current_user),
    org_service: OrganizationService = Depends(get_organization_service),
    mem_service: MembershipService = Depends(get_membership_service),
) -> OrganizationRead:
    # Verify caller is an admin or owner of this organization
    membership = mem_service.get_membership(current_user["id"], organization_id)
    if membership is None or membership.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to update this organization.",
        )
    org = org_service.update(organization_id, **payload.model_dump(exclude_unset=True))
    return OrganizationRead.model_validate(org)


# ── Membership endpoints ────────────────────────────────────────────────────


@router.get("/{organization_id}/members", response_model=MembershipList)
def list_members(
    organization_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    mem_service: MembershipService = Depends(get_membership_service),
) -> MembershipList:
    # Verify caller is a member (viewer+)
    membership = mem_service.get_membership(current_user["id"], organization_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization.",
        )
    members = mem_service.list_organization_members(organization_id, limit=limit, offset=offset)
    return MembershipList(
        items=[MembershipRead.model_validate(m) for m in members],
        total=len(members),
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{organization_id}/members",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    organization_id: str,
    payload: MembershipCreate,
    current_user: dict = Depends(get_current_user),
    mem_service: MembershipService = Depends(get_membership_service),
) -> MembershipRead:
    # Verify caller is an admin or owner
    membership = mem_service.get_membership(current_user["id"], organization_id)
    if membership is None or membership.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to add members.",
        )
    member = mem_service.create(
        user_id=payload.user_id,
        organization_id=organization_id,
        role=payload.role,
    )
    return MembershipRead.model_validate(member)


@router.post("/{organization_id}/transfer", response_model=MembershipRead)
def transfer_ownership(
    organization_id: str,
    payload: TransferOwnershipRequest,
    current_user: dict = Depends(get_current_user),
    mem_service: MembershipService = Depends(get_membership_service),
) -> MembershipRead:
    # Verify caller is an owner
    membership = mem_service.get_membership(current_user["id"], organization_id)
    if membership is None or membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an owner can transfer ownership.",
        )
    _, new_owner = mem_service.transfer_ownership(
        organization_id=organization_id,
        current_owner_id=current_user["id"],
        new_owner_id=payload.new_owner_id,
    )
    return MembershipRead.model_validate(new_owner)


@router.patch("/memberships/{membership_id}/role", response_model=MembershipRead)
def change_member_role(
    membership_id: str,
    payload: MembershipUpdateRole,
    current_user: dict = Depends(get_current_user),
    mem_service: MembershipService = Depends(get_membership_service),
) -> MembershipRead:
    # Look up the membership to determine the org and verify caller's role
    target = mem_service.get(membership_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )
    # Verify caller is an admin or owner of the same org
    caller_mem = mem_service.get_membership(current_user["id"], target.organization_id)
    if caller_mem is None or caller_mem.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to change roles.",
        )
    updated = mem_service.update_role(membership_id, payload.role)
    return MembershipRead.model_validate(updated)


@router.delete("/memberships/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    membership_id: str,
    current_user: dict = Depends(get_current_user),
    mem_service: MembershipService = Depends(get_membership_service),
) -> Response:
    # Look up the membership to determine the org and verify caller's role
    target = mem_service.get(membership_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found.",
        )
    # Verify caller is an admin or owner of the same org
    caller_mem = mem_service.get_membership(current_user["id"], target.organization_id)
    if caller_mem is None or caller_mem.role not in ("admin", "owner"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to remove members.",
        )
    mem_service.remove(membership_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
