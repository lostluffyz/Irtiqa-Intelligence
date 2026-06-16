from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import get_contact_service, get_current_organization
from app.core.tenant import TenantContext, require_role
from app.schemas.contact import ContactCreate, ContactList, ContactRead, ContactUpdate
from app.services import ContactService


router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    tenant: TenantContext = Depends(get_current_organization),
    service: ContactService = Depends(get_contact_service),
) -> ContactRead:
    require_role("member", tenant.role, "create contacts")
    contact = service.create(organization_id=tenant.organization_id, **payload.model_dump())
    return ContactRead.model_validate(contact)


@router.get("", response_model=ContactList)
def list_contacts(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_current_organization),
    service: ContactService = Depends(get_contact_service),
) -> ContactList:
    contacts = service.list(organization_id=tenant.organization_id, limit=limit, offset=offset)
    return ContactList(
        items=[ContactRead.model_validate(c) for c in contacts],
        total=len(contacts),
        limit=limit,
        offset=offset,
    )


@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(
    contact_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: ContactService = Depends(get_contact_service),
) -> ContactRead:
    contact = service.get_required(contact_id)
    if contact.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource.",
        )
    return ContactRead.model_validate(contact)


@router.patch("/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    tenant: TenantContext = Depends(get_current_organization),
    service: ContactService = Depends(get_contact_service),
) -> ContactRead:
    require_role("member", tenant.role, "update contacts")
    contact = service.get_required(contact_id)
    if contact.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    contact = service.update(contact_id, **payload.model_dump(exclude_unset=True))
    return ContactRead.model_validate(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: ContactService = Depends(get_contact_service),
) -> Response:
    require_role("admin", tenant.role, "delete contacts")
    contact = service.get_required(contact_id)
    if contact.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    service.delete(contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
