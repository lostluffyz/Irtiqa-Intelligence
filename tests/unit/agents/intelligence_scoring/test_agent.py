from unittest.mock import MagicMock
import uuid
import pytest
from datetime import datetime, timezone

from app.agents.context import AgentContext
from app.agents.intelligence_scoring.agent import IntelligenceScoringAgent
from app.agents.result import AGENT_STATUS_SUCCEEDED
from app.models.company import Company
from app.models.contact import Contact
from app.models.intent_signal import IntentSignal
from app.models.technology import Technology
from app.models.intelligence_score import IntelligenceScore
from app.services.company_service import CompanyService
from app.services.contact_service import ContactService
from app.services.intelligence_score_service import IntelligenceScoreService
from app.services.intent_signal_service import IntentSignalService
from app.services.technology_service import TechnologyService

@pytest.fixture
def mock_company_service() -> MagicMock:
    return MagicMock(spec=CompanyService)

@pytest.fixture
def mock_contact_service() -> MagicMock:
    return MagicMock(spec=ContactService)

@pytest.fixture
def mock_technology_service() -> MagicMock:
    return MagicMock(spec=TechnologyService)

@pytest.fixture
def mock_intent_signal_service() -> MagicMock:
    return MagicMock(spec=IntentSignalService)

@pytest.fixture
def mock_intelligence_score_service() -> MagicMock:
    return MagicMock(spec=IntelligenceScoreService)

@pytest.fixture
def services(
    mock_company_service: MagicMock,
    mock_contact_service: MagicMock,
    mock_technology_service: MagicMock,
    mock_intent_signal_service: MagicMock,
    mock_intelligence_score_service: MagicMock,
) -> dict:
    return {
        "company_service": mock_company_service,
        "contact_service": mock_contact_service,
        "technology_service": mock_technology_service,
        "intent_signal_service": mock_intent_signal_service,
        "intelligence_score_service": mock_intelligence_score_service,
    }

@pytest.mark.asyncio
async def test_intelligence_scoring_agent_company_only(
    services: dict,
    mock_company_service: MagicMock,
    mock_contact_service: MagicMock,
    mock_technology_service: MagicMock,
    mock_intent_signal_service: MagicMock,
    mock_intelligence_score_service: MagicMock,
) -> None:
    agent = IntelligenceScoringAgent(**services)
    company_id = str(uuid.uuid4())
    context = AgentContext(agent_name="intelligence_scoring_agent", company_id=company_id)

    # Mock Data
    company = Company(
        id=company_id,
        name="Test Corp",
        domain="test.com",
        industry="Tech",
        company_size="10-50",
    )
    mock_company_service.get.return_value = company

    mock_technology_service.list_by_company.return_value = [
        Technology(id=str(uuid.uuid4()), company_id=company_id, name="React", category="Frontend", confidence=0.9),
    ]

    mock_intent_signal_service.list_by_company.return_value = [
        IntentSignal(
            id=str(uuid.uuid4()),
            company_id=company_id,
            signal_type="pricing_page_visit",
            strength=0.8,
            confidence=0.9,
            observed_at=datetime.now(timezone.utc),
        )
    ]

    expected_score_id = str(uuid.uuid4())
    score_model = IntelligenceScore(id=expected_score_id, company_id=company_id, total_score=85.0)
    mock_intelligence_score_service.create.return_value = score_model

    # Run
    output = await agent._run(context)

    # Assertions
    mock_company_service.get.assert_called_once_with(company_id)
    mock_contact_service.get.assert_not_called()
    mock_technology_service.list_by_company.assert_called_once_with(company_id)
    mock_intent_signal_service.list_by_company.assert_called_once_with(company_id)
    mock_intent_signal_service.list_by_contact.assert_not_called()

    assert mock_intelligence_score_service.create.call_count == 1
    create_schema = mock_intelligence_score_service.create.call_args[0][0]
    assert create_schema.company_id == company_id
    assert create_schema.contact_id is None
    assert create_schema.total_score > 0

    assert output["output_ids"]["intelligence_scores"] == [expected_score_id]


