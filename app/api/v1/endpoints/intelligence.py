from __future__ import annotations

from pydantic import Field

from app.api.dependencies import get_job_service
from app.schemas.base import IrtiqaSchema
from app.schemas.job import JobRead
from app.services.job_service import JobService
from app.workflows.context import WorkflowContext
from fastapi import APIRouter, Depends, status


class PipelineTriggerRequest(IrtiqaSchema):
    company_id: str = Field(min_length=1, max_length=36)
    contact_id: str | None = Field(default=None, min_length=36, max_length=36)
    options: dict = Field(default_factory=dict)


class PipelineTriggerResponse(IrtiqaSchema):
    job_id: str
    status: str = "scheduled"
    target_name: str = "intelligence_pipeline"


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.post(
    "/pipeline",
    response_model=PipelineTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_pipeline(
    payload: PipelineTriggerRequest,
    job_service: JobService = Depends(get_job_service),
) -> PipelineTriggerResponse:
    context = WorkflowContext(
        workflow_name="intelligence_pipeline",
        company_id=payload.company_id,
        contact_id=payload.contact_id,
        options=payload.options,
    )
    job = job_service.schedule_workflow(
        name="intelligence_pipeline",
        context=context,
    )
    return PipelineTriggerResponse(
        job_id=job.id,
        status="scheduled",
        target_name="intelligence_pipeline",
    )


@router.get("/pipeline/{job_id}", response_model=JobRead)
def get_pipeline_status(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
) -> JobRead:
    job = job_service.get_required(job_id)
    return JobRead.model_validate(job)
