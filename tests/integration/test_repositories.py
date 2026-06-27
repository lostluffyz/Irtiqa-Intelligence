from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.repositories import (
    AgentRunRepository,
    CompanyRepository,
    ContactRepository,
    DiscoveryRunRepository,
    DiscoverySearchRepository,
    IntelligenceScoreRepository,
    IntentSignalRepository,
    OutreachMessageRepository,
    TechnologyRepository,
    WebsiteRepository,
)
from app.models.discovery_search import DiscoverySearch
from app.models.discovery_run import DiscoveryRun


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


# -- Discovery Search Repository Tests ---------------------------------------


def test_discovery_search_repository_list_by_organization(session, organization) -> None:
    session.add(organization)
    session.flush()

    search = DiscoverySearch(
        id=str(uuid4()),
        organization_id=organization.id,
        name="ICP Search 1",
        criteria='{"industry": "fintech"}',
        status="active",
        total_discovered=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(search)
    session.commit()

    repository = DiscoverySearchRepository(session)
    result = repository.list_by_organization(organization.id)

    assert len(result) == 1
    assert result[0].name == "ICP Search 1"


def test_discovery_search_repository_get_active(session, organization) -> None:
    session.add(organization)
    session.flush()

    active_search = DiscoverySearch(
        id=str(uuid4()),
        organization_id=organization.id,
        name="Active ICP",
        criteria='{"industry": "saas"}',
        status="active",
        total_discovered=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    archived_search = DiscoverySearch(
        id=str(uuid4()),
        organization_id=organization.id,
        name="Archived ICP",
        criteria='{"industry": "healthcare"}',
        status="archived",
        total_discovered=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(active_search)
    session.add(archived_search)
    session.commit()

    repository = DiscoverySearchRepository(session)
    active = repository.get_active(organization.id)

    assert len(active) == 1
    assert active[0].name == "Active ICP"


def test_discovery_search_repository_filters_other_organizations(session, organization) -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    other_org = type(organization)(
        id=str(uuid4()),
        name="Other Org",
        slug="other-org",
        status="active",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(organization)
    session.add(other_org)
    session.flush()

    search_a = DiscoverySearch(
        id=str(uuid4()),
        organization_id=organization.id,
        name="A",
        criteria='{}',
        status="active",
        total_discovered=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    search_b = DiscoverySearch(
        id=str(uuid4()),
        organization_id=other_org.id,
        name="B",
        criteria='{}',
        status="active",
        total_discovered=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(search_a)
    session.add(search_b)
    session.commit()

    repository = DiscoverySearchRepository(session)
    result = repository.list_by_organization(organization.id)

    assert len(result) == 1
    assert result[0].name == "A"


def test_discovery_search_repository_count_by_organization(session, organization) -> None:
    session.add(organization)
    session.flush()

    search = DiscoverySearch(
        id=str(uuid4()),
        organization_id=organization.id,
        name="ICP Search",
        criteria='{"industry": "ai"}',
        status="active",
        total_discovered=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(search)
    session.commit()

    repository = DiscoverySearchRepository(session)
    count = repository.count_by_organization(organization.id)

    assert count == 1


# -- Discovery Run Repository Tests --------------------------------------------


def _create_search(
    organization,
    name: str = "Test Search",
    status: str = "active",
) -> DiscoverySearch:
    return DiscoverySearch(
        id=str(uuid4()),
        organization_id=organization.id,
        name=name,
        criteria='{"industry": "fintech"}',
        status=status,
        total_discovered=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _create_run(
    organization,
    search_id: str,
    status: str = "running",
) -> DiscoveryRun:
    return DiscoveryRun(
        id=str(uuid4()),
        organization_id=organization.id,
        search_id=search_id,
        status=status,
        sources_queried=2,
        companies_found=10,
        companies_created=5,
        companies_skipped=3,
        started_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_discovery_run_repository_list_by_organization(session, organization) -> None:
    session.add(organization)
    session.flush()

    search = _create_search(organization)
    session.add(search)
    session.flush()

    run = _create_run(organization, search.id)
    session.add(run)
    session.commit()

    repository = DiscoveryRunRepository(session)
    result = repository.list_by_organization(organization.id)

    assert len(result) == 1
    assert result[0].status == "running"


def test_discovery_run_repository_list_by_search(session, organization) -> None:
    session.add(organization)
    session.flush()

    search1 = _create_search(organization, name="Search 1")
    search2 = _create_search(organization, name="Search 2")
    session.add(search1)
    session.add(search2)
    session.flush()

    run1 = _create_run(organization, search1.id)
    session.add(run1)
    session.commit()

    repository = DiscoveryRunRepository(session)
    result = repository.list_by_search(search1.id)

    assert len(result) == 1
    assert result[0].search_id == search1.id


def test_discovery_run_repository_list_by_status(session, organization) -> None:
    session.add(organization)
    session.flush()

    search = _create_search(organization)
    session.add(search)
    session.flush()

    running_run = _create_run(organization, search.id, status="running")
    failed_run = _create_run(organization, search.id, status="failed")
    session.add(running_run)
    session.add(failed_run)
    session.commit()

    repository = DiscoveryRunRepository(session)
    running = repository.list_by_status("running", organization.id)

    assert len(running) == 1
    assert running[0].status == "running"


def test_discovery_run_repository_list_recent_runs_orders_by_started_at(
    session, organization
) -> None:
    session.add(organization)
    session.flush()

    search = _create_search(organization)
    session.add(search)
    session.flush()

    earlier = DiscoveryRun(
        id=str(uuid4()),
        organization_id=organization.id,
        search_id=search.id,
        status="succeeded",
        sources_queried=1,
        companies_found=1,
        companies_created=1,
        companies_skipped=0,
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    later = DiscoveryRun(
        id=str(uuid4()),
        organization_id=organization.id,
        search_id=search.id,
        status="running",
        sources_queried=2,
        companies_found=5,
        companies_created=2,
        companies_skipped=1,
        started_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    session.add(earlier)
    session.add(later)
    session.commit()

    repository = DiscoveryRunRepository(session)
    recent = repository.list_recent_runs(organization.id, limit=10)

    assert [r.id for r in recent] == [later.id, earlier.id]


def test_discovery_run_repository_update_statistics(session, organization) -> None:
    session.add(organization)
    session.flush()

    search = _create_search(organization)
    session.add(search)
    session.flush()

    run = _create_run(organization, search.id)
    session.add(run)
    session.commit()

    repository = DiscoveryRunRepository(session)
    repository.update_statistics(
        run.id,
        sources_queried=4,
        companies_found=20,
        companies_created=8,
        companies_skipped=2,
    )
    session.commit()

    refreshed = repository.get(run.id)
    assert refreshed is not None
    assert refreshed.sources_queried == 4
    assert refreshed.companies_found == 20
    assert refreshed.companies_created == 8
    assert refreshed.companies_skipped == 2


def test_discovery_run_repository_complete_run(session, organization) -> None:
    session.add(organization)
    session.flush()

    search = _create_search(organization)
    session.add(search)
    session.flush()

    run = _create_run(organization, search.id)
    session.add(run)
    session.commit()

    repository = DiscoveryRunRepository(session)
    repository.complete_run(run.id, companies_found=20, companies_created=10)
    session.commit()

    refreshed = repository.get(run.id)
    assert refreshed is not None
    assert refreshed.status == "succeeded"
    assert refreshed.companies_found == 20
    assert refreshed.companies_created == 10
    assert refreshed.finished_at is not None


def test_discovery_run_repository_fail_run(session, organization) -> None:
    session.add(organization)
    session.flush()

    search = _create_search(organization)
    session.add(search)
    session.flush()

    run = _create_run(organization, search.id)
    session.add(run)
    session.commit()

    repository = DiscoveryRunRepository(session)
    repository.fail_run(run.id, error_message="Source API rate limit exhausted")
    session.commit()

    refreshed = repository.get(run.id)
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert refreshed.error_message == "Source API rate limit exhausted"
    assert refreshed.finished_at is not None


def test_discovery_run_repository_cascade_delete_runs_with_search(session, organization) -> None:
    session.add(organization)
    session.flush()

    search = _create_search(organization)
    session.add(search)
    session.flush()

    run = _create_run(organization, search.id)
    session.add(run)
    session.commit()

    run_id = run.id
    repository = DiscoveryRunRepository(session)

    repository.delete(search)
    session.commit()

    assert repository.get(run_id) is None
