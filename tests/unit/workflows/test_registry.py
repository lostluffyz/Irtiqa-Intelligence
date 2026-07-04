from __future__ import annotations

import pytest

from app.core.errors import WorkflowError
from app.workflows.base import Workflow
from app.workflows.context import WorkflowContext
from app.workflows.registry import WorkflowRegistry
from app.workflows.result import WorkflowResult
from app.workflows.states import WorkflowStatus


class RegisteredWorkflow(Workflow):
    name = "registered"

    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        return WorkflowResult(workflow_name=context.workflow_name, status=WorkflowStatus.SUCCEEDED)


class NamelessWorkflow(Workflow):
    name = ""

    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        return WorkflowResult(workflow_name=context.workflow_name, status=WorkflowStatus.SUCCEEDED)


def test_workflow_registry_registers_and_resolves_workflow() -> None:
    registry = WorkflowRegistry()

    registry.register(RegisteredWorkflow)

    assert registry.get("registered") is RegisteredWorkflow
    assert registry.names() == ("registered",)


def test_workflow_registry_rejects_duplicate_names() -> None:
    registry = WorkflowRegistry()
    registry.register(RegisteredWorkflow)

    with pytest.raises(WorkflowError) as exc_info:
        registry.register(RegisteredWorkflow)

    assert exc_info.value.code == "irtiqa.workflow_error"
    assert exc_info.value.details == {"workflow_name": "registered"}


def test_workflow_registry_rejects_nameless_workflows() -> None:
    registry = WorkflowRegistry()

    with pytest.raises(WorkflowError):
        registry.register(NamelessWorkflow)


def test_workflow_registry_rejects_unknown_workflow_lookup() -> None:
    registry = WorkflowRegistry()

    with pytest.raises(WorkflowError) as exc_info:
        registry.get("missing")

    assert exc_info.value.details == {"workflow_name": "missing"}
