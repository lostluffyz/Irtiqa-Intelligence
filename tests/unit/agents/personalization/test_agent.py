from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from app.agents.context import AgentContext
from app.agents.personalization.agent import PersonalizationAgent
from app.models.company import Company
from app.models.contact import Contact
from app.models.intelligence_score import IntelligenceScore
from app.models.intent_signal import IntentSignal
from app.models.technology import Technology
from app.models.outreach_message import OutreachMessage

@pytest.fixture
def mock_company():
    return Company(
        id="11111111-1111-1111-1111-111111111111",
        domain="example.com",
        name="Example Inc",
        industry="Software",
        status="active"
    )

@pytest.fixture
def mock_contact():
    return Contact(
        id="22222222-2222-2222-2222-222222222222",
        company_id="11111111-1111-1111-1111-111111111111",
        first_name="Alice",
        last_name="Smith",
        email="alice@example.com",
        status="active"
    )

@pytest.fixture
def mock_technology():
    return Technology(
        id="33333333-3333-3333-3333-333333333333",
        company_id="11111111-1111-1111-1111-111111111111",
        name="React",
        category="frontend",
        confidence=0.9
    )

@pytest.fixture
def mock_intent_signal():
    return IntentSignal(
        id="44444444-4444-4444-4444-444444444444",
        company_id="11111111-1111-1111-1111-111111111111",
        signal_type="growth",
        signal_name="Series A funding",
        confidence=0.9,
        strength=0.8,
        observed_at=datetime.now(timezone.utc)
    )

@pytest.fixture
def mock_intelligence_score():
    return IntelligenceScore(
        id="55555555-5555-5555-5555-555555555555",
        company_id="11111111-1111-1111-1111-111111111111",
        fit_score=60.0,
        intent_score=90.0,
        technographic_score=50.0,
        engagement_score=0.0,
        total_score=75.0,
        confidence=0.9,
        score_version="v1",
        scored_at=datetime.now(timezone.utc)
    )

@pytest.fixture
def services(mock_company, mock_contact, mock_technology, mock_intent_signal, mock_intelligence_score):
    company_service = MagicMock()
    company_service.get.return_value = mock_company
    
    contact_service = MagicMock()
    contact_service.get.return_value = mock_contact
    
    tech_service = MagicMock()
    tech_service.list_by_company.return_value = [mock_technology]
    
    intent_service = MagicMock()
    intent_service.list_by_company.return_value = [mock_intent_signal]
    intent_service.list_by_contact.return_value = []
    
    score_service = MagicMock()
    score_service.list_by_company.return_value = [mock_intelligence_score]
    
    outreach_service = MagicMock()
    outreach_service.create.side_effect = lambda **kw: OutreachMessage(
        id="66666666-6666-6666-6666-666666666666",
        company_id=kw.get("company_id", ""),
        channel=kw.get("channel", ""),
        message_body=kw.get("message_body", ""),
        personalization_angle=kw.get("personalization_angle", ""),
        status=kw.get("status", "draft"),
        confidence=kw.get("confidence", 0.5),
        generated_at=kw.get("generated_at", datetime.now(timezone.utc))
    )
    
    return {
        "company_service": company_service,
        "contact_service": contact_service,
        "technology_service": tech_service,
        "intent_signal_service": intent_service,
        "intelligence_score_service": score_service,
        "outreach_message_service": outreach_service
    }

@pytest.mark.asyncio
async def test_run_success_all_data(services):
    agent = PersonalizationAgent(**services)
    context = AgentContext(
        agent_name="personalization_agent",
        company_id="11111111-1111-1111-1111-111111111111",
        contact_id="22222222-2222-2222-2222-222222222222"
    )
    
    output = await agent._run(context)
    
    assert "outreach_messages" in output["output_ids"]
    assert len(output["output_ids"]["outreach_messages"]) == 3
    
    outreach_service = services["outreach_message_service"]
    assert outreach_service.create.call_count == 3
    
    # Check that angles were selected correctly based on score (intent=90, tech=50, fit=60)
    # primary should be intent_driven
    assert output["stats"]["primary_angle"] == "intent_driven"

@pytest.mark.asyncio
async def test_run_missing_contact(services):
    services["contact_service"].get.return_value = None
    
    agent = PersonalizationAgent(**services)
    context = AgentContext(
        agent_name="personalization_agent",
        company_id="11111111-1111-1111-1111-111111111111"
    )
    
    output = await agent._run(context)
    assert len(output["output_ids"]["outreach_messages"]) == 3
    # Schema should have used fallback for contact first name

@pytest.mark.asyncio
async def test_run_missing_intent_and_tech_and_scores(services):
    services["technology_service"].list_by_company.return_value = []
    services["intent_signal_service"].list_by_company.return_value = []
    services["intelligence_score_service"].list_by_company.return_value = []
    
    agent = PersonalizationAgent(**services)
    context = AgentContext(
        agent_name="personalization_agent",
        company_id="11111111-1111-1111-1111-111111111111"
    )
    
    output = await agent._run(context)
    assert len(output["output_ids"]["outreach_messages"]) == 3
    assert output["stats"]["primary_angle"] == "fit_driven"
    assert output["stats"]["secondary_angle"] == "fit_driven"


@pytest.mark.asyncio
async def test_personalization_agent_execute_lifecycle(services):
    """Verify PersonalizationAgent works through BaseAgent.execute() lifecycle."""
    agent_run_service = MagicMock()
    agent_run_service.start_workflow_run.return_value = MagicMock(id="f" * 36)
    services["agent_run_service"] = agent_run_service

    agent = PersonalizationAgent(**services)
    context = AgentContext(
        agent_name="personalization_agent",
        company_id="11111111-1111-1111-1111-111111111111",
        contact_id="22222222-2222-2222-2222-222222222222",
    )

    from app.agents.result import AGENT_STATUS_SUCCEEDED
    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert result.agent_run_id is not None
    assert "outreach_messages" in result.output_ids
    assert len(result.output_ids["outreach_messages"]) == 3
    assert result.summary is not None
