from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models.job import Job
from app.services.job_service import JobService


@pytest.fixture
def client() -> TestClient:
    app = create_app(configure_logging_on_startup=False)
    return TestClient(app)


def test_schedule_agent_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "workflow_name": None,
            "correlation_id": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["job_type"] == "agent"
    assert data["target_name"] == "test_agent"
    assert data["status"] == "pending"
    assert data["retry_count"] == 0
    assert data["max_retries"] == 3


def test_schedule_workflow_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-workflow",
        json={
            "workflow_name": "test_workflow",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "contact_id": None,
            "correlation_id": None,
            "requested_by": None,
            "options": {},
            "scheduled_at": None,
            "max_retries": 3,
        },
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["job_type"] == "workflow"
    assert data["target_name"] == "test_workflow"
    assert data["status"] == "pending"


def test_get_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "options": {},
        },
    )
    job_id = response.json()["id"]
    
    response = client.get(f"/jobs/{job_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["target_name"] == "test_agent"


def test_list_jobs_endpoint(client: TestClient) -> None:
    response = client.get("/jobs/")
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


def test_cancel_pending_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "options": {},
        },
    )
    job_id = response.json()["id"]
    
    response = client.post(f"/jobs/{job_id}/cancel")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"


def test_cancel_running_job_endpoint_fails(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "options": {},
        },
    )
    job_id = response.json()["id"]
    
    job_service = JobService()
    job_service.update(job_id, status="running", started_at=datetime.now(timezone.utc))
    
    response = client.post(f"/jobs/{job_id}/cancel")
    
    assert response.status_code == 409


def test_retry_failed_job_endpoint(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "options": {},
        },
    )
    job_id = response.json()["id"]
    
    job_service = JobService()
    job_service.update(job_id, status="failed", completed_at=datetime.now(timezone.utc))
    
    response = client.post(f"/jobs/{job_id}/retry")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert data["retry_count"] == 1


def test_retry_non_failed_job_endpoint_fails(client: TestClient) -> None:
    response = client.post(
        "/jobs/schedule-agent",
        json={
            "agent_name": "test_agent",
            "company_id": "11111111-1111-1111-1111-111111111111",
            "options": {},
        },
    )
    job_id = response.json()["id"]
    
    response = client.post(f"/jobs/{job_id}/retry")
    
    assert response.status_code == 409