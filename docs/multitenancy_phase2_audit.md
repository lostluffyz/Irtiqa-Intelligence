> **Status: IMPLEMENTED**

# Multi-Tenancy Phase 2: Implementation Audit

## 1. Phase 1 → Phase 2 Compatibility Check

### Phase 1 Changes That Affected the Phase 2 Plan

| Phase 1 Implementation | Phase 2 Design Assumption | Impact |
|---|---|---|
| `OrganizationService.create_with_owner()` exists | Design assumed `register()` would create org + membership manually | **Positive.** `register()` can delegate to the existing method. |
| `POST /organizations` uses `create_with_owner()` | Design assumed this was the case | **Confirmed.** No change needed. |
| `SwitchOrganizationRequest` schema exists | Design listed it as optional | **Already implemented.** Schema at `app/schemas/auth.py:61`. |
| `User.memberships` does NOT exist | Design says "add relationship" | **Still needed.** |
| `Membership.user` lacks `back_populates` | Design says "update" | **Still needed.** Has a placeholder comment noting Phase 2. |
| `LoginResponse.organization` does NOT exist | Design says "add organization field" | **Still needed.** |
| `RegisterResponse.organization` does NOT exist | Design didn't specify | **Design gap.** Design adds org to registration but doesn't mention the response schema. |
| `app/core/errors.py` has no `PermissionError` | Design references `PermissionError` | **Needs creation.** Must add an IrtiqaError subclass. |

**No blocking conflicts.** All Phase 1 code is compatible with Phase 2.

---

## 2. Required File Changes

### New Files (1)

| # | File | Purpose | Dependencies |
|---|---|---|---|
| N1 | `app/core/tenant.py` | `TenantContext` frozen dataclass, `require_role()`, `ROLE_LEVELS` | None |

### Modified Files (10)

| # | File | Required Change | Depends On | Risk |
|---|---|---|---|---|
| M1 | `app/models/user.py` | Add `memberships: Mapped[list[Membership]]` relationship | None | Low |
| M2 | `app/models/membership.py` | Update `user` relationship to `back_populates="memberships"` | M1 (same commit) | Low |
| M3 | `app/repositories/base.py` | Add `_apply_tenant_filter()` and `_check_tenant_filter()` | None | Low |
| M4 | `app/core/errors.py` | Add `PermissionError(IrtiqaError)` class | None | Low |
| M5 | `app/schemas/auth.py` | Add `OrganizationSummary` schema. Add `organization` field to `LoginResponse` and `RegisterResponse`. | None | Low |
| M6 | `app/services/auth_service.py` | `register()`: create org + owner membership atomically. `login()`: look up memberships, pass `org_id`/`role` to `create_access_token()`. | N1, M5 | Medium |
| M7 | `app/api/dependencies.py` | Add `get_current_organization()` dependency | N1, M6 | Medium |
| M8 | `app/api/v1/endpoints/auth.py` | Update login/register response serialization | M5, M6 | Low |
| M9 | `app/api/v1/endpoints/organizations.py` | Optional: replace temporary membership-lookup with `get_current_organization()` | M7 | Low |
| M10 | `app/schemas/__init__.py` | Export new schema types | M5 | Low |

### Test Files (4)

| # | File | Tests | Covers |
|---|---|---|---|
| T1 | `tests/unit/test_tenant.py` | TenantContext, require_role levels | N1 |
| T2 | `tests/unit/test_repository_tenant_filter.py` | _apply_tenant_filter behavior | M3 |
| T3 | `tests/unit/test_auth_integration.py` | register creates org, login returns org context, JWT claims | M6, M5 |
| T4 | `tests/integration/api/test_auth_multitenancy.py` | Full register+login+org-scoped flow | M6-M8 |

---

## 3. Dependency Graph

```text
Phase 2a (Infrastructure) — all independent:
  ├── M1: user.py                      ← no deps
  ├── M2: membership.py                ← M1 (same commit recommended)
  ├── M3: base.py                      ← no deps
  ├── M4: errors.py                    ← no deps
  ├── N1: tenant.py                    ← no deps
  └── T1, T2: unit tests              ← above code changes

Phase 2b (Auth Integration):
  ├── M5: schemas/auth.py              ← no code deps (standalone schema types)
  ├── M6: auth_service.py              ← N1 (TenantContext not needed — uses OrganizationService)
  ├── M7: dependencies.py              ← N1 (TenantContext return type)
  ├── M8: endpoints/auth.py            ← M5, M6
  ├── M9: endpoints/organizations.py   ← M7 (optional)
  ├── M10: schemas/__init__.py         ← M5
  └── T3, T4: tests                   ← all above
```

Safe parallel workstreams:
- `N1` + `M1` + `M2` + `M3` + `M4` can all be done in any order.
- `M6` depends on `OrganizationService.create_with_owner()` (already exists from Phase 1).
- `M7` depends on `N1` and `M6`.

---

## 4. Risks

### Risk 1: get_current_organization() Cannot Access JWT Claims from get_current_user()

**Severity: High**

