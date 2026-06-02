from __future__ import annotations

from app.agents.result import AGENT_STATUS_FAILED, AGENT_STATUS_SUCCEEDED, AgentResult


VALID_AGENT_RUN_ID = "22222222-2222-2222-2222-222222222222"


def test_agent_result_successful() -> None:
    result = AgentResult(
        agent_name="test_agent",
        agent_run_id=VALID_AGENT_RUN_ID,
        status=AGENT_STATUS_SUCCEEDED,
        output_ids={"technologies": ["aaa-bbb", "ccc-ddd"]},
        summary="Detected 2 technologies.",
        duration_ms=123.45,
        stats={"technologies_detected": 2},
    )

    assert result.status == "succeeded"
    assert result.agent_run_id == VALID_AGENT_RUN_ID
    assert result.output_ids == {"technologies": ["aaa-bbb", "ccc-ddd"]}
    assert result.error is None
    assert result.stats == {"technologies_detected": 2}


def test_agent_result_failed_with_error() -> None:
    error_dict = {
        "code": "irtiqa.agent_execution_error",
        "message": "Scraping failed.",
        "type": "AgentExecutionError",
    }
    result = AgentResult(
        agent_name="test_agent",
        agent_run_id=VALID_AGENT_RUN_ID,
        status=AGENT_STATUS_FAILED,
        summary="Failed: Scraping failed.",
        error=error_dict,
        duration_ms=50.0,
    )

    assert result.status == "failed"
    assert result.error == error_dict
    assert result.output_ids == {}
    assert result.stats == {}


def test_agent_result_defaults_empty_collections() -> None:
    result = AgentResult(
        agent_name="test_agent",
        status=AGENT_STATUS_SUCCEEDED,
        summary="No output produced.",
        duration_ms=0.0,
    )

    assert result.agent_run_id is None
    assert result.output_ids == {}
    assert result.stats == {}
    assert result.error is None
    assert result.finished_at is not None
