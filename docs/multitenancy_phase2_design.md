> **Status: IMPLEMENTED**

# Multi-Tenancy Phase 2: Tenant Isolation & Auth Integration

## 1. Phase 1 Completed Summary

Phase 1 delivered the structural foundation:

| Component | Status | Files |
|---|---|---|
| `organizations` table + model | ✅ | `app/models/organization.py` |
| `memberships` table + model | ✅ | `app/models/membership.py` |
| `OrganizationService` | ✅ | `create_with_owner()`, CRUD, slug generation |
| `MembershipService` | ✅ | Owner protection, role management, transfer |
| Organization API endpoints | ✅ | CRUD + member management + ownership transfer |
| Migration | ✅ | `20260613_0006` — both tables with indexes, FKs, constraints |
| Unit tests | ✅ | 36 tests covering models, services, owner protection |
| Integration tests | ✅ | 10 tests covering API auth enforcement and permissions |

**Phase 1 gap that Phase 2 must solve:** Organizations exist but the auth system has no awareness of them. JWT tokens carry no `org` or `role` claims. Services don't filter by `organization_id`. Repositories don't enforce tenant scoping. `AuthService.register()` creates users without an org. `AuthService.login()` never issues org-scoped tokens.

---

## 2. Architecture Audit

### Current State vs. Phase 2 Requirements

| Requirement | Phase 1 State | Phase 2 Target |
|---|---|---|
| JWT org claims | None | JWT includes `org` and `role` |
| Login with org context | Returns user + tokens | Returns user + tokens + org + role |
| Registration with org | User only | User + Organization + Owner membership |
| `get_current_organization()` | Does not exist | FastAPI dependency verifying membership |
| `require_role()` helper | Does not exist | Service-layer permission check |
| TenantContext | Does not exist | Frozen dataclass carried through request lifecycle |
| `BaseRepository._apply_tenant_filter()` | Does not exist | Automatic `WHERE organization_id = :org_id` |
| Existing service tenant scoping | Not scoped | Services accept `organization_id` parameter |
| Existing endpoint tenant scoping | Not scoped | Endpoints use `get_current_organization()` |
| Agent/Workflow org context | Contexts lack org_id | `organization_id` added to both contexts |
| `User.memberships` relationship | Not on User model | Added to enable user → org navigation |
| `POST /organizations` behavior | Creates org + owner membership | Unchanged (already correct) |
| `POST /auth/register` behavior | User only | User + Organization + Owner membership |

### Auth Flow After Phase 2

```text
POST /auth/register
  → Create user (is_active=False)
  → Create email verification token
  → **NEW: Create default organization**
  → **NEW: Create owner membership**
  → Return user + verification token

POST /auth/login
  → Verify email, password, rate limit
  → **NEW: Look up user's memberships**
  → **NEW: Include org_id and role in JWT claims**
  → Return tokens + user + org info

GET /auth/me
  → **NEW: Return current org and role**
```

---

## 3. TenantContext

### Definition

`TenantContext` is a frozen dataclass that carries the current organization's identity through the entire request lifecycle. It is created by `get_current_organization()` after verifying the caller's membership.

```python
# app/core/tenant.py (NEW)

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class TenantContext:
    """Immutable tenant context for the current request.

    Created by ``get_current_organization()`` after verifying the
    caller's membership in the target organization.
    """

    organization_id: str
    user_id: str | None  # None for API key auth
    role: str             # owner, admin, member, viewer
    is_api_key: bool      # True when authenticated via API key
```

### Lifecycle

```text
Request → HTTPBearer → get_current_user() → user dict
         → get_current_organization(required_org_id?) → TenantContext
         → Route handler receives TenantContext via Depends
         → Services receive organization_id from TenantContext
         → Repositories filter by organization_id
```

---

## 4. Tenant Filtering Strategy

### 4.1 BaseRepository Enforcement

A new method `_apply_tenant_filter()` is added to `BaseRepository`. All repository query methods that operate on tenant-scoped models automatically include `WHERE organization_id = :org_id`.

```python
# app/repositories/base.py

class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def _apply_tenant_filter(
        self,
        statement: Select,
        organization_id: str | None = None,
    ) -> Select:
        """Add organization_id = :org_id to the WHERE clause.

        Only applies when the model has an ``organization_id`` column.
        If ``organization_id`` is None, no filter is added (for
        non-tenant-scoped queries such as listing all organizations
        a user belongs to).
        """
        if organization_id is not None and hasattr(self.model, "organization_id"):
            return statement.where(self.model.organization_id == organization_id)
        return statement
```

