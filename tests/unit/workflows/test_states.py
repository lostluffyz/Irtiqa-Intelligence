from __future__ import annotations

import pytest

from app.core.errors import WorkflowStateError
from app.workflows.states import WorkflowStatus, is_terminal, validate_transition


def test_valid_workflow_state_transitions() -> None:
    validate_transition(WorkflowStatus.PENDING, WorkflowStatus.RUNNING)
    validate_transition(WorkflowStatus.RUNNING, WorkflowStatus.SUCCEEDED)
    validate_transition(WorkflowStatus.FAILED, WorkflowStatus.PENDING)


def test_invalid_workflow_state_transition_raises_structured_error() -> None:
    with pytest.raises(WorkflowStateError) as exc_info:
        validate_transition(WorkflowStatus.SUCCEEDED, WorkflowStatus.RUNNING)

    assert exc_info.value.code == "irtiqa.workflow_state_error"
    assert exc_info.value.details == {
        "current_status": "succeeded",
        "target_status": "running",
    }


def test_terminal_workflow_states() -> None:
    assert is_terminal(WorkflowStatus.SUCCEEDED)
    assert is_terminal(WorkflowStatus.FAILED)
    assert is_terminal(WorkflowStatus.PARTIALLY_SUCCEEDED)
    assert is_terminal(WorkflowStatus.CANCELLED)
    assert not is_terminal(WorkflowStatus.RUNNING)
