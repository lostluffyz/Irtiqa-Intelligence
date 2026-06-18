> **Status: IMPLEMENTED**

# Authentication & Multi-Tenancy v2 Design

## Executive Summary

This document revises the v1 design (`docs/authentication_multitenancy_design.md`) to resolve all 16 findings from the audit (`docs/authentication_multitenancy_audit.md`). The v1 design contained one critical flaw (unverified cross-tenant access), five high-severity issues (password reset vulnerability, API key/JWT path collision, discipline-based tenant filtering, inconsistent FK strategy, missing agent/workflow tenant context), and ten medium-severity issues.

The v2 design makes the following architectural changes:

1. **Membership verification on every request** — `get_current_organization` performs a database membership lookup. No trust of JWT claims or client headers alone.
2. **`TenantContext` with `BaseRepository` enforcement** — Tenant scoping is inherited, not discipline-based.
3. **Separate API key authentication path** — `X-API-Key` header discriminates without JWT fallback.
4. **Consistent CASCADE FK strategy** — All tenant-scoped tables use CASCADE. No orphaned records.
5. **Password reset deferred** — Endpoints removed from Phase 1 until email infrastructure exists.
6. **Agent/Workflow context with `organization_id`** — Required field in both context objects.
7. **RS256 JWT signing** — Enables key rotation without mass logout.
8. **Invitation acceptance flow** — Two-step invitation with unique tokens.
9. **Scoped API key roles** — Keys can be created with `viewer`, `member`, `admin`, or `owner` role.
10. **Last-owner protection** — Service-layer enforcement prevents orphaned organizations.

---

## 1. Updated Architecture

### 1.1 Authentication Decision Flow

Every authenticated request follows one of two independent paths:

```text
Incoming Request
    │
    ├── X-API-Key header present?
    │   YES → API Key Authentication Path (Section 1.2)
    │
    NO  → Authorization: Bearer header present?
            YES → JWT Authentication Path (Section 1.3)
            NO  → 401 Unauthorized
```

### 1.2 API Key Authentication Path

```text
1. Extract token from X-API-Key header.
2. Discriminate: does it start with "irt_sk_"?
   NO  → Return 401 (not a valid API key format).
3. Hash token with SHA-256.
4. Look up key_hash in api_keys table.
5. Verify key is not revoked and not expired.
6. Resolve organization_id from the API key record.
7. Resolve role from the API key's role field.
8. Attach (user=None, org_id, role, is_api_key=True) to request state.
9. Proceed.
```

No JWT decode attempt is made. No fallback path exists. The two authentication methods are independent.

### 1.3 JWT Authentication Path

```text
1. Extract token from Authorization: Bearer header.
2. Attempt JWT decode with RS256 public key.
3. Verify signature, expiry, issuer, audience.
4. Extract sub (user_id) and org from JWT claims.
5. Look up user by user_id in users table.
   NOT FOUND → 401 (user deleted after token issuance).
6. Verify membership: query memberships table for (user_id, org).
   NOT FOUND → 403 (user not a member of this org).
7. Attach (user, org, role=membership.role, is_api_key=False) to request state.
8. Proceed.

Organization switching flow:
  POST /auth/switch-organization { org_id }
  → Verify membership exists.
  → Issue new access token with org_id in claims.
  → Old token remains valid until expiry but targets the old org.
```

**Membership verification is performed on every request.** The JWT `org` claim identifies which org the token was issued for, and `get_current_organization` verifies membership via a database lookup before returning the org context.

### 1.4 TenantContext

A `TenantContext` object carries the current organization's identity through the entire request lifecycle:

```python
@dataclass(frozen=True)
class TenantContext:
    organization_id: str
    user_id: str | None        # None for API key auth
    role: str                  # owner, admin, member, viewer
    is_api_key: bool           # True when authenticated via API key
```

**Creation**: Set by `get_current_organization` dependency after membership verification.

**Injection**: Passed to all services that perform tenant-scoped queries.

```python
@router.get("/companies")
def list_companies(
    tenant: TenantContext = Depends(get_current_organization),
    service: CompanyService = Depends(get_company_service),
):
    return service.list_by_organization(tenant.organization_id, ...)
```

