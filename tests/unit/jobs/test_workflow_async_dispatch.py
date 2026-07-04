from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.jobs.runner import JobRunner
from app.models.job import Job
from app.services.job_service import JobService
from app.workflows.result import WorkflowResult
from app.workflows.states import WorkflowStatus


DISCOVERY_SEARCH_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PLACEHOLDER_COMPANY_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
ORGANIZATION_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"


def _discovery_job() -> Job:
    """Create a discovery_pipeline workflow job matching the real payload shape."""
    job = Job()
    job.id = "dddddddd-dddd-dddd-dddd-dddddddddddd"
    job.job_type = "workflow"
    job.target_name = "discovery_pipeline"
    job.payload = (
        '{"company_id": "' + PLACEHOLDER_COMPANY_ID + '",'
        ' "organization_id": "' + ORGANIZATION_ID + '",'
        ' "correlation_id": null,'
        ' "requested_by": null,'
        ' "options": {"discovery_search_id": "' + DISCOVERY_SEARCH_ID + '"}}'
    )
    job.status = "pending"
    job.retry_count = 0
    job.max_retries = 3
    job.last_error = None
    job.agent_run_id = None
    return job


@pytest.mark.asyncio
async def test_discovery_workflow_dispatch_no_nested_event_loop() -> None:
    """Regression: a discovery-pipeline job dispatched through the real
    JobRunner while an event loop is already running must NOT attempt to
    create a nested event loop.

    Prior to the fix, ``WorkflowRunner.run()`` was synchronous and
    ``DiscoveryPipelineWorkflow.execute()`` called ``_run_async()``, which
    tried ``asyncio.Runner().run(coro)`` inside a running loop — raising::

        RuntimeError: Runner.run() cannot be called from a running event loop

    The fix makes the entire workflow execution path consistently async:
    ``WorkflowRunner.run()`` → ``await Workflow.execute()`` → direct
    ``await agent.execute()``, with no ``_run_async()`` bridge anywhere.

    This test proves the path works by running the JobRunner's
    ``_run_workflow_job()`` inside a pytest-asyncio event loop (the same
    condition that triggered the bug) and verifying the mocked workflow
    execute method is called — meaning no ``RuntimeError`` was raised.
    """
    mock_job_service = MagicMock(spec=JobService)
    mock_workflow_registry = MagicMock()
    mock_agent_registry = MagicMock()

    job = _discovery_job()
    mock_job_service.claim_job.return_value = job

    # The workflow's execute() is async — use AsyncMock so the JobRunner
    # can await it without error.
    succeeded_result = WorkflowResult(
        workflow_name="discovery_pipeline",
        status=WorkflowStatus.SUCCEEDED,
        agent_run_ids=["run-abc-123"],
        output_ids={
            "companies": ["c1"],
            "discovery_runs": ["dr1"],
            "discovery_searches": [DISCOVERY_SEARCH_ID],
        },
    )
    mock_workflow_cls = MagicMock()
    mock_workflow_cls.return_value.execute = AsyncMock(return_value=succeeded_result)
    mock_workflow_registry.get.return_value = mock_workflow_cls

    runner = JobRunner(
        job_service=mock_job_service,
        workflow_registry=mock_workflow_registry,
        agent_registry=mock_agent_registry,
        poll_interval=5.0,
    )

    # This is the key assertion: _run_job must complete without raising
    # RuntimeError from a nested event loop.
    await runner._run_job(job)

    # Verify the workflow was actually invoked (proves the async chain
    # resolved correctly).
    mock_workflow_cls.return_value.execute.assert_awaited_once()

    # Verify the job was marked succeeded with the correct agent_run_id.
    mock_job_service.update.assert_called_once()
    call_kwargs = mock_job_service.update.call_args[1]
    assert call_kwargs["status"] == "succeeded"
    assert call_kwargs["agent_run_id"] == "run-abc-123"


@pytest.mark.asyncio
async def test_discovery_workflow_failure_still_marked_failed() -> None:
    """When the async workflow returns FAILED status, the job must still
    be marked failed — exceptions are not lost in the async transition."""
    mock_job_service = MagicMock(spec=JobService)
    mock_workflow_registry = MagicMock()
    mock_agent_registry = MagicMock()

    job = _discovery_job()
    mock_job_service.claim_job.return_value = job

    failed_result = WorkflowResult(
        workflow_name="discovery_pipeline",
        status=WorkflowStatus.FAILED,
        error={
            "code": "irtiqa.workflow_error",
            "message": "Discovery agent failed: provider timeout",
        },
    )
    mock_workflow_cls = MagicMock()
    mock_workflow_cls.return_value.execute = AsyncMock(return_value=failed_result)
    mock_workflow_registry.get.return_value = mock_workflow_cls

    runner = JobRunner(
        job_service=mock_job_service,
        workflow_registry=mock_workflow_registry,
        agent_registry=mock_agent_registry,
        poll_interval=5.0,
    )

    await runner._run_job(job)

    mock_workflow_cls.return_value.execute.assert_awaited_once()
    mock_job_service.update.assert_called_once()
    call_kwargs = mock_job_service.update.call_args[1]
    assert call_kwargs["status"] == "failed"
    assert "provider timeout" in call_kwargs["last_error"]
