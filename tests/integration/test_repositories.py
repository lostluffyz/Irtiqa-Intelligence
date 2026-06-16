from __future__ import annotations

from app.repositories import (
    AgentRunRepository,
    CompanyRepository,
    ContactRepository,
    IntelligenceScoreRepository,
    IntentSignalRepository,
    OutreachMessageRepository,
    TechnologyRepository,
    WebsiteRepository,
)


def test_company_repository_adds_and_finds_by_domain(session, company, organization) -> None:
    session.add(organization)
    session.flush()
    repository = CompanyRepository(session)
    repository.add(company)
    session.commit()

    assert repository.get(company.id) == company
    assert repository.get_by_domain(company.domain, organization_id=organization.id) == company
    assert repository.search_by_name("Irtiqa", organization_id=organization.id) == [company]
    assert repository.list_by_status("active", organization_id=organization.id) == [company]


def test_contact_repository_queries_by_email_company_and_status(session, company, contact, organization) -> None:
    session.add(organization)
    session.flush()
    session.add(contact)
    session.commit()

    repository = ContactRepository(session)

    assert repository.get_by_email(contact.email, organization_id=organization.id) == contact
    assert repository.list_by_company(company.id, organization_id=organization.id) == [contact]
    assert repository.list_by_status("active", organization_id=organization.id) == [contact]


def test_website_repository_queries_by_url_and_company(session, company, website, organization) -> None:
    session.add(organization)
    session.flush()
    session.add(website)
    session.commit()

    repository = WebsiteRepository(session)

    assert repository.get_by_normalized_url(website.normalized_url) == website
    assert repository.list_by_company(company.id) == [website]


def test_technology_repository_queries_company_technology_and_category(
    session,
    technology,
    organization,
) -> None:
    session.add(organization)
    session.flush()
    session.add(technology)
    session.commit()

    repository = TechnologyRepository(session)

    assert repository.list_by_company(technology.company_id) == [technology]
    assert (
        repository.get_company_technology(
            company_id=technology.company_id,
            name=technology.name,
            category=technology.category,
        )
        == technology
    )
    assert repository.list_by_category("crm") == [technology]


def test_intent_signal_repository_queries_by_company_contact_and_type(
    session,
    intent_signal,
    organization,
) -> None:
    session.add(organization)
    session.flush()
    session.add(intent_signal)
    session.commit()

    repository = IntentSignalRepository(session)

    assert repository.list_by_company(intent_signal.company_id, organization_id=organization.id) == [intent_signal]
    assert repository.list_by_contact(intent_signal.contact_id, organization_id=organization.id) == [intent_signal]
    assert repository.list_by_type("technology_change", organization_id=organization.id) == [intent_signal]


def test_intelligence_score_repository_queries_latest_and_top_scores(
    session,
    intelligence_score,
    organization,
) -> None:
    session.add(organization)
    session.flush()
    session.add(intelligence_score)
    session.commit()

    repository = IntelligenceScoreRepository(session)

    assert repository.latest_for_company(intelligence_score.company_id, organization_id=organization.id) == intelligence_score
    assert repository.latest_for_contact(intelligence_score.contact_id, organization_id=organization.id) == intelligence_score
    assert repository.list_top_scores(organization_id=organization.id) == [intelligence_score]


def test_outreach_message_repository_queries_by_company_contact_and_status(
    session,
    outreach_message,
    organization,
) -> None:
    session.add(organization)
    session.flush()
    session.add(outreach_message)
    session.commit()

    repository = OutreachMessageRepository(session)

    assert repository.list_by_company(outreach_message.company_id, organization_id=organization.id) == [outreach_message]
    assert repository.list_by_contact(outreach_message.contact_id, organization_id=organization.id) == [outreach_message]
    assert repository.list_by_status("draft", organization_id=organization.id) == [outreach_message]


def test_agent_run_repository_queries_by_agent_status_and_workflow(session, agent_run, organization) -> None:
    session.add(organization)
    session.flush()
    session.add(agent_run)
    session.commit()

    repository = AgentRunRepository(session)

    assert repository.list_by_agent("test_agent", organization_id=organization.id) == [agent_run]
    assert repository.list_by_status("succeeded", organization_id=organization.id) == [agent_run]
    assert repository.list_by_workflow("test_workflow", organization_id=organization.id) == [agent_run]