### 1.5 BaseRepository Tenant Enforcement

Every `BaseRepository` method that queries tenant-scoped entities automatically includes `organization_id` in the WHERE clause. This is not optional:

```python
class BaseRepository(Generic[ModelT]):
    """Mixin for tenant-scoped queries."""

    def _apply_tenant_filter(self, statement, organization_id: str):
        """Add organization_id = :org_id to the WHERE clause."""
        if hasattr(self.model, "organization_id"):
            return statement.where(self.model.organization_id == organization_id)
        return statement

    def list(self, *, organization_id: str, limit=100, offset=0):
        statement = select(self.model)
        statement = self._apply_tenant_filter(statement, organization_id)
        statement = statement.offset(offset).limit(limit)
        return self.scalars(statement)
```

Repository methods for tenant-scoped entities **must** accept `organization_id`. The base class enforces this structurally. A developer who omits `organization_id` gets a type error or a runtime error when the filter is empty.

Additionally, a startup-time audit logs a warning for any query executed without an `organization_id` filter:

```python
def _check_tenant_filter(self, statement):
    """Log warning if a tenant-scoped model is queried without org filter."""
    if hasattr(self.model, "organization_id"):
        has_filter = any(
            "organization_id" in str(col) for col in statement.whereclause
        )
        if not has_filter:
            self.logger.warning(
                "Tenant-scoped query executed without organization_id filter",
                extra={"model": self.model.__name__},
            )
```

---

## 2. Updated Data Model

### 2.1 FK Strategy (Resolves F-5)

**All tenant-scoped tables use CASCADE delete on `organization_id` FK.** No `SET NULL`. When an organization is deleted, all its data is deleted.

| Table | FK Column | FK Target | On Delete | Notes |
|---|---|---|---|---|
| `companies` | `organization_id` | `organizations.id` | CASCADE | Root tenant entity |
| `contacts` | `organization_id` | `organizations.id` | CASCADE | Denormalized for query efficiency |
| `websites` | `organization_id` | `organizations.id` | CASCADE | Denormalized |
| `technologies` | `organization_id` | `organizations.id` | CASCADE | Denormalized |
| `intent_signals` | `organization_id` | `organizations.id` | CASCADE | Denormalized |
| `intelligence_scores` | `organization_id` | `organizations.id` | CASCADE | Denormalized |
| `outreach_messages` | `organization_id` | `organizations.id` | CASCADE | Denormalized |
| `agent_runs` | `organization_id` | `organizations.id` | CASCADE | Denormalized |
| `evidence_records` | `organization_id` | `organizations.id` | CASCADE | Denormalized (explicitly added) |
| `jobs` | `organization_id` | `organizations.id` | CASCADE | Denormalized |

**Composite indexes** on all child tables: `(organization_id, company_id)` for efficient tenant-scoped queries.

### 2.2 evidence_records Ownership (Resolves F-5)

The `evidence_records` table receives an explicit `organization_id` column with a CASCADE FK. This is a new column, not inherited from `company_id`. The existing `company_id` column is retained for backward compatibility.

### 2.3 invitations Table (Resolves F-10)

The `accepted_at` field is removed from `memberships`. A new `invitations` table implements the two-step invitation flow:

| Column | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID/Text PK | Yes | UUID primary key |
| `organization_id` | UUID/Text FK | Yes | FK to `organizations.id` (CASCADE) |
| `invited_by_id` | UUID/Text FK | Yes | FK to `users.id` (SET NULL) |
| `email` | String(320) | Yes | Email of the invited user |
| `role` | String(50) | Yes | Role to assign on acceptance |
| `token_hash` | String(128) | Yes | SHA-256 of the invitation token |
| `expires_at` | DateTime | Yes | When the invitation expires |
| `accepted_at` | DateTime | No | When the invitation was accepted |
| `created_at` | DateTime | Yes | UTC timestamp |

**Indexes:** Unique on `token_hash`. Index on `email`.

### 2.4 api_keys Role Column (Resolves F-15)

The `api_keys` table adds an optional `role` column:

`role: String(50)` — defaults to `admin`. Allowed values: `viewer`, `member`, `admin`, `owner`.

