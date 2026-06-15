# Multi-Tenancy Phase 1: Organization & Membership Design

## 1. Scope

This document defines Phase 1 of the multi-tenancy implementation. Phase 1 creates the core organizational structure — `Organization` and `Membership` entities — without modifying any existing domain entities, authentication flows, or agent/workflow infrastructure.

### In Scope

- `Organization` model, repository, service, schemas, API endpoints
- `Membership` model, repository, service, schemas, API endpoints
- Alembic migration creating `organizations` and `memberships` tables
- Slug generation with collision resolution
- Owner-protection rules (cannot remove/change the last owner)
- Membership role management

### Explicitly Out of Scope

- `organization_id` on existing domain tables (Phase 3)
- `TenantContext` and `BaseRepository._apply_tenant_filter()` (Phase 2)
- JWT org/role claims (Phase 2)
- `AuthService.register()` extension to create orgs (Phase 2)
- `AuthService.login()` org/role claims (Phase 2)
- Invitations workflow (Phase 5)
- API Keys (Phase 5)
- AgentContext/WorkflowContext changes (Phase 4)
- `require_role()` permission helper (Phase 2)

---

## 2. Schema Design

### 2.1 organizations

| Column | Type | Required | Default | Notes |
|---|---|---|---|---|
| `id` | UUID/Text PK | Yes | — | UUID primary key |
| `name` | String(200) | Yes | — | Organization display name |
| `slug` | String(100) | Yes | — | URL-friendly unique identifier. Lowercase, hyphenated. |
| `status` | String(50) | Yes | `"active"` | `active`, `suspended`, `cancelled` |
| `created_at` | DateTime(tz) | Yes | `utc_now` | UTC timestamp |
| `updated_at` | DateTime(tz) | Yes | `utc_now` | UTC timestamp |

**Indexes:**
- Unique index on `slug` (application-level slug collision resolution prevents duplicates).
- Index on `status` (for admin listing/filtering).

**Check constraints:**
- `status IN ('active', 'suspended', 'cancelled')`

### 2.2 memberships

| Column | Type | Required | Default | Notes |
|---|---|---|---|---|
| `id` | UUID/Text PK | Yes | — | UUID primary key |
| `user_id` | UUID/Text FK | Yes | — | FK → `users.id`, CASCADE delete |
| `organization_id` | UUID/Text FK | Yes | — | FK → `organizations.id`, CASCADE delete |
| `role` | String(50) | Yes | `"member"` | `owner`, `admin`, `member`, `viewer` |
| `created_at` | DateTime(tz) | Yes | `utc_now` | UTC timestamp |
| `updated_at` | DateTime(tz) | Yes | `utc_now` | UTC timestamp |

**Indexes:**
- Unique composite index on `(user_id, organization_id)` — a user can have only one membership per org.
- Index on `organization_id` (for org-scoped member listing).
- Index on `user_id` (for user-scoped org listing).
- Index on `role` (for role-scoped filtering).

**Check constraints:**
- `role IN ('owner', 'admin', 'member', 'viewer')`

**Foreign keys:**
- `user_id` → `users.id`, `ON DELETE CASCADE`
- `organization_id` → `organizations.id`, `ON DELETE CASCADE`

### 2.3 Model Patterns

Both models follow the existing conventions:

```python
class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended', 'cancelled')", name="status"),
        Index("ix_organizations_slug", "slug", unique=True),
        Index("ix_organizations_status", "status"),
    )
```

```python
class Membership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner', 'admin', 'member', 'viewer')", name="role"),
        Index("ix_memberships_user_org", "user_id", "organization_id", unique=True),
        Index("ix_memberships_organization_id", "organization_id"),
        Index("ix_memberships_user_id", "user_id"),
    )
```

**Relationships:**

- `Organization.memberships: list[Membership]` — back-populates from `Membership.organization`.
- `Organization` has no direct `User` relationship — users are accessed through memberships.
- `User.memberships: list[Membership]` — added to the `User` model in Phase 2 (when auth is extended).
- `Membership.user: User` — FK to users table.
- `Membership.organization: Organization` — FK to organizations table.