`get_current_user()` calls `auth_service.authenticate_with_token(token)` which decodes the JWT to extract `sub` and verify the user. The decoded payload (containing `org` and `role` claims) is discarded. `get_current_organization()` needs those claims but has no access to them.

**Options:**

| Option | Complexity | Performance | Effort |
|---|---|---|---|
| A: Decode JWT twice | Low | ~1ms extra per request | Minimal |
| B: Return payload from `get_current_user()` | Medium | Best | Refactor all callers |
| C: Pass raw token header to `get_current_organization()` | Low | One decode | Slight duplication |

**Recommendation:** Option A. Two RS256 verifications per authenticated request cost ~1ms total. Option B affects 30+ callers. Option C duplicates token extraction logic.

### Risk 2: AuthService.register() Transaction Nesting

**Severity: Medium**

If `register()` calls `OrganizationService.create_with_owner()`, which already calls `_run_in_transaction()`, the inner session_scope creates a nested transaction. The outer `register()` transaction may not see the inner session's changes.

**Fix:** Do NOT delegate to `OrganizationService.create_with_owner()` from within `register()`. Instead, use `OrganizationRepository` and `MembershipRepository` directly inside `register()`'s existing `_run_in_transaction()` block, following the same pattern used by `create_with_owner()` but operating within `register()`'s transaction.

### Risk 3: PermissionError Type Doesn't Exist

**Severity: Low**

The design references `PermissionError` but this class doesn't exist in `app/core/errors.py`. Python has a built-in `PermissionError` (for filesystem), but the project uses `IrtiqaError` subclasses.

**Fix:** Add `class PermissionError(IrtiqaError)` with `default_code = "irtiqa.forbidden"` to `app/core/errors.py`. The existing error handler in `app/api/errors.py` maps `IrtiqaError` to HTTP status based on the type — a new mapping entry is needed for `PermissionError` → 403.

### Risk 4: get_current_organization() Location

**Severity: Low**

The design places `get_current_organization()` in `app/api/dependencies.py`. This function calls `get_current_user()` which uses `Depends(bearer_scheme)` and `Depends(get_auth_service)`. Placing it in the same file as the other dependencies is correct — FastAPI supports referencing `Depends()` within the same module.

### Risk 5: RegisterResponse Doesn't Include Organization

**Severity: Medium**

The design adds org creation to `AuthService.register()` but doesn't specify updating `RegisterResponse` to include the new org. Without this change, the client receives no org context in the registration response, requiring an additional API call to discover the org.

**Fix:** Add `organization: OrganizationSummary | None = None` to `RegisterResponse`.

### Risk 6: Existing PermissionMatrix Tests Are Broken After Phase 1

**Severity: Informational**

The integration test `test_organizations.py::test_update_organization_forbidden_for_member` tries to demote the owner to member and then test that the member can't update. With `create_with_owner()` in effect, the creator is already the owner — demoting the owner fails due to last-owner protection. This test is already enabled and may fail.

**Verification needed:** Check if this test passes in the current suite. If it's already fixed, no action needed.

---

## 5. Migration Plan

| Step | Change | Migration Required |
|---|---|---|
| 1 | `tenant.py`, `PermissionError`, `_apply_tenant_filter()` | **None** — pure Python |
| 2 | `User.memberships` + `Membership.user` back_populates | **None** — FK already exists |
| 3 | Response schemas | **None** — additive fields |
| 4 | `AuthService.register()` creates org + membership | **None** — same DB tables |
| 5 | `AuthService.login()` returns org context | **None** — same tokens, new claims |

**No new database migrations required.** Phase 2 is entirely application-layer changes.

---

## 6. Implementation Order

```text
Branch: feature/multi-tenancy-phase2

Commit 1: Infrastructure (Phase 2a)
  ├── app/core/tenant.py                 — new file
  ├── app/core/errors.py                 — add PermissionError
  ├── app/repositories/base.py           — add _apply_tenant_filter
  ├── app/models/user.py                 — add memberships relationship
  ├── app/models/membership.py           — add user back_populates
  └── tests/unit/test_tenant.py
  └── tests/unit/test_repository_tenant_filter.py
  └── python -m pytest (existing tests must pass)

Commit 2: Auth Integration (Phase 2b)
  ├── app/schemas/auth.py                — OrganizationSummary, update responses
  ├── app/services/auth_service.py       — register creates org, login returns org
  ├── app/api/dependencies.py            — get_current_organization
  ├── app/api/v1/endpoints/auth.py       — update login/register serialization
  └── tests/unit/test_auth_integration.py
  └── tests/integration/api/test_auth_multitenancy.py
  └── python -m pytest (421 must pass)

Commit 3: Optional Refactoring
  ├── app/api/v1/endpoints/organizations.py — use get_current_organization
  └── python -m pytest
```

---

## 7. Summary

| Metric | Count |
|---|---|
| New files | 1 |
| Modified files | 10 |
| New test files | 4 |
| New tests | ~15 |
| Design gaps found | 2 (RegisterResponse, nested transaction) |
| Implementation risks | 3 (JWT decode, PermissionError type, transaction nesting) |
| Phase 1 → Phase 2 conflicts | **0** |
| **Implementation readiness** | **Ready** (with noted fixes) |