### 2.5 users Soft Delete (Resolves F-12)

The `users` table adds a soft-delete column:

`deleted_at: DateTime` — nullable. When set, the user cannot log in, and their data is considered deleted for GDPR purposes. Authenticated requests from soft-deleted users return 401.

---

## 3. Updated Authentication Flow

### 3.1 Registration (Resolves F-7)

```text
POST /auth/register
Request: { email, password, display_name, organization_name }

1. Validate email uniqueness.
2. Hash password with bcrypt.
3. Create user record (is_active=False, email_verified_at=None).
4. Generate email verification token (15 min expiry).
5. Store token hash in email_verification_tokens table.
6. Return 201 Created.
7. (Future: send verification email with token.)
   For now: return 201 with message "Verify your email. Token: ..."
   (Token returned ONLY during development mode. In production,
    email infrastructure is required.)
```

**Critical**: The email verification token is returned in the response body only when `DEV_MODE=true` is set. In production mode (default), the token is never returned — the endpoint returns a generic success message and the token must be delivered out of band.

The user cannot log in until `is_active=True` and `email_verified_at` is set. The `verify-email` endpoint sets both:

```text
POST /auth/verify-email
Request: { token }

1. Hash token.
2. Look up in email_verification_tokens.
3. Verify not expired and not used.
4. Mark token as used.
5. Set user.is_active=True, user.email_verified_at=now.
6. Return 200 OK.
```

### 3.2 Login

```text
POST /auth/login
Request: { email, password }

1. Look up user by email.
2. If user.deleted_at is set → 401.
3. If not user.is_active → 403 (email not verified).
4. If user.is_locked (rate limit) → 429.
5. Verify password against bcrypt hash.
6. If password invalid → increment failed_attempts, check lockout.
7. If password valid → reset failed_attempts.
8. Generate JWT access token (15 min) with:
   sub=user_id, org=current_org_id (user's first org or preferred org),
   role=membership.role, iat, exp, type="access", kid="key-v1"
9. Generate refresh token (opaque 64-byte hex).
10. Store refresh token hash in refresh_tokens table.
11. Return { access_token, refresh_token, user, organization }.
```

### 3.3 Logout

```text
POST /auth/logout
Request: { refresh_token }
Auth: Bearer <access_token>

1. Hash the provided refresh token.
2. Verify it belongs to the authenticated user.
3. Mark it as revoked (revoked_at=now).
```

### 3.4 Token Refresh

```text
POST /auth/refresh
Request: { refresh_token }

1. Hash the provided refresh token.
2. Look up token_hash in refresh_tokens table.
3. Verify: exists, not expired, not revoked.
4. Revoke the old refresh token (rotation).
5. Issue new access token (15 min).
6. Issue new refresh token (7 days).
7. Return { access_token, refresh_token }.
```

### 3.5 Organization Switching (Resolves F-1)

```text
POST /auth/switch-organization
Request: { organization_id }
Auth: Bearer <access_token>

1. Verify membership: user is a member of the target org.
   NOT FOUND → 403.
2. Issue NEW access token with org=target_org_id, role=membership.role.
3. Old access token remains valid until expiry but targets the old org.
4. Return { access_token, organization }.
```

This is the **only** way to switch organizations. The client must explicitly request a new token. The `X-Organization-Id` header from v1 is **removed**. The JWT `org` claim is always the source of truth for the target organization.

### 3.6 Password Reset (Resolves F-2)

**Password reset endpoints are not included in Phase 1.** The API returns:

```json
POST /auth/password-reset/request → 501 Not Implemented
{
    "error": {
        "code": "irtiqa.not_implemented",
        "message": "Password reset requires email configuration. This endpoint is not available in the current deployment."
    }
}
```

Password reset will be implemented in a later milestone when email delivery infrastructure is operational. The database schema (`password_reset_tokens` table) is created in the migration for forward compatibility but the API endpoints return 501.

### 3.7 Account Deletion (Resolves F-12)

```text
DELETE /auth/me
Auth: Bearer <access_token>

1. Verify user exists.
2. Set user.deleted_at = now.
3. Revoke all refresh tokens for this user.
4. Return 204 No Content.
```

