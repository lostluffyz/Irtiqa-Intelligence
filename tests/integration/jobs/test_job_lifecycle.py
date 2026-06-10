from __future__ import annotations

from datetime import datetime, timezone
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.agents.context import AgentContext
from app.main import create_app
from app.models.job import Job
from app.services.job_service import JobService


@pytest.fixture
def client() -> TestClient:
    app = create_app(configure_logging_on_startup=False)
    return TestClient(app)


@pytest.fixture
def job_service() -> JobService:
    return JobService()


def test_schedule_agent_job_creates_pending_job(
    client: TestClient,
    job_service: JobService,
) -> None:
    context = AgentContext(
        agent_name="test_agent",
        company_id="11111111-1111-1111-1111-111111111111",
        contact_id=None,
        workflow_name=None,
        correlation_id=None,
        options={},
    )
    
    job = job_service.schedule_agent(
        name="test_agent",
        context=context,
        scheduled_at=None,
        max_retries=3,
    )
    
    assert job.id is not None
    assert job.job_type == "agent"
    assert job.target_name == "test_agent"
    assert job.status == "pending"
    assert job.retry_count == 0
    assert job.max_retries == 3
    
    payload = json.loads(job.payload)
    assert payload["company_id"] == "11111111-1111-1111-1111-111111111111"


def test_schedule_workflow_job_creates_pending_job(
    client: TestClient,
    job_service: JobService,
) -> None:
    from app.workflows.context import WorkflowContext
    
    context = WorkflowContext(
        workflow_name="test_workflow",
        company_id="11111111-1111-1111-1111-111111111111",
        contact_id=None,
        correlation_id=None,
        requested_by=None,
        options={},
    )
    
    job = job_service.schedule_workflow(
        name="test_workflow",
        context=context,
        scheduled_at=None,
        max_retries=3,
    )
    
    assert job.id is not None
    assert job.job_type == "workflow"
    assert job.target_name == "test_workflow"
    assert job.status == "pending"


def test_cancel_pending_job(job_service: JobService) -> None:
    context = AgentContext(
        agent_name="test_agent",
        company_id="11111111-1111-1111-1111-111111111111",
        contact_id=None,
        workflow_name=None,
        correlation_id=None,
        options={},
    )
    
    job = job_service.schedule_agent("test_agent", context)
    
    cancelled_job = job_service.cancel_job(job.id)
    
    assert cancelled_job.status == "cancelled"
    assert cancelled_job.completed_at is not None


def test_cancel_running_job_fails(job_service: JobService) -> None:
    context = AgentContext(
        agent_name="test_agent",
        company_id="11111111-1111-1111-1111-111111111111",
        contact_id=None,
        workflow_name=None,
        correlation_id=None,
        options={},
    )
    
    job = job_service.schedule_agent("test_agent", context)
    
    # Manually set to running
    job_service.update(job.id, status="running", started_at=datetime.now(timezone.utc))
    
    from app.core.errors import ServiceError
    with pytest.raises(ServiceError):
        job_service.cancel_job(job.id)


def test_retry_failed_job(job_service: JobService) -> None:
    context = AgentContext(
        agent_name="test_agent",
        company_id="11111111-1111-1111-1111-111111111111",
        contact_id=None,
        workflow_name=None,
        correlation_id=None,
        options={},
    )
    
    job = job_service.schedule_agent("test_agent", context)
    job_service.update(job.id, status="failed", completed_at=datetime.now(timezone.utc))
    
    retried_job = job_service.retry_job(job.id)
    
    assert retried_job.status == "pending"
    assert retried_job.retry_count == 1
    assert retried_job.scheduled_at is not None
    assert retried_job.last_error is None


def test_retry_non_failed_job_fails(job_service: JobService) -> None:
    context = AgentContext(
        agent_name="test_agent",
        company_id="11111111-1111-1111-1111-111111111111",
        contact_id=None,
        workflow_name=None,
        correlation_id=None,
        options={},
    )
    
    job = job_service.schedule_agent("test_agent", context)
    
    from app.core.errors import ServiceError
    with pytest.raises(ServiceError):
        job_service.retry_job(job.id)


def test_list_jobs_with_filters(job_service: JobService) -> None:
    import uuid
    context = AgentContext(
        agent_name="test_agent",
        company_id="11111111-1111-1111-1111-111111111111",
        contact_id=None,
        workflow_name=None,
        correlation_id=None,
        options={},
    )
    
    unique_suffix = str(uuid.uuid4())[:8]
    job1 = job_service.schedule_agent(f"agent_one_filter_test_{unique_suffix}", context)
    job2 = job_service.schedule_agent(f"agent_two_filter_test_{unique_suffix}", context)
    job_service.update(job2.id, status="failed", completed_at=datetime.now(timezone.utc))
    
    jobs = job_service.list_jobs(status="pending", target_name=f"agent_one_filter_test_{unique_suffix}", limit=50, offset=0)
    assert len(jobs) == 1
    assert jobs[0].target_name == f"agent_one_filter_test_{unique_suffix}"
    
    jobs = job_service.list_jobs(status="failed", target_name=f"agent_two_filter_test_{unique_suffix}", limit=50, offset=0)
    assert len(jobs) == 1
    assert jobs[0].target_name == f"agent_two_filter_test_{unique_suffix}"