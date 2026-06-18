> **Status: IMPLEMENTED**

# Authentication & Multi-Tenancy Design

## 1. Goals

### Authentication

- Users authenticate with email and password.
- Sessions are managed via short-lived JWT access tokens (15 min) and longer-lived refresh tokens (7 days).
- Passwords are hashed with bcrypt (via `passlib`).
- Tokens are issued by the Irtiqa API, not by a third-party identity provider.
- No OAuth, SAML, or social login in the initial design — the system is self-contained.
- Password reset uses time-limited, single-use tokens emailed to the user.

### Multi-Tenancy

- Every piece of data belongs to exactly one organization.
- Users can belong to multiple organizations with different roles in each.
- All queries are scoped to the user's current organization.
- Cross-tenant data access is prevented at the database query layer, not just at the API layer.
- The multi-tenancy model is **organization-scoped** (each org sees only its own data), not row-level or schema-per-tenant.

### Organization Management

- Organizations are the top-level account entity.
- An organization has a name, billing details, and status (active, suspended, cancelled).
- Organization creation is the first step after user registration (the user creates or joins an org).

### User Management

- Users have an identity separate from any organization.
- A user can be invited to an organization via email.
- Users can be removed from an organization (membership deleted).
- A user's personal data (email, name) is global; their role and permissions are per-organization.

### Role-Based Access Control

- Four roles: Owner, Admin, Member, Viewer.
- Permissions are defined per action type (create, read, update, delete) per resource category.
- Role assignment is at the membership level (user + organization).

### API Access

- Authenticated API calls require a JWT access token in the `Authorization` header.
- Programmatic access uses API keys (long-lived, scoped to an organization).
- API keys can be created, listed, revoked, and deleted.

---

## 2. Architecture

### Design Conflicts Checked

The authentication and multi-tenancy system must integrate with the existing Irtiqa architecture. The following conflicts were evaluated and ruled out:

| Concern | Assessment |
|---|---|
| **Agent framework compatibility** | No conflict. Agents receive context including the current organization. All agent-created records (technologies, signals, scores, messages, evidence) are linked to an organization. |
| **Workflow system compatibility** | No conflict. Workflows operate on organization-scoped data. The pipeline workflow receives org context via `AgentContext`. |
| **Job system compatibility** | No conflict. Jobs are already scoped to company/contact. Adding org_id to job payloads enables tenant-aware job dispatch. |
| **Evidence records compatibility** | No conflict. Evidence records already link to company_id. Adding org_id to the evidence_records table (as a denormalized column) enables tenant-scoped evidence queries. |
| **PostgreSQL compatibility** | The auth system is PostgreSQL-first. UUIDs use native PostgreSQL `UUID` type. SQLite compatibility is maintained for development by using `String(36)` for UUID columns in the auth tables as well, with a migration path to native PG UUIDs. |
| **FastAPI architecture** | No conflict. Authentication is implemented as FastAPI middleware and dependency injection — the same pattern used for existing service dependencies. |
| **Existing entities (companies, contacts, etc.)** | All existing entities gain an `organization_id` column to establish tenant ownership. |

### Entity Model

```text
Organization ──1:N── Membership ──N:1── User
     │                                    │
     │                                    │
     └────── API Key (scoped to org)      │
                                          │
                                     Password Reset Token
```

All existing domain entities (companies, contacts, websites, technologies, etc.) gain an `organization_id` foreign key.

### Directory Structure

New files follow the existing Irtiqa package structure:

```text
app/
├── api/
│   └── v1/
│       └── endpoints/
│           ├── auth.py              NEW: login, register, refresh, logout
│           ├── organizations.py     NEW: org CRUD
│           ├── memberships.py       NEW: invite, list, role management
│           └── api_keys.py          NEW: API key management
├── core/
│   └── security.py                  NEW: password hashing, JWT, API key generation
├── models/
│   ├── user.py                      NEW
│   ├── organization.py              NEW
│   ├── membership.py                NEW
│   ├── refresh_token.py             NEW
│   ├── password_reset_token.py      NEW
│   └── api_key.py                   NEW
├── repositories/
│   ├── user_repository.py           NEW
│   ├── organization_repository.py   NEW
│   ├── membership_repository.py     NEW
│   ├── refresh_token_repository.py  NEW
│   ├── password_reset_repository.py NEW
│   └── api_key_repository.py        NEW
├── schemas/
│   ├── auth.py                      NEW
│   ├── organization.py              NEW
│   ├── membership.py                NEW
│   └── api_key.py                   NEW
├── services/
│   ├── auth_service.py              NEW
│   ├── organization_service.py      NEW
│   ├── membership_service.py        NEW
│   └── api_key_service.py           NEW
└── core/
    ├── config.py                    MODIFY: add auth settings
    └── errors.py                    MODIFY: add auth-specific errors
```

