from unittest.mock import MagicMock

import pytest

from app.agents.context import AgentContext
from app.agents.technographic import TechnographicAgent
from app.core.errors import AgentValidationError
from app.models.website import Website


@pytest.fixture
def agent():
    return TechnographicAgent()


@pytest.fixture
def context():
    return AgentContext(agent_name="technographic", company_id="12345678-1234-1234-1234-123456789012", options={})


@pytest.mark.asyncio
async def test_validate_context_invalid_min_confidence(agent):
    context = AgentContext(agent_name="technographic", company_id="12345678-1234-1234-1234-123456789012", options={"min_confidence": 1.5})
    with pytest.raises(AgentValidationError):
        await agent._validate_context(context)

    context2 = AgentContext(agent_name="technographic", company_id="12345678-1234-1234-1234-123456789012", options={"min_confidence": "0.5"})
    with pytest.raises(AgentValidationError):
        await agent._validate_context(context2)


@pytest.mark.asyncio
async def test_validate_context_invalid_categories(agent):
    context = AgentContext(agent_name="technographic", company_id="12345678-1234-1234-1234-123456789012", options={"categories": ["invalid_cat"]})
    with pytest.raises(AgentValidationError):
        await agent._validate_context(context)


@pytest.mark.asyncio
async def test_run_empty_websites(agent, context):
    agent.services = {
        "website_service": MagicMock(),
        "technology_service": MagicMock(),
        "agent_run_service": MagicMock(),
    }
    agent.services["website_service"].list_by_company.return_value = []

    output = await agent._run(context)

    assert output["output_ids"]["technologies"] == []
    assert output["stats"]["pages_scanned"] == 0
    assert output["stats"]["technologies_detected"] == 0


@pytest.mark.asyncio
async def test_run_with_detections(agent, context):
    agent.services = {
        "website_service": MagicMock(),
        "technology_service": MagicMock(),
        "agent_run_service": MagicMock(),
    }

    # Mock website with recognizable signatures (WordPress and Google Analytics)
    html = """
    <html>
        <head>
            <meta name="generator" content="WordPress 6.0" />
            <script src="https://www.google-analytics.com/analytics.js"></script>
        </head>
        <body></body>
    </html>
    """
    website = Website(id="web_1", company_id="company_1", raw_html=html)
    agent.services["website_service"].list_by_company.return_value = [website]

    # Mock technology service to return a new ID on create
    tech_mock = MagicMock()
    tech_mock.id = "tech_1"
    agent.services["technology_service"].get_company_technology.return_value = None
    agent.services["technology_service"].create.return_value = tech_mock

    output = await agent._run(context)

    assert len(output["output_ids"]["technologies"]) >= 2
    assert output["stats"]["pages_scanned"] == 1
    assert output["stats"]["technologies_detected"] >= 2

    # Verify that create was called for WordPress and Google Analytics
    create_calls = agent.services["technology_service"].create.mock_calls
    created_names = [call.kwargs["name"] for call in create_calls]
    assert "WordPress" in created_names
    assert "Google Analytics" in created_names


@pytest.mark.asyncio
async def test_run_with_upsert(agent):
    context = AgentContext(agent_name="technographic", company_id="12345678-1234-1234-1234-123456789012", options={"categories": ["cms"]})
    agent.services = {
        "website_service": MagicMock(),
        "technology_service": MagicMock(),
        "agent_run_service": MagicMock(),
    }

    html = '<meta name="generator" content="WordPress 6.0" />'
    website = Website(id="web_1", company_id="company_1", raw_html=html)
    agent.services["website_service"].list_by_company.return_value = [website]

    # Return an existing technology to trigger upsert (update)
    existing_tech = MagicMock()
    existing_tech.id = "existing_tech_1"
    agent.services["technology_service"].get_company_technology.return_value = existing_tech

    updated_tech = MagicMock()
    updated_tech.id = "existing_tech_1"
    agent.services["technology_service"].update.return_value = updated_tech

    output = await agent._run(context)

    assert "existing_tech_1" in output["output_ids"]["technologies"]
    agent.services["technology_service"].update.assert_called()
    agent.services["technology_service"].create.assert_not_called()


@pytest.mark.asyncio
async def test_run_skips_empty_raw_html(agent, context):
    agent.services = {
        "website_service": MagicMock(),
        "technology_service": MagicMock(),
        "agent_run_service": MagicMock(),
    }

    website = Website(id="web_1", company_id="company_1", raw_html=None)
    agent.services["website_service"].list_by_company.return_value = [website]

    output = await agent._run(context)

    assert output["stats"]["pages_scanned"] == 0
    assert output["stats"]["pages_skipped_no_html"] == 1
    assert output["stats"]["technologies_detected"] == 0


@pytest.mark.asyncio
async def test_technographic_agent_execute_lifecycle():
    """Verify TechnographicAgent works through BaseAgent.execute() lifecycle."""
    agent_run_service = MagicMock()
    agent_run_service.start_workflow_run.return_value = MagicMock(id="f" * 36)

    agent = TechnographicAgent(agent_run_service=agent_run_service)
    agent.services = {
        "website_service": MagicMock(),
        "technology_service": MagicMock(),
        "agent_run_service": agent_run_service,
    }
    agent.services["website_service"].list_by_company.return_value = []
    agent.services["technology_service"].get_company_technology.return_value = None

    context = AgentContext(
        agent_name="technographic",
        company_id="12345678-1234-1234-1234-123456789012",
        options={},
    )

    from app.agents.result import AGENT_STATUS_SUCCEEDED
    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert result.agent_run_id is not None
    assert "technologies" in result.output_ids
    assert result.summary is not None
