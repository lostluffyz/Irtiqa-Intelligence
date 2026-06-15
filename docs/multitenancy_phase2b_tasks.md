# Multi-Tenancy Phase 2b: Auth Integration — Implementation Tasks

## Background

Phase 2a completed the infrastructure layer (TenantContext, require_role, PermissionError, BaseRepository tenant filtering, User/Membership relationships). Phase 2b integrates the auth system with organizations.

### Audit Resolutions

| Audit Finding | Resolution |
|---|---|
| JWT `org`/`role` claims not accessible from `get_current_user()` | `get_current_organization()` accepts the raw `Authorization` header via `Header(default=None)` and decodes the JWT a second time (Option A — two decodes per request, ~1ms overhead). |
| `RegisterResponse` missing `organization` field | Add `organization: OrganizationSummary \| None = None` field. |
| Transaction nesting risk in `register()` | `register()` uses `OrganizationRepository` and `MembershipRepository` directly within its own `_run_in_transaction()` block — does NOT call `OrganizationService.create_with_owner()`. |
| `PermissionError` type | Already implemented in Phase 2a. |

### Completed in Phase 2a (Not Modified Here)

- `app/core/tenant.py` — TenantContext, require_role, ROLE_LEVELS
- `app/core/errors.py` — PermissionError
- `app/repositories/base.py` — _apply_tenant_filter, _check_tenant_filter
- `app/models/user.py` — memberships relationship
- `app/models/membership.py` — user back_populates
- Migration — None needed (all Python changes)

---

## Task 1: OrganizationSummary Schema

### Objective

Add the `OrganizationSummary` schema used by auth response payloads. Add `organization` field to `LoginResponse` and `RegisterResponse`.

### Files Modified

| File | Change |
|---|---|
| `app/schemas/auth.py` | Add `OrganizationSummary` schema. Add `organization: OrganizationSummary \| None = None` to `LoginResponse`. Add same field to `RegisterResponse`. |

### Details

```python
class OrganizationSummary(IrtiqaSchema):
    id: str
    name: str
    slug: str
    role: str  # caller's role in this org


class LoginResponse(IrtiqaSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    organization: OrganizationSummary | None = None  # NEW


class RegisterResponse(IrtiqaSchema):
    id: str
    email: str
    display_name: str
    message: str = "Account created. Verify your email to activate."
    organization: OrganizationSummary | None = None  # NEW
```

### Verification

```text
python -c "from app.schemas.auth import OrganizationSummary, LoginResponse, RegisterResponse; print('OK')"
python -m compileall app/schemas/
```

---

## Task 2: AuthService.register() Creates Org + Membership

### Objective

Extend `AuthService.register()` to atomically create a user, organization, and owner membership in a single transaction. Uses repositories directly (not `OrganizationService.create_with_owner()`) to avoid nested transactions.

### Files Modified

| File | Change |
|---|---|
| `app/services/auth_service.py` | Import `OrganizationRepository`, `MembershipRepository`, `Organization`, `Membership`, `generate_slug`. Extend `register()` operation. |

### Implementation

```python
def register(self, email: str, password: str, display_name: str) -> User:
    normalized_email = email.strip().lower()
    existing = self.get_by_email(normalized_email)
    if existing is not None:
        raise EntityConflictError(...)

    hashed = hash_password(password)
    now = datetime.now(timezone.utc)

    def operation(session: Session) -> User:
        repo = self._repository(session)
        user = User(email=normalized_email, password_hash=hashed, ...)
        repo.add(user)
        session.flush()

        # Email verification token (existing behavior)
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        session.add(EmailVerificationToken(user_id=user.id, ...))
        session.flush()

        # NEW: Create organization
        org_repo = OrganizationRepository(session)
        slug = generate_unique_slug(f"{display_name}'s Organization", session)
        org = Organization(
            name=f"{display_name}'s Organization",
            slug=slug,
            status="active",
            created_at=now,
            updated_at=now,
        )
        org_repo.add(org)
        session.flush()

        # NEW: Create owner membership
        mem_repo = MembershipRepository(session)
        membership = Membership(
            user_id=user.id,
            organization_id=org.id,
            role="owner",
            created_at=now,
            updated_at=now,
        )
        mem_repo.add(membership)
        session.flush()

        # Store org info for response
        user._organization_data = OrganizationSummary(
            id=org.id, name=org.name, slug=org.slug, role="owner"
        )
        user._verification_token_raw = raw_token
        return user

    return self._run_in_transaction("register", operation)
```

### New Imports Required

```python
from app.models.organization import Organization, generate_unique_slug, generate_slug
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.membership_repository import MembershipRepository
# OrganizationSummary is imported from schemas in the endpoint layer, not the service
```