### 2.4 Slug Generation

Slugs are generated from the organization name using a simple slugify function with collision resolution:

```python
import re
import secrets

def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from an organization name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        slug = "org"
    return slug

def generate_unique_slug(name: str, session: Session) -> str:
    """Generate a unique slug, appending a random suffix on collision."""
    base = generate_slug(name)
    candidate = base
    for _ in range(10):
        existing = session.scalar(
            select(Organization).where(Organization.slug == candidate)
        )
        if existing is None:
            return candidate
        suffix = secrets.token_hex(4)  # 8-char random hex
        candidate = f"{base}-{suffix}"
    # Final fallback — extremely unlikely
    return f"{base}-{secrets.token_hex(8)}"
```

---

## 3. Repository Design

### 3.1 OrganizationRepository

Extends `BaseRepository[Organization]`.

| Method | Signature | Returns | SQL |
|---|---|---|---|
| `get_by_slug` | `(slug: str)` | `Organization \| None` | `WHERE slug = :slug` |
| `list_by_user` | `(user_id: str, *, limit, offset)` | `Sequence[Organization]` | `JOIN memberships ON orgs.id = memberships.org_id WHERE memberships.user_id = :uid` |

**Convention:** Follows existing repository patterns — accepts `Session` via constructor, does not commit, returns ORM entities.

### 3.2 MembershipRepository

Extends `BaseRepository[Membership]`.

| Method | Signature | Returns | SQL |
|---|---|---|---|
| `get_by_user_and_org` | `(user_id: str, organization_id: str)` | `Membership \| None` | `WHERE user_id = :uid AND organization_id = :oid` |
| `list_by_org` | `(organization_id: str, *, limit, offset)` | `Sequence[Membership]` | `WHERE organization_id = :oid` |
| `list_by_user` | `(user_id: str, *, limit, offset)` | `Sequence[Membership]` | `WHERE user_id = :uid` |
| `count_owners` | `(organization_id: str)` | `int` | `SELECT COUNT(*) WHERE organization_id = :oid AND role = 'owner'` |

---

## 4. Service Design

### 4.1 OrganizationService

Extends `BaseService[Organization, OrganizationRepository]`.

| Method | Description | Role Check | Owner Protection |
|---|---|---|---|
| `create(name, slug=None)` | Create organization. Auto-generates slug if not provided. | None (anyone can create) | First user gets owner membership via MembershipService |
| `get(org_id)` | Get org by ID | None (public query) | No |
| `update(org_id, **values)` | Update org name or status | admin | Cannot change status of an org with only one owner? |
| `delete(org_id)` | Delete org and all CASCADE data | owner | Yes |
| `list_by_user(user_id)` | List orgs for a user | None | No |

**Edge cases:**
- `create` with a name that generates a duplicate slug must retry with a suffix.
- `delete` must verify the caller is an owner of the org (not just any owner of any org).
- `update` must verify the caller has `admin` role in the target org.
- An organization with `status='suspended'` should prevent membership operations.

### 4.2 MembershipService

Extends `BaseService[Membership, MembershipRepository]`.

| Method | Description | Role Check | Owner Protection |
|---|---|---|---|
| `create(user_id, org_id, role, actor_role)` | Add a member to an org | `actor_role` must be admin or owner | Cannot create a second owner without existing owner approval |
| `get(membership_id)` | Get by ID | None | No |
| `list_by_org(org_id, *, limit, offset)` | List org members | None | No |
| `list_by_user(user_id, *, limit, offset)` | List user's memberships | None | No |
| `update_role(membership_id, new_role, actor_role)` | Change a member's role | `actor_role` must be admin or owner | Cannot downgrade the last owner. Cannot change to `owner` without existing owner approval |
| `remove(membership_id, actor_role)` | Remove a member | `actor_role` must be admin or owner | Cannot remove the last owner |
| `transfer_ownership(org_id, current_owner_id, new_owner_id)` | Transfer ownership | Both must be members | Changes `current_owner` to `admin`, sets `new_owner` to `owner` in a single transaction |

