from __future__ import annotations

from collections.abc import Iterator
from types import MethodType
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.agents.discovery.sources.common import DiscoveredCompany
from app.database import session as database_session
from app.models.company import Company
from app.models.discovery_run import DiscoveryRun
from app.models.discovery_search import DiscoverySearch
from app.models.organization import Organization
from app.services import AgentRunService, CompanyService, DiscoveryRunService, DiscoverySearchService
from app.workflows.context import WorkflowContext
from app.workflows.discovery_pipeline import DiscoveryPipelineWorkflow
from app.workflows.registry import WorkflowRegistry
from app.workflows.runner import WorkflowRunner
from app.workflows.states import WorkflowStatus


@pytest.fixture()
def service_session_factory(
    migrated_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> sessionmaker[Session]:
    factory = sessionmaker(
        bind=migrated_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )
    monkeypatch.setattr(database_session, "SessionLocal", factory)
    return factory


@pytest.fixture()
def service_database(service_session_factory: sessionmaker[Session]) -> Iterator[sessionmaker[Session]]:
    yield service_session_factory


@pytest.fixture()
def org_id(service_session_factory: sessionmaker[Session]) -> str:
    organization_id = str(uuid4())
    with service_session_factory() as session:
        session.add(
            Organization(
                id=organization_id,
                name="Discovery Pipeline Test Org",
                slug="discovery-pipeline-test",
                status="active",
            )
        )
        session.commit()
    return organization_id


@pytest.fixture()
def other_org_id(service_session_factory: sessionmaker[Session]) -> str:
    organization_id = str(uuid4())
    with service_session_factory() as session:
        session.add(
            Organization(
                id=organization_id,
                name="Other Discovery Pipeline Test Org",
                slug="other-discovery-pipeline-test",
                status="active",
            )
        )
        session.commit()
    return organization_id


def _criteria_payload() -> dict[str, object]:
    return {
        "industry": "fintech",
        "company_size_min": 10,
        "company_size_max": 500,
        "geography": "United States",
        "technologies": ["hubspot", "salesforce"],
        "keywords": ["Series A", "hiring engineer"],
        "exclude_domains": ["example.com"],
        "sources": ["sec_edgar", "google_news_rss", "opencorporates"],
    }


def _create_search(
    service: DiscoverySearchService,
    *,
    organization_id: str,
    name: str = "Fintech Series A",
    status: str = "active",
) -> DiscoverySearch:
    return service.create(
        organization_id=organization_id,
        name=name,
        description="Find recently funded fintech companies.",
        criteria=_criteria_payload(),
        status=status,
    )


def _seed_company(
    service: CompanyService,
    *,
    organization_id: str,
    domain: str,
    name: str = "Existing Co",
) -> Company:
    return service.create(
        organization_id=organization_id,
        name=name,
        domain=domain,
        industry="fintech",
        status="active",
    )


class _Provider:
    def __init__(self, source_name: str, results: list[DiscoveredCompany] | None = None, error: Exception | None = None) -> None:
        self.source_name = source_name
        self.results = results or []
        self.error = error

    def search(self, criteria: dict[str, object]) -> list[DiscoveredCompany]:
        if self.error is not None:
            raise self.error
        return list(self.results)


def _company(
    *,
    domain: str,
    source: str = "sec_edgar",
    confidence: float = 0.7,
    name: str = "Acme Corp",
) -> DiscoveredCompany:
    return DiscoveredCompany(
        name=name,
        domain=domain,
        website=f"https://{domain}",
        country="United States",
        city="New York",
        industry="fintech",
        source=source,
        confidence=confidence,
        metadata={"provider_id": f"{source}-1"},
    )


def _runner(*, providers: list[_Provider], **services: object) -> WorkflowRunner:
    registry = WorkflowRegistry()
    registry.register(DiscoveryPipelineWorkflow)
    return WorkflowRunner(
        registry,
        agent_run_service=services.get("agent_run_service", AgentRunService()),
        company_service=services.get("company_service", CompanyService()),
        discovery_search_service=services.get("discovery_search_service", DiscoverySearchService()),
        discovery_run_service=services.get("discovery_run_service", DiscoveryRunService()),
        discovery_sources=providers,
    )


def _context(*, org_id: str, search_id: str, placeholder_company_id: str) -> WorkflowContext:
    return WorkflowContext(
        workflow_name="discovery_pipeline",
        company_id=placeholder_company_id,
        organization_id=org_id,
        options={"discovery_search_id": search_id},
    )


@pytest.mark.asyncio
async def test_discovery_pipeline_successfully_creates_companies_and_updates_statistics(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    _seed_company(company_service, organization_id=org_id, domain="anchor.example")
    search = _create_search(search_service, organization_id=org_id)
    placeholder = _seed_company(company_service, organization_id=org_id, domain="placeholder.example", name="Placeholder")

    runner = _runner(
        providers=[_Provider("sec_edgar", [_company(domain="new.example")])],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=DiscoveryRunService(),
    )

    result = await runner.run(_context(org_id=org_id, search_id=search.id, placeholder_company_id=placeholder.id))

    assert result.status == WorkflowStatus.SUCCEEDED
    assert len(result.output_ids["companies"]) == 1
    assert result.output_ids["discovery_searches"] == [search.id]
    assert result.agent_run_ids

    with service_database() as session:
        persisted_search = session.get(DiscoverySearch, search.id)
        runs = session.query(DiscoveryRun).filter(DiscoveryRun.organization_id == org_id).all()
        companies = session.query(Company).filter(Company.organization_id == org_id).all()

    assert persisted_search is not None
    assert persisted_search.total_discovered == 1
    assert persisted_search.last_run_at is not None
    assert len(runs) == 1
    assert runs[0].status == "succeeded"
    assert runs[0].sources_queried == 1
    assert runs[0].companies_found == 1
    assert runs[0].companies_created == 1
    assert runs[0].companies_skipped == 0
    assert any(company.domain == "new.example" and company.status == "needs_review" for company in companies)


@pytest.mark.asyncio
async def test_discovery_pipeline_skips_duplicate_companies_by_domain(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    existing = _seed_company(company_service, organization_id=org_id, domain="duplicate.example")
    search = _create_search(search_service, organization_id=org_id)
    placeholder = _seed_company(company_service, organization_id=org_id, domain="placeholder.example", name="Placeholder")

    runner = _runner(
        providers=[_Provider("sec_edgar", [_company(domain="duplicate.example")])],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=DiscoveryRunService(),
    )

    result = await runner.run(_context(org_id=org_id, search_id=search.id, placeholder_company_id=placeholder.id))

    assert result.status == WorkflowStatus.SUCCEEDED
    assert result.output_ids["companies"] == []

    with service_database() as session:
        runs = session.query(DiscoveryRun).filter(DiscoveryRun.organization_id == org_id).all()
        companies = session.query(Company).filter(Company.organization_id == org_id).all()

    assert len(runs) == 1
    assert runs[0].companies_created == 0
    assert runs[0].companies_skipped == 1
    assert sum(1 for company in companies if company.domain == existing.domain) == 1


@pytest.mark.asyncio
async def test_discovery_pipeline_enforces_tenant_isolation(
    service_database: sessionmaker[Session],
    org_id: str,
    other_org_id: str,
) -> None:
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    _seed_company(company_service, organization_id=org_id, domain="anchor.example")
    other_search = _create_search(search_service, organization_id=other_org_id, name="Other Search")
    placeholder = _seed_company(company_service, organization_id=org_id, domain="placeholder.example", name="Placeholder")

    runner = _runner(
        providers=[_Provider("sec_edgar", [_company(domain="tenant.example")])],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=DiscoveryRunService(),
    )

    result = await runner.run(_context(org_id=org_id, search_id=other_search.id, placeholder_company_id=placeholder.id))

    assert result.status == WorkflowStatus.FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.workflow_error"


@pytest.mark.asyncio
async def test_discovery_pipeline_handles_partial_provider_failure(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    _seed_company(company_service, organization_id=org_id, domain="anchor.example")
    search = _create_search(search_service, organization_id=org_id)
    placeholder = _seed_company(company_service, organization_id=org_id, domain="placeholder.example", name="Placeholder")

    runner = _runner(
        providers=[
            _Provider("sec_edgar", [_company(domain="partial.example")]),
            _Provider("opencorporates", error=RuntimeError("provider down")),
        ],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=DiscoveryRunService(),
    )

    result = await runner.run(_context(org_id=org_id, search_id=search.id, placeholder_company_id=placeholder.id))

    assert result.status == WorkflowStatus.SUCCEEDED

    with service_database() as session:
        run = session.query(DiscoveryRun).filter(DiscoveryRun.organization_id == org_id).one()
        persisted_search = session.get(DiscoverySearch, search.id)

    assert run.sources_queried == 2
    assert run.companies_found == 1
    assert run.companies_created == 1
    assert run.companies_skipped == 0
    assert persisted_search is not None
    assert persisted_search.total_discovered == 1


@pytest.mark.asyncio
async def test_discovery_pipeline_succeeds_with_empty_results(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    _seed_company(company_service, organization_id=org_id, domain="anchor.example")
    search = _create_search(search_service, organization_id=org_id)
    placeholder = _seed_company(company_service, organization_id=org_id, domain="placeholder.example", name="Placeholder")

    runner = _runner(
        providers=[_Provider("sec_edgar", [])],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=DiscoveryRunService(),
    )

    result = await runner.run(_context(org_id=org_id, search_id=search.id, placeholder_company_id=placeholder.id))

    assert result.status == WorkflowStatus.SUCCEEDED
    assert result.output_ids["companies"] == []

    with service_database() as session:
        run = session.query(DiscoveryRun).filter(DiscoveryRun.organization_id == org_id).one()
        persisted_search = session.get(DiscoverySearch, search.id)

    assert run.companies_found == 0
    assert run.companies_created == 0
    assert run.companies_skipped == 0
    assert persisted_search is not None
    assert persisted_search.total_discovered == 0


@pytest.mark.asyncio
async def test_discovery_pipeline_records_failure_path(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    _seed_company(company_service, organization_id=org_id, domain="anchor.example")
    search = _create_search(search_service, organization_id=org_id)
    placeholder = _seed_company(company_service, organization_id=org_id, domain="placeholder.example", name="Placeholder")

    def _fail_create(self: CompanyService, organization_id: str, **values: object) -> Company:
        raise RuntimeError("boom")

    company_service.create = MethodType(_fail_create, company_service)

    runner = _runner(
        providers=[_Provider("sec_edgar", [_company(domain="failure.example")])],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=DiscoveryRunService(),
    )

    result = await runner.run(_context(org_id=org_id, search_id=search.id, placeholder_company_id=placeholder.id))

    assert result.status == WorkflowStatus.FAILED
    assert result.error is not None
    assert result.error["code"] == "irtiqa.workflow_error"

    with service_database() as session:
        run = session.query(DiscoveryRun).filter(DiscoveryRun.organization_id == org_id).one()
        persisted_search = session.get(DiscoverySearch, search.id)
        companies = session.query(Company).filter(Company.organization_id == org_id).all()

    assert run.status == "failed"
    assert run.error_message is not None
    assert persisted_search is not None
    assert persisted_search.total_discovered == 0
    assert all(company.domain != "failure.example" for company in companies)


@pytest.mark.asyncio
async def test_discovery_pipeline_resumes_existing_run_when_provided(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    """Verify that workflow resumes an existing run instead of creating a new one (Progress Token pattern)."""
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()
    _seed_company(company_service, organization_id=org_id, domain="anchor.example")
    search = _create_search(search_service, organization_id=org_id)
    placeholder = _seed_company(company_service, organization_id=org_id, domain="placeholder.example", name="Placeholder")

    # Pre-create a run (simulating API endpoint behavior)
    existing_run = run_service.start_run(organization_id=org_id, search_id=search.id)

    runner = _runner(
        providers=[_Provider("sec_edgar", [_company(domain="resume.example")])],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=run_service,
    )

    # Workflow context includes the existing run_id
    context = WorkflowContext(
        workflow_name="discovery_pipeline",
        company_id=placeholder.id,
        organization_id=org_id,
        options={
            "discovery_search_id": search.id,
            "discovery_run_id": existing_run.id,
        },
    )

    result = await runner.run(context)

    assert result.status == WorkflowStatus.SUCCEEDED
    assert len(result.output_ids["companies"]) == 1
    assert result.output_ids["discovery_runs"] == [existing_run.id]

    # Verify only one run exists (no duplicate creation)
    with service_database() as session:
        runs = session.query(DiscoveryRun).filter(DiscoveryRun.organization_id == org_id).all()

    assert len(runs) == 1
    assert runs[0].id == existing_run.id
    assert runs[0].status == "succeeded"


@pytest.mark.asyncio
async def test_discovery_pipeline_creates_run_when_not_provided(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    """Verify that workflow creates a run when run_id is not provided (legacy/direct invocation)."""
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()
    _seed_company(company_service, organization_id=org_id, domain="anchor.example")
    search = _create_search(search_service, organization_id=org_id)
    placeholder = _seed_company(company_service, organization_id=org_id, domain="placeholder.example", name="Placeholder")

    runner = _runner(
        providers=[_Provider("sec_edgar", [_company(domain="direct.example")])],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=run_service,
    )

    # Workflow context WITHOUT run_id (old behavior)
    context = WorkflowContext(
        workflow_name="discovery_pipeline",
        company_id=placeholder.id,
        organization_id=org_id,
        options={
            "discovery_search_id": search.id,
            # No discovery_run_id
        },
    )

    result = await runner.run(context)

    assert result.status == WorkflowStatus.SUCCEEDED
    assert len(result.output_ids["companies"]) == 1

    # Verify run was created by the workflow
    with service_database() as session:
        runs = session.query(DiscoveryRun).filter(DiscoveryRun.organization_id == org_id).all()

    assert len(runs) == 1
    assert runs[0].status == "succeeded"


@pytest.mark.asyncio
async def test_discovery_pipeline_validates_existing_run_organization_id(
    service_database: sessionmaker[Session],
    org_id: str,
    other_org_id: str,
) -> None:
    """Verify that workflow enforces tenant isolation when resuming a run."""
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()
    _seed_company(company_service, organization_id=org_id, domain="anchor.example")
    search = _create_search(search_service, organization_id=org_id)
    placeholder = _seed_company(company_service, organization_id=org_id, domain="placeholder.example", name="Placeholder")

    # Create a run in the OTHER organization
    other_search = _create_search(search_service, organization_id=other_org_id, name="Other Search")
    other_run = run_service.start_run(organization_id=other_org_id, search_id=other_search.id)

    runner = _runner(
        providers=[_Provider("sec_edgar", [_company(domain="isolated.example")])],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=run_service,
    )

    # Attempt to resume a run from another organization
    context = WorkflowContext(
        workflow_name="discovery_pipeline",
        company_id=placeholder.id,
        organization_id=org_id,
        options={
            "discovery_search_id": search.id,
            "discovery_run_id": other_run.id,  # Wrong org
        },
    )

    result = await runner.run(context)

    # Workflow should fail due to tenant isolation
    assert result.status == WorkflowStatus.FAILED
    assert result.error is not None


@pytest.mark.asyncio
async def test_discovery_pipeline_supports_organization_only_context(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    """Verify that workflow supports organization-only context without company_id or contact_id."""
    company_service = CompanyService()
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()
    search = _create_search(search_service, organization_id=org_id)

    runner = _runner(
        providers=[_Provider("sec_edgar", [_company(domain="org-only.example")])],
        company_service=company_service,
        discovery_search_service=search_service,
        discovery_run_service=run_service,
    )

    # Workflow context with ONLY organization_id (no company_id/contact_id)
    context = WorkflowContext(
        workflow_name="discovery_pipeline",
        company_id=None,
        contact_id=None,
        organization_id=org_id,
        options={
            "discovery_search_id": search.id,
        },
    )

    result = await runner.run(context)

    assert result.status == WorkflowStatus.SUCCEEDED
    assert len(result.output_ids["companies"]) == 1

    with service_database() as session:
        runs = session.query(DiscoveryRun).filter(DiscoveryRun.organization_id == org_id).all()

    assert len(runs) == 1
    assert runs[0].status == "succeeded"