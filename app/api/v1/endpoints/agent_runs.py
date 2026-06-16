from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import get_agent_run_service, get_current_organization
from app.core.tenant import TenantContext, require_role
from app.schemas.agent_run import (
    AgentRunCreate,
    AgentRunList,
    AgentRunRead,
    AgentRunUpdate,
)
from app.services import AgentRunService


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.post("", response_model=AgentRunRead, status_code=status.HTTP_201_CREATED)
def create_agent_run(
    payload: AgentRunCreate,
    tenant: TenantContext = Depends(get_current_organization),
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunRead:
    require_role("member", tenant.role, "create agent runs")
    agent_run = service.create(organization_id=tenant.organization_id, **payload.model_dump())
    return AgentRunRead.model_validate(agent_run)


@router.get("", response_model=AgentRunList)
def list_agent_runs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tenant: TenantContext = Depends(get_current_organization),
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunList:
    agent_runs = service.list(organization_id=tenant.organization_id, limit=limit, offset=offset)
    return AgentRunList(
        items=[AgentRunRead.model_validate(r) for r in agent_runs],
        total=len(agent_runs),
        limit=limit,
        offset=offset,
    )


@router.get("/{agent_run_id}", response_model=AgentRunRead)
def get_agent_run(
    agent_run_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunRead:
    agent_run = service.get_required(agent_run_id)
    if agent_run.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this resource.",
        )
    return AgentRunRead.model_validate(agent_run)


@router.patch("/{agent_run_id}", response_model=AgentRunRead)
def update_agent_run(
    agent_run_id: str,
    payload: AgentRunUpdate,
    tenant: TenantContext = Depends(get_current_organization),
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunRead:
    require_role("member", tenant.role, "update agent runs")
    agent_run = service.get_required(agent_run_id)
    if agent_run.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    agent_run = service.update(agent_run_id, **payload.model_dump(exclude_unset=True))
    return AgentRunRead.model_validate(agent_run)


@router.delete("/{agent_run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_run(
    agent_run_id: str,
    tenant: TenantContext = Depends(get_current_organization),
    service: AgentRunService = Depends(get_agent_run_service),
) -> Response:
    require_role("admin", tenant.role, "delete agent runs")
    agent_run = service.get_required(agent_run_id)
    if agent_run.organization_id != tenant.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    service.delete(agent_run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