### Tenant Isolation Architecture

Tenant isolation uses a **shared-table, filter-by-organization_id** strategy:

```text
Every query includes: WHERE organization_id = current_org_id
```

This is enforced through:
1. **Middleware**: Extracts the current organization from the JWT or API key and attaches it to the request state.
2. **Dependency injection**: A `get_current_organization()` FastAPI dependency provides the org context to route handlers.
3. **Service layer**: Services that query domain entities accept `organization_id` as a parameter. Repository queries include `organization_id` in WHERE clauses.
4. **Repository layer**: Base repository methods are augmented with optional `organization_id` filtering.

This strategy follows the existing pattern where services own transaction boundaries and repositories own query logic.

---

## 3. Database Design

### New Tables

#### `users`

| Column | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID/Text PK | Yes | UUID primary key |
| `email` | String(320) | Yes | Unique, lowercased, trimmed |
| `password_hash` | String(128) | Yes | bcrypt hash |
| `display_name` | String(200) | Yes | User's display name |
| `is_active` | Boolean | Yes | Whether the user can log in |
| `email_verified_at` | DateTime | No | When email was verified (nullable) |
| `created_at` | DateTime | Yes | UTC timestamp |
| `updated_at` | DateTime | Yes | UTC timestamp |

**Indexes:**
- Unique index on `email`.
- Index on `is_active`.

**Constraints:**
- `email` must be a valid email format (application-level validation via Pydantic).

#### `organizations`

| Column | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID/Text PK | Yes | UUID primary key |
| `name` | String(200) | Yes | Organization display name |
| `slug` | String(100) | Yes | URL-friendly unique identifier |
| `status` | String(50) | Yes | `active`, `suspended`, `cancelled` |
| `created_at` | DateTime | Yes | UTC timestamp |
| `updated_at` | DateTime | Yes | UTC timestamp |

**Indexes:**
- Unique index on `slug`.
- Index on `status`.

**Constraints:**
- `status` must be `active`, `suspended`, or `cancelled`.

#### `memberships`

| Column | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID/Text PK | Yes | UUID primary key |
| `user_id` | UUID/Text FK | Yes | FK to `users.id` (CASCADE delete) |
| `organization_id` | UUID/Text FK | Yes | FK to `organizations.id` (CASCADE delete) |
| `role` | String(50) | Yes | `owner`, `admin`, `member`, `viewer` |
| `invited_by_id` | UUID/Text FK | No | FK to `users.id` who invited (SET NULL) |
| `accepted_at` | DateTime | No | When the user accepted the invitation |
| `created_at` | DateTime | Yes | UTC timestamp |
| `updated_at` | DateTime | Yes | UTC timestamp |

**Indexes:**
- Unique composite index on `(user_id, organization_id)`.
- Index on `organization_id`.
- Index on `role`.
- Index on `user_id`.

**Constraints:**
- `role` must be `owner`, `admin`, `member`, or `viewer`.

#### `refresh_tokens`

| Column | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID/Text PK | Yes | UUID primary key |
| `user_id` | UUID/Text FK | Yes | FK to `users.id` (CASCADE delete) |
| `token_hash` | String(128) | Yes | SHA-256 hash of the refresh token |
| `expires_at` | DateTime | Yes | When the token expires |
| `revoked_at` | DateTime | No | When the token was revoked |
| `created_at` | DateTime | Yes | UTC timestamp |

**Indexes:**
- Index on `token_hash`.
- Index on `user_id`.

#### `password_reset_tokens`

| Column | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID/Text PK | Yes | UUID primary key |
| `user_id` | UUID/Text FK | Yes | FK to `users.id` (CASCADE delete) |
| `token_hash` | String(128) | Yes | SHA-256 hash of the reset token |
| `expires_at` | DateTime | Yes | When the token expires |
| `used_at` | DateTime | No | When the token was used |
| `created_at` | DateTime | Yes | UTC timestamp |

**Indexes:**
- Index on `token_hash`.
- Index on `user_id`.

#### `api_keys`

| Column | Type | Required | Notes |
|---|---|---|---|
| `id` | UUID/Text PK | Yes | UUID primary key |
| `organization_id` | UUID/Text FK | Yes | FK to `organizations.id` (CASCADE delete) |
| `created_by_id` | UUID/Text FK | Yes | FK to `users.id` (SET NULL on delete) |
| `name` | String(200) | Yes | Human-readable key name |
| `key_prefix` | String(8) | Yes | First 8 chars of the API key (for display) |
| `key_hash` | String(128) | Yes | SHA-256 hash of the full API key |
| `last_used_at` | DateTime | No | Last usage timestamp |
| `expires_at` | DateTime | No | Optional expiration |
| `revoked_at` | DateTime | No | When the key was revoked |
| `created_at` | DateTime | Yes | UTC timestamp |
| `updated_at` | DateTime | Yes | UTC timestamp |