### Edge Cases

| Scenario | Behavior |
|---|---|
| User exists | `EntityConflictError` (unchanged) |
| Slug collision | `generate_unique_slug()` appends random suffix |
| Org creation fails | Entire transaction rolls back — user is not created |
| Membership creation fails | Entire transaction rolls back — user + org not created |

### Verification

```text
python -m compileall app/services/
python -m pytest tests/unit/test_auth_integration.py::test_register_creates_org_and_membership -x -v
```

---

## Task 3: AuthService.login() Returns Org Context

### Objective

Extend `AuthService.login()` to look up the user's memberships and include `org_id` and `role` in the JWT claims. Return org context alongside tokens.

### Files Modified

| File | Change |
|---|---|
| `app/services/auth_service.py` | Modify `login()` to accept `MembershipRepository`, pass `organization_id` and `role` to `create_access_token()`. |

### Implementation

```python
def login(self, email: str, password: str, ip_address: str) -> tuple[User, str, str, OrganizationSummary | None]:
    normalized_email = email.strip().lower()
    settings = get_settings()

    self._check_rate_limit(normalized_email)
    user = self.get_by_email(normalized_email)

    if user is None or user.deleted_at is not None:
        self._record_failed_attempt(normalized_email, ip_address)
        raise ValidationError("Invalid email or password.")

    if not user.is_active:
        raise ValidationError("Account is not activated.")

    if not verify_password(password, user.password_hash):
        self._record_failed_attempt(normalized_email, ip_address)
        raise ValidationError("Invalid email or password.")

    self._clear_failed_attempts(normalized_email)

    # NEW: Look up default org
    org_id = None
    org_role = None
    org_summary = None

    def lookup_org(session: Session) -> tuple[str | None, str | None, OrganizationSummary | None]:
        mem_repo = MembershipRepository(session)
        memberships = mem_repo.list_user_memberships(user.id, limit=1)
        if memberships:
            m = memberships[0]
            org_obj = session.get(Organization, m.organization_id)
            summary = OrganizationSummary(id=m.organization_id, name=org_obj.name,
                                           slug=org_obj.slug, role=m.role)
            return m.organization_id, m.role, summary
        return None, None, None

    org_id, org_role, org_summary = self._run_in_transaction("lookup_org", lookup_org)

    # Generate tokens
    access_token = create_access_token(
        user_id=user.id,
        organization_id=org_id,
        role=org_role,
    )
    raw_refresh, hashed_refresh = generate_refresh_token()
    self._store_refresh_token(user.id, hashed_refresh)

    return user, access_token, raw_refresh, org_summary
```

### Return Type Change

The return type changes from `tuple[User, str, str]` to `tuple[User, str, str, OrganizationSummary | None]`. The endpoint layer handles the new fourth element.

### Verification

```text
python -m compileall app/services/
python -m pytest tests/unit/test_auth_integration.py::test_login_returns_org_context -x -v
```

---

## Task 4: get_current_organization() Dependency

### Objective

Add `get_current_organization()` FastAPI dependency that decodes the JWT, extracts `org`/`role` claims, and performs a membership database lookup on every request.

### Files Modified

| File | Change |
|---|---|
| `app/api/dependencies.py` | Add `get_current_organization()` that accepts `Authorization` header, decodes JWT, looks up membership, returns `TenantContext`. |

### Implementation

