from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.discovery import (
    DiscoveryRunCreate,
    DiscoveryRunList,
    DiscoveryRunQueryParams,
    DiscoveryRunRead,
    DiscoveryRunUpdate,
    DiscoverySearchCreate,
    DiscoverySearchCriteria,
    DiscoverySearchList,
    DiscoverySearchQueryParams,
    DiscoverySearchRead,
    DiscoverySearchUpdate,
)


ORG_ID = "11111111-1111-1111-1111-111111111111"
SEARCH_ID = "22222222-2222-2222-2222-222222222222"
RUN_ID = "33333333-3333-3333-3333-333333333333"
NOW = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)


def _criteria_payload() -> dict[str, object]:
    return {
        "industry": "fintech",
        "company_size_min": 10,
        "company_size_max": 500,
        "geography": "United States",
        "technologies": ["hubspot", "salesforce"],
        "keywords": ["Series A", "hiring engineer"],
        "exclude_domains": ["example.com"],
        "sources": ["sec_edgar", "google_news_rss", "opencorporates"],
    }


def test_discovery_search_criteria_validates_documented_shape() -> None:
    criteria = DiscoverySearchCriteria.model_validate(_criteria_payload())

    assert criteria.industry == "fintech"
    assert criteria.company_size_min == 10
    assert criteria.company_size_max == 500
    assert criteria.sources == ["sec_edgar", "google_news_rss", "opencorporates"]


def test_discovery_search_criteria_applies_optional_defaults() -> None:
    criteria = DiscoverySearchCriteria.model_validate(
        {"industry": "healthcare", "keywords": ["funding"]}
    )

    assert criteria.company_size_min is None
    assert criteria.company_size_max is None
    assert criteria.technologies == []
    assert criteria.exclude_domains == []
    assert criteria.sources == ["sec_edgar", "google_news_rss", "opencorporates"]


def test_discovery_search_create_validates_payload() -> None:
    payload = {
        "name": "Fintech Series A",
        "description": "Find recently funded fintech companies.",
        "criteria": _criteria_payload(),
    }

    schema = DiscoverySearchCreate.model_validate(payload)

    assert schema.name == "Fintech Series A"
    assert schema.status == "active"
    assert schema.criteria.keywords == ["Series A", "hiring engineer"]


def test_discovery_search_update_rejects_empty_payload() -> None:
    with pytest.raises(ValidationError):
        DiscoverySearchUpdate.model_validate({})


def test_discovery_search_update_validates_partial_payload() -> None:
    schema = DiscoverySearchUpdate.model_validate({"status": "archived"})

    assert schema.model_dump(exclude_unset=True) == {"status": "archived"}


def test_discovery_search_read_parses_persisted_criteria_json() -> None:
    source = SimpleNamespace(
        id=SEARCH_ID,
        organization_id=ORG_ID,
        name="Fintech Series A",
        description=None,
        criteria=DiscoverySearchCriteria.model_validate(_criteria_payload()).model_dump_json(),
        status="active",
        last_run_at=NOW,
        total_discovered=7,
        created_at=NOW,
        updated_at=NOW,
    )

    schema = DiscoverySearchRead.model_validate(source)

    assert schema.criteria.industry == "fintech"
    assert schema.model_dump(mode="json")["criteria"]["keywords"] == [
        "Series A",
        "hiring engineer",
    ]


def test_discovery_search_list_serializes_items() -> None:
    search = DiscoverySearchRead.model_validate(
        {
            "id": SEARCH_ID,
            "organization_id": ORG_ID,
            "name": "Fintech Series A",
            "description": None,
            "criteria": _criteria_payload(),
            "status": "active",
            "last_run_at": None,
            "total_discovered": 0,
            "created_at": NOW,
            "updated_at": NOW,
        }
    )
    response = DiscoverySearchList(items=[search], total=1, limit=100, offset=0)

    assert response.total == 1
    assert response.items[0].id == SEARCH_ID