**Indexes:**
- Unique index on `key_hash`.
- Index on `organization_id`.
- Index on `revoked_at`.

### Existing Table Modifications

Every existing domain entity table gains a new column:

#### `organizations` reference on existing tables

| Table | New Column | FK | Rationale |
|---|---|---|---|
| `companies` | `organization_id` | FK → `organizations.id` (CASCADE) | Root tenant-scoped entity |
| `contacts` | (inherited via company join or direct org FK) | — | See FK strategy below |
| `websites` | (inherited via company) | — | See FK strategy below |
| `technologies` | (inherited via company) | — | See FK strategy below |
| `intent_signals` | (inherited via company) | — | See FK strategy below |
| `intelligence_scores` | (inherited via company) | — | See FK strategy below |
| `outreach_messages` | (inherited via company) | — | See FK strategy below |
| `agent_runs` | (inherited via company) | — | See FK strategy below |
| `evidence_records` | Already has `company_id` (denormalized) | — | `evidence_records.company_id` already provides tenant scoping via company → org |

**Tenant FK strategy**: The simplest and safest approach is to add `organization_id` directly to `companies` (the root tenant entity) and all child entities either inherit tenant scope through their `company_id` join or also have a direct `organization_id` column for efficient query pruning.

For the initial design:
- **`companies`**: Direct `organization_id` FK.
- **All child entities** (`contacts`, `websites`, `technologies`, `intent_signals`, `intelligence_scores`, `outreach_messages`, `agent_runs`): Add `organization_id` as a denormalized FK with `SET NULL` on org delete. This enables tenant-scoped queries without joining through companies.

This matches the existing evidence_records pattern where `company_id` and `contact_id` are denormalized for query efficiency.

### Migration Strategy

1. Create new auth tables (6 tables in one migration).
2. Add `organization_id` column to `companies` (nullable initially, made non-nullable after backfill).
3. Add `organization_id` column to all child tables (nullable, no backfill needed — existing rows remain NULL for backward compatibility until migration).
4. Create indexes on all new `organization_id` columns.

Migration revision naming follows existing conventions: `YYYYMMDD_NNNN_description.py`.

---

## 4. Authentication Design

### Registration Flow

```text
POST /auth/register
Request: { email, password, display_name, organization_name }

1. Validate email uniqueness.
2. Hash password with bcrypt.
3. Create user record (is_active=True, email_verified_at=None).
4. Create organization with provided name and generated slug.
5. Create membership with role=owner for the new user in the new org.
6. Optionally send email verification.
7. Return user profile + access + refresh tokens.
```

### Login Flow

```text
POST /auth/login
Request: { email, password }
Response: { access_token, refresh_token, user, organization }

1. Look up user by email.
2. Verify password against bcrypt hash.
3. If the user has a current_organization_id cookie/preference, use that.
4. Otherwise, use the user's first organization (or require org selection).
5. Generate JWT access token (15 min) with sub=user_id, org_id, role.
6. Generate refresh token (7 days), store SHA-256 hash in database.
7. Return tokens + user profile + current org.
```

### Logout Flow

```text
POST /auth/logout
Request: { refresh_token }

1. Hash the provided refresh token.
2. Look up the token hash in the refresh_tokens table.
3. Mark it as revoked (revoked_at=now).
4. Client discards access token.
```

### Token Refresh Flow

```text
POST /auth/refresh
Request: { refresh_token }
Response: { access_token, refresh_token }

1. Hash the provided refresh token.
2. Look up token_hash in refresh_tokens table.
3. Verify it exists, is not expired, and is not revoked.
4. Revoke the old refresh token (token rotation).
5. Issue a new access token (15 min) and new refresh token (7 days).
6. Return new tokens.
```

### Password Reset Flow

```text
POST /auth/password-reset/request
Request: { email }

1. Look up user by email (do NOT reveal whether email exists).
2. Generate a time-limited reset token (15 min).
3. Hash the token with SHA-256, store in password_reset_tokens.
4. Return 200 OK regardless of whether email was found.
5. (Future: send email with reset link — for now, return token in response body for API clients.)

POST /auth/password-reset/confirm
Request: { token, new_password }

1. Hash the provided token.
2. Look up token_hash in password_reset_tokens.
3. Verify it exists, is not expired, and is not used.
4. Mark token as used (used_at=now).
5. Update user's password_hash with new bcrypt hash.
6. Revoke all refresh tokens for the user (force re-login).
```

