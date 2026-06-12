from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AuthSettings, DatabaseSettings, LoggingSettings, Settings
from app.database import session as database_session
from app.main import create_app


OBSERVED_AT = "2026-06-01T10:00:00Z"
MISSING_UUID = "00000000-0000-0000-0000-000000000000"


@pytest.fixture()
def api_session_factory(
    migrated_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    factory = sessionmaker(
        bind=migrated_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    monkeypatch.setattr(database_session, "SessionLocal", factory)
    return factory


@pytest.fixture()
def client(api_session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    app = create_app(_test_settings(), configure_logging_on_startup=False)
    with TestClient(app) as test_client:
        yield test_client


def test_agent_run_crud_endpoints(client: TestClient) -> None:
    company = _create_company(client, domain="agent-run-parent.example")
    contact = _create_contact(client, company_id=company["id"])

    created = client.post(
        "/agent-runs",
        json={
            "company_id": company["id"],
            "contact_id": contact["id"],
            "agent_name": "Intelligence Scoring Agent",
            "workflow_name": "lead_intelligence",
            "status": "running",
            "input_summary": "Scoring existing company and contact records.",
            "started_at": OBSERVED_AT,
        },
    )

    assert created.status_code == 201
    agent_run = created.json()
    assert agent_run["company_id"] == company["id"]
    assert agent_run["contact_id"] == contact["id"]
    assert agent_run["agent_name"] == "Intelligence Scoring Agent"

    listed = client.get("/agent-runs", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == agent_run["id"]

    fetched = client.get(f"/agent-runs/{agent_run['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["workflow_name"] == "lead_intelligence"

    updated = client.patch(
        f"/agent-runs/{agent_run['id']}",
        json={
            "status": "succeeded",
            "output_summary": "Score generated successfully.",
            "finished_at": OBSERVED_AT,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "succeeded"
    assert updated.json()["output_summary"] == "Score generated successfully."

    deleted = client.delete(f"/agent-runs/{agent_run['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/agent-runs/{agent_run['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def test_outreach_message_crud_endpoints(client: TestClient) -> None:
    company = _create_company(client, domain="outreach-parent.example")
    contact = _create_contact(client, company_id=company["id"])
    agent_run = _create_agent_run(client, company_id=company["id"], contact_id=contact["id"])

    created = client.post(
        "/outreach-messages",
        json={
            "company_id": company["id"],
            "contact_id": contact["id"],
            "agent_run_id": agent_run["id"],
            "channel": "email",
            "subject": "Operational intelligence follow-up",
            "message_body": "Your recent signals suggest a timely operational review.",
            "personalization_angle": "Recent technology and intent signals",
            "call_to_action": "Book a short discovery call",
            "status": "draft",
            "confidence": 0.82,
            "generated_at": OBSERVED_AT,
        },
    )

    assert created.status_code == 201
    outreach_message = created.json()
    assert outreach_message["company_id"] == company["id"]
    assert outreach_message["contact_id"] == contact["id"]
    assert outreach_message["agent_run_id"] == agent_run["id"]
    assert outreach_message["channel"] == "email"

    listed = client.get("/outreach-messages", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == outreach_message["id"]

    fetched = client.get(f"/outreach-messages/{outreach_message['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["subject"] == "Operational intelligence follow-up"

    updated = client.patch(
        f"/outreach-messages/{outreach_message['id']}",
        json={"status": "ready_for_review", "confidence": 0.9},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "ready_for_review"
    assert updated.json()["confidence"] == 0.9

    deleted = client.delete(f"/outreach-messages/{outreach_message['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/outreach-messages/{outreach_message['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def test_crud_phase_3_error_responses_are_structured(client: TestClient) -> None:
    invalid_agent_run = client.post(
        "/agent-runs",
        json={
            "company_id": MISSING_UUID,
            "agent_name": "Intent Signal Agent",
            "status": "running",
            "started_at": OBSERVED_AT,
        },
    )
    assert invalid_agent_run.status_code == 409
    assert invalid_agent_run.json()["error"]["code"] == "irtiqa.entity_conflict"

    company = _create_company(client, domain="phase-three-errors.example")

    invalid_outreach_status = client.post(
        "/outreach-messages",
        json={
            "company_id": company["id"],
            "channel": "email",
            "message_body": "Invalid status should be rejected.",
            "personalization_angle": "Validation coverage",
            "status": "queued",
            "confidence": 0.8,
            "generated_at": OBSERVED_AT,
        },
    )
    assert invalid_outreach_status.status_code == 422
    assert invalid_outreach_status.json()["error"]["code"] == "irtiqa.request_validation_error"

    invalid_agent_status = client.post(
        "/agent-runs",
        json={
            "agent_name": "Personalization Agent",
            "status": "complete",
            "started_at": OBSERVED_AT,
        },
    )
    assert invalid_agent_status.status_code == 422
    assert invalid_agent_status.json()["error"]["code"] == "irtiqa.request_validation_error"

    invalid_pagination = client.get("/agent-runs", params={"limit": 0})
    assert invalid_pagination.status_code == 422
    assert invalid_pagination.json()["error"]["code"] == "irtiqa.request_validation_error"

    missing = client.delete(f"/outreach-messages/{MISSING_UUID}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def _create_company(client: TestClient, *, domain: str) -> dict[str, object]:
    response = client.post(
        "/companies",
        json={"name": "Parent Company", "domain": domain, "status": "active"},
    )
    assert response.status_code == 201
    return response.json()


def _create_contact(client: TestClient, *, company_id: object) -> dict[str, object]:
    response = client.post(
        "/contacts",
        json={
            "company_id": company_id,
            "first_name": "Asha",
            "last_name": "Rao",
            "full_name": "Asha Rao",
            "email": f"asha.rao.{company_id}@example.com",
            "title": "VP Revenue",
            "status": "active",
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_agent_run(
    client: TestClient,
    *,
    company_id: object,
    contact_id: object,
) -> dict[str, object]:
    response = client.post(
        "/agent-runs",
        json={
            "company_id": company_id,
            "contact_id": contact_id,
            "agent_name": "Personalization Agent",
            "workflow_name": "lead_intelligence",
            "status": "running",
            "input_summary": "Preparing outreach from existing records.",
            "started_at": OBSERVED_AT,
        },
    )
    assert response.status_code == 201
    return response.json()


def _test_settings(database_url: str = "sqlite:///:memory:") -> Settings:
    return Settings(
        database=DatabaseSettings(
            url=database_url,
            echo=False,
            pool_pre_ping=True,
            sqlite_foreign_keys=True,
            sqlite_journal_mode="WAL",
            sqlite_busy_timeout_ms=5000,
        ),
        logging=LoggingSettings(
            level="INFO",
            app_level="INFO",
            database_level="WARNING",
            repository_level="INFO",
            console_enabled=False,
            file_enabled=False,
            file_path=Path("unused.log"),
            file_max_bytes=10_485_760,
            file_backup_count=5,
            format="%(levelname)s:%(name)s:%(message)s",
            date_format="%Y-%m-%dT%H:%M:%S%z",
        ),
        auth=AuthSettings(),
    )
