from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.api.dependencies import get_job_service
from app.schemas.job import (
    JobList,
    JobRead,
    JobScheduleAgentRequest,
    JobScheduleWorkflowRequest,
)
from app.services import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/schedule-agent", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def schedule_agent_job(
    payload: JobScheduleAgentRequest,
    service: JobService = Depends(get_job_service),
) -> JobRead:
    from app.agents.context import AgentContext

    context = AgentContext(
        agent_name=payload.agent_name,
        company_id=payload.company_id,
        contact_id=payload.contact_id,
        workflow_name=payload.workflow_name,
        correlation_id=payload.correlation_id,
        options=payload.options,
    )
    job = service.schedule_agent(
        name=payload.agent_name,
        context=context,
        scheduled_at=payload.scheduled_at,
        max_retries=payload.max_retries,
    )
    return JobRead.model_validate(job)


@router.post("/schedule-workflow", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def schedule_workflow_job(
    payload: JobScheduleWorkflowRequest,
    service: JobService = Depends(get_job_service),
) -> JobRead:
    from app.workflows.context import WorkflowContext

    context = WorkflowContext(
        workflow_name=payload.workflow_name,
        company_id=payload.company_id,
        contact_id=payload.contact_id,
        correlation_id=payload.correlation_id,
        requested_by=payload.requested_by,
        options=payload.options,
    )
    job = service.schedule_workflow(
        name=payload.workflow_name,
        context=context,
        scheduled_at=payload.scheduled_at,
        max_retries=payload.max_retries,
    )
    return JobRead.model_validate(job)


@router.get("", response_model=JobList)
def list_jobs(
    status: str | None = Query(default=None),
    target_name: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: JobService = Depends(get_job_service),
) -> JobList:
    jobs = service.list_jobs(status=status, target_name=target_name, limit=limit, offset=offset)
    total = service.count()
    return JobList(
        items=[JobRead.model_validate(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: str,
    service: JobService = Depends(get_job_service),
) -> JobRead:
    job = service.get_required(job_id)
    return JobRead.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobRead)
def cancel_job(
    job_id: str,
    service: JobService = Depends(get_job_service),
) -> JobRead:
    job = service.cancel_job(job_id)
    return JobRead.model_validate(job)


@router.post("/{job_id}/retry", response_model=JobRead)
def retry_job(
    job_id: str,
    service: JobService = Depends(get_job_service),
) -> JobRead:
    job = service.retry_job(job_id)
    return JobRead.model_validate(job)