### JWT Token Design

```python
# Access token payload
{
    "sub": "user-uuid",          # User ID
    "org": "org-uuid",           # Current organization ID
    "role": "admin",             # Role in current organization
    "iat": 1718000000,           # Issued at
    "exp": 1718000900,           # Expires (15 min)
    "type": "access"
}

# Refresh token payload (stored hash in DB, not JWT)
# Carried as an opaque string; hashed before DB storage
```

- **Algorithm**: HS256 (HMAC-SHA256), not RS256. The JWT secret is an environment variable.
- **Issuer**: `irtiqa-api`
- **Audience**: `irtiqa-client`
- **Token rotation**: On refresh, the old refresh token is revoked and a new one is issued.
- **Multiple devices**: Each device gets its own refresh token. All remain valid until expiry or revocation.

### Authentication Middleware

Authentication is implemented as a FastAPI dependency, not as middleware. This follows the existing pattern used for service dependencies (`Depends(get_current_user)`).

```python
# FastAPI dependency
async def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db_session),
) -> User:
    # 1. Extract Bearer token from Authorization header.
    # 2. Decode and verify JWT access token.
    # 3. Look up user by sub (user_id).
    # 4. Return user or raise 401.
```

For API key authentication, a separate dependency is used:

```python
async def get_current_organization(
    user: User = Depends(get_current_user),
    current_org_id: str | None = None,  # from session or cookie
) -> Organization:
    # 1. Verify user is a member of the current org.
    # 2. Return organization or raise 403.
```

### Session Structure

There is no server-side session store. Sessions are stateless and managed through JWT tokens. The client stores:
- `access_token`: Short-lived JWT (15 min), sent in `Authorization: Bearer <token>` header.
- `refresh_token`: Opaque string (7 days), sent in `POST /auth/refresh` body.
- `current_organization_id`: Stored client-side, sent as a custom header `X-Organization-Id` on each request when the user has access to multiple orgs.

---

## 5. Multi-Tenancy Model

### Organization Ownership

- Every organization has exactly one member with `role=owner` (the creator).
- The owner can transfer ownership to another member (changes their role to `owner`, the current owner becomes `admin`).
- An organization cannot exist without at least one owner.

### Membership Model

- A user must have an active membership in an organization to access its data.
- Memberships can be created by:
  - **Registration**: Automatic owner membership for the new user in the new org.
  - **Invitation**: An existing admin or owner invites a user via email. The membership is created in `pending` status until the user accepts.
- Memberships can be deleted by:
  - **Self-removal**: A member can leave an organization (unless they are the last owner).
  - **Admin removal**: An admin or owner can remove any non-owner member.
  - **Owner removal**: An owner can remove any member except themselves (transfer ownership first).

### Tenant Isolation

Tenant isolation is enforced at three layers:

**Layer 1: Database queries**
All service methods that query tenant-scoped entities accept `organization_id` as a parameter:

```python
class CompanyService(BaseService[Company, CompanyRepository]):
    def list_by_organization(self, organization_id: str, *, limit=100, offset=0):
        def operation(session):
            return self._repository(session).list_by_organization(organization_id, limit=limit, offset=offset)
        return self._run_in_transaction("list_by_organization", operation)
```

Repository queries include `WHERE organization_id = :org_id` in all SELECT, UPDATE, and DELETE statements for tenant-scoped entities.

**Layer 2: FastAPI dependency injection**
The `get_current_organization` dependency extracts the organization from:
1. The JWT access token's `org` claim (for user-authenticated requests), or
2. The API key's organization (for API-key-authenticated requests).

Route handlers receive `organization_id` as a dependency:

```python
@router.get("/companies")
def list_companies(
    org: Organization = Depends(get_current_organization),
    service: CompanyService = Depends(get_company_service),
):
    return service.list_by_organization(org.id, ...)
```

**Layer 3: Cross-tenant protection**
- API keys are scoped to a specific organization. An API key from Org A cannot access Org B's data.
- JWT tokens encode the organization ID in the `org` claim. The server verifies that the user is a member of that org on each request (for sensitive operations) or trusts the JWT claim (for read operations).
- A user cannot switch to an organization they don't belong to.

### Query Filtering Strategy

The strategy uses **explicit parameter passing**, not SQLAlchemy event listeners or automatic query interceptors. This is the safest approach because:

1. It's explicit — every query visibly includes `organization_id`.
2. It's testable — no magic behavior to mock or verify.
3. It's maintainable — adding a new query doesn't require configuring a filter system.
4. It follows the existing Irtiqa pattern where services pass explicit parameters to repositories.

