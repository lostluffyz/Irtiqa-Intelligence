from __future__ import annotations

import json
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import EntityNotFoundError, ValidationError
from app.database import session as database_session
from app.models.organization import Organization
from app.services import DiscoveryRunService, DiscoverySearchService


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


def _create_org(factory: sessionmaker[Session], *, slug: str) -> str:
    organization_id = str(uuid4())
    with factory() as session:
        session.add(
            Organization(
                id=organization_id,
                name=f"{slug} Organization",
                slug=slug,
                status="active",
            )
        )
        session.commit()
    return organization_id


@pytest.fixture()
def org_id(service_session_factory: sessionmaker[Session]) -> str:
    return _create_org(service_session_factory, slug="discovery-service")


@pytest.fixture()
def other_org_id(service_session_factory: sessionmaker[Session]) -> str:
    return _create_org(service_session_factory, slug="other-discovery-service")


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
):
    return service.create(
        organization_id=organization_id,
        name=name,
        description="Find recently funded fintech companies.",
        criteria=_criteria_payload(),
        status=status,
    )


def test_discovery_search_service_creates_and_lists_searches(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    service = DiscoverySearchService()

    search = _create_search(service, organization_id=org_id)
    searches = service.list(organization_id=org_id)
    active_searches = service.list_active(organization_id=org_id)

    assert search.organization_id == org_id
    assert json.loads(search.criteria)["industry"] == "fintech"
    assert [item.id for item in searches] == [search.id]
    assert [item.id for item in active_searches] == [search.id]
    assert service.count_by_organization(org_id) == 1


def test_discovery_search_service_updates_and_deletes_with_tenant_scope(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    service = DiscoverySearchService()
    search = _create_search(service, organization_id=org_id)

    updated = service.update_for_organization(
        search.id,
        organization_id=org_id,
        status="archived",
        criteria={**_criteria_payload(), "keywords": ["funding"]},
    )
    active_searches = service.list_active(organization_id=org_id)

    assert updated.status == "archived"
    assert json.loads(updated.criteria)["keywords"] == ["funding"]
    assert active_searches == []

    service.delete_for_organization(search.id, organization_id=org_id)

    with pytest.raises(EntityNotFoundError):
        service.get_for_organization(search.id, organization_id=org_id)


def test_discovery_search_service_enforces_tenant_isolation(
    service_database: sessionmaker[Session],
    org_id: str,
    other_org_id: str,
) -> None:
    service = DiscoverySearchService()
    org_search = _create_search(service, organization_id=org_id, name="Org Search")
    other_search = _create_search(service, organization_id=other_org_id, name="Other Search")

    assert [item.id for item in service.list(organization_id=org_id)] == [org_search.id]

    with pytest.raises(EntityNotFoundError):
        service.get_for_organization(other_search.id, organization_id=org_id)

    with pytest.raises(EntityNotFoundError):
        service.update_for_organization(other_search.id, organization_id=org_id, name="Leak")


def test_discovery_search_service_rejects_invalid_criteria(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    service = DiscoverySearchService()

    with pytest.raises(ValidationError):
        service.create(
            organization_id=org_id,
            name="Invalid Criteria",
            criteria={"industry": "fintech"},
        )

    with pytest.raises(ValidationError):
        service.create(
            organization_id=org_id,
            name="Invalid Status",
            criteria=_criteria_payload(),
            status="running",
        )


def test_discovery_run_service_lifecycle(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()
    search = _create_search(search_service, organization_id=org_id)

    run = run_service.start_run(organization_id=org_id, search_id=search.id)
    updated = run_service.update_statistics(
        run.id,
        organization_id=org_id,
        sources_queried=3,
        companies_found=12,
        companies_created=8,
        companies_skipped=4,
    )
    completed = run_service.complete_run(run.id, organization_id=org_id)

    assert run.status == "running"
    assert updated.sources_queried == 3
    assert completed.status == "succeeded"
    assert completed.finished_at is not None
    assert completed.error_message is None


def test_discovery_run_service_fail_run(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()
    search = _create_search(search_service, organization_id=org_id)
    run = run_service.start_run(organization_id=org_id, search_id=search.id)

    failed = run_service.fail_run(
        run.id,
        organization_id=org_id,
        error_message="All sources failed.",
    )

    assert failed.status == "failed"
    assert failed.finished_at is not None
    assert failed.error_message == "All sources failed."


def test_discovery_run_service_lists_runs_by_scope_and_status(
    service_database: sessionmaker[Session],
    org_id: str,
    other_org_id: str,
) -> None:
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()
    search = _create_search(search_service, organization_id=org_id, name="Org Search")
    other_search = _create_search(search_service, organization_id=other_org_id, name="Other Search")
    run = run_service.start_run(organization_id=org_id, search_id=search.id)
    other_run = run_service.start_run(organization_id=other_org_id, search_id=other_search.id)

    by_search = run_service.list_by_search(search.id, organization_id=org_id)
    recent = run_service.list_recent_runs(organization_id=org_id)
    by_status = run_service.list_by_status("running", organization_id=org_id)

    assert [item.id for item in by_search] == [run.id]
    assert [item.id for item in recent] == [run.id]
    assert [item.id for item in by_status] == [run.id]
    assert other_run.id not in {item.id for item in recent}


def test_discovery_run_service_enforces_tenant_isolation(
    service_database: sessionmaker[Session],
    org_id: str,
    other_org_id: str,
) -> None:
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()
    other_search = _create_search(search_service, organization_id=other_org_id)
    other_run = run_service.start_run(organization_id=other_org_id, search_id=other_search.id)

    with pytest.raises(EntityNotFoundError):
        run_service.start_run(organization_id=org_id, search_id=other_search.id)

    with pytest.raises(EntityNotFoundError):
        run_service.get_run(other_run.id, organization_id=org_id)

    with pytest.raises(EntityNotFoundError):
        run_service.list_by_search(other_search.id, organization_id=org_id)


def test_discovery_run_service_rejects_invalid_lifecycle_operations(
    service_database: sessionmaker[Session],
    org_id: str,
) -> None:
    search_service = DiscoverySearchService()
    run_service = DiscoveryRunService()
    search = _create_search(search_service, organization_id=org_id)
    archived_search = _create_search(
        search_service,
        organization_id=org_id,
        name="Archived Search",
        status="archived",
    )
    run = run_service.start_run(organization_id=org_id, search_id=search.id)

    with pytest.raises(ValidationError):
        run_service.start_run(organization_id=org_id, search_id=archived_search.id)

    with pytest.raises(ValidationError):
        run_service.update_statistics(
            run.id,
            organization_id=org_id,
            companies_found=1,
            companies_created=2,
        )

    completed = run_service.complete_run(
        run.id,
        organization_id=org_id,
        companies_found=2,
        companies_created=1,
        companies_skipped=1,
    )

    with pytest.raises(ValidationError):
        run_service.fail_run(
            completed.id,
            organization_id=org_id,
            error_message="Cannot fail completed run.",
        )
