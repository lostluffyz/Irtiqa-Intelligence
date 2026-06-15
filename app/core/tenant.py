from __future__ import annotations

from dataclasses import dataclass

from app.core.errors import PermissionError


ROLE_LEVELS: dict[str, int] = {
    "viewer": 10,
    "member": 50,
    "admin": 80,
    "owner": 100,
}


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context for the current request.

    Created by ``get_current_organization()`` after verifying the
    caller's membership in the target organization.
    """

    organization_id: str
    user_id: str | None = None  # None for API key auth
    role: str = "viewer"         # owner, admin, member, viewer
    is_api_key: bool = False     # True when authenticated via API key


def require_role(minimum_role: str, actual_role: str, action: str = "") -> None:
    """Raise ``PermissionError`` if ``actual_role`` is below ``minimum_role``."""
    min_level = ROLE_LEVELS.get(minimum_role, 0)
    actual_level = ROLE_LEVELS.get(actual_role, 0)
    if actual_level < min_level:
        raise PermissionError(
            f"Insufficient permissions. Requires {minimum_role}, "
            f"has {actual_role}. {action}".strip(),
            details={
                "required_role": minimum_role,
                "required_level": min_level,
                "actual_role": actual_role,
                "actual_level": actual_level,
            },
        )