The tradeoff is that every new query method must remember to include `organization_id`. This is mitigated by:
- Code review requirements for new query methods.
- Integration tests that verify cross-tenant isolation.
- Base repository methods that include optional `organization_id` filtering.

---

## 6. Authorization

### Role Definitions

| Role | Level | Description |
|---|---|---|
| **Owner** | 100 | Full control. Can manage billing, delete the org, transfer ownership. |
| **Admin** | 80 | Can manage members, create/update/delete all data, configure integrations. |
| **Member** | 50 | Can create and edit data, run workflows, view results. |
| **Viewer** | 10 | Read-only access to all data in the org. |

### Permission Matrix

| Action | Owner | Admin | Member | Viewer |
|---|---|---|---|---|
| View companies | ✅ | ✅ | ✅ | ✅ |
| Create companies | ✅ | ✅ | ✅ | ❌ |
| Update companies | ✅ | ✅ | ✅ | ❌ |
| Delete companies | ✅ | ✅ | ❌ | ❌ |
| View contacts | ✅ | ✅ | ✅ | ✅ |
| Create/update contacts | ✅ | ✅ | ✅ | ❌ |
| Delete contacts | ✅ | ✅ | ❌ | ❌ |
| View technologies | ✅ | ✅ | ✅ | ✅ |
| Run agents/workflows | ✅ | ✅ | ✅ | ❌ |
| View evidence | ✅ | ✅ | ✅ | ✅ |
| Manage members | ✅ | ✅ | ❌ | ❌ |
| Manage API keys | ✅ | ✅ | ❌ | ❌ |
| Manage organization | ✅ | ❌ | ❌ | ❌ |
| Delete organization | ✅ | ❌ | ❌ | ❌ |
| View billing | ✅ | ✅ | ❌ | ❌ |

### Permission Enforcement

Permissions are enforced in the service layer, not the API layer. Each service method checks the caller's role against the required permission:

```python
class CompanyService(BaseService[Company, CompanyRepository]):
    def create(self, organization_id: str, user_role: str, **values):
        if user_role not in ("owner", "admin", "member"):
            raise PermissionError("Insufficient permissions to create companies.")
        return super().create(organization_id=organization_id, **values)
```

A reusable `require_role` helper is provided:

```python
def require_role(minimum_role: str, current_role: str, action: str = "") -> None:
    levels = {"viewer": 10, "member": 50, "admin": 80, "owner": 100}
    if levels.get(current_role, 0) < levels.get(minimum_role, 0):
        raise PermissionError(
            f"Insufficient permissions. Required: {minimum_role}, "
            f"actual: {current_role}. {action}"
        )
```

---

## 7. API Design

All authentication and organization endpoints are prefixed under `/auth` and `/organizations`.

### Authentication Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| `POST` | `/auth/register` | Register a new user + org | None |
| `POST` | `/auth/login` | Authenticate and get tokens | None |
| `POST` | `/auth/logout` | Revoke refresh token | Bearer |
| `POST` | `/auth/refresh` | Refresh access token | None (uses refresh token body) |
| `GET` | `/auth/me` | Get current user profile | Bearer |
| `PATCH` | `/auth/me` | Update current user profile | Bearer |
| `POST` | `/auth/password-reset/request` | Request password reset | None |
| `POST` | `/auth/password-reset/confirm` | Confirm password reset | None (uses reset token body) |

### Organization Endpoints

| Method | Path | Description | Auth | Min Role |
|---|---|---|---|---|
| `GET` | `/organizations` | List user's organizations | Bearer | — |
| `GET` | `/organizations/{org_id}` | Get org details | Bearer | viewer |
| `PATCH` | `/organizations/{org_id}` | Update org | Bearer | admin |
| `DELETE` | `/organizations/{org_id}` | Delete org | Bearer | owner |

### Membership Endpoints

| Method | Path | Description | Auth | Min Role |
|---|---|---|---|---|
| `GET` | `/organizations/{org_id}/members` | List members | Bearer | viewer |
| `POST` | `/organizations/{org_id}/members` | Invite member | Bearer | admin |
| `PATCH` | `/organizations/{org_id}/members/{user_id}` | Change role | Bearer | admin |
| `DELETE` | `/organizations/{org_id}/members/{user_id}` | Remove member | Bearer | admin |
| `POST` | `/organizations/{org_id}/transfer` | Transfer ownership | Bearer | owner |

### API Key Endpoints

