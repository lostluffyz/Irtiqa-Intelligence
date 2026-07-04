from __future__ import annotations

import logging

import pytest

from app.core.errors import WorkflowError
from app.workflows.base import Workflow
from app.workflows.context import WorkflowContext
from app.workflows.registry import WorkflowRegistry
from app.workflows.result import WorkflowResult
from app.workflows.runner import WorkflowRunner
from app.workflows.states import WorkflowStatus


COMPANY_ID = "00000000-0000-0000-0000-000000000000"


class SuccessfulWorkflow(Workflow):
    name = "successful"

    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        assert "company_service" in self.services
        return WorkflowResult(
            workflow_name=context.workflow_name,
            status=WorkflowStatus.SUCCEEDED,
            company_id=context.company_id,
        )


class FailingWorkflow(Workflow):
    name = "failing"

    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        raise WorkflowError("Expected failure.", details={"workflow_name": context.workflow_name})


class UnexpectedFailingWorkflow(Workflow):
    name = "unexpected"

    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_workflow_runner_executes_registered_workflow() -> None:
    registry = WorkflowRegistry()
    registry.register(SuccessfulWorkflow)
    runner = WorkflowRunner(registry, company_service=object())
    context = WorkflowContext(workflow_name="successful", company_id=COMPANY_ID)

    result = await runner.run(context)

    assert result.status == WorkflowStatus.SUCCEEDED
    assert result.company_id == COMPANY_ID


@pytest.mark.asyncio
async def test_workflow_runner_returns_failed_result_for_structured_errors() -> None:
    registry = WorkflowRegistry()
    registry.register(FailingWorkflow)
    runner = WorkflowRunner(registry, company_service=object())
    context = WorkflowContext(workflow_name="failing", company_id=COMPANY_ID)

    result = await runner.run(context)

    assert result.status == WorkflowStatus.FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.workflow_error"
    assert result.error["details"] == {"workflow_name": "failing"}
    assert result.finished_at is not None


@pytest.mark.asyncio
async def test_workflow_runner_wraps_unexpected_errors() -> None:
    registry = WorkflowRegistry()
    registry.register(UnexpectedFailingWorkflow)
    runner = WorkflowRunner(registry, company_service=object())
    context = WorkflowContext(workflow_name="unexpected", company_id=COMPANY_ID)

    result = await runner.run(context)

    assert result.status == WorkflowStatus.FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.workflow_error"
    assert result.error["cause"] == "RuntimeError"


class MessageCaptureHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.mark.asyncio
async def test_workflow_runner_logs_start_and_completion() -> None:
    registry = WorkflowRegistry()
    registry.register(SuccessfulWorkflow)
    runner = WorkflowRunner(registry, company_service=object())
    context = WorkflowContext(workflow_name="successful", company_id=COMPANY_ID)
    logger = logging.getLogger("irtiqa.workflows.runner")
    original_propagate = logger.propagate
    original_level = logger.level
    original_disabled = logger.disabled
    original_manager_disable = logger.manager.disable
    handler = MessageCaptureHandler()

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.disabled = False
    logger.propagate = False
    try:
        logging.disable(logging.NOTSET)
        await runner.run(context)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(original_level)
        logger.disabled = original_disabled
        logger.propagate = original_propagate
        logging.disable(original_manager_disable)

    assert handler.messages == [
        "Starting workflow",
        "Completed workflow",
    ]
