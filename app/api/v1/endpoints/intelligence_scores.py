from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import get_current_organization, get_intelligence_score_service
from app.core.tenant import TenantContext, require_role
from app.schemas.intelligence_score import (
    IntelligenceScoreCreate,
    IntelligenceScoreList,
    IntelligenceScoreRead,
    IntelligenceScoreUpdate,
)
from app.services import IntelligenceScoreService


router = APIRouter(prefix="/intelligence-scores", tags=["intelligence-scores"])


@router.post("", response_model=IntelligenceScoreRead, status_code=status.HTTP_201_CREATED)
def create_intelligence_score(
    payload: IntelligenceScoreCreate,
    tenant: TenantContext = Depends(get_current_organization),
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreRead:
    require_role("member", tenant.role, "create intelligence scores")
    intelligence_score = service.create(organization_id=tenant.organization_id, **payload.model_dump())
    return IntelligenceScoreRead.model_validate(intelligence_score)


@router.get("", response_model=IntelligenceScoreList)
def list_intelligence_scores(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_current_organization),
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreList:
    scores = service.list(organization_id=tenant.organization_id, limit=limit, offset=offset)
    return IntelligenceScoreList(
        items=[IntelligenceScoreRead.model_validate(s) for s in scores],
        total=len(scores),
        limit=limit,
        offset=offset,
    )


@router.get("/top", response_model=IntelligenceScoreList)
def list_top_scores(
    limit: int = Query(default=100, ge=1, le=500),
    global_scores: bool = Query(default=False, alias="global"),
    tenant: TenantContext = Depends(get_current_organization),
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreList:
    org_id: str | None = None
    if global_scores:
        require_role("owner", tenant.role, "view global scores")
    else:
        org_id = tenant.organization_id
    scores = service.list_top_scores(organization_id=org_id, limit=limit)
    return IntelligenceScoreList(
        items=[IntelligenceScoreRead.model_validate(s) for s in scores],
        total=len(scores),
        limit=limit,
        offset=0,
    )


@router.get("/{intelligence_score_id}", response_model=IntelligenceScoreRead)
def get_intelligence_score(
    intelligence_score_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreRead:
    intelligence_score = service.get_required(intelligence_score_id)
    if intelligence_score.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource.",
        )
    return IntelligenceScoreRead.model_validate(intelligence_score)


@router.patch("/{intelligence_score_id}", response_model=IntelligenceScoreRead)
def update_intelligence_score(
    intelligence_score_id: str,
    payload: IntelligenceScoreUpdate,
    tenant: TenantContext = Depends(get_current_organization),
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreRead:
    require_role("member", tenant.role, "update intelligence scores")
    intelligence_score = service.get_required(intelligence_score_id)
    if intelligence_score.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    intelligence_score = service.update(intelligence_score_id, **payload.model_dump(exclude_unset=True))
    return IntelligenceScoreRead.model_validate(intelligence_score)


@router.delete("/{intelligence_score_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intelligence_score(
    intelligence_score_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> Response:
    require_role("admin", tenant.role, "delete intelligence scores")
    intelligence_score = service.get_required(intelligence_score_id)
    if intelligence_score.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    service.delete(intelligence_score_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
