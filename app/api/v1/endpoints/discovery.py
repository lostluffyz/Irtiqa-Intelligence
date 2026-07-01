from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
    get_current_organization,
    get_discovery_run_service,
    get_discovery_search_service,
    get_job_service,
)
from app.core.logging import get_logger
from app.core.tenant import TenantContext, require_role
from app.schemas.discovery import (
    DiscoveryRunList,
    DiscoveryRunRead,
    DiscoverySearchCreate,
    DiscoverySearchList,
    DiscoverySearchRead,
    DiscoverySearchUpdate,
)
from app.services import DiscoveryRunService, DiscoverySearchService, JobService
from app.workflows.context import WorkflowContext


router = APIRouter(prefix="/discovery", tags=["discovery"])
logger = get_logger("api.discovery")


@router.get("/searches", response_model=DiscoverySearchList)
def list_discovery_searches(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_current_organization),
    service: DiscoverySearchService = Depends(get_discovery_search_service),
) -> DiscoverySearchList:
    searches = service.list(
        organization_id=tenant.organization_id,
        limit=limit,
        offset=offset,
    )
    total = service.count_by_organization(tenant.organization_id)
    return DiscoverySearchList(
        items=[DiscoverySearchRead.model_validate(search) for search in searches],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/searches",
    response_model=DiscoverySearchRead,
    status_code=status.HTTP_201_CREATED,
)
def create_discovery_search(
    payload: DiscoverySearchCreate,
    tenant: TenantContext = Depends(get_current_organization),
    service: DiscoverySearchService = Depends(get_discovery_search_service),
) -> DiscoverySearchRead:
    require_role("member", tenant.role, "create discovery searches")
    search = service.create(
        organization_id=tenant.organization_id,
        **payload.model_dump(),
    )
    return DiscoverySearchRead.model_validate(search)


@router.get("/searches/{search_id}", response_model=DiscoverySearchRead)
def get_discovery_search(
    search_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: DiscoverySearchService = Depends(get_discovery_search_service),
) -> DiscoverySearchRead:
    search = service.get_for_organization(
        search_id,
        organization_id=tenant.organization_id,
    )
    return DiscoverySearchRead.model_validate(search)


@router.patch("/searches/{search_id}", response_model=DiscoverySearchRead)
def update_discovery_search(
    search_id: str,
    payload: DiscoverySearchUpdate,
    tenant: TenantContext = Depends(get_current_organization),
    service: DiscoverySearchService = Depends(get_discovery_search_service),
) -> DiscoverySearchRead:
    require_role("member", tenant.role, "update discovery searches")
    search = service.update_for_organization(
        search_id,
        organization_id=tenant.organization_id,
        **payload.model_dump(exclude_unset=True),
    )
    return DiscoverySearchRead.model_validate(search)


@router.delete("/searches/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_discovery_search(
    search_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: DiscoverySearchService = Depends(get_discovery_search_service),
) -> Response:
    require_role("admin", tenant.role, "delete discovery searches")
    service.delete_for_organization(
        search_id,
        organization_id=tenant.organization_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/searches/{search_id}/run",
    response_model=DiscoveryRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_discovery_run(
    search_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    run_service: DiscoveryRunService = Depends(get_discovery_run_service),
    job_service: JobService = Depends(get_job_service),
) -> DiscoveryRunRead:
    require_role("member", tenant.role, "run discovery searches")

    # Progress Token pattern: create run immediately, execute async
    run = run_service.start_run(
        organization_id=tenant.organization_id,
        search_id=search_id,
    )

    # Schedule background workflow with the existing run_id
    # If job scheduling fails, mark run as failed to prevent orphaned runs
    try:
        context = WorkflowContext(
            workflow_name="discovery_pipeline",
            company_id=None,
            contact_id=None,
            organization_id=tenant.organization_id,
            options={
                "discovery_search_id": search_id,
                "discovery_run_id": run.id,
            },
        )
        job_service.schedule_workflow(
            name="discovery_pipeline",
            context=context,
        )
        logger.info(
            "Discovery run scheduled",
            extra={
                "run_id": run.id,
                "search_id": search_id,
                "organization_id": tenant.organization_id,
            },
        )
    except Exception as exc:
        logger.error(
            "Failed to schedule discovery job",
            extra={
                "run_id": run.id,
                "search_id": search_id,
                "organization_id": tenant.organization_id,
                "error_type": exc.__class__.__name__,
            },
            exc_info=True,
        )
        # Mark run as failed if job scheduling fails
        run_service.fail_run(
            run.id,
            organization_id=tenant.organization_id,
            error_message=f"Failed to schedule discovery job: {exc.__class__.__name__}",
        )
        raise

    return DiscoveryRunRead.model_validate(run)


@router.get("/runs/{run_id}", response_model=DiscoveryRunRead)
def get_discovery_run(
    run_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: DiscoveryRunService = Depends(get_discovery_run_service),
) -> DiscoveryRunRead:
    run = service.get_run(
        run_id,
        organization_id=tenant.organization_id,
    )
    return DiscoveryRunRead.model_validate(run)


@router.get("/searches/{search_id}/runs", response_model=DiscoveryRunList)
def list_discovery_runs_for_search(
    search_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_current_organization),
    service: DiscoveryRunService = Depends(get_discovery_run_service),
) -> DiscoveryRunList:
    runs = service.list_by_search(
        search_id,
        organization_id=tenant.organization_id,
        limit=limit,
        offset=offset,
    )
    return DiscoveryRunList(
        items=[DiscoveryRunRead.model_validate(run) for run in runs],
        total=len(runs),
        limit=limit,
        offset=offset,
    )
