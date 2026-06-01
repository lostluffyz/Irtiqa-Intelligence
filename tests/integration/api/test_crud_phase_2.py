from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DatabaseSettings, LoggingSettings, Settings
from app.database import session as database_session
from app.main import create_app


OBSERVED_AT = "2026-06-01T10:00:00Z"


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


def test_technology_crud_endpoints(client: TestClient) -> None:
    company = _create_company(client, domain="technology-parent.example")
    website = _create_website(client, company_id=company["id"])

    created = client.post(
        "/technologies",
        json={
            "company_id": company["id"],
            "website_id": website["id"],
            "name": "HubSpot",
            "category": "crm",
            "vendor": "HubSpot",
            "detection_method": "html_signature",
            "confidence": 0.92,
            "first_detected_at": OBSERVED_AT,
            "last_detected_at": OBSERVED_AT,
        },
    )

    assert created.status_code == 201
    technology = created.json()
    assert technology["company_id"] == company["id"]
    assert technology["website_id"] == website["id"]
    assert technology["name"] == "HubSpot"

    listed = client.get("/technologies", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == technology["id"]

    fetched = client.get(f"/technologies/{technology['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["category"] == "crm"

    updated = client.patch(
        f"/technologies/{technology['id']}",
        json={"confidence": 0.84, "vendor": "HubSpot Inc."},
    )
    assert updated.status_code == 200
    assert updated.json()["confidence"] == 0.84
    assert updated.json()["vendor"] == "HubSpot Inc."

    deleted = client.delete(f"/technologies/{technology['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/technologies/{technology['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def test_intent_signal_crud_endpoints(client: TestClient) -> None:
    company = _create_company(client, domain="intent-parent.example")
    website = _create_website(client, company_id=company["id"])
    technology = _create_technology(client, company_id=company["id"], website_id=website["id"])

    created = client.post(
        "/intent-signals",
        json={
            "company_id": company["id"],
            "website_id": website["id"],
            "technology_id": technology["id"],
            "signal_type": "technology_change",
            "signal_name": "CRM detected",
            "signal_value": "HubSpot detected on homepage",
            "strength": 0.75,
            "confidence": 0.88,
            "source_url": "https://intent-parent.example",
            "observed_at": OBSERVED_AT,
        },
    )

    assert created.status_code == 201
    intent_signal = created.json()
    assert intent_signal["company_id"] == company["id"]
    assert intent_signal["technology_id"] == technology["id"]
    assert intent_signal["signal_type"] == "technology_change"

    listed = client.get("/intent-signals", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == intent_signal["id"]

    fetched = client.get(f"/intent-signals/{intent_signal['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["signal_name"] == "CRM detected"

    updated = client.patch(
        f"/intent-signals/{intent_signal['id']}",
        json={"strength": 0.81, "confidence": 0.9},
    )
    assert updated.status_code == 200
    assert updated.json()["strength"] == 0.81
    assert updated.json()["confidence"] == 0.9

    deleted = client.delete(f"/intent-signals/{intent_signal['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/intent-signals/{intent_signal['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def test_intelligence_score_crud_endpoints(client: TestClient) -> None:
    company = _create_company(client, domain="score-parent.example")
    website = _create_website(client, company_id=company["id"])
    technology = _create_technology(client, company_id=company["id"], website_id=website["id"])

    created = client.post(
        "/intelligence-scores",
        json={
            "company_id": company["id"],
            "technology_id": technology["id"],
            "fit_score": 82.0,
            "intent_score": 76.0,
            "technographic_score": 91.0,
            "engagement_score": 70.0,
            "total_score": 81.4,
            "confidence": 0.86,
            "score_version": "api-test-v1",
            "rationale": "Strong fit based on explicit API test records.",
            "scored_at": OBSERVED_AT,
        },
    )

    assert created.status_code == 201
    score = created.json()
    assert score["company_id"] == company["id"]
    assert score["technology_id"] == technology["id"]
    assert score["total_score"] == 81.4

    listed = client.get("/intelligence-scores", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == score["id"]

    fetched = client.get(f"/intelligence-scores/{score['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["score_version"] == "api-test-v1"

    updated = client.patch(
        f"/intelligence-scores/{score['id']}",
        json={"total_score": 84.2, "confidence": 0.9},
    )
    assert updated.status_code == 200
    assert updated.json()["total_score"] == 84.2
    assert updated.json()["confidence"] == 0.9

    deleted = client.delete(f"/intelligence-scores/{score['id']}")
    assert deleted.status_code == 204

    missing = client.get(f"/intelligence-scores/{score['id']}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def test_crud_phase_2_error_responses_are_structured(client: TestClient) -> None:
    company = _create_company(client, domain="phase-two-errors.example")
    website = _create_website(client, company_id=company["id"])
    technology = _create_technology(client, company_id=company["id"], website_id=website["id"])

    conflict = client.post(
        "/technologies",
        json={
            "company_id": company["id"],
            "website_id": website["id"],
            "name": technology["name"],
            "category": technology["category"],
            "vendor": "Duplicate",
            "detection_method": "html_signature",
            "confidence": 0.77,
            "first_detected_at": OBSERVED_AT,
            "last_detected_at": OBSERVED_AT,
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "irtiqa.entity_conflict"

    invalid_payload = client.post(
        "/intent-signals",
        json={
            "company_id": company["id"],
            "signal_type": "technology_change",
            "signal_name": "Invalid strength",
            "strength": 1.5,
            "confidence": 0.8,
            "observed_at": OBSERVED_AT,
        },
    )
    assert invalid_payload.status_code == 422
    assert invalid_payload.json()["error"]["code"] == "irtiqa.request_validation_error"

    invalid_score = client.post(
        "/intelligence-scores",
        json={
            "company_id": company["id"],
            "fit_score": 101.0,
            "intent_score": 76.0,
            "technographic_score": 91.0,
            "engagement_score": 70.0,
            "total_score": 81.4,
            "confidence": 0.86,
            "score_version": "api-test-v1",
            "rationale": "Invalid score should fail validation.",
            "scored_at": OBSERVED_AT,
        },
    )
    assert invalid_score.status_code == 422
    assert invalid_score.json()["error"]["code"] == "irtiqa.request_validation_error"

    missing = client.delete("/technologies/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "irtiqa.entity_not_found"


def _create_company(client: TestClient, *, domain: str) -> dict[str, object]:
    response = client.post(
        "/companies",
        json={"name": "Parent Company", "domain": domain, "status": "active"},
    )
    assert response.status_code == 201
    return response.json()


def _create_website(client: TestClient, *, company_id: object) -> dict[str, object]:
    response = client.post(
        "/websites",
        json={
            "company_id": company_id,
            "url": f"https://{company_id}.example",
            "normalized_url": f"https://{company_id}.example/",
            "page_type": "homepage",
            "http_status": 200,
        },
    )
    assert response.status_code == 201
    return response.json()


def _create_technology(
    client: TestClient,
    *,
    company_id: object,
    website_id: object,
) -> dict[str, object]:
    response = client.post(
        "/technologies",
        json={
            "company_id": company_id,
            "website_id": website_id,
            "name": "HubSpot",
            "category": "crm",
            "vendor": "HubSpot",
            "detection_method": "html_signature",
            "confidence": 0.92,
            "first_detected_at": OBSERVED_AT,
            "last_detected_at": OBSERVED_AT,
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
    )
