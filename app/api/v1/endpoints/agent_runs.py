from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import get_agent_run_service
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
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunRead:
    agent_run = service.create(**payload.model_dump())
    return AgentRunRead.model_validate(agent_run)


@router.get("", response_model=AgentRunList)
def list_agent_runs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunList:
    agent_runs = service.list(limit=limit, offset=offset)
    return AgentRunList(
        items=[AgentRunRead.model_validate(agent_run) for agent_run in agent_runs],
        total=service.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/{agent_run_id}", response_model=AgentRunRead)
def get_agent_run(
    agent_run_id: str,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunRead:
    agent_run = service.get_required(agent_run_id)
    return AgentRunRead.model_validate(agent_run)


@router.patch("/{agent_run_id}", response_model=AgentRunRead)
def update_agent_run(
    agent_run_id: str,
    payload: AgentRunUpdate,
    service: AgentRunService = Depends(get_agent_run_service),
) -> AgentRunRead:
    agent_run = service.update(agent_run_id, **payload.model_dump(exclude_unset=True))
    return AgentRunRead.model_validate(agent_run)


@router.delete("/{agent_run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent_run(
    agent_run_id: str,
    service: AgentRunService = Depends(get_agent_run_service),
) -> Response:
    service.delete(agent_run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
