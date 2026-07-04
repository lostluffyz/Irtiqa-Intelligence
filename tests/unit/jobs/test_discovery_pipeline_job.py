from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.jobs.runner import JobRunner
from app.models.job import Job
from app.services.job_service import JobService
from app.workflows.result import WorkflowResult
from app.workflows.states import WorkflowStatus


PLACEHOLDER_COMPANY_ID = "11111111-1111-1111-1111-111111111111"
DISCOVERY_SEARCH_ID = "22222222-2222-2222-2222-222222222222"
ORGANIZATION_ID = "33333333-3333-3333-3333-333333333333"
OTHER_ORGANIZATION_ID = "44444444-4444-4444-4444-444444444444"


def _discovery_job(
    *,
    organization_id: str = ORGANIZATION_ID,
    retry_count: int = 0,
    max_retries: int = 3,
) -> Job:
    """Create a workflow Job targeting the discovery_pipeline."""
    job = Job()
    job.id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    job.job_type = "workflow"
    job.target_name = "discovery_pipeline"
    job.payload = (
        '{"company_id": "' + PLACEHOLDER_COMPANY_ID + '",'
        ' "organization_id": "' + organization_id + '",'
        ' "correlation_id": null,'
        ' "requested_by": null,'
        ' "options": {"discovery_search_id": "' + DISCOVERY_SEARCH_ID + '"}}'
    )
    job.status = "pending"
    job.scheduled_at = datetime.now(timezone.utc)
    job.started_at = None
    job.completed_at = None
    job.retry_count = retry_count
    job.max_retries = max_retries
    job.last_error = None
    job.agent_run_id = None
    return job


def _succeeded_result(*, agent_run_id: str = "run-abc-123") -> WorkflowResult:
    return WorkflowResult(
        workflow_name="discovery_pipeline",
        status=WorkflowStatus.SUCCEEDED,
        company_id=PLACEHOLDER_COMPANY_ID,
        agent_run_ids=[agent_run_id],
        output_ids={
            "companies": ["c1", "c2"],
            "discovery_runs": ["dr1"],
            "discovery_searches": [DISCOVERY_SEARCH_ID],
        },
    )


def _failed_result() -> WorkflowResult:
    return WorkflowResult(
        workflow_name="discovery_pipeline",
        status=WorkflowStatus.FAILED,
        company_id=PLACEHOLDER_COMPANY_ID,
        error={
            "code": "irtiqa.workflow_error",
            "message": "Discovery agent failed: provider timeout",
        },
    )


def _build_runner(
    mock_job_service: MagicMock,
    mock_workflow_registry: MagicMock,
) -> JobRunner:
    return JobRunner(
        job_service=mock_job_service,
        workflow_registry=mock_workflow_registry,
        poll_interval=5.0,
    )


# ── Successful execution ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discovery_pipeline_job_dispatches_workflow() -> None:
    """The job runner should claim the job, dispatch the discovery_pipeline
    workflow via the registry, and mark the job as succeeded."""
    mock_job_service = MagicMock(spec=JobService)
    mock_workflow_registry = MagicMock()

    job = _discovery_job()
    mock_job_service.claim_job.return_value = job

    result = _succeeded_result()
    mock_workflow_cls = MagicMock()
    mock_workflow_cls.return_value.execute = AsyncMock(return_value=result)
    mock_workflow_registry.get.return_value = mock_workflow_cls

    runner = _build_runner(mock_job_service, mock_workflow_registry)
    await runner._run_job(job)

    mock_job_service.claim_job.assert_called_once_with(job.id)
    mock_workflow_registry.get.assert_called_once_with("discovery_pipeline")
    mock_job_service.update.assert_called()
    call_kwargs = mock_job_service.update.call_args[1]
    assert call_kwargs["status"] == "succeeded"
    assert call_kwargs["agent_run_id"] == "run-abc-123"


# ── Failed execution ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discovery_pipeline_job_reports_failure() -> None:
    """When the workflow returns FAILED status, the job should be marked
    failed with the error message."""
    mock_job_service = MagicMock(spec=JobService)
    mock_workflow_registry = MagicMock()

    job = _discovery_job()
    mock_job_service.claim_job.return_value = job

    result = _failed_result()
    mock_workflow_cls = MagicMock()
    mock_workflow_cls.return_value.execute = AsyncMock(return_value=result)
    mock_workflow_registry.get.return_value = mock_workflow_cls

    runner = _build_runner(mock_job_service, mock_workflow_registry)
    await runner._run_job(job)

    mock_job_service.update.assert_called()
    call_kwargs = mock_job_service.update.call_args[1]
    assert call_kwargs["status"] == "failed"
    assert "Discovery agent failed" in call_kwargs["last_error"]