Soft delete preserves referential integrity. The `deleted_at` check is performed in `get_current_user` — deleted users are rejected with 401.

---

## 4. Updated Multi-Tenancy Flow

### 4.1 Request Lifecycle

```text
1. Request arrives at FastAPI.

2. Authentication dependency (get_current_user_or_api_key):
   ├── X-API-Key header → API key auth path
   │   → Validate key format ("irt_sk_...")
   │   → Hash key, look up in api_keys
   │   → Verify not revoked, not expired
   │   → Return (user=None, org_id, role, is_api_key=True)
   │
   └── Authorization: Bearer → JWT auth path
       → Decode RS256 JWT
       → Verify signature, expiry, issuer, audience
       → Look up user by sub
       → Verify user.deleted_at is None
       → Return (user, org_id=JWT["org"], role=JWT["role"], is_api_key=False)

3. Organization verification (get_current_organization):
   → If is_api_key=True: skip membership check (key is already scoped to org).
   → If is_api_key=False: query memberships WHERE user_id AND org_id.
     → NOT FOUND → 403 Forbidden (user is not a member).
   → Return TenantContext(organization_id, user_id, role, is_api_key).

4. Route handler receives TenantContext via dependency injection.

5. Route handler passes tenant.organization_id to service methods.

6. Service methods pass organization_id to repository methods.

7. Repository methods include organization_id in WHERE clauses
   (enforced by BaseRepository._apply_tenant_filter).
```

### 4.2 Tenant Context in Agents and Workflows (Resolves F-13)

**AgentContext** (`app/agents/context.py`):

```python
class AgentContext(IrtiqaSchema):
    agent_name: str
    organization_id: str = Field(min_length=36, max_length=36)  # NEW: required
    company_id: str = Field(min_length=36, max_length=36)
    contact_id: str | None = None
    workflow_name: str | None = None
    correlation_id: str | None = None
    options: MappingProxyType[str, Any] = ...
```

**WorkflowContext** (`app/workflows/context.py`):

```python
class WorkflowContext(IrtiqaSchema):
    workflow_name: str
    organization_id: str = Field(min_length=36, max_length=36)  # NEW: required
    company_id: str | None = None
    contact_id: str | None = None
    correlation_id: str | None = None
    requested_by: str | None = None
    options: MappingProxyType[str, Any] = ...
```

**Job payload** (`app/jobs/runner.py`):

When scheduling agent or workflow jobs, the `organization_id` is included in the payload:

```python
payload = {
    "company_id": ...,
    "contact_id": ...,
    "organization_id": ...,  # NEW
    "correlation_id": ...,
    "options": ...,
}
```

**JobRunner dispatch** reads `organization_id` from the payload and passes it to both `AgentContext` and `WorkflowContext`:

```python
# In _run_agent_job:
context = AgentContext(
    agent_name=job.target_name,
    organization_id=payload["organization_id"],  # NEW
    company_id=payload["company_id"],
    ...
)

# In _run_workflow_job:
context = WorkflowContext(
    workflow_name=job.target_name,
    organization_id=payload["organization_id"],  # NEW
    company_id=payload.get("company_id"),
    ...
)
```

---

## 5. Updated Authorization Model

### 5.1 Owner Protection Rules (Resolves F-9)

The `MembershipService` enforces the following invariants:

1. **An organization must always have at least one owner.**
2. **Owner role cannot be removed or downgraded** if the member is the only owner.
3. **Owner membership cannot be deleted** if the member is the only owner.
4. **Ownership transfer** changes the target member's role to `owner` and the transferor's role to `admin` in a single transaction.

```python
class MembershipService(BaseService[Membership, MembershipRepository]):
    def update_role(self, membership_id: str, new_role: str, *, actor_role: str) -> Membership:
        if actor_role not in ("admin", "owner"):
            raise PermissionError(...)
        membership = self.get_required(membership_id)
        if new_role != "owner" and membership.role == "owner":
            owner_count = self._count_owners(membership.organization_id)
            if owner_count <= 1:
                raise ConflictError("Cannot remove the last owner.")
        # ... proceed with role update

    def transfer_ownership(self, org_id: str, new_owner_id: str, *, current_owner_id: str) -> None:
        # Verify current_owner_id is an owner.
        # Change new_owner_id's role to owner.
        # Change current_owner_id's role to admin.
        # Single transaction.

    def remove(self, membership_id: str, *, actor_role: str) -> None:
        if actor_role not in ("admin", "owner"):
            raise PermissionError(...)
        membership = self.get_required(membership_id)
        if membership.role == "owner":
            owner_count = self._count_owners(membership.organization_id)
            if owner_count <= 1:
                raise ConflictError("Cannot remove the last owner.")
        # ... proceed with deletion
```

