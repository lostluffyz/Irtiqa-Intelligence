from __future__ import annotations

from enum import StrEnum

from app.core.errors import WorkflowStateError


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    CANCELLED = "cancelled"


TERMINAL_WORKFLOW_STATUSES = frozenset(
    {
        WorkflowStatus.SUCCEEDED,
        WorkflowStatus.FAILED,
        WorkflowStatus.PARTIALLY_SUCCEEDED,
        WorkflowStatus.CANCELLED,
    }
)

ALLOWED_WORKFLOW_TRANSITIONS: dict[WorkflowStatus, frozenset[WorkflowStatus]] = {
    WorkflowStatus.PENDING: frozenset({WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED}),
    WorkflowStatus.RUNNING: frozenset(
        {
            WorkflowStatus.SUCCEEDED,
            WorkflowStatus.FAILED,
            WorkflowStatus.PARTIALLY_SUCCEEDED,
            WorkflowStatus.CANCELLED,
        }
    ),
    WorkflowStatus.SUCCEEDED: frozenset(),
    WorkflowStatus.FAILED: frozenset({WorkflowStatus.PENDING}),
    WorkflowStatus.PARTIALLY_SUCCEEDED: frozenset({WorkflowStatus.PENDING}),
    WorkflowStatus.CANCELLED: frozenset(),
}


def validate_transition(current: WorkflowStatus, target: WorkflowStatus) -> None:
    if target not in ALLOWED_WORKFLOW_TRANSITIONS[current]:
        raise WorkflowStateError(
            "Workflow state transition is not allowed.",
            details={"current_status": current.value, "target_status": target.value},
        )


def is_terminal(status: WorkflowStatus) -> bool:
    return status in TERMINAL_WORKFLOW_STATUSES