**Owner protection invariants (enforced by all mutation methods):**

1. An organization must always have at least one member with `role=owner`.
2. The last owner cannot be removed, have their role downgraded from `owner`, or leave the org.
3. Ownership transfer is the only way to change the owner — it swaps roles atomically.

**Slug resolution helper:**

`OrganizationService.create()` calls `generate_unique_slug()` before persisting to avoid `IntegrityError` on the unique `slug` column. This is a service-layer concern, not a database-layer concern.

---

## 5. Schema Design

### 5.1 Organization Schemas

```python
class OrganizationCreate(IrtiqaSchema):
    name: str = Field(min_length=1, max_length=200)

class OrganizationUpdate(IrtiqaSchema):
    name: str | None = Field(default=None, min_length=1, max_length=200)

class OrganizationRead(IrtiqaSchema):
    id: str
    name: str
    slug: str
    status: str
    created_at: datetime

class OrganizationList(ListSchema):
    items: list[OrganizationRead]
```

Following existing conventions: `Create`, `Update`, `Read`, `List` with `IrtiqaSchema` base and `from_attributes=True`.

### 5.2 Membership Schemas

```python
class MembershipRead(IrtiqaSchema):
    id: str
    user_id: str
    organization_id: str
    role: str
    created_at: datetime

class MembershipList(ListSchema):
    items: list[MembershipRead]

class RoleUpdateRequest(IrtiqaSchema):
    role: str = Field(min_length=1, max_length=50)

class TransferOwnershipRequest(IrtiqaSchema):
    new_owner_id: str = Field(min_length=36, max_length=36)
```

---

## 6. API Design

### 6.1 Organization Endpoints

| Method | Path | Auth | Min Role | Request Body | Response | Status |
|---|---|---|---|---|---|---|
| `POST` | `/organizations` | Bearer | — (any auth user) | `OrganizationCreate` | `OrganizationRead` | 201 |
| `GET` | `/organizations` | Bearer | — | — | `OrganizationList` | 200 |
| `GET` | `/organizations/{org_id}` | Bearer | viewer | — | `OrganizationRead` | 200 |
| `PATCH` | `/organizations/{org_id}` | Bearer | admin | `OrganizationUpdate` | `OrganizationRead` | 200 |
| `DELETE` | `/organizations/{org_id}` | Bearer | owner | — | — | 204 |

### 6.2 Membership Endpoints