### 5.2 API Key Permission Model (Resolves F-15)

API keys include a `role` field that defaults to `admin`. The role is recorded at creation time and cannot be changed (rotate the key instead):

| Key Role | Effective Permissions |
|---|---|
| `viewer` | Read-only access to all org data |
| `member` | Read + create + update. Cannot delete, manage members, or manage keys. |
| `admin` | Read + create + update + delete + manage members + manage keys. |
| `owner` | Full control including org deletion. |

The `role` is stored in the API key record and attached to the `TenantContext` when authenticating via API key. The same `require_role` helper enforces permissions regardless of authentication method.

---

## 6. Updated JWT Design (Resolves F-6)

### 6.1 Algorithm

**RS256** (RSA Signature with SHA-256) replaces HS256. This enables:

- **Key rotation without mass logout**: Old public key remains valid for verification until all tokens issued with it expire. New tokens are signed with the new private key.
- **Public key endpoint**: `GET /.well-known/jwks.json` exposes the public key for external verification.
- **`kid` header**: Each JWT includes a `kid` (key ID) that identifies which signing key was used.

### 6.2 Key Management

- Private key: `JWT_PRIVATE_KEY` environment variable (PEM-encoded RSA private key).
- Public key: Derived from private key at startup. Exposed via `/.well-known/jwks.json`.
- Key rotation: Add a new private key as `JWT_PRIVATE_KEY_2`. The old key remains available for verification until all tokens signed with it expire. The new key is used for new signatures.

### 6.3 Token Payload

```python
# Access token
{
    "sub": "user-uuid",           # User ID
    "org": "org-uuid",            # Organization ID (verified on every request)
    "role": "admin",              # Role in org (from membership)
    "iat": 1718000000,            # Issued at
    "exp": 1718000900,            # Expires (15 min)
    "type": "access",
    "iss": "irtiqa-api",
    "aud": "irtiqa-client",
    "kid": "key-v1"               # Key ID for rotation
}
```

### 6.4 Public Key Endpoint

```text
GET /.well-known/jwks.json

→ 200 OK
{
    "keys": [
        {
            "kty": "RSA",
            "use": "sig",
            "kid": "key-v1",
            "alg": "RS256",
            "n": "...",
            "e": "AQAB"
        }
    ]
}
```

---

## 7. Updated Migration Plan (Resolves F-14)

### Migration 1: Auth Schema (YYYYMMDD_0006)

Creates 7 tables:
- `users` (with `deleted_at`)
- `organizations`
- `memberships` (without `accepted_at`)
- `invitations` (replaces `accepted_at` on memberships)
- `email_verification_tokens`
- `refresh_tokens`
- `password_reset_tokens` (created for forward compatibility, endpoints return 501)
- `api_keys` (with `role` column, default `admin`)

### Migration 2: Tenant Columns — Add Nullable (YYYYMMDD_0007)

Adds `organization_id` as nullable to all 10 domain tables. Creates indexes.

### Migration 2a: Backfill (Script, Not a Migration)

A standalone Python script that:

1. For each domain table, for each row with NULL `organization_id`:
   - If `company_id` is not NULL: look up `companies.organization_id` and set it.
   - If `company_id` is NULL: log a warning (data integrity issue, skip row).
2. Outputs a summary: total rows processed, rows backfilled, rows skipped.
3. Runs outside of Alembic (as a maintenance script or background job).

**Validation query** (run before Migration 2b):