| Method | Path | Description | Auth | Min Role |
|---|---|---|---|---|
| `GET` | `/organizations/{org_id}/api-keys` | List API keys | Bearer | admin |
| `POST` | `/organizations/{org_id}/api-keys` | Create API key | Bearer | admin |
| `DELETE` | `/organizations/{org_id}/api-keys/{key_id}` | Revoke API key | Bearer | admin |

### API Key Authentication

API keys can be used as an alternative to Bearer JWT tokens:

```text
Authorization: Bearer irt_sk_abc123def456...
```

When the token does not decode as a valid JWT, the system checks if it matches a known API key hash. If it does, the request is authenticated as the API key's organization with the `admin` role (API keys inherit the admin role).

---

## 8. Service Layer Design

### AuthService

| Method | Description |
|---|---|
| `register(email, password, display_name, org_name)` | Create user + org + membership |
| `login(email, password)` | Verify credentials, issue tokens |
| `logout(refresh_token)` | Revoke refresh token |
| `refresh(refresh_token)` | Rotate tokens |
| `get_user(user_id)` | Get user profile |
| `update_user(user_id, **kwargs)` | Update user profile |
| `request_password_reset(email)` | Create reset token |
| `confirm_password_reset(token, new_password)` | Reset password |

### OrganizationService

| Method | Description |
|---|---|
| `create(name, slug)` | Create organization |
| `get(org_id)` | Get org by ID |
| `update(org_id, **kwargs)` | Update org |
| `delete(org_id)` | Delete org (owner only) |
| `list_by_user(user_id)` | List orgs for a user |

### MembershipService

| Method | Description |
|---|---|
| `create(user_id, org_id, role, invited_by)` | Add membership |
| `get(membership_id)` | Get membership |
| `list_by_org(org_id)` | List members in org |
| `list_by_user(user_id)` | List memberships for a user |
| `update_role(membership_id, new_role)` | Change role |
| `remove(membership_id)` | Delete membership |
| `transfer_ownership(org_id, new_owner_id)` | Transfer ownership |

### ApiKeyService

| Method | Description |
|---|---|
| `create(org_id, created_by, name)` | Create API key, return full key once |
| `get_by_key(key)` | Look up API key by its hash |
| `list_by_org(org_id)` | List API keys (without secret values) |
| `revoke(key_id)` | Revoke API key |

---

## 9. Security Review

### Password Hashing

- Algorithm: bcrypt via `passlib.context.CryptContext`.
- Work factor: 12 (configurable).
- Library: `passlib[bcrypt]` — already a common FastAPI dependency.
- Password requirements: minimum 8 characters, no maximum enforced (bcrypt has a 72-byte limit; longer passwords are pre-hashed with SHA-256 before bcrypt).

