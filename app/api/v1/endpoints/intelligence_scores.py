from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_intelligence_score_service
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
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreRead:
    intelligence_score = service.create(**payload.model_dump())
    return IntelligenceScoreRead.model_validate(intelligence_score)


@router.get("", response_model=IntelligenceScoreList)
def list_intelligence_scores(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreList:
    intelligence_scores = service.list(limit=limit, offset=offset)
    return IntelligenceScoreList(
        items=[
            IntelligenceScoreRead.model_validate(intelligence_score)
            for intelligence_score in intelligence_scores
        ],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/{intelligence_score_id}", response_model=IntelligenceScoreRead)
def get_intelligence_score(
    intelligence_score_id: str,
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreRead:
    intelligence_score = service.get_required(intelligence_score_id)
    return IntelligenceScoreRead.model_validate(intelligence_score)


@router.patch("/{intelligence_score_id}", response_model=IntelligenceScoreRead)
def update_intelligence_score(
    intelligence_score_id: str,
    payload: IntelligenceScoreUpdate,
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> IntelligenceScoreRead:
    intelligence_score = service.update(
        intelligence_score_id,
        **payload.model_dump(exclude_unset=True),
    )
    return IntelligenceScoreRead.model_validate(intelligence_score)


@router.delete("/{intelligence_score_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intelligence_score(
    intelligence_score_id: str,
    service: IntelligenceScoreService = Depends(get_intelligence_score_service),
) -> Response:
    service.delete(intelligence_score_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
