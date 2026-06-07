from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.agents.context import AgentContext
from app.agents.intent_signal import IntentSignalAgent
from app.agents.result import AGENT_STATUS_FAILED, AGENT_STATUS_SUCCEEDED
from app.core.errors import AgentValidationError


VALID_COMPANY_ID = "00000000-0000-0000-0000-000000000000"
VALID_AGENT_RUN_ID = "11111111-1111-1111-1111-111111111111"
VALID_WEBSITE_ID = "22222222-2222-2222-2222-222222222222"
VALID_TECHNOLOGY_ID = "33333333-3333-3333-3333-333333333333"
VALID_SIGNAL_ID = "44444444-4444-4444-4444-444444444444"


def _context(**overrides: Any) -> AgentContext:
    values: dict[str, Any] = {
        "agent_name": "intent_signal",
        "company_id": VALID_COMPANY_ID,
        "options": {},
    }
    values.update(overrides)
    return AgentContext(**values)


def _website(
    *,
    text: str | None,
    page_type: str = "careers",
    website_id: str = VALID_WEBSITE_ID,
) -> MagicMock:
    website = MagicMock()
    website.id = website_id
    website.company_id = VALID_COMPANY_ID
    website.url = f"https://example.com/{page_type}"
    website.page_type = page_type
    website.extracted_text = text
    website.last_scraped_at = datetime(2026, 6, 7, tzinfo=timezone.utc)
    return website


def _technology(
    *,
    name: str = "Google Analytics",
    category: str = "analytics",
    confidence: float = 0.9,
) -> MagicMock:
    technology = MagicMock()
    technology.id = VALID_TECHNOLOGY_ID
    technology.name = name
    technology.category = category
    technology.confidence = confidence
    return technology


def _existing_signal() -> MagicMock:
    signal = MagicMock()
    signal.id = "55555555-5555-5555-5555-555555555555"
    signal.company_id = VALID_COMPANY_ID
    signal.signal_type = "hiring_activity"
    signal.signal_name = "Hiring for growth roles"
    signal.website_id = VALID_WEBSITE_ID
    signal.technology_id = VALID_TECHNOLOGY_ID
    return signal


def _services(
    *,
    websites: list[MagicMock] | None = None,
    technologies: list[MagicMock] | None = None,
    existing_signals: list[MagicMock] | None = None,
) -> dict[str, MagicMock]:
    agent_run_service = MagicMock()
    run = MagicMock()
    run.id = VALID_AGENT_RUN_ID
    agent_run_service.start_workflow_run.return_value = run
    agent_run_service.mark_succeeded.return_value = run
    agent_run_service.mark_failed.return_value = run

    website_service = MagicMock()
    website_service.list_by_company.return_value = websites or []

    technology_service = MagicMock()
    technology_service.list_by_company.return_value = technologies or []

    intent_signal_service = MagicMock()
    intent_signal_service.list_by_company.return_value = existing_signals or []
    created = MagicMock()
    created.id = VALID_SIGNAL_ID
    intent_signal_service.create.return_value = created

    return {
        "agent_run_service": agent_run_service,
        "website_service": website_service,
        "technology_service": technology_service,
        "intent_signal_service": intent_signal_service,
    }


@pytest.mark.asyncio
async def test_validate_context_rejects_invalid_options() -> None:
    agent = IntentSignalAgent()

    with pytest.raises(AgentValidationError):
        await agent._validate_context(_context(options={"min_confidence": 2.0}))
    with pytest.raises(AgentValidationError):
        await agent._validate_context(_context(options={"min_strength": -0.1}))
    with pytest.raises(AgentValidationError):
        await agent._validate_context(_context(options={"max_signals_per_type": 0}))
    with pytest.raises(AgentValidationError):
        await agent._validate_context(_context(options={"require_source_url": "yes"}))
    with pytest.raises(AgentValidationError):
        await agent._validate_context(_context(options={"signal_types": ["unknown"]}))


@pytest.mark.asyncio
async def test_run_empty_websites_succeeds_with_no_outputs() -> None:
    agent = IntentSignalAgent(**_services())

    output = await agent._run(_context())

    assert output["output_ids"]["intent_signals"] == []
    assert output["stats"]["pages_scanned"] == 0
    assert output["stats"]["signals_persisted"] == 0