| Method | Path | Auth | Min Role | Request Body | Response | Status |
|---|---|---|---|---|---|---|
| `GET` | `/organizations/{org_id}/members` | Bearer | viewer | — | `MembershipList` | 200 |
| `POST` | `/organizations/{org_id}/members` | Bearer | admin | `RoleUpdateRequest` (user_id + role) | `MembershipRead` | 201 |
| `PATCH` | `/organizations/{org_id}/members/{user_id}` | Bearer | admin | `RoleUpdateRequest` | `MembershipRead` | 200 |
| `DELETE` | `/organizations/{org_id}/members/{user_id}` | Bearer | admin | — | — | 204 |
| `POST` | `/organizations/{org_id}/transfer` | Bearer | owner | `TransferOwnershipRequest` | `MembershipRead` (new owner's) | 200 |

### 6.3 Path Design Rationale

Membership endpoints are nested under `/organizations/{org_id}` because memberships always exist within an organization context. This matches the existing pattern of nested resources.

The `POST /organizations/{org_id}/members` endpoint requires a `user_id` in the request body (not a `membership_id` in the path) because the member doesn't have a membership record until the endpoint creates one. The `PATCH` and `DELETE` variants use `user_id` in the path as the identifier because it's stable and known to the caller.

### 6.4 Error Responses

| Condition | Status | Code |
|---|---|---|
| Org not found | 404 | `irtiqa.entity_not_found` |
| Membership not found | 404 | `irtiqa.entity_not_found` |
| Duplicate membership | 409 | `irtiqa.entity_conflict` |
| Insufficient permissions | 403 | `irtiqa.forbidden` |
| Cannot remove last owner | 409 | `irtiqa.entity_conflict` |
| Invalid role value | 422 | `irtiqa.request_validation_error` |
| Slug collision | 409 | `irtiqa.entity_conflict` |

---

## 7. Migration Plan

### Migration 1: Create Organizations and Memberships (YYYYMMDD_0006)

```python
def upgrade() -> None:
    # ── organizations ──────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_index("ix_organizations_status", "organizations", ["status"])

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_organizations_status"),
            "status IN ('active', 'suspended', 'cancelled')",
        )

    # ── memberships ────────────────────────────────────────────────────
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default=sa.text("'member'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_memberships_user_org", "memberships", ["user_id", "organization_id"], unique=True)
    op.create_index("ix_memberships_organization_id", "memberships", ["organization_id"])
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])

    with op.batch_alter_table("memberships") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_memberships_role"),
            "role IN ('owner', 'admin', 'member', 'viewer')",
        )


def downgrade() -> None:
    op.drop_table("memberships")
    op.drop_table("organizations")
```

Note: `server_default` for `status` uses `sa.text("'active'")` — SQLAlchemy text with properly quoted string literal, compatible with both SQLite and PostgreSQL.

### Migration Naming

The current head is `20260612_0005` (auth tables). The next migration is `20260613_0006`.

### Rollback

Drop `memberships` table first (respects FK order), then `organizations`.

---

## 8. Testing Plan

### 8.1 Unit Tests

| Test | What It Verifies |
|---|---|
| `test_organization_create` | Slug generation, default status |
| `test_organization_duplicate_slug` | Slug collision generates unique slug |
| `test_membership_unique_constraint` | Same user+org raises IntegrityError |
| `test_membership_role_validation` | Invalid role raises CheckConstraint error |
| `test_organization_repository_get_by_slug` | Slug lookup works |
| `test_membership_repository_get_by_user_and_org` | Composite lookup works |
| `test_membership_repository_count_owners` | Owner count is accurate |
| `test_membership_repository_list_by_org` | Org-scoped listing |
| `test_organization_service_create` | Org creation with auto-slug |
| `test_organization_service_list_by_user` | User-scoped org listing |
| `test_membership_service_create` | Member creation |
| `test_membership_service_update_role` | Role change |
| `test_membership_service_remove_last_owner_blocked` | Last owner cannot be removed |
| `test_membership_service_transfer_ownership` | Owner → admin, target → owner |
| `test_organization_slug_generation` | Multiple name variations produce valid slugs |

### 8.2 Integration Tests

| Test | What It Verifies |
|---|---|
| `test_create_organization_endpoint` | POST /organizations returns 201 |
| `test_list_organizations_endpoint` | GET /organizations returns user's orgs |
| `test_get_organization_endpoint` | GET /organizations/{id} returns org |
| `test_update_organization_endpoint` | PATCH /organizations/{id} updates name |
| `test_delete_organization_endpoint` | DELETE /organizations/{id} returns 204 |
| `test_add_member_endpoint` | POST /organizations/{id}/members returns 201 |
| `test_list_members_endpoint` | GET /organizations/{id}/members returns members |
| `test_change_role_endpoint` | PATCH /organizations/{id}/members/{uid} changes role |
| `test_remove_member_endpoint` | DELETE /organizations/{id}/members/{uid} returns 204 |
| `test_transfer_ownership_endpoint` | POST /organizations/{id}/transfer swaps roles |
| `test_unauthorized_access` | Requests without auth return 401 |
| `test_forbidden_operation` | Viewer cannot create members |

### 8.3 Estimated Test Count

Approximately 20 unit tests + 12 integration tests = **32 new tests**.

---

## 9. Risks

### Risk 1: Membership Endpoint Authorization Requires get_current_user

Membership endpoints require knowing the authenticated user's role in the target organization to enforce permissions. The existing `get_current_user` dependency returns user identity without org context. Since Phase 1 does not include `get_current_organization` (Phase 2), the membership endpoints must accept the `organization_id` from the URL path and look up the caller's membership to determine their role.

**Mitigation**: Endpoints that require role checks will do a membership lookup inside the endpoint or service:

```python
def add_member(
    org_id: str,
    payload: AddMemberRequest,
    current_user: dict = Depends(get_current_user),
    membership_service: MembershipService = Depends(get_membership_service),
):
    # Look up caller's role in this org
    caller_membership = membership_service.get_by_user_and_org(
        current_user["id"], org_id
    )
    if caller_membership is None or caller_membership.role not in ("admin", "owner"):
        raise HTTPException(403, ...)
    # Proceed...
```

This is a temporary pattern. Phase 2 will replace it with the `get_current_organization` dependency which performs this lookup centrally.

### Risk 2: No Transactional Consistency for Multi-Service Operations

Operations like "create org + create owner membership" span two services (OrganizationService + MembershipService). Each service owns its own transaction via `_run_in_transaction()`. If org creation succeeds but membership creation fails, the org exists without an owner.

**Mitigation**: For the initial Phase 1, org and membership creation will be done in a single `_run_in_transaction()` call in `OrganizationService.create()`. The service calls both repository operations within the same session, ensuring atomicity. This is consistent with the existing pattern where `AuthService.register()` creates both a user and a verification token in a single transaction.

### Risk 3: Slug Collision After Failed Create

If slug generation encounters a collision on the final retry, the create operation raises an `IntegrityError` which is caught by `BaseService._run_in_transaction()` and wrapped in `EntityConflictError`. The caller receives a 409 response.

**Mitigation**: The 10-attempt slug generation loop makes collision astronomically unlikely. The service-layer slug generation prevents the database-level `IntegrityError` from ever being raised.

### Risk 4: DELETE /organizations/{id} Has No Cascade in Application Code

The migration uses `ON DELETE CASCADE` on both `memberships.organization_id` and `memberships.user_id`. This means deleting an organization automatically deletes all its memberships. The application code does not need to handle cascading explicitly. This is consistent with existing patterns (e.g., `users` table cascades to `refresh_tokens`).

**Mitigation**: No application code change needed. The CASCADE is handled at the database level. PostgreSQL and SQLite both support CASCADE.

---

## 10. Files Expected to Be Created

- `app/models/organization.py`
- `app/models/membership.py`
- `app/repositories/organization_repository.py`
- `app/repositories/membership_repository.py`
- `app/services/organization_service.py`
- `app/services/membership_service.py`
- `app/schemas/organization.py`
- `app/schemas/membership.py`
- `app/api/v1/endpoints/organizations.py`
- `database/migrations/versions/YYYYMMDD_0006_create_organizations_memberships.py`
- `tests/unit/test_organization_model.py`
- `tests/unit/test_membership_model.py`
- `tests/unit/test_organization_service.py`
- `tests/unit/test_membership_service.py`
- `tests/integration/api/test_organizations.py`

## 11. Files Expected to Be Modified

- `app/models/__init__.py` (export `Organization`, `Membership`)
- `app/repositories/__init__.py` (export `OrganizationRepository`, `MembershipRepository`)
- `app/services/__init__.py` (export `OrganizationService`, `MembershipService`)
- `app/api/dependencies.py` (add `get_organization_service`, `get_membership_service`)
- `app/api/v1/router.py` (register organization routes)
- `tests/unit/test_models.py` (add org/membership to metadata + PK/timestamp tests)
- `tests/integration/test_migrations.py` (update `EXPECTED_TABLES` and revision)

## 12. Implementation Order

```text
1. Migration
2. Models
3. Repositories
4. Services
5. Schemas
6. API endpoints
7. Router registration
8. Dependency providers
9. Unit tests
10. Integration tests
11. Documentation updates
12. Final verification (pytest, alembic check, compileall)
```
