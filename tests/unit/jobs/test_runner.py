from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.jobs.runner import JobRunner
from app.models.job import Job
from app.services.job_service import JobService


@pytest.fixture
def mock_job_service() -> MagicMock:
    return MagicMock(spec=JobService)


@pytest.fixture
def mock_agent_registry() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_workflow_registry() -> MagicMock:
    return MagicMock()


@pytest.fixture
def sample_job() -> Job:
    job = Job()
    job.id = "11111111-1111-1111-1111-111111111111"
    job.job_type = "agent"
    job.target_name = "test_agent"
    job.payload = '{"company_id": "11111111-1111-1111-1111-111111111111", "contact_id": null, "workflow_name": null, "correlation_id": null, "options": {}}'
    job.status = "pending"
    job.scheduled_at = datetime.now(timezone.utc)
    job.started_at = None
    job.completed_at = None
    job.retry_count = 0
    job.max_retries = 3
    job.last_error = None
    job.agent_run_id = None
    return job


@pytest.mark.asyncio
async def test_runner_claims_job_and_executes(
    mock_job_service: MagicMock,
    mock_agent_registry: MagicMock,
    sample_job: Job,
) -> None:
    mock_job_service.get_next_jobs.return_value = [sample_job]
    mock_job_service.claim_job.return_value = sample_job
    
    mock_agent_class = MagicMock()
    mock_agent_instance = AsyncMock()
    mock_agent_instance.execute = AsyncMock()
    mock_agent_instance.execute.return_value = MagicMock(
        agent_run_id="test-run-id",
        output_ids={"test": ["1"]},
        summary="Test completed",
    )
    mock_agent_class.return_value = mock_agent_instance
    mock_agent_registry.get.return_value = mock_agent_class

    runner = JobRunner(
        job_service=mock_job_service,
        agent_registry=mock_agent_registry,
        poll_interval=5.0,
    )
    
    await runner._run_job(sample_job)
    
    mock_job_service.claim_job.assert_called_once_with(sample_job.id)
    mock_agent_registry.get.assert_called_once_with("test_agent")
    mock_agent_instance.execute.assert_called_once()
    mock_job_service.update.assert_called()


@pytest.mark.asyncio
async def test_runner_skips_already_claimed_job(
    mock_job_service: MagicMock,
    mock_agent_registry: MagicMock,
    sample_job: Job,
) -> None:
    mock_job_service.get_next_jobs.return_value = [sample_job]
    mock_job_service.claim_job.return_value = None  # Already claimed
    
    runner = JobRunner(
        job_service=mock_job_service,
        agent_registry=mock_agent_registry,
        poll_interval=5.0,
    )
    
    await runner._run_job(sample_job)
    
    mock_agent_registry.get.assert_not_called()


@pytest.mark.asyncio
async def test_runner_handles_agent_failure_with_retry(
    mock_job_service: MagicMock,
    mock_agent_registry: MagicMock,
    sample_job: Job,
) -> None:
    sample_job.retry_count = 0
    sample_job.max_retries = 3
    
    mock_job_service.claim_job.return_value = sample_job
    
    mock_agent_class = MagicMock()
    mock_agent_instance = AsyncMock()
    mock_agent_instance.execute = AsyncMock(side_effect=Exception("Agent failed"))
    mock_agent_class.return_value = mock_agent_instance
    mock_agent_registry.get.return_value = mock_agent_class

    runner = JobRunner(
        job_service=mock_job_service,
        agent_registry=mock_agent_registry,
        poll_interval=5.0,
    )
    
    await runner._run_job(sample_job)
    
    # Should update job to pending with incremented retry count
    mock_job_service.update.assert_called()
    call_args = mock_job_service.update.call_args
    assert call_args[1]["status"] == "pending"
    assert call_args[1]["retry_count"] == 1


@pytest.mark.asyncio
async def test_runner_handles_agent_failure_no_retries_left(
    mock_job_service: MagicMock,
    mock_agent_registry: MagicMock,
    sample_job: Job,
) -> None:
    sample_job.retry_count = 3
    sample_job.max_retries = 3
    
    mock_job_service.claim_job.return_value = sample_job
    
    mock_agent_class = MagicMock()
    mock_agent_instance = AsyncMock()
    mock_agent_instance.execute = AsyncMock(side_effect=Exception("Agent failed"))
    mock_agent_class.return_value = mock_agent_instance
    mock_agent_registry.get.return_value = mock_agent_class

    runner = JobRunner(
        job_service=mock_job_service,
        agent_registry=mock_agent_registry,
        poll_interval=5.0,
    )

    await runner._run_job(sample_job)

    # Should update job to failed
    mock_job_service.update.assert_called()
    call_args = mock_job_service.update.call_args
    assert call_args[1]["status"] == "failed"


@pytest.mark.asyncio
async def test_runner_dispatches_workflow_job(
    mock_job_service: MagicMock,
    mock_workflow_registry: MagicMock,
) -> None:
    """Verify workflow job dispatch uses agent_run_ids[0] for the job FK."""
    wf_job = Job()
    wf_job.id = "22222222-2222-2222-2222-222222222222"
    wf_job.job_type = "workflow"
    wf_job.target_name = "test_workflow"
    wf_job.payload = '{"company_id": "11111111-1111-1111-1111-111111111111"}'
    wf_job.status = "pending"
    wf_job.scheduled_at = datetime.now(timezone.utc)
    wf_job.started_at = None
    wf_job.completed_at = None
    wf_job.retry_count = 0
    wf_job.max_retries = 3
    wf_job.last_error = None
    wf_job.agent_run_id = None

    mock_job_service.get_next_jobs.return_value = [wf_job]
    mock_job_service.claim_job.return_value = wf_job

    # Use a real WorkflowResult to avoid MagicMock attribute surprises
    from app.workflows.result import WorkflowResult
    from app.workflows.states import WorkflowStatus

    real_result = WorkflowResult(
        workflow_name="test_workflow",
        status=WorkflowStatus.SUCCEEDED,
        agent_run_ids=["run-1", "run-2", "run-3"],
        output_ids={"scores": ["1"]},
    )

    mock_workflow_cls = MagicMock()
    mock_workflow_cls.return_value.execute.return_value = real_result
    mock_workflow_registry.get.return_value = mock_workflow_cls

    runner = JobRunner(
        job_service=mock_job_service,
        workflow_registry=mock_workflow_registry,
        poll_interval=5.0,
    )

    await runner._run_job(wf_job)

    mock_job_service.claim_job.assert_called_once_with(wf_job.id)
    mock_workflow_registry.get.assert_called_once_with("test_workflow")
    mock_job_service.update.assert_called()
    # Verify the job was updated with the FIRST agent_run_id
    call_kwargs = mock_job_service.update.call_args[1]
    assert call_kwargs["status"] == "succeeded"
    assert call_kwargs["agent_run_id"] == "run-1"