@pytest.mark.asyncio
async def test_intelligence_scoring_agent_with_contact(
    services: dict,
    mock_company_service: MagicMock,
    mock_contact_service: MagicMock,
    mock_technology_service: MagicMock,
    mock_intent_signal_service: MagicMock,
    mock_intelligence_score_service: MagicMock,
) -> None:
    agent = IntelligenceScoringAgent(**services)
    company_id = str(uuid.uuid4())
    contact_id = str(uuid.uuid4())
    context = AgentContext(agent_name="intelligence_scoring_agent", company_id=company_id, contact_id=contact_id)

    # Mock Data
    company = Company(
        id=company_id,
        name="Test Corp",
        domain="test.com",
    )
    mock_company_service.get.return_value = company

    contact = Contact(
        id=contact_id,
        company_id=company_id,
        email="test@test.com",
        title="CEO",
    )
    mock_contact_service.get.return_value = contact

    mock_technology_service.list_by_company.return_value = []
    
    # We return different lists to test merging
    signal_1 = IntentSignal(
        id=str(uuid.uuid4()),
        company_id=company_id,
        signal_type="page_visit",
        strength=0.5,
        confidence=0.8,
        observed_at=datetime.now(timezone.utc),
    )
    signal_2 = IntentSignal(
        id=str(uuid.uuid4()),
        company_id=company_id,
        contact_id=contact_id,
        signal_type="pricing_page_visit",
        strength=0.9,
        confidence=0.9,
        observed_at=datetime.now(timezone.utc),
    )
    # The company list has signal_1, the contact list has signal_1 (due to some overlapping query) and signal_2
    mock_intent_signal_service.list_by_company.return_value = [signal_1]
    mock_intent_signal_service.list_by_contact.return_value = [signal_1, signal_2]

    expected_score_id = str(uuid.uuid4())
    score_model = IntelligenceScore(id=expected_score_id, company_id=company_id, contact_id=contact_id, total_score=70.0)
    mock_intelligence_score_service.create.return_value = score_model

    # Run
    output = await agent._run(context)

    # Assertions
    mock_company_service.get.assert_called_once_with(company_id)
    mock_contact_service.get.assert_called_once_with(contact_id)
    
    assert mock_intelligence_score_service.create.call_count == 1
    create_schema = mock_intelligence_score_service.create.call_args[0][0]
    assert create_schema.company_id == company_id
    assert create_schema.contact_id == contact_id
    # Ensure it parsed intent signals
    assert "2 intent signals" in create_schema.rationale

    assert output["output_ids"]["intelligence_scores"] == [expected_score_id]


@pytest.mark.asyncio
async def test_intelligence_scoring_agent_company_not_found(
    services: dict,
    mock_company_service: MagicMock,
) -> None:
    agent = IntelligenceScoringAgent(**services)
    company_id = str(uuid.uuid4())
    context = AgentContext(agent_name="intelligence_scoring_agent", company_id=company_id)

    mock_company_service.get.return_value = None

    with pytest.raises(ValueError, match=f"Company {company_id} not found."):
        await agent._run(context)


@pytest.mark.asyncio
async def test_intelligence_scoring_agent_contact_not_found(
    services: dict,
    mock_company_service: MagicMock,
    mock_contact_service: MagicMock,
) -> None:
    agent = IntelligenceScoringAgent(**services)
    company_id = str(uuid.uuid4())
    contact_id = str(uuid.uuid4())
    context = AgentContext(agent_name="intelligence_scoring_agent", company_id=company_id, contact_id=contact_id)

    mock_company_service.get.return_value = Company(id=company_id, name="Test Corp")
    mock_contact_service.get.return_value = None

    with pytest.raises(ValueError, match=f"Contact {contact_id} not found."):
        await agent._run(context)


@pytest.mark.asyncio
async def test_intelligence_scoring_agent_execute_lifecycle(
    services: dict,
    mock_company_service: MagicMock,
    mock_technology_service: MagicMock,
    mock_intent_signal_service: MagicMock,
    mock_intelligence_score_service: MagicMock,
) -> None:
    """Verify IntelligenceScoringAgent works through BaseAgent.execute() lifecycle."""
    agent_run_service = MagicMock()
    agent_run_service.start_workflow_run.return_value = MagicMock(id="f" * 36)
    services["agent_run_service"] = agent_run_service
    agent = IntelligenceScoringAgent(**services)

    company_id = str(uuid.uuid4())
    context = AgentContext(agent_name="intelligence_scoring_agent", company_id=company_id)

    company = Company(id=company_id, name="Test Corp", domain="test.com", industry="Tech")
    mock_company_service.get.return_value = company
    mock_technology_service.list_by_company.return_value = []
    mock_intent_signal_service.list_by_company.return_value = []

    expected_score_id = str(uuid.uuid4())
    score_model = IntelligenceScore(id=expected_score_id, company_id=company_id, total_score=85.0)
    mock_intelligence_score_service.create.return_value = score_model

    result = await agent.execute(context)

    assert result.status == AGENT_STATUS_SUCCEEDED
    assert result.agent_run_id is not None
    assert "intelligence_scores" in result.output_ids
    assert result.output_ids["intelligence_scores"] == [expected_score_id]
    assert result.summary is not None
