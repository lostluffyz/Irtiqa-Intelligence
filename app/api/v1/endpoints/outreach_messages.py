from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_outreach_message_service
from app.schemas.outreach_message import (
    OutreachMessageCreate,
    OutreachMessageList,
    OutreachMessageRead,
    OutreachMessageUpdate,
)
from app.services import OutreachMessageService


router = APIRouter(prefix="/outreach-messages", tags=["outreach-messages"])


@router.post("", response_model=OutreachMessageRead, status_code=status.HTTP_201_CREATED)
def create_outreach_message(
    payload: OutreachMessageCreate,
    service: OutreachMessageService = Depends(get_outreach_message_service),
) -> OutreachMessageRead:
    outreach_message = service.create(**payload.model_dump())
    return OutreachMessageRead.model_validate(outreach_message)


@router.get("", response_model=OutreachMessageList)
def list_outreach_messages(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: OutreachMessageService = Depends(get_outreach_message_service),
) -> OutreachMessageList:
    outreach_messages = service.list(limit=limit, offset=offset)
    return OutreachMessageList(
        items=[
            OutreachMessageRead.model_validate(outreach_message)
            for outreach_message in outreach_messages
        ],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/{outreach_message_id}", response_model=OutreachMessageRead)
def get_outreach_message(
    outreach_message_id: str,
    service: OutreachMessageService = Depends(get_outreach_message_service),
) -> OutreachMessageRead:
    outreach_message = service.get_required(outreach_message_id)
    return OutreachMessageRead.model_validate(outreach_message)


@router.patch("/{outreach_message_id}", response_model=OutreachMessageRead)
def update_outreach_message(
    outreach_message_id: str,
    payload: OutreachMessageUpdate,
    service: OutreachMessageService = Depends(get_outreach_message_service),
) -> OutreachMessageRead:
    outreach_message = service.update(
        outreach_message_id,
        **payload.model_dump(exclude_unset=True),
    )
    return OutreachMessageRead.model_validate(outreach_message)


@router.delete("/{outreach_message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outreach_message(
    outreach_message_id: str,
    service: OutreachMessageService = Depends(get_outreach_message_service),
) -> Response:
    service.delete(outreach_message_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