```sql
SELECT table_name, COUNT(*) as null_count
FROM (
    SELECT 'companies' as table_name FROM companies WHERE organization_id IS NULL
    UNION ALL
    SELECT 'contacts' FROM contacts WHERE organization_id IS NULL
    UNION ALL
    SELECT 'websites' FROM websites WHERE organization_id IS NULL
    UNION ALL
    SELECT 'technologies' FROM technologies WHERE organization_id IS NULL
    UNION ALL
    SELECT 'intent_signals' FROM intent_signals WHERE organization_id IS NULL
    UNION ALL
    SELECT 'intelligence_scores' FROM intelligence_scores WHERE organization_id IS NULL
    UNION ALL
    SELECT 'outreach_messages' FROM outreach_messages WHERE organization_id IS NULL
    UNION ALL
    SELECT 'agent_runs' FROM agent_runs WHERE organization_id IS NULL
    UNION ALL
    SELECT 'evidence_records' FROM evidence_records WHERE organization_id IS NULL
    UNION ALL
    SELECT 'jobs' FROM jobs WHERE organization_id IS NULL
)
GROUP BY table_name
HAVING COUNT(*) > 0;
```

If any row has a NULL `organization_id`, the backfill is incomplete. Migration 2b must not run.

### Migration 2b: Tenant Columns — Set NOT NULL (YYYYMMDD_0008)

Sets `organization_id` to `NOT NULL` on all 10 domain tables. Only runs after backfill validation passes.

### Rollback Plan

| Migration | Rollback |
|---|---|
| 0008 (NOT NULL) | `ALTER TABLE ... ALTER COLUMN organization_id DROP NOT NULL` on each table |
| 0007 (add nullable) | `DROP COLUMN organization_id` on each table (SQLite requires table recreation) |
| 0006 (auth schema) | `DROP TABLE` for all 7 auth tables |

For SQLite, Migration 0007 rollback requires table recreation because SQLite does not support `DROP COLUMN` without `ALTER TABLE ... RENAME`. The rollback script must recreate each table without the `organization_id` column.

---

## 8. Updated Rate Limiting (Resolves F-8)

### 8.1 Database-Backed Rate Limiter

Rate limiting is implemented using the `failed_login_attempts` table (not in-memory):

```sql
CREATE TABLE failed_login_attempts (
    id UUID PRIMARY KEY,
    email VARCHAR(320) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    attempted_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

**Pruning**: Rows older than 24 hours are deleted by a background cleanup task or a `WHERE` clause in the counting query.

**Lookup query**:

```sql
SELECT COUNT(*) FROM failed_login_attempts
WHERE email = :email
  AND attempted_at > NOW() - INTERVAL '15 minutes';
