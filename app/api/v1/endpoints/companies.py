from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_company_service
from app.schemas.company import CompanyCreate, CompanyList, CompanyRead, CompanyUpdate
from app.services import CompanyService


router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    company = service.create(**payload.model_dump())
    return CompanyRead.model_validate(company)


@router.get("", response_model=CompanyList)
def list_companies(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: CompanyService = Depends(get_company_service),
) -> CompanyList:
    companies = service.list(limit=limit, offset=offset)
    return CompanyList(
        items=[CompanyRead.model_validate(company) for company in companies],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: str,
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    company = service.get_required(company_id)
    return CompanyRead.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: str,
    payload: CompanyUpdate,
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    company = service.update(company_id, **payload.model_dump(exclude_unset=True))
    return CompanyRead.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: str,
    service: CompanyService = Depends(get_company_service),
) -> Response:
    service.delete(company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
