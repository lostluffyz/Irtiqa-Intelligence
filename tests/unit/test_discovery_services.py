from __future__ import annotations

import json

import pytest

from app.core.errors import ValidationError
from app.schemas.discovery import DiscoverySearchCriteria
from app.services.discovery_run_service import DiscoveryRunService
from app.services.discovery_search_service import DiscoverySearchService


def _criteria_payload() -> dict[str, object]:
    return {
        "industry": "fintech",
        "company_size_min": 10,
        "company_size_max": 500,
        "geography": "United States",
        "technologies": ["hubspot"],
        "keywords": ["Series A"],
        "exclude_domains": ["example.com"],
        "sources": ["sec_edgar", "google_news_rss"],
    }


def test_discovery_search_service_normalizes_criteria_dict() -> None:
    service = DiscoverySearchService()

    normalized = service._normalize_criteria_json(_criteria_payload())

    data = json.loads(normalized)
    assert data["industry"] == "fintech"
    assert data["keywords"] == ["Series A"]
    assert data["sources"] == ["sec_edgar", "google_news_rss"]


def test_discovery_search_service_normalizes_criteria_model() -> None:
    service = DiscoverySearchService()
    criteria = DiscoverySearchCriteria.model_validate(_criteria_payload())

    normalized = service._normalize_criteria_json(criteria)

    assert json.loads(normalized)["technologies"] == ["hubspot"]


def test_discovery_search_service_rejects_invalid_criteria() -> None:
    service = DiscoverySearchService()

    with pytest.raises(ValidationError):
        service._normalize_criteria_json({"industry": "fintech"})

    with pytest.raises(ValidationError):
        service._normalize_criteria_json("{not-json")


def test_discovery_search_service_rejects_invalid_status() -> None:
    service = DiscoverySearchService()

    with pytest.raises(ValidationError):
        service._validate_status("running")


def test_discovery_run_service_rejects_invalid_counters_and_status() -> None:
    service = DiscoveryRunService()

    with pytest.raises(ValidationError):
        service._validate_optional_counter(-1, field_name="companies_found")

    with pytest.raises(ValidationError):
        service._validate_status("archived")