This is applied in the `list` method and other tenant-scoped query methods:

```python
def list(self, *, organization_id: str | None = None, limit=100, offset=0):
    statement = select(self.model)
    statement = self._apply_tenant_filter(statement, organization_id)
    statement = statement.offset(offset).limit(limit)
    return self.scalars(statement)
```

**Models that have `organization_id`:** All entities that belong to an organization. In Phase 2, `organization_id` is not yet on domain tables (that's Phase 3). The filtering applies to models that currently have the column — initially just `Organization` and `Membership`. When Phase 3 adds `organization_id` to `Company`, `Contact`, etc., the same `_apply_tenant_filter` method protects them automatically.

### 4.2 No Query Interceptors or Middleware

The design uses **explicit parameter passing**, not SQLAlchemy event listeners or middleware-based query interception. Rationale (unchanged from v2 design):

1. Explicit — every query visibly includes `organization_id`.
2. Testable — no magic behavior to mock or verify.
3. Maintainable — adding a new query doesn't require configuring a filter system.

### 4.3 Audit Logging for Missing Filters

A warning is logged when a tenant-scoped model is queried without an `organization_id` filter:

```python
def _check_tenant_filter(self, statement, organization_id):
    if organization_id is None and hasattr(self.model, "organization_id"):
        self.logger.warning(
            "Tenant-scoped query without organization_id filter",
            extra={"model": self.model.__name__},
        )
```

---

## 5. JWT Org/Role Claims

### 5.1 Token Payload Changes

The JWT payload gains `org` and `role` claims when the user has an active organization:

```python
# Before (current):
{
    "sub": "user-uuid",
    "type": "access",
    "iss": "irtiqa-api",
    "aud": "irtiqa-client",
    "kid": "key-v1"
}

# After (Phase 2):
{
    "sub": "user-uuid",
    "org": "organization-uuid",     # NEW: current organization
    "role": "admin",                # NEW: role in current org
    "type": "access",
    "iss": "irtiqa-api",
    "aud": "irtiqa-client",
    "kid": "key-v1"
}
```

### 5.2 Login Flow Changes

`AuthService.login()` is extended to:

1. After successful password verification, look up the user's memberships.
2. If the user has at least one membership, use the first organization as the default context (or the most recently used, tracked via a `current_organization_id` preference on the user).
3. Include `org` and `role` in the JWT claims.
4. Return the org context alongside the tokens.

```python
# Modified AuthService.login()
def login(self, email: str, password: str, ip_address: str):
    # ... existing verification ...
    
    # NEW: Look up default org
    memberships = membership_service.list_user_memberships(user.id)
    if not memberships:
        # User has no org (should not happen after Phase 2 registration)
        # Return token without org claims
        access_token = create_access_token(user_id=user.id)
    else:
        default_membership = memberships[0]
        access_token = create_access_token(
            user_id=user.id,
            organization_id=default_membership.organization_id,
            role=default_membership.role,
        )
    
    # ... existing refresh token logic ...
```

### 5.3 Registration Flow Changes

`AuthService.register()` is extended to:

1. Create the user (existing behavior).
2. Create a default organization named after the user's display name (with slug collision resolution).
3. Create an owner membership for the new user in the new org.
4. All within a single transaction.

```python
# Modified AuthService.register()
def register(self, email: str, password: str, display_name: str):
    # ... existing user creation ...
    
    # NEW: Create org + owner membership
    org = Organization(
        name=f"{display_name}'s Organization",
        slug=generate_unique_slug(slugify(f"{display_name}'s Organization"), session),
        status="active",
    )
    session.add(org)
    session.flush()
    
    membership = Membership(
        user_id=user.id,
        organization_id=org.id,
        role="owner",
    )
    session.add(membership)
    session.flush()
```

### 5.4 get_current_organization() Dependency

A new FastAPI dependency that:
1. Extracts the `org` claim from the JWT (via `get_current_user` → token decode).
2. Verifies the user is still a member of that org via a database membership lookup.
3. Returns a `TenantContext` with `organization_id`, `user_id`, `role`.
4. Raises `403 Forbidden` if membership is no longer valid.

```python
# app/api/dependencies.py

def get_current_organization(
    current_user: dict = Depends(get_current_user),
    membership_service: MembershipService = Depends(get_membership_service),
) -> TenantContext:
    """Verify the caller's membership and return a TenantContext.
    
    The organization ID comes from the JWT's ``org`` claim, which is set
    at login time.  On every request, a membership lookup is performed
    to verify the user is still a member of that org.
    """
    # Extract org from JWT (requires decoding the token — already done
    # in get_current_user, but we need the raw payload)
    # For Phase 2, the org is passed separately: either from a header
    # or from the JWT's org claim.
    #
    # Implementation: re-decode the JWT to get the org and role claims,
    # then verify membership in a single query.
    pass  # See implementation section
```

The key design decision: **the org claim in the JWT is trusted for routing but verified on every request**. This means:
- The JWT identifies which org the token was issued for.
- `get_current_organization()` performs a `memberships` lookup to confirm the user is still a member.
- If the membership was revoked, the token is rejected even if unexpired.
- This is the F-1 fix from the v2 audit: never trust the JWT claim alone.

---

## 6. require_role() Helper

### Definition

```python
# app/core/tenant.py

ROLE_LEVELS = {
    "viewer": 10,
    "member": 50,
    "admin": 80,
    "owner": 100,
}


def require_role(minimum_role: str, actual_role: str, action: str = "") -> None:
    """Raise PermissionError if the caller's role is below the minimum."""
    if ROLE_LEVELS.get(actual_role, 0) < ROLE_LEVELS.get(minimum_role, 0):
        raise PermissionError(
            f"Insufficient permissions. Requires {minimum_role}, "
            f"has {actual_role}. {action}".strip(),
        )
```

### Usage Pattern

```python
class CompanyService(BaseService[Company, CompanyRepository]):
    def create(self, organization_id: str, role: str, **values):
        require_role("member", role, "create companies")
        return super().create(organization_id=organization_id, **values)
    
    def delete(self, entity_id: str, role: str):
        require_role("admin", role, "delete companies")
        return super().delete(entity_id)
```

In endpoints, `require_role` is called with the role from `TenantContext`:

```python
@router.post("/companies", response_model=CompanyRead)
def create_company(
    payload: CompanyCreate,
    tenant: TenantContext = Depends(get_current_organization),
    service: CompanyService = Depends(get_company_service),
):
    require_role("member", tenant.role, "create companies")
    return service.create(organization_id=tenant.organization_id, **payload.model_dump())
```

---

## 7. User.memberships Relationship

The `User` model gains a `memberships` relationship to enable navigation from user → memberships → organizations.

```python
# app/models/user.py — modified

class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    # ... existing columns ...
    
    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
```

The `Membership.user` relationship, which currently lacks `back_populates`, is updated:

```python
# app/models/membership.py — modified

class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    # ... existing columns ...
    
    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship(back_populates="memberships")
```

---

## 8. AuthService Changes

### 8.1 Registration

`AuthService.register()` gains org + membership creation:

| Step | Current | Phase 2 |
|---|---|---|
| Create user | ✅ | ✅ (unchanged) |
| Create email verification token | ✅ | ✅ (unchanged) |
| Create organization | ❌ | ✅ New step |
| Create owner membership | ❌ | ✅ New step |
| Transaction | Single user | Atomic user + org + membership |

The `RegisterRequest` schema remains unchanged — the org is auto-generated from the user's display name. No new API fields are needed.

### 8.2 Login

`AuthService.login()` gains org context:

| Step | Current | Phase 2 |
|---|---|---|
| Rate limit check | ✅ | ✅ |
| Verify email | ✅ | ✅ |
| Verify password | ✅ | ✅ |
| Look up memberships | ❌ | ✅ New step |
| Issue JWT with `org`/`role` claims | ❌ | ✅ New step |
| Return org context | ❌ | ✅ New field in response |

### 8.3 get_current_organization() Implementation

```python
def get_current_organization(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    membership_service: MembershipService = Depends(get_membership_service),
) -> TenantContext:
    """Authenticate the user and verify membership in the org specified
    in the JWT claims.

    Performs a membership lookup on every request.
    """
    # Authenticate via existing dependency
    user = get_current_user(authorization=authorization, auth_service=auth_service)
    user_id = user["id"]
    
    # Decode the JWT to extract org/role claims
    token = authorization.removeprefix("Bearer ")
    payload = decode_access_token(token)
    org_id = payload.get("org")
    jwt_role = payload.get("role")
    
    if org_id is None:
        # User has no org context — raise 403
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No organization context. Please authenticate with an organization.",
        )
    
    # Verify membership (F-1 fix: never trust JWT alone)
    membership = membership_service.get_membership(user_id, org_id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization.",
        )
    
    return TenantContext(
        organization_id=org_id,
        user_id=user_id,
        role=membership.role,
        is_api_key=False,
    )
```

---

## 9. Existing Service Integration

### 9.1 Pattern for Tenant-Scoped Services

Existing services (CompanyService, ContactService, etc.) need new methods that accept `organization_id`. The existing methods (without org_id) are retained for backward compatibility until Phase 3 adds the organization_id column to domain tables.

```python
# Example — CompanyService adds tenant-scoped methods:
class CompanyService(BaseService[Company, CompanyRepository]):
    
    # NEW: Tenant-scoped list
    def list_by_organization(
        self,
        organization_id: str,
        role: str,
        *,
        limit=100,
        offset=0,
    ):
        require_role("viewer", role, "list companies")
        def operation(session):
            return self._repository(session).list(
                organization_id=organization_id,
                limit=limit,
                offset=offset,
            )
        return self._run_in_transaction("list_by_organization", operation)
```

This pattern is applied to every existing service. In Phase 2, only the `OrganizationService` and `MembershipService` gain tenant-scoped methods (they already have `organization_id`). All other services gain tenant-scoped methods in Phase 3 when the `organization_id` column is added.

### 9.2 Services That Stay Unchanged in Phase 2

| Service | Reason |
|---|---|
| `CompanyService` | No `organization_id` column yet (Phase 3) |
| `ContactService` | Same |
| `WebsiteService` | Same |
| `TechnologyService` | Same |
| `IntentSignalService` | Same |
| `IntelligenceScoreService` | Same |
| `OutreachMessageService` | Same |
| `AgentRunService` | Same |
| `JobService` | Same |

These services are **not modified** in Phase 2. They will receive tenant-scoped methods in Phase 3 when their tables gain `organization_id`.

---

## 10. API Surface Changes

### 10.1 Modified Endpoints

| Endpoint | Change |
|---|---|
| `POST /auth/register` | Response includes `organization` info |
| `POST /auth/login` | Response includes `organization` and `role` |
| `GET /auth/me` | Response includes `current_organization` |
| Organization endpoints | Now use `get_current_organization()` internally |

### 10.2 New Endpoint (Optional)

| Method | Path | Purpose |
|---|---|---|
| `POST /auth/switch-organization` | Switch current org | Issue new JWT with different org + role claims |

The switch-organization endpoint verifies membership in the target org, then issues a new JWT with updated `org` and `role` claims. The old JWT remains valid until expiry but targets the old org. This is the explicit org-switching mechanism (replacing any implicit `X-Organization-Id` header approach).

### 10.3 Response Schema Changes

```python
# LoginResponse gains org field:
class LoginResponse(IrtiqaSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    organization: OrganizationSummary | None  # NEW

# OrganizationSummary — lightweight org info for auth responses:
class OrganizationSummary(IrtiqaSchema):
    id: str
    name: str
    slug: str
    role: str  # caller's role in this org
```

---

## 11. Migration Plan

No new schema migrations are required in Phase 2. Phase 2 is entirely code-level:

| Change | File | Migration Needed |
|---|---|---|
| `TenantContext` + `require_role()` | `app/core/tenant.py` (new) | None |
| `BaseRepository._apply_tenant_filter()` | `app/repositories/base.py` | None |
| `get_current_organization()` | `app/api/dependencies.py` | None |
| JWT org/role claims in `login()` | `app/services/auth_service.py` | None |
| Org creation in `register()` | `app/services/auth_service.py` | None |
| `User.memberships` relationship | `app/models/user.py` | None (FK already exists) |
| `Membership.user` back_populates | `app/models/membership.py` | None |
| Schema response changes | `app/schemas/auth.py` | None |

**No new tables. No new columns. No Alembic revision.** Phase 2 is entirely application-layer changes.

---

## 12. Testing Strategy

### 12.1 Unit Tests

| Test | What It Verifies |
|---|---|
| `test_tenant_context_creation` | TenantContext frozen dataclass fields |
| `test_require_role_passes` | Sufficient role passes |
| `test_require_role_fails` | Insufficient role raises |
| `test_require_role_edge_cases` | Viewer (10) < Member (50) < Admin (80) < Owner (100) |
| `test_apply_tenant_filter_adds_clause` | WHERE clause added for models with org_id |
| `test_apply_tenant_filter_skips` | No WHERE for models without org_id |
| `test_jwt_with_org_claims` | Token contains `org` and `role` |
| `test_jwt_without_org_claims` | Token without org is valid (no-org fallback) |

### 12.2 Service Tests

| Test | What It Verifies |
|---|---|
| `test_register_creates_org_and_membership` | New user gets org + owner membership |
| `test_login_returns_org_context` | Login response includes org and role |
| `test_login_no_org_fallback` | User without memberships gets token without org |
| `test_login_returns_current_role` | Role in JWT matches membership role |
| `test_get_current_organization_valid` | Member gets TenantContext |
| `test_get_current_organization_revoked` | Revoked membership returns 403 |
| `test_get_current_organization_no_org` | Token without org returns 403 |
| `test_get_current_organization_tampered` | Forged org_id returns 403 |

### 12.3 Integration Tests

| Test | What It Verifies |
|---|---|
| `test_register_creates_org` | POST /auth/register response includes org |
| `test_login_with_org` | POST /auth/login returns org + role in JWT |
| `test_authenticated_org_scoped_request` | GET /companies with org context works |
| `test_cross_tenant_access_blocked` | Different org returns 403 |

### 12.4 Test Count Estimate

Approximately 15 unit tests + 8 integration tests = **23 new tests**.

---

## 13. Implementation Phases

```text
Phase 2a: Infrastructure
  1. Create app/core/tenant.py (TenantContext, require_role)
  2. Add _apply_tenant_filter() to BaseRepository
  3. Add get_current_organization() to dependencies
  Tests: ~8 new

Phase 2b: Auth Integration
  4. Modify AuthService.register() to create org + membership
  5. Modify AuthService.login() to return org context
  6. Update LoginResponse schema with org info
  7. Add POST /auth/switch-organization (optional)
  Tests: ~10 new

Phase 2c: User Model Relationship
  8. Add memberships relationship to User model
  9. Update Membership.user back_populates
  Tests: ~5 new
```

---

## 14. Risks

### Risk 1: Registration Flow Change

Adding org + membership creation to `AuthService.register()` changes the API contract. The response gains an `organization` field. Existing clients that call `/auth/register` will still work — the new field is additive. Failures during org creation (e.g., slug collision) will roll back the entire transaction including the user creation.

**Mitigation**: Wrap user + org + membership creation in a single `_run_in_transaction()`. Rollback on any failure.

### Risk 2: get_current_organization() Performs Two Token Decodes

The current `get_current_user()` dependency decodes the JWT to extract the `sub` claim. `get_current_organization()` would need to decode it again to extract the `org` and `role` claims. This is two `RS256` verifications per authenticated request.

**Mitigation**: `get_current_user()` can be refactored to return the decoded JWT payload alongside the user data, avoiding a second decode. The refactoring is internal — the `get_current_user()` return type remains `dict`.

### Risk 3: Membership Revocation Detection Delay

If an admin removes a user's membership, the user's JWT still contains the old `org` and `role` claims until the token expires (up to 15 minutes). During this window, the user could access data of the org they were removed from.

**Mitigation**: `get_current_organization()` performs a database membership lookup on every request. If the membership was deleted, the lookup returns `None` and the request is rejected with 403 — regardless of what the JWT claims say. This is the F-1 fix from the v2 audit.

### Risk 4: User Without Any Organization

After Phase 2, every registered user has at least one organization (created during registration). But Phase 1 users who registered before this change exist without any organization. These users can still log in but cannot access any tenant-scoped endpoints.

**Mitigation**: Phase 1 users are edge cases in a development environment. A one-time migration script can create default organizations for existing users. The `login()` flow handles the no-org case gracefully by issuing a JWT without `org` claims.

---

## 15. Files Expected to Be Modified

| File | Change |
|---|---|
| `app/core/tenant.py` | **Create** — `TenantContext`, `require_role()`, `ROLE_LEVELS` |
| `app/repositories/base.py` | Add `_apply_tenant_filter()` and `_check_tenant_filter()` |
| `app/api/dependencies.py` | Add `get_current_organization()` dependency |
| `app/services/auth_service.py` | Modify `register()` to create org + membership. Modify `login()` to include org context. |
| `app/models/user.py` | Add `memberships` relationship |
| `app/models/membership.py` | Update `user` relationship to include `back_populates="memberships"` |
| `app/schemas/auth.py` | Add `OrganizationSummary` schema. Add `organization` field to `LoginResponse`. |
| `app/api/v1/endpoints/auth.py` | Update `login` and `register` endpoint responses. |
| `app/api/v1/endpoints/organizations.py` | (Optional) Replace temporary membership-lookup with `get_current_organization()`. |
| `app/core/errors.py` | Add `PermissionError` if not already present. |
