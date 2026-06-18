from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_organization, get_lead_retrieval_service
from app.core.tenant import TenantContext
from app.schemas.lead import LeadListResponse
from app.services.lead_retrieval_service import LeadRetrievalService


router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=LeadListResponse)
def list_leads(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    minimum_score: float | None = Query(default=None, ge=0.0, le=100.0),
    tenant: TenantContext = Depends(get_current_organization),
    service: LeadRetrievalService = Depends(get_lead_retrieval_service),
) -> LeadListResponse:
    """Retrieve aggregated lead intelligence for the authenticated organization.

    Returns companies along with their technologies, intent signals,
    latest intelligence score, and outreach messages. Results are scoped
    to the caller's organization.

    Query parameters:
        limit: Maximum number of leads to return (1-500, default 100).
        offset: Number of leads to skip (default 0).
        minimum_score: If provided, only return leads whose latest total
            intelligence score is >= this value.
    """
    return service.get_leads(
        organization_id=tenant.organization_id,
        limit=limit,
        offset=offset,
        minimum_score=minimum_score,
    )