```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

### Token Security

- **JWT access tokens**: 15-minute expiry. Signed with HS256. Secret stored as `JWT_SECRET` environment variable (minimum 32 bytes, generated with `secrets.token_bytes(32)`).
- **Refresh tokens**: 7-day expiry. Opaque string (64 bytes of entropy from `secrets.token_hex(64)`). Stored as SHA-256 hash in the database. The raw token is only returned in the API response and never stored server-side.
- **Token rotation**: Each refresh invalidates the old refresh token and issues a new one. If a revoked refresh token is reused, all refresh tokens for that user are revoked (breach detection).
- **JWT secret rotation**: The JWT secret supports multiple valid secrets via a rotation mechanism. The primary secret signs new tokens; secondary secrets are accepted for verification until their expiry.

### API Key Security

- API key format: `irt_sk_<64-char-hex>` (prefix identifies the key type, hex is high-entropy random).
- API key is hashed with SHA-256 before storage. The raw key is shown exactly once at creation time.
- API key prefix (first 8 characters of the hex portion) is stored in plain text for display in the UI without revealing the full key.
- API keys can be revoked. A revoked key is unusable even if leaked.

### Brute-Force Protection

- Login rate limiting: A configurable maximum number of failed attempts per IP address per minute (default: 5 attempts per minute).
- Rate limiting is implemented at the application level using an in-memory counter (no Redis dependency). The counter tracks `(ip_address, email)` tuples.
- After `max_failed_attempts` (default: 5), the account is locked for `lockout_duration_minutes` (default: 15).
- Failed attempt counters reset on successful login.
- Password reset tokens expire after 15 minutes.

### Audit Logging

- All authentication events (login success, login failure, logout, token refresh, password reset) are logged through the existing structured logging system.
- All authorization failures (permission denied, cross-tenant access attempt) are logged through the existing structured logging system.
- The log level for successful auth events is `INFO`. For failed auth events, it's `WARNING`.
- Sensitive data (passwords, tokens, API keys) are never logged.

### Additional Security Considerations

- **Email verification**: The `users` table has `email_verified_at`. Accounts with unverified emails can log in but certain operations may be restricted.
- **HTTPS**: The API is expected to be served behind HTTPS in production. No HTTP-only endpoints.
- **Security headers**: The FastAPI application should include security headers (X-Content-Type-Options, X-Frame-Options, Strict-Transport-Security) via middleware.
- **CORS**: CORS is configured via environment variables to restrict allowed origins.

---

## 10. Testing Strategy

### Unit Tests

| Test | Description |
|---|---|
| `test_password_hashing` | bcrypt hash/verify round-trip |
| `test_jwt_encode_decode` | JWT token issuance and verification |
| `test_jwt_expired_token` | Expired token is rejected |
| `test_refresh_token_hash` | SHA-256 hash is computed correctly |
| `test_api_key_generation` | API key format and entropy |
| `test_permission_levels` | Role hierarchy comparisons |
| `test_rate_limiter` | Failed attempts counter and lockout |

### Repository Tests

| Test | Description |
|---|---|
| `test_user_repository_create` | Create user with unique email |
| `test_user_repository_duplicate_email` | Duplicate email raises integrity error |
| `test_organization_repository_crud` | Organization CRUD |
| `test_membership_repository_unique` | Duplicate membership raises integrity error |
| `test_refresh_token_repository_lookup` | Token hash lookup |
| `test_api_key_repository_revoke` | Key revocation status |

### Service Tests

| Test | Description |
|---|---|
| `test_auth_register_creates_user_org_membership` | Full registration flow |
| `test_auth_login_valid_credentials` | Successful login |
| `test_auth_login_invalid_password` | Failed login |
| `test_auth_refresh_token_rotation` | Old token revoked, new token issued |
| `test_auth_refresh_breach_detection` | Reused revoked token revokes all |
| `test_organization_crud` | Org creation and management |
| `test_membership_invite` | Invitation flow |
| `test_membership_role_change` | Role upgrade/downgrade |
| `test_api_key_create_and_authenticate` | Key creation and usage |
| `test_api_key_revoke` | Key is rejected after revocation |
| `test_tenant_isolation` | User A cannot access Org B's data |

### Integration Tests

| Test | Description |
|---|---|
| `test_register_endpoint` | POST /auth/register returns 201 |
| `test_login_endpoint` | POST /auth/login returns tokens |
| `test_authenticated_endpoint` | GET /auth/me with valid token returns 200 |
| `test_unauthenticated_endpoint` | GET /auth/me without token returns 401 |
| `test_cross_tenant_access` | User from Org A gets 403 on Org B resource |
| `test_api_key_authentication` | API key on header authenticates correctly |
| `test_organization_membership_list` | GET members returns role-appropriate list |
| `test_permission_enforcement` | Viewer cannot create companies |

### PostgreSQL Tests

| Test | Description |
|---|---|
| `test_auth_postgresql_migration` | Auth migrations apply cleanly to PostgreSQL |
| `test_auth_postgresql_crud` | Auth CRUD works on PostgreSQL |
| `test_tenant_isolation_postgresql` | Cross-tenant access blocked on PostgreSQL |

### Expected Test Count

Approximately 30 unit tests + 10 integration tests + 3 PostgreSQL tests = 43 new tests.

---

## 11. Migration Strategy

### Migration 1: Auth Schema (YYYYMMDD_0006)

Creates tables:
- `users`
- `organizations`
- `memberships`
- `refresh_tokens`
- `password_reset_tokens`
- `api_keys`

All tables use the existing naming convention and `op.f()` wrappers for PostgreSQL compatibility.

### Migration 2: Tenant Columns (YYYYMMDD_0007)

Adds `organization_id` column to:
- `companies` (nullable, FK → organizations.id, CASCADE)
- All child tables (nullable, FK → organizations.id, SET NULL)

Creates indexes on all new `organization_id` columns.

### Backfill Strategy

- New deployments (no existing data): Set `organization_id` as NOT NULL from the start.
- Existing deployments with data: Add columns as nullable. Migrate existing `companies` data to an organization. Backfill `organization_id` on `companies`. Then set `organization_id` as NOT NULL on `companies`.

---

## 12. Risks and Tradeoffs

### Risk: Multi-Tenancy Adds Complexity to Every Query

Every tenant-scoped query now requires an `organization_id` filter. This increases the surface area for bugs where a query omits the filter and leaks data across tenants.

**Mitigation**: Integration tests specifically verify cross-tenant isolation. The repository layer provides base filtering that new query methods inherit. Code review enforces organization_id inclusion.

### Risk: Token Rotation Breach Detection May Cause Inconvenience

If a user's refresh token is revoked due to suspected breach (reuse of a previously revoked token), all their active sessions are terminated. This can happen if a network issue causes a client to retry with an already-used refresh token.

**Mitigation**: The breach detection includes a grace window. A reused token is logged as a warning on the first occurrence. Only the second reuse within the token's lifetime triggers full revocation.

### Risk: API Key Without Rotation

Initial API keys have no automatic rotation mechanism. A leaked API key remains valid until manually revoked.

**Mitigation**: API keys include an optional `expires_at` field. The design recommends setting expiration for programmatic keys. A future enhancement can add auto-rotation.

### Risk: No External Identity Provider

The current design does not support SSO, OAuth, or social login. Organizations that require SAML/OIDC integration cannot use the platform.

**Mitigation**: The authentication model is designed to accommodate external providers. A future `external_identities` table can link a user's platform account to an external identity without changing the core auth model.

### Risk: Rate Limiting Is In-Memory

The rate limiter uses an in-memory counter. If the application runs multiple processes or is restarted, rate limit counters reset. This makes the rate limiter ineffective against distributed attacks.

**Mitigation**: For the initial stage, in-memory rate limiting is sufficient for basic brute-force protection. A production deployment should use a Redis-backed rate limiter. The rate limiter interface is designed to be swappable.

### Risk: Password Reset Token Is Returned in API Response

The initial design returns the password reset token in the API response body because there is no email-sending infrastructure. This makes password reset less secure.

**Mitigation**: This is a documented limitation. The token is short-lived (15 minutes) and single-use. Email integration should be added before production use.

### Design Conflict: None

All architectural conflicts with existing Irtiqa patterns were evaluated in Section 2. No blocking conflicts were found.

---

## Architecture Summary

| Layer | New Files | Modified Files |
|---|---|---|
| Models | 6 (`user.py`, `organization.py`, `membership.py`, `refresh_token.py`, `password_reset_token.py`, `api_key.py`) | Existing models (add `organization_id`) |
| Repositories | 6 | Existing repositories (add org filtering) |
| Services | 4 (`auth_service.py`, `organization_service.py`, `membership_service.py`, `api_key_service.py`) | Existing services (add org parameter) |
| Schemas | 4 (`auth.py`, `organization.py`, `membership.py`, `api_key.py`) | None |
| API | 4 (`auth.py`, `organizations.py`, `memberships.py`, `api_keys.py`) | `router.py` (register new routes) |
| Core | `security.py` | `config.py`, `errors.py` |
| Migration | 2 (`0006_auth_schema.py`, `0007_tenant_columns.py`) | None |

## Database Summary

| New Tables | 6 |
|---|---|
| Modified Tables | 10 (all existing + `organization_id`) |
| New Indexes | ~15 |
| New Migrations | 2 |

## Security Summary

| Feature | Status |
|---|---|
| Password hashing | bcrypt, work factor 12 |
| Access tokens | JWT HS256, 15 min expiry |
| Refresh tokens | Opaque 64-byte hex, SHA-256 hash in DB, 7 day expiry |
| Token rotation | Yes — old token revoked on refresh |
| Breach detection | Yes — reused revoked token revokes all sessions |
| API keys | `irt_sk_` prefix, SHA-256 hash storage, revocable |
| Rate limiting | In-memory, 5 attempts/minute per IP+email |
| Audit logging | Structured logs for all auth events |
| Cross-tenant protection | Database query filtering + API dependency injection |

## Risks Discovered

1. **No email infrastructure** — Password reset tokens are returned in API responses.
2. **In-memory rate limiting** — Resets on restart, ineffective in multi-process deployments.
3. **API key self-service only** — No auto-rotation or expiration enforcement.
4. **No external identity provider** — SSO/OAuth requires future work.
5. **Tenant filter bug surface** — Every new query must include `organization_id`.

## Recommended Next Milestone

**Issue #15: Auth Implementation (Phase 1)**

Implement the authentication foundation first, without multi-tenancy:

1. Add `passlib[bcrypt]` and `PyJWT` dependencies.
2. Create `app/core/security.py` (password hashing, JWT, token generation).
3. Create `users` table and `User` model + repository + service.
4. Implement `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/refresh`, `/auth/me`.
5. Add JWT authentication dependency (`get_current_user`).
6. Test the full auth flow.

This provides the authentication foundation. Multi-tenancy (organizations, memberships, API keys, tenant-scoped queries) is Phase 2.

**Issue #16: Multi-Tenancy Implementation (Phase 2)**

After auth is operational:

1. Create organizations, memberships, API keys tables and models.
2. Implement org CRUD, membership management, API key management.
3. Add `organization_id` to existing tables.
4. Implement tenant-scoped queries and cross-tenant protection.
5. Test tenant isolation.
