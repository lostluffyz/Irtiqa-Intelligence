from __future__ import annotations

from sqlalchemy import inspect

from app.models.organization import Organization, generate_slug


def test_organization_model_columns() -> None:
    org = Organization(
        id="10000000-0000-0000-0000-000000000001",
        name="Test Org",
        slug="test-org",
        status="active",
    )
    assert org.id == "10000000-0000-0000-0000-000000000001"
    assert len(org.id) == 36
    assert org.name == "Test Org"
    assert org.slug == "test-org"
    assert org.status == "active"


def test_organization_default_status() -> None:
    org = Organization(name="Default", slug="default")
    # The Python-side mapped_column default fires on INSERT, not on
    # instance construction. When persisted with a session, status
    # defaults to 'active' at the database level.
    assert org.status is None


def test_organization_table_name() -> None:
    assert Organization.__tablename__ == "organizations"


def test_organization_indexes() -> None:
    table = Organization.__table__
    index_names = {idx.name for idx in table.indexes}
    assert "ix_organizations_slug" in index_names
    assert "ix_organizations_status" in index_names


def test_organization_uuid_generated() -> None:
    with_inspect = inspect(Organization)
    pk = with_inspect.primary_key
    assert len(pk) == 1
    assert pk[0].name == "id"


def test_slug_generation_basic() -> None:
    assert generate_slug("My Company") == "my-company"
    assert generate_slug("  Hello   World!  ") == "hello-world"
    assert generate_slug("ABC Corp") == "abc-corp"


def test_slug_generation_empty_input() -> None:
    assert generate_slug("") == "org"
    assert generate_slug("   ") == "org"


def test_slug_generation_special_chars() -> None:
    assert generate_slug("My Company, Inc.") == "my-company-inc"
    assert generate_slug("AT&T Services") == "at-t-services"
