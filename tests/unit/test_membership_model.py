from __future__ import annotations

from app.models.membership import Membership


def test_membership_model_columns() -> None:
    mem = Membership(
        id="30000000-0000-0000-0000-000000000003",
        user_id="a" * 36,
        organization_id="b" * 36,
        role="owner",
    )
    assert mem.id == "30000000-0000-0000-0000-000000000003"
    assert len(mem.id) == 36
    assert mem.user_id == "a" * 36
    assert mem.organization_id == "b" * 36
    assert mem.role == "owner"


def test_membership_default_role() -> None:
    mem = Membership(
        user_id="a" * 36,
        organization_id="b" * 36,
    )
    # The default fires on INSERT, not on construction.
    assert mem.role is None


def test_membership_table_name() -> None:
    assert Membership.__tablename__ == "memberships"


def test_membership_indexes() -> None:
    table = Membership.__table__
    index_names = {idx.name for idx in table.indexes}
    assert "ix_memberships_user_org" in index_names
    assert "ix_memberships_user_id" in index_names
    assert "ix_memberships_organization_id" in index_names
