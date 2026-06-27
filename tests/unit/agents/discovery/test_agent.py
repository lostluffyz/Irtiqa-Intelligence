from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.agents.context import AgentContext
from app.agents.discovery.agent import DiscoveryAgent
from app.agents.discovery.sources.common import DiscoveredCompany
from app.agents.result import AGENT_STATUS_FAILED, AGENT_STATUS_SUCCEEDED


VALID_COMPANY_ID = "00000000-0000-0000-0000-000000000000"
VALID_AGENT_RUN_ID = "11111111-1111-1111-1111-111111111111"
VALID_SEARCH_ID = "22222222-2222-2222-2222-222222222222"
VALID_RUN_ID = "33333333-3333-3333-3333-333333333333"
VALID_ORG_ID = "44444444-4444-4444-4444-444444444444"


class _Provider:
    def __init__(
        self,
        source_name: str,
        results: list[DiscoveredCompany] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.source_name = source_name
        self.results = results or []
        self.error = error
        self.calls = 0

    def search(self, criteria: dict[str, Any]) -> list[DiscoveredCompany]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.results


def _company(
    *,
    name: str = "Acme Corp",
    domain: str = "acme.example",
    source: str = "sec_edgar",
    confidence: float = 0.7,
    website: str | None = "https://acme.example",
    country: str | None = "United States",
    city: str | None = "New York",
    industry: str | None = "fintech",
) -> DiscoveredCompany:
    return DiscoveredCompany(
        name=name,
        domain=domain,
        website=website,
        country=country,
        city=city,
        industry=industry,
        source=source,
        confidence=confidence,
        metadata={"provider_id": f"{source}-1"},
    )


def _context(**overrides: Any) -> AgentContext:
    values: dict[str, Any] = {
        "agent_name": "discovery",
        "company_id": VALID_COMPANY_ID,
        "organization_id": VALID_ORG_ID,
        "workflow_name": "discovery_pipeline",
        "options": {
            "discovery_search_id": VALID_SEARCH_ID,
            "discovery_run_id": VALID_RUN_ID,
            "criteria": {
                "industry": "fintech",
                "geography": "United States",
                "keywords": ["Series A"],
            },
        },
    }
    values.update(overrides)
    return AgentContext(**values)


def _services(
    *,
    providers: list[_Provider],
    existing_domain: str | None = None,
) -> dict[str, Any]:
    agent_run_service = MagicMock()
    agent_run = MagicMock()
    agent_run.id = VALID_AGENT_RUN_ID
    agent_run_service.start_workflow_run.return_value = agent_run
    agent_run_service.mark_succeeded.return_value = agent_run
    agent_run_service.mark_failed.return_value = agent_run

    company_service = MagicMock()
    company_service.get_by_domain.side_effect = (
        lambda domain, organization_id: MagicMock(id="existing") if domain == existing_domain else None
    )
    created_ids: list[str] = []

    def _create_company(**kwargs: Any) -> MagicMock:
        company = MagicMock()
        company.id = f"aaaaaaaa-aaaa-aaaa-aaaa-{len(created_ids) + 1:012d}"
        created_ids.append(company.id)
        return company

    company_service.create.side_effect = _create_company

    run_service = MagicMock()

    return {
        "agent_run_service": agent_run_service,
        "company_service": company_service,
        "discovery_run_service": run_service,
        "discovery_sources": providers,
    }


@pytest.mark.asyncio
async def test_run_single_provider_creates_company_and_updates_statistics() -> None:
    provider = _Provider("sec_edgar", [_company()])
    services = _services(providers=[provider])
    agent = DiscoveryAgent(**services)

    output = await agent._run(_context())

    assert output["output_ids"]["companies"] == ["aaaaaaaa-aaaa-aaaa-aaaa-000000000001"]
    assert output["stats"]["companies_found"] == 1
    assert output["stats"]["companies_created"] == 1
    assert output["stats"]["sources_queried"] == 1
    services["company_service"].create.assert_called_once()
    create_kwargs = services["company_service"].create.call_args.kwargs
    assert create_kwargs["organization_id"] == VALID_ORG_ID
    assert create_kwargs["status"] == "needs_review"
    assert create_kwargs["discovered_via"] == "discovery_pipeline"
    assert create_kwargs["discovery_search_id"] == VALID_SEARCH_ID
    assert 0.0 <= create_kwargs["discovery_score"] <= 1.0
    services["discovery_run_service"].update_statistics.assert_called_once_with(
        VALID_RUN_ID,
        organization_id=VALID_ORG_ID,
        sources_queried=1,
        companies_found=1,
        companies_created=1,
        companies_skipped=0,
    )


@pytest.mark.asyncio
async def test_run_multiple_providers_deduplicates_by_domain() -> None:
    providers = [
        _Provider("sec_edgar", [_company(confidence=0.65)]),
        _Provider("google_news_rss", [_company(name="Acme Corporation", confidence=0.8)]),
    ]
    agent = DiscoveryAgent(**_services(providers=providers))

    output = await agent._run(_context())

    assert output["stats"]["companies_found"] == 2
    assert output["stats"]["companies_deduplicated"] == 1
    assert output["stats"]["companies_created"] == 1


@pytest.mark.asyncio
async def test_run_provider_failure_returns_partial_success() -> None:
    providers = [
        _Provider("sec_edgar", [_company()]),
        _Provider("opencorporates", error=RuntimeError("provider down")),
    ]
    agent = DiscoveryAgent(**_services(providers=providers))

    output = await agent._run(_context())

    assert output["stats"]["providers_failed"] == 1
    assert output["stats"]["provider_failures"] == {"opencorporates": "RuntimeError"}
    assert output["stats"]["companies_created"] == 1


@pytest.mark.asyncio
async def test_run_skips_existing_company_duplicate() -> None:
    provider = _Provider("sec_edgar", [_company(domain="existing.example")])
    services = _services(providers=[provider], existing_domain="existing.example")
    agent = DiscoveryAgent(**services)

    output = await agent._run(_context())

    assert output["output_ids"]["companies"] == []
    assert output["stats"]["skipped_existing"] == 1
    services["company_service"].create.assert_not_called()


@pytest.mark.asyncio
async def test_run_skips_company_without_domain() -> None:
    provider = _Provider("sec_edgar", [_company(domain="", website=None)])
    agent = DiscoveryAgent(**_services(providers=[provider]))

    output = await agent._run(_context())

    assert output["stats"]["skipped_without_domain"] == 1
    assert output["stats"]["companies_created"] == 0


def test_discovery_score_rewards_provider_agreement_and_completeness() -> None:
    agent = DiscoveryAgent()
    candidate = agent._deduplicate([
        _company(source="sec_edgar", confidence=0.7),
        _company(source="google_news_rss", confidence=0.85),
    ])[0][0]

    score = agent._calculate_discovery_score(
        candidate,
        {"industry": "fintech", "geography": "United States"},
    )

    assert score > 0.9


def test_deduplication_merges_metadata_and_keeps_highest_confidence() -> None:
    agent = DiscoveryAgent()

    candidates, skipped = agent._deduplicate([
        _company(source="sec_edgar", confidence=0.6),
        _company(source="opencorporates", confidence=0.85, city=None),
    ])

    assert skipped == 0
    assert len(candidates) == 1
    assert candidates[0].confidence == 0.85
    assert candidates[0].sources == {"sec_edgar", "opencorporates"}
    assert set(candidates[0].metadata) == {"sec_edgar", "opencorporates"}


@pytest.mark.asyncio
async def test_execute_uses_base_agent_lifecycle_and_records_evidence() -> None:
    provider = _Provider("sec_edgar", [_company()])
    services = _services(providers=[provider])
    agent = DiscoveryAgent(**services)

    with patch("app.services.evidence_service.EvidenceService.record_evidence_batch") as evidence:
        evidence.return_value = []
        result = await agent.execute(_context())

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert result.agent_run_id == VALID_AGENT_RUN_ID
    assert result.output_ids["companies"] == ["aaaaaaaa-aaaa-aaaa-aaaa-000000000001"]
    evidence.assert_called_once()
    assert evidence.call_args.kwargs["organization_id"] == VALID_ORG_ID


@pytest.mark.asyncio
async def test_execute_returns_failed_result_for_invalid_context() -> None:
    services = _services(providers=[])
    agent = DiscoveryAgent(**services)

    result = await agent.execute(_context(options={}))

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_validation_error"


@pytest.mark.asyncio
async def test_run_empty_results_updates_zero_statistics() -> None:
    provider = _Provider("sec_edgar", [])
    services = _services(providers=[provider])
    agent = DiscoveryAgent(**services)

    output = await agent._run(_context())

    assert output["output_ids"]["companies"] == []
    assert output["stats"]["companies_found"] == 0
    assert output["stats"]["companies_created"] == 0
    services["discovery_run_service"].update_statistics.assert_called_once()


@pytest.mark.asyncio
async def test_disabled_provider_list_is_not_executed() -> None:
    services = _services(providers=[])
    agent = DiscoveryAgent(**services)

    output = await agent._run(_context())

    assert output["stats"]["sources_queried"] == 0
    assert output["stats"]["companies_found"] == 0


@pytest.mark.asyncio
async def test_company_creation_is_tenant_scoped() -> None:
    provider = _Provider("sec_edgar", [_company()])
    services = _services(providers=[provider])
    agent = DiscoveryAgent(**services)

    await agent._run(_context())

    assert services["company_service"].create.call_args.kwargs["organization_id"] == VALID_ORG_ID
