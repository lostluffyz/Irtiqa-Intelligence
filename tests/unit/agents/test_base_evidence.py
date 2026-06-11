from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agents.base import AGENT_STATUS_SUCCEEDED, BaseAgent
from app.agents.context import AgentContext


class _EvidenceTestAgent(BaseAgent):
    name = "test_evidence_agent"
    version = "1.0"

    def __init__(self, **services: dict) -> None:
        super().__init__(**services)
        self._return_evidence = True

    async def _run(self, context: AgentContext) -> dict:
        return {
            "output_ids": {"test": ["id1"]},
            "evidence": [
                {
                    "source_type": "agent_run",
                    "source_id": "a" * 36,
                    "source_detail": "Test evidence from agent",
                    "evidence_type": "computed_metric",
                    "evidence_value": "test value",
                    "relationship_type": "contributes_to",
                    "target_type": "technology",
                    "target_id": "b" * 36,
                    "confidence": 0.9,
                }
            ]
            if self._return_evidence
            else [],
            "summary": "Test agent execution",
            "stats": {"items": 1},
        }


@pytest.mark.asyncio
async def test_agent_evidence_integration() -> None:
    run_service = MagicMock()
    run_service.start_workflow_run.return_value = MagicMock(id="f" * 36)

    agent = _EvidenceTestAgent(agent_run_service=run_service)
    context = AgentContext(
        agent_name="test_evidence_agent",
        company_id="c" * 36,
        contact_id="d" * 36,
    )

    with patch(
        "app.services.evidence_service.EvidenceService.record_evidence_batch",
    ) as mock_evidence:
        mock_evidence.return_value = []
        result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    mock_evidence.assert_called_once()
    call_kwargs = mock_evidence.call_args.kwargs
    assert call_kwargs["company_id"] == context.company_id
    assert call_kwargs["contact_id"] == context.contact_id


@pytest.mark.asyncio
async def test_agent_execute_succeeds_when_evidence_fails() -> None:
    run_service = MagicMock()
    run_service.start_workflow_run.return_value = MagicMock(id="f" * 36)

    agent = _EvidenceTestAgent(agent_run_service=run_service)
    context = AgentContext(
        agent_name="test_evidence_agent",
        company_id="c" * 36,
    )

    with patch(
        "app.services.evidence_service.EvidenceService.record_evidence_batch",
    ) as mock_evidence:
        mock_evidence.side_effect = RuntimeError("Evidence service unavailable")
        result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    mock_evidence.assert_called_once()
