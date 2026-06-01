from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_intent_signal_service
from app.schemas.intent_signal import (
    IntentSignalCreate,
    IntentSignalList,
    IntentSignalRead,
    IntentSignalUpdate,
)
from app.services import IntentSignalService


router = APIRouter(prefix="/intent-signals", tags=["intent-signals"])


@router.post("", response_model=IntentSignalRead, status_code=status.HTTP_201_CREATED)
def create_intent_signal(
    payload: IntentSignalCreate,
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> IntentSignalRead:
    intent_signal = service.create(**payload.model_dump())
    return IntentSignalRead.model_validate(intent_signal)


@router.get("", response_model=IntentSignalList)
def list_intent_signals(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> IntentSignalList:
    intent_signals = service.list(limit=limit, offset=offset)
    return IntentSignalList(
        items=[IntentSignalRead.model_validate(intent_signal) for intent_signal in intent_signals],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/{intent_signal_id}", response_model=IntentSignalRead)
def get_intent_signal(
    intent_signal_id: str,
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> IntentSignalRead:
    intent_signal = service.get_required(intent_signal_id)
    return IntentSignalRead.model_validate(intent_signal)


@router.patch("/{intent_signal_id}", response_model=IntentSignalRead)
def update_intent_signal(
    intent_signal_id: str,
    payload: IntentSignalUpdate,
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> IntentSignalRead:
    intent_signal = service.update(intent_signal_id, **payload.model_dump(exclude_unset=True))
    return IntentSignalRead.model_validate(intent_signal)


@router.delete("/{intent_signal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intent_signal(
    intent_signal_id: str,
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> Response:
    service.delete(intent_signal_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
