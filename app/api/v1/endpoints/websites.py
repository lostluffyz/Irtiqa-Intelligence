from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_website_service
from app.schemas.website import WebsiteCreate, WebsiteList, WebsiteRead, WebsiteUpdate
from app.services import WebsiteService


router = APIRouter(prefix="/websites", tags=["websites"])


@router.post("", response_model=WebsiteRead, status_code=status.HTTP_201_CREATED)
def create_website(
    payload: WebsiteCreate,
    service: WebsiteService = Depends(get_website_service),
) -> WebsiteRead:
    website = service.create(**payload.model_dump())
    return WebsiteRead.model_validate(website)


@router.get("", response_model=WebsiteList)
def list_websites(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: WebsiteService = Depends(get_website_service),
) -> WebsiteList:
    websites = service.list(limit=limit, offset=offset)
    return WebsiteList(
        items=[WebsiteRead.model_validate(website) for website in websites],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/{website_id}", response_model=WebsiteRead)
def get_website(
    website_id: str,
    service: WebsiteService = Depends(get_website_service),
) -> WebsiteRead:
    website = service.get_required(website_id)
    return WebsiteRead.model_validate(website)


@router.patch("/{website_id}", response_model=WebsiteRead)
def update_website(
    website_id: str,
    payload: WebsiteUpdate,
    service: WebsiteService = Depends(get_website_service),
) -> WebsiteRead:
    website = service.update(website_id, **payload.model_dump(exclude_unset=True))
    return WebsiteRead.model_validate(website)


@router.delete("/{website_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_website(
    website_id: str,
    service: WebsiteService = Depends(get_website_service),
) -> Response:
    service.delete(website_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
