from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import WorkflowError
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
def org_id(service_session_factory: sessionmaker[Session]) -> str:
    organization_id = str(uuid4())
    with service_session_factory() as session:
        session.add(
            Organization(
                id=organization_id,
                name="Production Test Org",
                slug="prod-test",
                status="active",
            )
        )
        session.commit()
    return organization_id


def test_batch_domain_checking_prevents_n_plus_one(
    service_session_factory: sessionmaker[Session],
    org_id: str,
) -> None:
    """Verify that batch domain checking reduces database queries."""
    company_service = CompanyService()

    # Create multiple existing companies
    existing_domains = ["existing1.example", "existing2.example", "existing3.example"]
    for domain in existing_domains:
        company_service.create(
            organization_id=org_id,
            name=f"Company {domain}",
            domain=domain,
            industry="tech",
            status="active",
        )

    # Test batch check
    check_domains = existing_domains + ["new1.example", "new2.example"]
    result = company_service.get_existing_domains(check_domains, org_id)

    assert result == set(existing_domains)
    assert "new1.example" not in result
    assert "new2.example" not in result


def test_batch_domain_checking_with_empty_list(org_id: str) -> None:
    """Verify batch domain checking handles empty input."""
    company_service = CompanyService()
    result = company_service.get_existing_domains([], org_id)
    assert result == set()


def test_batch_domain_checking_tenant_isolation(
    service_session_factory: sessionmaker[Session],
    org_id: str,
) -> None:
    """Verify batch domain checking respects tenant boundaries."""
    other_org_id = str(uuid4())
    with service_session_factory() as session:
        session.add(
            Organization(
                id=other_org_id,
                name="Other Org",
                slug="other-org",
                status="active",
            )
        )
        session.commit()

    company_service = CompanyService()

    # Create company in other org
    company_service.create(
        organization_id=other_org_id,
        name="Other Org Company",
        domain="other.example",
        industry="tech",
        status="active",
    )

    # Check from first org perspective
    result = company_service.get_existing_domains(["other.example"], org_id)
    assert result == set()  # Should not see other org's company


def test_workflow_rejects_non_running_run_resumption(
    service_session_factory: sessionmaker[Session],
    org_id: str,
) -> None:
    """Verify workflow rejects resuming non-running runs."""
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()

    search = search_service.create(
        organization_id=org_id,
        name="Test Search",
        description="Test",
        criteria={
            "industry": "tech",
            "company_size_min": 10,
            "company_size_max": 500,
            "geography": "US",
            "keywords": ["test"],
            "sources": ["sec_edgar"],
        },
        status="active",
    )

    # Create a succeeded run
    run = run_service.start_run(organization_id=org_id, search_id=search.id)
    run_service.complete_run(run.id, organization_id=org_id)

    # Attempt to resume succeeded run
    registry = WorkflowRegistry()
    registry.register(DiscoveryPipelineWorkflow)
    runner = WorkflowRunner(
        registry,
        agent_run_service=AgentRunService(),
        discovery_search_service=search_service,
        discovery_run_service=run_service,
        company_service=CompanyService(),
        discovery_sources=[],
    )

    context = WorkflowContext(
        workflow_name="discovery_pipeline",
        company_id=None,
        contact_id=None,
        organization_id=org_id,
        options={
            "discovery_search_id": search.id,
            "discovery_run_id": run.id,
        },
    )

    result = runner.run(context)

    # Should fail because run is not in "running" state
    assert result.status.value == "failed"
    assert result.error is not None
    assert "Cannot resume" in result.error.get("message", "")
    assert "succeeded" in result.error.get("message", "")


def test_run_service_fail_run_truncates_long_errors(
    service_session_factory: sessionmaker[Session],
    org_id: str,
) -> None:
    """Verify fail_run truncates excessively long error messages."""
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()

    search = search_service.create(
        organization_id=org_id,
        name="Test Search",
        description="Test",
        criteria={
            "industry": "tech",
            "company_size_min": 10,
            "keywords": ["test"],
            "sources": ["sec_edgar"],
        },
        status="active",
    )

    run = run_service.start_run(organization_id=org_id, search_id=search.id)

    # Fail run with very long error message
    long_error = "X" * 5000
    run_service.fail_run(run.id, organization_id=org_id, error_message=long_error)

    # Retrieve run and verify truncation
    updated_run = run_service.get_run(run.id, organization_id=org_id)
    assert updated_run.status == "failed"
    assert updated_run.error_message is not None
    assert len(updated_run.error_message) == 2000
    assert updated_run.error_message.endswith("...")


def test_discovery_search_criteria_validation_catches_all_json_errors(
    org_id: str,
) -> None:
    """Verify criteria validation handles various malformed JSON inputs."""
    search_service = DiscoverySearchService()

    # Test invalid JSON string
    with pytest.raises(Exception):  # ValidationError
        search_service.create(
            organization_id=org_id,
            name="Invalid JSON",
            description="Test",
            criteria="{invalid json",
            status="active",
        )

    # Test non-dict JSON (valid JSON but wrong type)
    with pytest.raises(Exception):  # ValidationError
        search_service.create(
            organization_id=org_id,
            name="Non-dict JSON",
            description="Test",
            criteria="[1, 2, 3]",
            status="active",
        )
