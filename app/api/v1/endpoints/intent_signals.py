from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import get_current_organization, get_intent_signal_service
from app.core.tenant import TenantContext, require_role
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
    tenant: TenantContext = Depends(get_current_organization),
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> IntentSignalRead:
    require_role("member", tenant.role, "create intent signals")
    intent_signal = service.create(organization_id=tenant.organization_id, **payload.model_dump())
    return IntentSignalRead.model_validate(intent_signal)


@router.get("", response_model=IntentSignalList)
def list_intent_signals(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    company_id: str | None = Query(default=None),
    tenant: TenantContext = Depends(get_current_organization),
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> IntentSignalList:
    intent_signals = service.list(
        organization_id=tenant.organization_id,
        company_id=company_id,
        limit=limit,
        offset=offset,
    )
    return IntentSignalList(
        items=[IntentSignalRead.model_validate(s) for s in intent_signals],
        total=service.count(
            organization_id=tenant.organization_id,
            company_id=company_id,
        ),
        limit=limit,
        offset=offset,
    )


@router.get("/{intent_signal_id}", response_model=IntentSignalRead)
def get_intent_signal(
    intent_signal_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> IntentSignalRead:
    intent_signal = service.get_required(intent_signal_id)
    if intent_signal.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource.",
        )
    return IntentSignalRead.model_validate(intent_signal)


@router.patch("/{intent_signal_id}", response_model=IntentSignalRead)
def update_intent_signal(
    intent_signal_id: str,
    payload: IntentSignalUpdate,
    tenant: TenantContext = Depends(get_current_organization),
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> IntentSignalRead:
    require_role("member", tenant.role, "update intent signals")
    intent_signal = service.get_required(intent_signal_id)
    if intent_signal.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    intent_signal = service.update(intent_signal_id, **payload.model_dump(exclude_unset=True))
    return IntentSignalRead.model_validate(intent_signal)


@router.delete("/{intent_signal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intent_signal(
    intent_signal_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: IntentSignalService = Depends(get_intent_signal_service),
) -> Response:
    require_role("admin", tenant.role, "delete intent signals")
    intent_signal = service.get_required(intent_signal_id)
    if intent_signal.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    service.delete(intent_signal_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