def test_discovery_search_schema_rejects_invalid_criteria() -> None:
    with pytest.raises(ValidationError):
        DiscoverySearchCreate(
            name="Missing keywords",
            criteria={"industry": "fintech"},
        )

    with pytest.raises(ValidationError):
        DiscoverySearchCriteria(
            industry="fintech",
            keywords=["funding"],
            company_size_min=500,
            company_size_max=10,
        )

    with pytest.raises(ValidationError):
        DiscoverySearchCriteria(
            industry="fintech",
            keywords=["funding"],
            sources=["unknown"],
        )


def test_discovery_search_read_rejects_invalid_criteria_json() -> None:
    with pytest.raises(ValidationError):
        DiscoverySearchRead.model_validate(
            {
                "id": SEARCH_ID,
                "organization_id": ORG_ID,
                "name": "Invalid JSON",
                "description": None,
                "criteria": "{not-json",
                "status": "active",
                "last_run_at": None,
                "total_discovered": 0,
                "created_at": NOW,
                "updated_at": NOW,
            }
        )


def test_discovery_search_status_enum_validation() -> None:
    with pytest.raises(ValidationError):
        DiscoverySearchCreate(
            name="Invalid",
            criteria=_criteria_payload(),
            status="running",
        )


def test_discovery_search_query_params_validate_filters() -> None:
    params = DiscoverySearchQueryParams(status="active", limit=25, offset=5)

    assert params.status == "active"
    assert params.limit == 25
    assert params.offset == 5

    with pytest.raises(ValidationError):
        DiscoverySearchQueryParams(status="running")

    with pytest.raises(ValidationError):
        DiscoverySearchQueryParams(limit=501)


def test_discovery_run_create_validates_payload_and_defaults() -> None:
    schema = DiscoveryRunCreate(
        organization_id=ORG_ID,
        search_id=SEARCH_ID,
        started_at=NOW,
    )

    assert schema.status == "running"
    assert schema.sources_queried == 0
    assert schema.companies_found == 0
    assert schema.finished_at is None


def test_discovery_run_update_rejects_empty_payload() -> None:
    with pytest.raises(ValidationError):
        DiscoveryRunUpdate.model_validate({})


def test_discovery_run_update_validates_partial_payload() -> None:
    schema = DiscoveryRunUpdate(status="succeeded", companies_created=3, finished_at=NOW)

    assert schema.status == "succeeded"
    assert schema.companies_created == 3


def test_discovery_run_read_and_list_serialize_from_attributes() -> None:
    source = SimpleNamespace(
        id=RUN_ID,
        organization_id=ORG_ID,
        search_id=SEARCH_ID,
        status="succeeded",
        sources_queried=3,
        companies_found=12,
        companies_created=8,
        companies_skipped=4,
        started_at=NOW,
        finished_at=NOW,
        error_message=None,
        created_at=NOW,
        updated_at=NOW,
    )

    read = DiscoveryRunRead.model_validate(source)
    response = DiscoveryRunList(items=[read], total=1, limit=100, offset=0)

    assert read.model_dump(mode="json")["id"] == RUN_ID
    assert response.items[0].companies_created == 8


def test_discovery_run_schema_rejects_invalid_status_and_negative_counts() -> None:
    with pytest.raises(ValidationError):
        DiscoveryRunCreate(
            organization_id=ORG_ID,
            search_id=SEARCH_ID,
            status="archived",
            started_at=NOW,
        )

    with pytest.raises(ValidationError):
        DiscoveryRunCreate(
            organization_id=ORG_ID,
            search_id=SEARCH_ID,
            started_at=NOW,
            companies_found=-1,
        )


def test_discovery_run_query_params_validate_filters() -> None:
    params = DiscoveryRunQueryParams(
        search_id=SEARCH_ID,
        status="failed",
        limit=50,
        offset=10,
    )

    assert params.search_id == SEARCH_ID
    assert params.status == "failed"

    with pytest.raises(ValidationError):
        DiscoveryRunQueryParams(search_id="not-a-uuid")

    with pytest.raises(ValidationError):
        DiscoveryRunQueryParams(status="archived")