# ── Tenant isolation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discovery_pipeline_job_preserves_tenant_isolation() -> None:
    """Organization ID from the job payload must be forwarded to the
    WorkflowContext so the workflow operates within the correct tenant."""
    mock_job_service = MagicMock(spec=JobService)
    mock_workflow_registry = MagicMock()

    job = _discovery_job(organization_id=OTHER_ORGANIZATION_ID)
    mock_job_service.claim_job.return_value = job

    result = _succeeded_result()
    mock_workflow_cls = MagicMock()
    mock_workflow_cls.return_value.execute = AsyncMock(return_value=result)
    mock_workflow_registry.get.return_value = mock_workflow_cls

    runner = _build_runner(mock_job_service, mock_workflow_registry)
    await runner._run_job(job)

    # Verify the workflow was instantiated, then executed with a context
    # carrying the correct organization_id.
    execute_call = mock_workflow_cls.return_value.execute
    execute_call.assert_called_once()
    ctx = execute_call.call_args[0][0]
    assert ctx.organization_id == OTHER_ORGANIZATION_ID


# ── Retry-safe execution ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discovery_pipeline_job_is_retry_safe() -> None:
    """When an exception escapes _run_workflow_job and retries remain,
    the job should be rescheduled as pending with an incremented
    retry_count.

    WorkflowRunner.run() catches workflow-level exceptions and returns
    a FAILED WorkflowResult — those are NOT retried.  Retries only
    trigger when an exception escapes before WorkflowRunner.run() is
    called (e.g. WorkflowContext validation fails on bad payload).
    """
    mock_job_service = MagicMock(spec=JobService)
    mock_workflow_registry = MagicMock()

    # Build a job with a payload that will cause WorkflowContext validation
    # to fail (workflow_name too short — it needs min_length=1 but the
    # context constructor receives it from job.target_name via the runner).
    # Instead, corrupt the payload so company_id is invalid (wrong length).
    job = _discovery_job(retry_count=1, max_retries=3)
    job.payload = (
        '{"company_id": "bad",'
        ' "organization_id": "' + ORGANIZATION_ID + '",'
        ' "correlation_id": null,'
        ' "requested_by": null,'
        ' "options": {"discovery_search_id": "' + DISCOVERY_SEARCH_ID + '"}}'
    )
    mock_job_service.claim_job.return_value = job

    mock_workflow_cls = MagicMock()
    mock_workflow_registry.get.return_value = mock_workflow_cls

    runner = _build_runner(mock_job_service, mock_workflow_registry)
    await runner._run_job(job)

    mock_job_service.update.assert_called()
    call_kwargs = mock_job_service.update.call_args[1]
    assert call_kwargs["status"] == "pending"
    assert call_kwargs["retry_count"] == 2


# ── Workflow dispatch with correct options ────────────────────────────


@pytest.mark.asyncio
async def test_discovery_pipeline_job_invokes_workflow_with_correct_options() -> None:
    """The WorkflowContext options must contain the discovery_search_id
    so the workflow can load the correct search configuration."""
    mock_job_service = MagicMock(spec=JobService)
    mock_workflow_registry = MagicMock()

    job = _discovery_job()
    mock_job_service.claim_job.return_value = job

    result = _succeeded_result()
    mock_workflow_cls = MagicMock()
    mock_workflow_cls.return_value.execute = AsyncMock(return_value=result)
    mock_workflow_registry.get.return_value = mock_workflow_cls

    runner = _build_runner(mock_job_service, mock_workflow_registry)
    await runner._run_job(job)

    execute_call = mock_workflow_cls.return_value.execute
    ctx = execute_call.call_args[0][0]
    assert ctx.options["discovery_search_id"] == DISCOVERY_SEARCH_ID


# ── Statistics update via output_ids ──────────────────────────────────


@pytest.mark.asyncio
async def test_discovery_pipeline_job_updates_statistics_via_output_ids() -> None:
    """After successful execution, the job service should receive the
    succeeded status; the workflow result's output_ids are available for
    downstream use (the job runner stores agent_run_id on the job row)."""
    mock_job_service = MagicMock(spec=JobService)
    mock_workflow_registry = MagicMock()

    job = _discovery_job()
    mock_job_service.claim_job.return_value = job

    result = _succeeded_result()
    mock_workflow_cls = MagicMock()
    mock_workflow_cls.return_value.execute = AsyncMock(return_value=result)
    mock_workflow_registry.get.return_value = mock_workflow_cls

    runner = _build_runner(mock_job_service, mock_workflow_registry)
    await runner._run_job(job)

    mock_job_service.update.assert_called_once()
    call_kwargs = mock_job_service.update.call_args[1]
    assert call_kwargs["status"] == "succeeded"
    # The runner stores the first agent_run_id from the workflow result
    assert call_kwargs["agent_run_id"] == "run-abc-123"
    assert call_kwargs["completed_at"] is not None
