from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.agents.base import AgentRunOutput, BaseAgent
from app.agents.context import AgentContext
from app.agents.result import AGENT_STATUS_FAILED, AGENT_STATUS_SUCCEEDED
from app.core.errors import (
    AgentConfigurationError,
    AgentError,
    AgentExecutionError,
    AgentValidationError,
    ServiceError,
)


VALID_COMPANY_ID = "00000000-0000-0000-0000-000000000000"
VALID_AGENT_RUN_ID = "22222222-2222-2222-2222-222222222222"


class SuccessAgent(BaseAgent):
    name = "success_agent"
    version = "1.0.0"

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        return {
            "output_ids": {"technologies": ["tech-001"]},
            "summary": "Detected 1 technology.",
            "stats": {"technologies_detected": 1},
        }


class FailingAgent(BaseAgent):
    name = "failing_agent"
    version = "1.0.0"

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        raise RuntimeError("Something went wrong")


class AgentErrorAgent(BaseAgent):
    name = "agent_error_agent"
    version = "1.0.0"

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        raise AgentExecutionError(
            "Custom agent failure.",
            details={"reason": "test"},
        )


class ValidationAgent(BaseAgent):
    name = "validation_agent"
    version = "1.0.0"

    async def _validate_context(self, context: AgentContext) -> None:
        await super()._validate_context(context)
        if "required_key" not in context.options:
            raise AgentValidationError(
                "Missing required_key in options.",
                details={"agent_name": self.name},
            )

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        return {
            "output_ids": {},
            "summary": "Validated successfully.",
            "stats": {},
        }


def _mock_agent_run_service() -> MagicMock:
    """Create a mock AgentRunService with expected method signatures."""
    service = MagicMock()
    mock_run = MagicMock()
    mock_run.id = VALID_AGENT_RUN_ID
    service.start_workflow_run.return_value = mock_run
    service.mark_succeeded.return_value = mock_run
    service.mark_failed.return_value = mock_run
    return service


def _make_context(agent_name: str, **overrides: Any) -> AgentContext:
    defaults: dict[str, Any] = {
        "agent_name": agent_name,
        "company_id": VALID_COMPANY_ID,
    }
    defaults.update(overrides)
    return AgentContext(**defaults)


@pytest.mark.asyncio
async def test_successful_agent_lifecycle() -> None:
    mock_service = _mock_agent_run_service()
    agent = SuccessAgent(agent_run_service=mock_service)
    context = _make_context("success_agent")

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert result.agent_run_id == VALID_AGENT_RUN_ID
    assert result.output_ids == {"technologies": ["tech-001"]}
    assert result.summary == "Detected 1 technology."
    assert result.stats == {"technologies_detected": 1}
    assert result.error is None
    assert result.duration_ms >= 0.0

    mock_service.start_workflow_run.assert_called_once()
    mock_service.mark_succeeded.assert_called_once_with(
        VALID_AGENT_RUN_ID,
        output_summary="Detected 1 technology.",
    )


@pytest.mark.asyncio
async def test_failed_agent_lifecycle_with_unexpected_exception() -> None:
    mock_service = _mock_agent_run_service()
    agent = FailingAgent(agent_run_service=mock_service)
    context = _make_context("failing_agent")

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.agent_run_id == VALID_AGENT_RUN_ID
    assert "Failed:" in result.summary
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_execution_error"
    assert result.error["cause"] == "RuntimeError"
    assert result.duration_ms >= 0.0

    mock_service.start_workflow_run.assert_called_once()
    mock_service.mark_failed.assert_called_once()


@pytest.mark.asyncio
async def test_failed_agent_lifecycle_with_agent_error() -> None:
    mock_service = _mock_agent_run_service()
    agent = AgentErrorAgent(agent_run_service=mock_service)
    context = _make_context("agent_error_agent")

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_execution_error"
    assert result.error["details"] == {"reason": "test"}

    mock_service.mark_failed.assert_called_once()


@pytest.mark.asyncio
async def test_context_validation_failure_prevents_run_record() -> None:
    mock_service = _mock_agent_run_service()
    agent = SuccessAgent(agent_run_service=mock_service)

    # Agent name mismatch triggers validation failure
    context = _make_context("wrong_name")

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.agent_run_id is None
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_validation_error"

    # No agent_runs record should have been created
    mock_service.start_workflow_run.assert_not_called()
    mock_service.mark_failed.assert_not_called()


@pytest.mark.asyncio
async def test_custom_validation_failure() -> None:
    mock_service = _mock_agent_run_service()
    agent = ValidationAgent(agent_run_service=mock_service)
    context = _make_context("validation_agent")  # no required_key in options

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.agent_validation_error"
    mock_service.start_workflow_run.assert_not_called()


@pytest.mark.asyncio
async def test_custom_validation_success() -> None:
    mock_service = _mock_agent_run_service()
    agent = ValidationAgent(agent_run_service=mock_service)
    context = _make_context("validation_agent", options={"required_key": True})

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    mock_service.start_workflow_run.assert_called_once()


@pytest.mark.asyncio
async def test_exception_translation_preserves_agent_errors() -> None:
    agent = SuccessAgent(agent_run_service=_mock_agent_run_service())
    original = AgentExecutionError("original error", details={"key": "val"})

    translated = agent._translate_exception(original)

    assert translated is original


@pytest.mark.asyncio
async def test_exception_translation_wraps_irtiqa_errors() -> None:
    agent = SuccessAgent(agent_run_service=_mock_agent_run_service())
    original = ServiceError("service broke", details={"svc": "test"})

    translated = agent._translate_exception(original)

    assert isinstance(translated, AgentExecutionError)
    assert translated.message == "service broke"
    assert translated.details == {"svc": "test"}
    assert translated.cause is original


@pytest.mark.asyncio
async def test_exception_translation_wraps_unknown_exceptions() -> None:
    agent = SuccessAgent(agent_run_service=_mock_agent_run_service())
    original = ValueError("unexpected")

    translated = agent._translate_exception(original)

    assert isinstance(translated, AgentExecutionError)
    assert "Unexpected" in translated.message
    assert translated.details == {"exception_type": "ValueError"}
    assert translated.cause is original


def test_service_lookup_returns_correct_type() -> None:
    mock_service = _mock_agent_run_service()
    agent = SuccessAgent(agent_run_service=mock_service)

    result = agent._service("agent_run_service", MagicMock)
    assert result is mock_service


def test_service_lookup_raises_on_missing_service() -> None:
    agent = SuccessAgent()

    with pytest.raises(AgentConfigurationError) as exc_info:
        agent._service("missing_service", MagicMock)

    assert exc_info.value.code == "irtiqa.agent_configuration_error"
    assert exc_info.value.details["agent_name"] == "success_agent"
    assert exc_info.value.details["service"] == "missing_service"


@pytest.mark.asyncio
async def test_mark_failed_failure_does_not_crash_agent() -> None:
    """If marking the run as failed itself fails, the agent still returns a result."""
    mock_service = _mock_agent_run_service()
    mock_service.mark_failed.side_effect = Exception("DB is down")
    agent = FailingAgent(agent_run_service=mock_service)
    context = _make_context("failing_agent")

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_FAILED
    assert result.agent_run_id == VALID_AGENT_RUN_ID
    mock_service.mark_failed.assert_called_once()
