from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.agents.context import AgentContext


VALID_COMPANY_ID = "00000000-0000-0000-0000-000000000000"
VALID_CONTACT_ID = "11111111-1111-1111-1111-111111111111"


def test_agent_context_accepts_valid_company_id() -> None:
    context = AgentContext(
        agent_name="test_agent",
        company_id=VALID_COMPANY_ID,
    )

    assert context.agent_name == "test_agent"
    assert context.company_id == VALID_COMPANY_ID
    assert context.contact_id is None
    assert context.workflow_name is None
    assert context.correlation_id is None


def test_agent_context_accepts_optional_fields() -> None:
    context = AgentContext(
        agent_name="test_agent",
        company_id=VALID_COMPANY_ID,
        contact_id=VALID_CONTACT_ID,
        workflow_name="contact_intelligence",
        correlation_id="req-001",
    )

    assert context.contact_id == VALID_CONTACT_ID
    assert context.workflow_name == "contact_intelligence"
    assert context.correlation_id == "req-001"


def test_agent_context_rejects_blank_agent_name() -> None:
    with pytest.raises(PydanticValidationError):
        AgentContext(agent_name="", company_id=VALID_COMPANY_ID)


def test_agent_context_rejects_missing_company_id() -> None:
    with pytest.raises(PydanticValidationError):
        AgentContext(agent_name="test_agent")


def test_agent_context_freezes_options_copy() -> None:
    options = {"crawl_depth": 3}
    context = AgentContext(
        agent_name="test_agent",
        company_id=VALID_COMPANY_ID,
        options=options,
    )

    options["crawl_depth"] = 99

    assert context.options["crawl_depth"] == 3
    with pytest.raises(TypeError):
        context.options["crawl_depth"] = 99


def test_agent_context_rejects_non_mapping_options() -> None:
    with pytest.raises(PydanticValidationError):
        AgentContext(
            agent_name="test_agent",
            company_id=VALID_COMPANY_ID,
            options=["invalid"],
        )


def test_agent_context_is_immutable() -> None:
    context = AgentContext(
        agent_name="test_agent",
        company_id=VALID_COMPANY_ID,
    )

    with pytest.raises(PydanticValidationError):
        context.agent_name = "modified"
