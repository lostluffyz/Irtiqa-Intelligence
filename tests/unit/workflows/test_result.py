from __future__ import annotations

from app.workflows.result import WorkflowResult, WorkflowStepResult
from app.workflows.states import WorkflowStatus


def test_workflow_result_serializes_status_and_outputs() -> None:
    result = WorkflowResult(
        workflow_name="score_refresh",
        status=WorkflowStatus.SUCCEEDED,
        company_id="00000000-0000-0000-0000-000000000000",
        agent_run_ids=["11111111-1111-1111-1111-111111111111"],
        output_ids={"intelligence_scores": ["22222222-2222-2222-2222-222222222222"]},
        steps=[
            WorkflowStepResult(
                step_name="score",
                status=WorkflowStatus.SUCCEEDED,
                agent_run_id="11111111-1111-1111-1111-111111111111",
            )
        ],
    )

    payload = result.model_dump(mode="json")

    assert payload["workflow_name"] == "score_refresh"
    assert payload["status"] == "succeeded"
    assert payload["agent_run_ids"] == ["11111111-1111-1111-1111-111111111111"]
    assert payload["steps"][0]["status"] == "succeeded"


def test_workflow_result_finish_sets_terminal_status_error_and_finished_at() -> None:
    result = WorkflowResult(workflow_name="score_refresh", status=WorkflowStatus.RUNNING)

    finished = result.finish(
        WorkflowStatus.FAILED,
        error={"code": "irtiqa.workflow_error", "message": "failed"},
    )

    assert result.status == WorkflowStatus.RUNNING
    assert finished.status == WorkflowStatus.FAILED
    assert finished.error == {"code": "irtiqa.workflow_error", "message": "failed"}
    assert finished.finished_at is not None