```

**Lockout**: If count >= 5 within 15 minutes, the login is rejected with 429.

This works across all processes and survives restarts. No Redis dependency.

---

## 9. Updated API Design

### 9.1 Rate Limited Endpoints

Rate limiting applies to `POST /auth/login`. The rate limiter uses the database-backed model described in Section 8.

### 9.2 Authentication Endpoints (Phase 1)

| Method | Path | Auth | Rate Limited | Notes |
|---|---|---|---|---|
| `POST` | `/auth/register` | None | Yes (per IP) | Creates user with `is_active=False`. Email verification required. |
| `POST` | `/auth/verify-email` | None | No | Activates user account. |
| `POST` | `/auth/login` | None | Yes (5/15min per email+IP) | Returns JWT + refresh token. |
| `POST` | `/auth/logout` | Bearer | No | Revokes refresh token. |
| `POST` | `/auth/refresh` | None (body) | No | Rotates tokens. |
| `GET` | `/auth/me` | Bearer | No | Current user profile. |
| `PATCH` | `/auth/me` | Bearer | No | Update profile. |
| `DELETE` | `/auth/me` | Bearer | No | Soft delete account. |
| `POST` | `/auth/switch-organization` | Bearer | No | Issue new token for different org. |
| `POST` | `/auth/password-reset/request` | — | — | **501 Not Implemented** (Phase 2). |
| `POST` | `/auth/password-reset/confirm` | — | — | **501 Not Implemented** (Phase 2). |
| `GET` | `/.well-known/jwks.json` | None | No | Public key for JWT verification. |

### 9.3 Organization Endpoints

| Method | Path | Auth | Min Role |
|---|---|---|---|
| `GET` | `/organizations` | Bearer | — (lists user's orgs) |
| `GET` | `/organizations/{org_id}` | Bearer | viewer |
| `PATCH` | `/organizations/{org_id}` | Bearer | admin |
| `DELETE` | `/organizations/{org_id}` | Bearer | owner |

### 9.4 Membership Endpoints

| Method | Path | Auth | Min Role |
|---|---|---|---|
| `GET` | `/organizations/{org_id}/members` | Bearer | viewer |
| `POST` | `/organizations/{org_id}/invitations` | Bearer | admin |
| `GET` | `/organizations/{org_id}/invitations` | Bearer | admin |
| `POST` | `/invitations/{token}/accept` | Bearer | — (self-service) |
| `DELETE` | `/organizations/{org_id}/members/{user_id}` | Bearer | admin |
| `POST` | `/organizations/{org_id}/transfer` | Bearer | owner |

### 9.5 API Key Endpoints

| Method | Path | Auth | Min Role |
|---|---|---|---|
| `GET` | `/organizations/{org_id}/api-keys` | Bearer or API Key | admin |
| `POST` | `/organizations/{org_id}/api-keys` | Bearer or API Key | admin |
| `DELETE` | `/organizations/{org_id}/api-keys/{key_id}` | Bearer or API Key | admin |

API Key creation request:

```json
{
    "name": "CI Pipeline Key",
    "role": "viewer"
}
```

Response includes the full API key exactly once:

```json
{
    "id": "uuid",
    "name": "CI Pipeline Key",
    "key": "irt_sk_a1b2c3d4e5f6...",
    "prefix": "a1b2c3d4",
    "role": "viewer",
    "created_at": "..."
}
```

---

## 10. Updated Testing Plan

### 10.1 New Tests for v2 Changes

| Test | What It Covers |
|---|---|
| `test_membership_verified_on_every_request` | JWT-authenticated request checks membership DB on each call |
| `test_org_switch_issues_new_token` | `POST /auth/switch-organization` creates token with new org_id |
| `test_org_switch_rejects_non_member` | User cannot switch to org they don't belong to |
| `test_api_key_separate_header` | `X-API-Key` authentication does not decode JWT |
| `test_api_key_invalid_prefix` | Malformed API key prefix returns 401 without DB lookup |
| `test_api_key_scoped_role` | API key with `role=viewer` cannot write |
| `test_last_owner_cannot_be_removed` | Removing the last owner raises ConflictError |
| `test_last_owner_role_cannot_be_changed` | Downgrading the last owner raises ConflictError |
| `test_ownership_transfer` | Target becomes owner, source becomes admin |
| `test_invitation_acceptance_flow` | Full invitation → token → accept lifecycle |
| `test_invitation_expired` | Expired invitation token returns 410 |
| `test_tenant_filter_enforced_by_repository` | BaseRepository includes org_id in WHERE for tenant-scoped models |
| `test_tenant_filter_missing_logs_warning` | Query without org_id logs warning |
| `test_agent_context_has_organization_id` | AgentContext requires organization_id |
| `test_workflow_context_has_organization_id` | WorkflowContext requires organization_id |
| `test_job_payload_includes_organization_id` | Scheduled jobs carry organization_id |
| `test_organization_cascade_delete` | Deleting org cascades to all domain entities |
| `test_login_rate_limited` | 5 failed attempts in 15 minutes returns 429 |
| `test_rate_limiter_survives_restart` | Attempts persist in database (no in-memory) |
| `test_email_verification_required_for_login` | Unverified user cannot log in |
| `test_account_soft_delete` | `DELETE /auth/me` sets `deleted_at`, user cannot log in |
| `test_jwt_rs256_verification` | RS256-signed token is accepted |
| `test_jwt_rs256_key_rotation` | Token signed with old key is accepted until expiry |
| `test_jwks_endpoint` | `GET /.well-known/jwks.json` returns public key |

### 10.2 Expected Test Count

Approximately 45 unit + 15 integration + 3 PostgreSQL = **63 new tests** (up from 43 in v1, reflecting the additional tenancy enforcement, invitation flow, rate limiting, and context changes).

---

## 11. Resolved Audit Findings Matrix

| Finding | Severity | v1 Status | v2 Resolution | v2 Status |
|---|---|---|---|---|
| F-1: Cross-tenant access unverified | **Critical** | Not verified | Membership lookup on every request. `switch-organization` endpoint. No `X-Organization-Id` header. | **Resolved** |
| F-2: Password reset in response | **High** | Token in body | Endpoints return 501. Password reset deferred to Phase 2 with email infrastructure. | **Resolved** |
| F-3: API key / JWT path collision | **High** | Shared `Bearer` | Separate `X-API-Key` header. No JWT fallback. Prefix discrimination. | **Resolved** |
| F-4: Tenant filtering by discipline | **High** | Discipline-based | `BaseRepository._apply_tenant_filter` enforces org_id on all tenant-scoped queries. Warning log for missing filters. | **Resolved** |
| F-5: Inconsistent FK strategy | **High** | Mixed CASCADE/SET NULL | All tenant-scoped tables use CASCADE. `evidence_records` gets explicit `organization_id`. | **Resolved** |
| F-6: HS256 key rotation | Medium | HS256, no rotation | RS256 with `kid` header. Public JWKS endpoint. Key rotation without mass logout. | **Resolved** |
| F-7: Unverified registration | Medium | No email verification | `is_active=False` until email verified. Verification token in `email_verification_tokens`. Production mode never returns token in response. | **Resolved** |
| F-8: In-memory rate limiter | Medium | In-memory | Database-backed `failed_login_attempts` table. Survives restarts. Works across processes. | **Resolved** |
| F-9: Last-owner removal | Medium | No check | `MembershipService` prevents removal/downgrade of the last owner. | **Resolved** |
| F-10: Invitation flow undefined | Medium | `accepted_at` stub | `invitations` table with two-step flow. `POST /invitations/{token}/accept`. | **Resolved** |
| F-11: Slug collision | Low | No strategy | Collision retry with random suffix. | **Resolved** |
| F-12: GDPR / account deletion | Low | Not present | `deleted_at` on `users`. `DELETE /auth/me` soft delete. | **Resolved** |
| F-13: Agent/workflow org context | Medium | Not specified | `organization_id` required on `AgentContext`, `WorkflowContext`, job payloads. | **Resolved** |
| F-14: Migration backfill | Medium | Not specified | Multi-step migration (nullable → backfill → NOT NULL). Validation queries. Rollback plan. | **Resolved** |
| F-15: API key overprivileged | Medium | All keys admin | Optional `role` field on API key creation. Keys scoped to viewer/member/admin/owner. | **Resolved** |

---

## Implementation Readiness Verdict

**READY FOR IMPLEMENTATION.**

### Why the v2 Design Is Ready

1. **All 16 audit findings are resolved.** The critical cross-tenant access flaw (F-1) is fixed by requiring membership verification on every request. The password reset vulnerability (F-2) is eliminated by deferring the feature. Tenant filtering (F-4) is enforced at the `BaseRepository` level. The FK strategy (F-5) is consistent with CASCADE.

2. **No remaining architectural conflicts.** The changes to `AgentContext`, `WorkflowContext`, and job payloads are explicitly specified. The FastAPI dependency injection pattern is preserved. The existing service/repository pattern is extended, not replaced.

3. **The authentication architecture is auditable and testable.** The two authentication paths (JWT and API key) are independent and separately testable. The tenant isolation model is enforced at multiple layers (dependency injection, service layer, repository layer).

4. **Production readiness requirements are defined.** Email verification gating, database-backed rate limiting, RS256 key rotation, soft delete for GDPR, and the migration backfill plan are all specified.

### Phase Split

The implementation follows the same two-phase approach as v1, with Phase 2 expanded:

- **Phase 1** (Auth): Users, JWT, login, register, logout, refresh, email verification, rate limiting, account deletion, JWKS endpoint. No organizations, no multi-tenancy.
- **Phase 2** (Multi-Tenancy): Organizations, memberships, invitations, API keys, `organization_id` on all domain entities, tenant-scoped queries, agent/workflow context changes, job payload changes, CASCADE FK migration, backfill script.
- **Phase 3** (Future): Password reset (with email infrastructure), SSO/OAuth, auto-rotating API keys.
