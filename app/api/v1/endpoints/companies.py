from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import get_company_service, get_current_organization
from app.core.tenant import TenantContext, require_role
from app.schemas.company import CompanyCreate, CompanyList, CompanyRead, CompanyUpdate
from app.services import CompanyService


router = APIRouter(prefix="/companies", tags=["companies"])


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    tenant: TenantContext = Depends(get_current_organization),
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    require_role("member", tenant.role, "create companies")
    company = service.create(organization_id=tenant.organization_id, **payload.model_dump())
    return CompanyRead.model_validate(company)


@router.get("", response_model=CompanyList)
def list_companies(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_current_organization),
    service: CompanyService = Depends(get_company_service),
) -> CompanyList:
    companies = service.list(organization_id=tenant.organization_id, limit=limit, offset=offset)
    return CompanyList(
        items=[CompanyRead.model_validate(c) for c in companies],
        total=len(companies),
        limit=limit,
        offset=offset,
    )


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    company = service.get_required(company_id)
    if company.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource.",
        )
    return CompanyRead.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyRead)
def update_company(
    company_id: str,
    payload: CompanyUpdate,
    tenant: TenantContext = Depends(get_current_organization),
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    require_role("member", tenant.role, "update companies")
    company = service.get_required(company_id)
    if company.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    company = service.update(company_id, **payload.model_dump(exclude_unset=True))
    return CompanyRead.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: CompanyService = Depends(get_company_service),
) -> Response:
    require_role("admin", tenant.role, "delete companies")
    company = service.get_required(company_id)
    if company.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    service.delete(company_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