@pytest.mark.asyncio
async def test_run_skips_pages_without_extracted_text() -> None:
    agent = IntentSignalAgent(
        **_services(websites=[_website(text=None)], technologies=[_technology()])
    )

    output = await agent._run(_context())

    assert output["output_ids"]["intent_signals"] == []
    assert output["stats"]["pages_skipped_no_text"] == 1


@pytest.mark.asyncio
async def test_run_persists_detected_intent_signal() -> None:
    website = _website(
        text="Careers: We are hiring sales and RevOps roles as we continue rapid growth.",
        page_type="careers",
    )
    services = _services(websites=[website], technologies=[_technology()])
    agent = IntentSignalAgent(**services)

    output = await agent._run(_context())

    assert output["output_ids"]["intent_signals"] == [VALID_SIGNAL_ID]
    assert output["stats"]["signals_persisted"] == 1
    services["intent_signal_service"].create.assert_called_once()
    create_kwargs = services["intent_signal_service"].create.call_args.kwargs
    assert create_kwargs["company_id"] == VALID_COMPANY_ID
    assert create_kwargs["website_id"] == VALID_WEBSITE_ID
    assert create_kwargs["technology_id"] == VALID_TECHNOLOGY_ID
    assert create_kwargs["signal_type"] == "hiring_activity"
    assert create_kwargs["signal_name"] == "Hiring for growth roles"
    assert create_kwargs["agent_run_id"] is None
    assert create_kwargs["source_url"] == "https://example.com/careers"
    assert create_kwargs["confidence"] >= 0.35
    assert create_kwargs["strength"] >= 0.25


@pytest.mark.asyncio
async def test_run_filters_by_signal_types() -> None:
    website = _website(
        text="Careers: We are hiring sales roles. Our security page includes SOC 2 and SSO.",
        page_type="security",
    )
    services = _services(websites=[website], technologies=[_technology()])
    agent = IntentSignalAgent(**services)

    output = await agent._run(_context(options={"signal_types": ["enterprise_readiness"]}))

    assert output["stats"]["signals_persisted"] == 1
    create_kwargs = services["intent_signal_service"].create.call_args.kwargs
    assert create_kwargs["signal_type"] == "enterprise_readiness"


@pytest.mark.asyncio
async def test_run_applies_thresholds() -> None:
    website = _website(text="Join our team.", page_type="about")
    services = _services(websites=[website], technologies=[])
    agent = IntentSignalAgent(**services)

    output = await agent._run(
        _context(options={"min_confidence": 0.99, "min_strength": 0.99})
    )

    assert output["output_ids"]["intent_signals"] == []
    assert output["stats"]["signals_below_threshold"] >= 1
    services["intent_signal_service"].create.assert_not_called()


@pytest.mark.asyncio
async def test_run_deduplicates_existing_signals() -> None:
    website = _website(
        text="Careers: We are hiring sales and RevOps roles.",
        page_type="careers",
    )
    services = _services(
        websites=[website],
        technologies=[_technology()],
        existing_signals=[_existing_signal()],
    )
    agent = IntentSignalAgent(**services)

    output = await agent._run(_context())

    assert output["output_ids"]["intent_signals"] == []
    assert output["stats"]["signals_deduplicated"] == 1
    services["intent_signal_service"].create.assert_not_called()


@pytest.mark.asyncio
async def test_execute_uses_base_agent_lifecycle() -> None:
    website = _website(
        text="We launched our new product and announced a platform rollout.",
        page_type="blog",
    )
    services = _services(websites=[website], technologies=[_technology(category="hosting")])
    agent = IntentSignalAgent(**services)

    result = await agent.execute(_context())

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert result.agent_run_id == VALID_AGENT_RUN_ID
    assert result.output_ids["intent_signals"] == [VALID_SIGNAL_ID]
    services["agent_run_service"].start_workflow_run.assert_called_once()
    services["agent_run_service"].mark_succeeded.assert_called_once()


@pytest.mark.asyncio
async def test_execute_returns_failed_result_for_invalid_options() -> None:
    agent = IntentSignalAgent(**_services())

    result = await agent.execute(_context(options={"signal_types": ["bad"]}))

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_validation_error"