```python
from app.core.security import decode_access_token
from app.core.tenant import TenantContext


def get_current_organization(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    membership_service: MembershipService = Depends(get_membership_service),
) -> TenantContext:
    """Authenticate the user and verify membership in the org specified
    in the JWT claims.

    Performs a membership database lookup on every request.
    This is the F-1 fix: never trust the JWT claim alone.
    """
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ")

    # Decode JWT — reuses existing auth logic
    user = auth_service.authenticate_with_token(token)
    user_id = user["id"] if isinstance(user, dict) else user.id

    # Decode JWT a second time to extract org/role claims
    # (Two decodes per request. This avoids refactoring get_current_user()
    # which would affect 30+ callers. Cost: ~1ms.)
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    org_id = payload.get("org")
    jwt_role = payload.get("role")

    if org_id is None:
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

**Note:** `get_current_user()` is still used by endpoints that don't need org scoping. `get_current_organization()` is used when org context is required. Both are available as separate dependencies.

### Verification

```text
python -c "from app.api.dependencies import get_current_organization; print('OK')"
python -m compileall app/api/
```

---

## Task 5: Update Auth Endpoint Response Serialization

### Objective

Update the `login` and `register` endpoint handlers to serialize the new org data returned by the service.

### Files Modified

| File | Change |
|---|---|
| `app/api/v1/endpoints/auth.py` | Update `login()` to unpack fourth return value. Update `register()` to serialize org data. |

### Changes

**login() endpoint:**

```python
@router.post("/auth/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    ip_address = request.client.host if request.client else "unknown"
    user, access_token, refresh_token, org_summary = auth_service.login(
        email=payload.email,
        password=payload.password,
        ip_address=ip_address,
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
        organization=org_summary,
    )
```

**register() endpoint:**

The `register()` method already returns `RegisterResponse`. The `organization` field is populated from `user._organization_data` if available.

```python
org_data = getattr(user, "_organization_data", None)
return RegisterResponse(
    id=user.id,
    email=user.email,
    display_name=user.display_name,
    message=message,
    organization=org_data,
)
```

### Verification

```text
python -m compileall app/api/
python -c "from app.main import create_app; create_app(); print('App builds OK')"
```

---

## Task 6: Tests — Auth Integration

### Objective

Create tests verifying the auth + org integration: registration creates org, login returns org context, JWT carries claims, `get_current_organization()` validates membership.

### Files Created

| File | Tests |
|---|---|
| `tests/unit/test_auth_integration.py` | Service-layer tests (no HTTP) |
| `tests/integration/api/test_auth_multitenancy.py` | API-level tests |

### Unit Tests (`tests/unit/test_auth_integration.py`)

| Test | What It Verifies |
|---|---|
| `test_register_creates_org_and_membership` | After register, user has a membership with role=owner |
| `test_register_org_has_correct_slug` | Org slug is generated from display name |
| `test_login_returns_org_context` | Login returns fourth element (OrganizationSummary) |
| `test_login_jwt_contains_org_claim` | Decoded JWT has `org` and `role` claims |
| `test_login_returns_correct_role` | Role in JWT matches membership role |
| `test_login_no_org_fallback` | User without memberships gets None org |
| `test_get_current_organization_valid` | Valid membership returns TenantContext |
| `test_get_current_organization_revoked` | Deleted membership returns None |
| `test_get_current_organization_no_org` | JWT without org claim returns None |

### Integration Tests (`tests/integration/api/test_auth_multitenancy.py`)

| Test | What It Verifies |
|---|---|
| `test_register_response_includes_org` | POST /auth/register returns organization data |
| `test_login_response_includes_org` | POST /auth/login returns organization + role |
| `test_authenticated_user_can_access_org` | GET /organizations/{org_id} works after login |
| `test_register_creates_user_with_owner_membership` | Created user can access their org |

### Fixture Pattern

```python
@pytest.fixture()
def client(api_session_factory, monkeypatch):
    from app.core.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("DEV_MODE", "true")
    app = create_app(dev_settings, configure_logging_on_startup=False)
    with TestClient(app) as test_client:
        yield test_client
```

### Verification

```text
python -m pytest tests/unit/test_auth_integration.py -v
python -m pytest tests/integration/api/test_auth_multitenancy.py -v
```

---

## Implementation Order

```text
Commit 1: Schema + Service (auth_service.py)
  ├── app/schemas/auth.py              — OrganizationSummary, update LoginResponse/RegisterResponse
  ├── app/services/auth_service.py     — register creates org, login returns org
  ├── app/schemas/__init__.py          — export new schema types
  └── python -m compileall app/

  ATMOMICITY NOTE: register() uses OrganizationRepository and
  MembershipRepository directly within its own _run_in_transaction().
  This avoids nested transaction issues. Slug collision is handled
  by generate_unique_slug().

Commit 2: Dependency + Endpoint
  ├── app/api/dependencies.py          — get_current_organization()
  ├── app/api/v1/endpoints/auth.py     — update login/register serialization
  └── python -m compileall app/

Commit 3: Tests
  ├── tests/unit/test_auth_integration.py
  ├── tests/integration/api/test_auth_multitenancy.py
  └── python -m pytest
```

## Files Summary

| Action | Files |
|---|---|
| **Modified** | `app/schemas/auth.py`, `app/services/auth_service.py`, `app/api/dependencies.py`, `app/api/v1/endpoints/auth.py`, `app/schemas/__init__.py` |
| **Created** | `tests/unit/test_auth_integration.py`, `tests/integration/api/test_auth_multitenancy.py` |
| **New Tests** | ~13 |

## Rollback Considerations

| Change | Rollback |
|---|---|
| Schema fields | Remove `organization` field from response schemas |
| Service changes | Revert `register()` and `login()` to originals |
| Dependency | Remove `get_current_organization()` |
| Endpoint | Revert response serialization |
