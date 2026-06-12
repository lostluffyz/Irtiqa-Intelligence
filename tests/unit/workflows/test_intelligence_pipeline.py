from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.result import AGENT_STATUS_FAILED, AGENT_STATUS_SUCCEEDED, AgentResult
from app.core.errors import WorkflowError
from app.workflows.context import WorkflowContext
from app.workflows.intelligence_pipeline import IntelligencePipelineWorkflow
from app.workflows.states import WorkflowStatus


def _mock_async_agent(output_ids: dict, agent_run_id: str = "a" * 36, status: str = AGENT_STATUS_SUCCEEDED, summary: str = "Completed"):
    """Return an AsyncMock configured to return an AgentResult."""
    result = AgentResult(
        agent_name="test_agent",
        agent_run_id=agent_run_id,
        status=status,
        output_ids=output_ids,
        summary=summary,
        duration_ms=100.0,
    )
    return AsyncMock(return_value=result)


def _mock_services() -> dict:
    """Create mock services that all pipeline agents need."""
    return {
        "company_service": MagicMock(),
        "contact_service": MagicMock(),
        "website_service": MagicMock(),
        "technology_service": MagicMock(),
        "intent_signal_service": MagicMock(),
        "intelligence_score_service": MagicMock(),
        "outreach_message_service": MagicMock(),
        "agent_run_service": MagicMock(),
    }


def test_pipeline_step_execution() -> None:
    """Each agent executes correctly when called sequentially in the pipeline."""
    services = _mock_services()
    services["company_service"].get_required.return_value = MagicMock(id="c" * 36)

    workflow = IntelligencePipelineWorkflow(**services)

    with patch(
        "app.agents.deep_scraper.DeepScraperAgent.execute",
        _mock_async_agent(output_ids={"websites": ["w1"]}, agent_run_id="r1" + "a" * 34),
    ), patch(
        "app.agents.technographic.TechnographicAgent.execute",
        _mock_async_agent(output_ids={"technologies": ["t1"]}, agent_run_id="r2" + "a" * 34),
    ), patch(
        "app.agents.intent_signal.IntentSignalAgent.execute",
        _mock_async_agent(output_ids={"intent_signals": ["s1"]}, agent_run_id="r3" + "a" * 34),
    ), patch(
        "app.agents.intelligence_scoring.IntelligenceScoringAgent.execute",
        _mock_async_agent(output_ids={"intelligence_scores": ["sc1"]}, agent_run_id="r4" + "a" * 34),
    ), patch(
        "app.agents.personalization.PersonalizationAgent.execute",
        _mock_async_agent(output_ids={"outreach_messages": ["m1"]}, agent_run_id="r5" + "a" * 34),
    ):
        context = WorkflowContext(
            workflow_name="intelligence_pipeline",
            company_id="c" * 36,
        )
        result = workflow.execute(context)

    assert result.status == WorkflowStatus.SUCCEEDED
    assert result.output_ids["websites"] == ["w1"]
    assert result.output_ids["technologies"] == ["t1"]
    assert result.output_ids["intent_signals"] == ["s1"]
    assert result.output_ids["intelligence_scores"] == ["sc1"]
    assert result.output_ids["outreach_messages"] == ["m1"]


def test_pipeline_fails_on_step_failure() -> None:
    """Pipeline stops and returns FAILED when an agent fails."""
    services = _mock_services()
    services["company_service"].get_required.return_value = MagicMock(id="c" * 36)

    workflow = IntelligencePipelineWorkflow(**services)

    with patch(
        "app.agents.deep_scraper.DeepScraperAgent.execute",
        _mock_async_agent(status=AGENT_STATUS_FAILED, output_ids={}, summary="HTTP 500"),
    ):
        context = WorkflowContext(
            workflow_name="intelligence_pipeline",
            company_id="c" * 36,
        )
        with pytest.raises(WorkflowError, match="Deep Scraper Agent failed"):
            workflow.execute(context)


def test_pipeline_aggregates_output_ids() -> None:
    """WorkflowResult contains output_ids from all 5 steps."""
    services = _mock_services()
    services["company_service"].get_required.return_value = MagicMock(id="c" * 36)

    workflow = IntelligencePipelineWorkflow(**services)

    with patch(
        "app.agents.deep_scraper.DeepScraperAgent.execute",
        _mock_async_agent(output_ids={"websites": ["w1", "w2"]}),
    ), patch(
        "app.agents.technographic.TechnographicAgent.execute",
        _mock_async_agent(output_ids={"technologies": ["t1"]}),
    ), patch(
        "app.agents.intent_signal.IntentSignalAgent.execute",
        _mock_async_agent(output_ids={"intent_signals": ["s1", "s2", "s3"]}),
    ), patch(
        "app.agents.intelligence_scoring.IntelligenceScoringAgent.execute",
        _mock_async_agent(output_ids={"intelligence_scores": ["sc1"]}),
    ), patch(
        "app.agents.personalization.PersonalizationAgent.execute",
        _mock_async_agent(output_ids={"outreach_messages": ["m1", "m2"]}),
    ):
        context = WorkflowContext(
            workflow_name="intelligence_pipeline",
            company_id="c" * 36,
        )
        result = workflow.execute(context)

    assert len(result.output_ids["websites"]) == 2
    assert len(result.output_ids["technologies"]) == 1
    assert len(result.output_ids["intent_signals"]) == 3
    assert len(result.output_ids["intelligence_scores"]) == 1
    assert len(result.output_ids["outreach_messages"]) == 2


