from __future__ import annotations

import pytest

from app.core.errors import PermissionError
from app.core.tenant import ROLE_LEVELS, TenantContext, require_role


class TestTenantContext:
    def test_creation(self) -> None:
        ctx = TenantContext(organization_id="org-123", user_id="user-456", role="admin")
        assert ctx.organization_id == "org-123"
        assert ctx.user_id == "user-456"
        assert ctx.role == "admin"
        assert ctx.is_api_key is False

    def test_defaults(self) -> None:
        ctx = TenantContext(organization_id="org-789")
        assert ctx.organization_id == "org-789"
        assert ctx.user_id is None
        assert ctx.role == "viewer"
        assert ctx.is_api_key is False

    def test_frozen(self) -> None:
        ctx = TenantContext(organization_id="org-111")
        with pytest.raises(AttributeError):
            ctx.organization_id = "org-222"  # type: ignore[misc]


class TestRoleLevels:
    def test_hierarchy(self) -> None:
        assert ROLE_LEVELS["viewer"] == 10
        assert ROLE_LEVELS["member"] == 50
        assert ROLE_LEVELS["admin"] == 80
        assert ROLE_LEVELS["owner"] == 100

    def test_viewer_lt_member(self) -> None:
        assert ROLE_LEVELS["viewer"] < ROLE_LEVELS["member"]

    def test_member_lt_admin(self) -> None:
        assert ROLE_LEVELS["member"] < ROLE_LEVELS["admin"]

    def test_admin_lt_owner(self) -> None:
        assert ROLE_LEVELS["admin"] < ROLE_LEVELS["owner"]


class TestRequireRole:
    def test_sufficient_role_passes(self) -> None:
        require_role("viewer", "owner")  # no error
        require_role("member", "admin")  # no error
        require_role("admin", "owner")   # no error
        require_role("viewer", "viewer") # no error

    def test_insufficient_role_fails(self) -> None:
        with pytest.raises(PermissionError) as exc:
            require_role("admin", "member")
        assert "irtiqa.forbidden" in str(exc.value)

    def test_unknown_role_treated_as_zero(self) -> None:
        with pytest.raises(PermissionError):
            require_role("admin", "nonexistent")

    def test_unknown_minimum_is_lenient(self) -> None:
        require_role("god", "owner")  # unknown minimum = no restriction
