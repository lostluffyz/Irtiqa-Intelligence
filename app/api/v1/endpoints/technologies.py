from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_technology_service
from app.schemas.technology import TechnologyCreate, TechnologyList, TechnologyRead, TechnologyUpdate
from app.services import TechnologyService


router = APIRouter(prefix="/technologies", tags=["technologies"])


@router.post("", response_model=TechnologyRead, status_code=status.HTTP_201_CREATED)
def create_technology(
    payload: TechnologyCreate,
    service: TechnologyService = Depends(get_technology_service),
) -> TechnologyRead:
    technology = service.create(**payload.model_dump())
    return TechnologyRead.model_validate(technology)


@router.get("", response_model=TechnologyList)
def list_technologies(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    company_id: str | None = Query(default=None),
    service: TechnologyService = Depends(get_technology_service),
) -> TechnologyList:
    technologies = service.list(company_id=company_id, limit=limit, offset=offset)
    return TechnologyList(
        items=[TechnologyRead.model_validate(technology) for technology in technologies],
        total=service.count(company_id=company_id),
        limit=limit,
        offset=offset,
    )


@router.get("/{technology_id}", response_model=TechnologyRead)
def get_technology(
    technology_id: str,
    service: TechnologyService = Depends(get_technology_service),
) -> TechnologyRead:
    technology = service.get_required(technology_id)
    return TechnologyRead.model_validate(technology)


@router.patch("/{technology_id}", response_model=TechnologyRead)
def update_technology(
    technology_id: str,
    payload: TechnologyUpdate,
    service: TechnologyService = Depends(get_technology_service),
) -> TechnologyRead:
    technology = service.update(technology_id, **payload.model_dump(exclude_unset=True))
    return TechnologyRead.model_validate(technology)


@router.delete("/{technology_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_technology(
    technology_id: str,
    service: TechnologyService = Depends(get_technology_service),
) -> Response:
    service.delete(technology_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