def test_pipeline_agent_run_ids() -> None:
    """WorkflowResult contains 5 agent_run_ids (one per step)."""
    services = _mock_services()
    services["company_service"].get_required.return_value = MagicMock(id="c" * 36)

    workflow = IntelligencePipelineWorkflow(**services)

    with patch(
        "app.agents.deep_scraper.DeepScraperAgent.execute",
        _mock_async_agent(output_ids={"websites": ["w1"]}, agent_run_id="r1" + "a" * 34),
    ), patch(
        "app.agents.technographic.TechnographicAgent.execute",
        _mock_async_agent(output_ids={"technologies": ["t1"]}, agent_run_id="r2" + "a" * 34),
    ), patch(
        "app.agents.intent_signal.IntentSignalAgent.execute",
        _mock_async_agent(output_ids={"intent_signals": ["s1"]}, agent_run_id="r3" + "a" * 34),
    ), patch(
        "app.agents.intelligence_scoring.IntelligenceScoringAgent.execute",
        _mock_async_agent(output_ids={"intelligence_scores": ["sc1"]}, agent_run_id="r4" + "a" * 34),
    ), patch(
        "app.agents.personalization.PersonalizationAgent.execute",
        _mock_async_agent(output_ids={"outreach_messages": ["m1"]}, agent_run_id="r5" + "a" * 34),
    ):
        context = WorkflowContext(
            workflow_name="intelligence_pipeline",
            company_id="c" * 36,
        )
        result = workflow.execute(context)

    assert len(result.agent_run_ids) == 5
    assert result.agent_run_ids == ["r1" + "a" * 34, "r2" + "a" * 34, "r3" + "a" * 34, "r4" + "a" * 34, "r5" + "a" * 34]


def test_pipeline_handles_service_error() -> None:
    """Pipeline wraps service errors in WorkflowError."""
    services = _mock_services()
    from app.core.errors import EntityNotFoundError

    # Make company lookup raise
    mock_company = MagicMock()
    mock_company.get_required.side_effect = EntityNotFoundError(
        "Company not found.",
        details={"entity_id": "x"},
    )
    services["company_service"] = mock_company

    workflow = IntelligencePipelineWorkflow(**services)
    context = WorkflowContext(
        workflow_name="intelligence_pipeline",
        company_id="00000000-0000-0000-0000-000000000000",
    )
    with pytest.raises(WorkflowError, match="Intelligence pipeline failed"):
        workflow.execute(context)


def test_pipeline_evidence_forwarded_to_agents() -> None:
    """Each agent receives workflow_name='intelligence_pipeline' in context."""
    services = _mock_services()
    services["company_service"].get_required.return_value = MagicMock(id="c" * 36)

    workflow = IntelligencePipelineWorkflow(**services)

    with patch(
        "app.agents.deep_scraper.DeepScraperAgent.execute",
        _mock_async_agent(output_ids={"websites": ["w1"]}),
    ) as mock_ds, patch(
        "app.agents.technographic.TechnographicAgent.execute",
        _mock_async_agent(output_ids={"technologies": ["t1"]}),
    ) as mock_tg, patch(
        "app.agents.intent_signal.IntentSignalAgent.execute",
        _mock_async_agent(output_ids={"intent_signals": ["s1"]}),
    ) as mock_is, patch(
        "app.agents.intelligence_scoring.IntelligenceScoringAgent.execute",
        _mock_async_agent(output_ids={"intelligence_scores": ["sc1"]}),
    ) as mock_isc, patch(
        "app.agents.personalization.PersonalizationAgent.execute",
        _mock_async_agent(output_ids={"outreach_messages": ["m1"]}),
    ) as mock_pa:
        context = WorkflowContext(
            workflow_name="intelligence_pipeline",
            company_id="c" * 36,
        )
        workflow.execute(context)

    for mock in [mock_ds, mock_tg, mock_is, mock_isc, mock_pa]:
        call_context = mock.call_args[0][0]
        assert call_context.workflow_name == "intelligence_pipeline"
