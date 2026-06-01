from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_contact_service
from app.schemas.contact import ContactCreate, ContactList, ContactRead, ContactUpdate
from app.services import ContactService


router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    service: ContactService = Depends(get_contact_service),
) -> ContactRead:
    contact = service.create(**payload.model_dump())
    return ContactRead.model_validate(contact)


@router.get("", response_model=ContactList)
def list_contacts(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ContactService = Depends(get_contact_service),
) -> ContactList:
    contacts = service.list(limit=limit, offset=offset)
    return ContactList(
        items=[ContactRead.model_validate(contact) for contact in contacts],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/{contact_id}", response_model=ContactRead)
def get_contact(
    contact_id: str,
    service: ContactService = Depends(get_contact_service),
) -> ContactRead:
    contact = service.get_required(contact_id)
    return ContactRead.model_validate(contact)


@router.patch("/{contact_id}", response_model=ContactRead)
def update_contact(
    contact_id: str,
    payload: ContactUpdate,
    service: ContactService = Depends(get_contact_service),
) -> ContactRead:
    contact = service.update(contact_id, **payload.model_dump(exclude_unset=True))
    return ContactRead.model_validate(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: str,
    service: ContactService = Depends(get_contact_service),
) -> Response:
    service.delete(contact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
