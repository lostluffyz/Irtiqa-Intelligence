> **Status: IMPLEMENTED**

# Multi-Tenancy Implementation: Architecture Audit & Execution Plan

## 1. Current State Assessment

### Completed (Issue #14 — Auth Foundation)

| Component | Status | Details |
|---|---|---|
| User model | ✅ `User` with email, password, soft-delete | No organization association |
| Auth service | ✅ Register, login, logout, refresh, verify, delete | No org creation during registration |
| JWT auth | ✅ RS256, 15-min access, 7-day refresh | JWT has `sub` but no `org` or `role` claims |
| Email verification | ✅ Required before login | No org context needed |
| Rate limiting | ✅ Database-backed | No org context needed |
| Account deletion | ✅ Soft delete | Token revoked, user blocked |
| Password reset | ⏭️ Deferred (Phase 3) | 501 until email infra exists |
| API keys | ❌ Not implemented | Planned for Phase 2 |
| Organizations | ❌ Not implemented | **Entire Phase 2** |
| Memberships | ❌ Not implemented | **Entire Phase 2** |
| Tenant isolation | ❌ Not implemented | **Entire Phase 2** |
| Agent/workflow org context | ❌ Not implemented | **Entire Phase 2** |

### Auth Token Payload (Current)

```python
# Current JWT payload — no organization or role
{
    "sub": "user-uuid",
    "type": "access",
    "iss": "irtiqa-api",
    "aud": "irtiqa-client",
    "kid": "key-v1"
}
```

### Auth Service (Current Limitations)

- `AuthService.register()` creates a User but does **not** create an Organization or Membership.
- `AuthService.login()` returns tokens with no `org` or `role` claims.
- `create_access_token()` accepts optional `organization_id` and `role` but they are never passed.

---

## 2. Gap Analysis

### Gap 1: No Organization Model

The `organizations` table does not exist. Every domain entity (`companies`, `contacts`, etc.) has no `organization_id` column. There is no way to associate data with a tenant.

**Required**: New `Organization` model with `name`, `slug`, `status` columns. Unique index on `slug`.

### Gap 2: No Membership Model

The `memberships` table does not exist. Users have no association to organizations. There is no role data.

**Required**: New `Membership` model with `user_id`, `organization_id`, `role` columns. Unique composite index on `(user_id, organization_id)`. Check constraint on `role` values.

### Gap 3: No Invitation Model

The v2 design specifies an `invitations` table for the two-step invitation flow. This does not exist.

**Required**: New `Invitation` model with `organization_id`, `invited_by_id`, `email`, `role`, `token_hash`, `expires_at`, `accepted_at`.

### Gap 4: No API Key Models or Authentication

The `api_keys` table does not exist. The `X-API-Key` authentication path is not implemented.

**Required**: New `ApiKey` model. New `ApiKeyService`. API key authentication dependency. API key CRUD endpoints.

### Gap 5: No TenantContext or Tenant Isolation

The `TenantContext` object does not exist. No `BaseRepository` enforcement of `organization_id` filtering. Existing repositories and services have no tenant-awareness.

**Required**: `TenantContext` dataclass. `BaseRepository._apply_tenant_filter()` method. Updated service methods accepting `organization_id`.

### Gap 6: No organization_id on Domain Entities

All 10 domain tables (`companies`, `contacts`, `websites`, `technologies`, `intent_signals`, `intelligence_scores`, `outreach_messages`, `evidence_records`, `agent_runs`, `jobs`) lack an `organization_id` column.

**Required**: Migration 2 (add nullable `organization_id` + FK → `organizations.id` + CASCADE). Migration 3 (backfill). Migration 4 (set NOT NULL).

### Gap 7: AgentContext and WorkflowContext Lack organization_id

`AgentContext` and `WorkflowContext` have no `organization_id` field. Agents and workflows cannot scope their operations to a tenant.

**Required**: Add `organization_id` as a required field to both context models. Update `JobRunner` to pass `organization_id` from job payloads.

### Gap 8: JWT Tokens Don't Carry Org/Role Claims

The `create_access_token()` function accepts `organization_id` and `role` parameters but `AuthService.login()` never passes them. The `get_current_user` dependency returns `User` data without org/role context.

**Required**: After login, if the user has memberships, include `org` and `role` claims in the JWT. Add `get_current_organization` dependency that performs a membership verification database lookup.

### Gap 9: Registration Doesn't Create an Organization

`AuthService.register()` creates only a User. The v2 design specifies that registration should create an Organization and an Owner membership alongside the User.

**Required**: Extend registration flow to create Organization + Owner membership. Add `slug` generation with collision resolution.

### Gap 10: No Role/Permission Infrastructure

The `require_role()` helper function described in the v2 design does not exist. There is no permission-checking infrastructure in the service layer.

**Required**: `require_role()` helper. Service-layer permission checks on all create/update/delete operations for tenant-scoped entities.

---

## 3. Required Schema Changes

### New Tables (Migration 1)

| Table | Key Columns | Indexes |
|---|---|---|
| `organizations` | `id`, `name`, `slug` (unique), `status` | Unique on `slug`, index on `status` |
| `memberships` | `id`, `user_id` (FK), `organization_id` (FK), `role` | Unique on `(user_id, org_id)`, index on `org_id`, `user_id` |
| `invitations` | `id`, `org_id` (FK), `email`, `role`, `token_hash` (unique), `expires_at`, `accepted_at` | Unique on `token_hash`, index on `email` |
| `api_keys` | `id`, `org_id` (FK), `name`, `key_prefix`, `key_hash` (unique), `role`, `expires_at`, `revoked_at` | Unique on `key_hash`, index on `org_id` |

### Modified Tables (Migration 2)

All 10 existing domain tables gain an `organization_id` column:

| Table | FK | On Delete |
|---|---|---|
| `companies` | → `organizations.id` | CASCADE |
| `contacts` | → `organizations.id` | CASCADE |
| `websites` | → `organizations.id` | CASCADE |
| `technologies` | → `organizations.id` | CASCADE |
| `intent_signals` | → `organizations.id` | CASCADE |
| `intelligence_scores` | → `organizations.id` | CASCADE |
| `outreach_messages` | → `organizations.id` | CASCADE |
| `evidence_records` | → `organizations.id` | CASCADE |
| `agent_runs` | → `organizations.id` | CASCADE |
| `jobs` | → `organizations.id` | CASCADE |

Each receives a composite index `(organization_id, company_id)` for query performance.

### Backfill (Migration 3)

A data migration script that:
1. For each domain row with NULL `organization_id`, looks up `company → organization_id`.
2. Sets `organization_id` on each row.
3. Reports rows that could not be backfilled (missing company references).

### NOT NULL Enforcement (Migration 4)

Sets `organization_id` to `NOT NULL` on all 10 tables after backfill is verified.

---

## 4. Required Service-Layer Changes

### New Services

| Service | Repository | Methods |
|---|---|---|
| `OrganizationService` | `OrganizationRepository` | `create`, `get`, `update`, `delete`, `list_by_user` |
| `MembershipService` | `MembershipRepository` | `create`, `get`, `list_by_org`, `list_by_user`, `update_role`, `remove`, `transfer_ownership` |
| `InvitationService` | `InvitationRepository` | `create`, `accept`, `revoke`, `list_by_org` |
| `ApiKeyService` | `ApiKeyRepository` | `create`, `authenticate`, `list_by_org`, `revoke` |

### Modified Services

| Service | Changes |
|---|---|
| `AuthService.register()` | Add org + membership creation after user creation |
| `AuthService.login()` | Include `org_id` and `role` in JWT claims |
| `CompanyService` | Accept `organization_id` parameter. Add `require_role` checks on create/update/delete. |
| `ContactService` | Same pattern |
| `WebsiteService` | Same pattern |
| `TechnologyService` | Same pattern |
| `IntentSignalService` | Same pattern |
| `IntelligenceScoreService` | Same pattern |
| `OutreachMessageService` | Same pattern |
| `AgentRunService` | Same pattern |
| `JobService` | Same pattern |

### Infrastructure

| Component | Changes |
|---|---|
| `TenantContext` | New frozen dataclass: `organization_id`, `user_id`, `role`, `is_api_key` |
| `BaseRepository._apply_tenant_filter()` | New method. Automatically adds `WHERE organization_id = :org_id` when the model has that column. |
| `get_current_organization()` | New FastAPI dependency. Performs membership lookup on every request. |
| `require_role()` | New helper function. Compares `current_role` against `minimum_role` level. |

---

## 5. Required API Changes

### New Endpoints

| Method | Path | Min Role | Purpose |
|---|---|---|---|
| `GET` | `/organizations` | — | List user's organizations |
| `GET` | `/organizations/{org_id}` | viewer | Org details |
| `PATCH` | `/organizations/{org_id}` | admin | Update org |
| `DELETE` | `/organizations/{org_id}` | owner | Delete org |
| `GET` | `/organizations/{org_id}/members` | viewer | List members |
| `POST` | `/organizations/{org_id}/members` | admin | Invite member |
| `DELETE` | `/organizations/{org_id}/members/{user_id}` | admin | Remove member |
| `POST` | `/organizations/{org_id}/transfer` | owner | Transfer ownership |
| `GET` | `/organizations/{org_id}/api-keys` | admin | List API keys |
| `POST` | `/organizations/{org_id}/api-keys` | admin | Create API key |
| `DELETE` | `/organizations/{org_id}/api-keys/{key_id}` | admin | Revoke API key |
| `POST` | `/invitations/{token}/accept` | — | Accept invitation |
| `POST` | `/auth/switch-organization` | — | Switch active org |

### Modified Endpoints (Post-Multi-Tenancy)

All existing CRUD endpoints (`/companies`, `/contacts`, `/websites`, etc.) must be updated to:
1. Accept `TenantContext` dependency.
2. Pass `organization_id` to service methods.
3. Apply `require_role()` checks for create/update/delete operations.

---

## 6. Ordered Execution Phases

### Phase 1: Organization & Membership Foundation

**Duration**: Priority — builds the core tenant structure.

| Step | Files | Description |
|---|---|---|
| 1.1 | `app/models/organization.py` | `Organization` model: `id`, `name`, `slug` (unique), `status` |
| 1.2 | `app/models/membership.py` | `Membership` model: `user_id`, `organization_id`, `role`, unique composite index |
| 1.3 | `app/repositories/organization_repository.py` | `OrganizationRepository` |
| 1.4 | `app/repositories/membership_repository.py` | `MembershipRepository` |
| 1.5 | `app/services/organization_service.py` | `OrganizationService`: create, get, update, delete, list_by_user |
| 1.6 | `app/services/membership_service.py` | `MembershipService`: create, remove, update_role, list_by_org, list_by_user, transfer_ownership, last-owner protection |
| 1.7 | `app/schemas/organization.py` | `OrganizationCreate`, `OrganizationRead`, `OrganizationList` |
| 1.8 | `app/schemas/membership.py` | `MembershipRead`, `MembershipList`, `RoleUpdate` |
| 1.9 | Migration 1 | Create `organizations`, `memberships` tables |
| 1.10 | API endpoints | `GET /organizations`, `GET /organizations/{id}`, `PATCH /organizations/{id}`, `DELETE /organizations/{id}`, `GET /organizations/{id}/members`, `POST /organizations/{id}/members`, `DELETE /organizations/{id}/members/{user_id}`, `POST /organizations/{id}/transfer` |

### Phase 2: TenantContext & Tenant Isolation

**Duration**: Parallel with Phase 1 — required before domain changes.

| Step | Files | Description |
|---|---|---|
| 2.1 | `app/core/tenant.py` | `TenantContext` dataclass. `require_role()` helper. |
| 2.2 | `app/api/dependencies.py` | Add `get_current_organization()` dependency with membership verification |
| 2.3 | `app/repositories/base.py` | Add `_apply_tenant_filter()` method to `BaseRepository`. Add tenant-scoped query warning. |
| 2.4 | `AuthService.register()` | Extend to create org + owner membership |
| 2.5 | `AuthService.login()` | Include `org_id` and `role` in JWT claims |
| 2.6 | `create_access_token()` | No change needed — already accepts `organization_id` and `role` |
| 2.7 | `app/core/errors.py` | Add `PermissionError` if not exists |

### Phase 3: Domain Tenant Columns

**Duration**: Depends on Phase 1 + 2.

| Step | Files | Description |
|---|---|---|
| 3.1 | Migration 2 | Add `organization_id` to all 10 existing tables (nullable, FK, CASCADE) |
| 3.2 | Migration 3 (backfill) | Data migration script for existing rows |
| 3.3 | Migration 4 | Set `organization_id` to `NOT NULL` after backfill verification |
| 3.4 | Existing models | Add `organization_id` column + FK to each model |
| 3.5 | Existing repositories | Add `organization_id` filtering to all query methods |
| 3.6 | Existing services | Add `organization_id` parameter to all create/update/delete methods. Add `require_role` checks. |
| 3.7 | Existing API endpoints | Add `TenantContext` dependency. Pass `organization_id` to services. |

### Phase 4: Agent & Workflow Tenant Context

**Duration**: Can overlap with Phase 3.

| Step | Files | Description |
|---|---|---|
| 4.1 | `app/agents/context.py` | Add `organization_id: str` required field |
| 4.2 | `app/workflows/context.py` | Add `organization_id: str` required field |
| 4.3 | `app/jobs/runner.py` | Pass `organization_id` from job payload to context |
| 4.4 | `app/workflows/runner.py` | Pass `organization_id` from context to workflow |
| 4.5 | Pipeline workflow | No change needed — context carries org_id |
| 4.6 | Score refresh workflow | No change needed — context carries org_id |

### Phase 5: Invitations & API Keys

**Duration**: Final phase — depends on org/membership infrastructure.

| Step | Files | Description |
|---|---|---|
| 5.1 | `app/models/invitation.py` | `Invitation` model |
| 5.2 | `app/models/api_key.py` | `ApiKey` model with `role` field |
| 5.3 | Migration 5 | Create `invitations`, `api_keys` tables |
| 5.4 | `app/services/invitation_service.py` | Create, accept, revoke |
| 5.5 | `app/services/api_key_service.py` | Create (return once), authenticate, list, revoke |
| 5.6 | `app/core/security.py` | `generate_api_key()` already implemented (unused) |
| 5.7 | API endpoints | Invitation endpoints + API key CRUD |
| 5.8 | Auth dependency | Add `X-API-Key` authentication path |

---

## 7. Risks and Security Considerations

### Risk 1: Tenant Isolation Gap Between Migration and Code

During Phase 3, after Migration 2 adds `organization_id` as nullable but before service-layer enforcement is complete, existing queries will not filter by organization. This creates a window where cross-tenant data is accessible.

**Mitigation**: Deploy Phase 3 as a single atomic change — migration + model + repository + service changes together. The nullable migration is safe because services filter by `organization_id` before the column is set to NOT NULL.

### Risk 2: Actor Role Verification on Every Request

The `get_current_organization()` dependency performs a membership database lookup on every authenticated request. If the `memberships` table is not properly indexed, this adds latency to every API call.

**Mitigation**: Index `(user_id, organization_id)` as a composite index — this is already in the schema design. The lookup is a single indexed query.

### Risk 3: Registration Flow Change

Extending `AuthService.register()` to create an Organization + Membership changes the API contract. Existing clients that call `/auth/register` will now receive a 500 error if the registration fails during org creation (e.g., slug collision, database constraint).

**Mitigation**: Wrap org + membership creation in the same transaction as user creation. If any step fails, the entire registration is rolled back. Add slug collision resolution with random suffix.

### Risk 4: Backfill Completeness

The backfill script must process all 10 domain tables and handle edge cases where `company_id` is NULL (orphaned rows). If any row is missed, Migration 4 (NOT NULL) will fail.

**Mitigation**: Run the backfill validation query (from v2 design, Section 7) before Migration 4. Verify zero NULL `organization_id` values across all 10 tables.

### Risk 5: API Key Authentication Path Overlaps with JWT

The v2 design resolves F-3 by using `X-API-Key` header for API keys and `Authorization: Bearer` for JWT tokens. The authentication dependency must first check the header name, then the prefix — not the other way around.

**Mitigation**: Implement as two independent dependencies: `authenticate_request` that delegates to either `authenticate_jwt` or `authenticate_api_key` based on header presence, never falling through from one to the other.

### Risk 6: Existing Data Cannot Be Backfilled

If existing deployments have `companies` rows with NULL `organization_id` and no way to determine the owning organization, the backfill cannot proceed.

**Mitigation**: New deployments (no data) set `organization_id` as NOT NULL from the start. Existing deployments require a manual mapping step before backfill — assign each existing company to an organization.

### Risk 7: Permission Model Is Not Fine-Grained Enough

The v2 permission matrix has 4 roles (owner, admin, member, viewer) with fixed permissions. A future requirement for per-resource permissions (e.g., "can view companies but not contacts") would require a redesign.

**Mitigation**: Accept the current model for Phase 2. A future enhancement can add a permission registry or resource-level ACL without changing the membership/role structure.

---

## 8. Estimated Implementation Timeline

| Phase | Description | Files | Tests | Dependencies |
|---|---|---|---|---|
| 1 | Organization & Membership | ~15 new + ~5 modified | ~20 | Phase 0 (auth) complete |
| 2 | TenantContext & Isolation | ~3 new + ~5 modified | ~10 | Phase 1 |
| 3 | Domain Tenant Columns | ~2 migrations + ~30 modified | ~30 | Phase 1 + 2 |
| 4 | Agent/Workflow Context | ~4 modified | ~5 | Phase 2 |
| 5 | Invitations & API Keys | ~10 new + ~5 modified | ~15 | Phase 1 |
| **Total** | | **~40 new + ~50 modified** | **~80 new tests** | |

**Total new test count**: ~80 (bringing the suite to approximately 455).

---

## 9. Summary: Is the Codebase Ready for Multi-Tenancy?

| Question | Answer |
|---|---|
| User model supports multi-org? | **No** — no organization or membership associations |
| Organization model exists? | **No** — must be created |
| Membership model exists? | **No** — must be created |
| Role/permission model exists? | **No** — `require_role()` not implemented |
| Tenant isolation exists? | **No** — no `TenantContext`, no `organization_id` on any table |
| API key model exists? | **No** — `generate_api_key()` is implemented but unused |
| AgentContext has org_id? | **No** — must be added |
| WorkflowContext has org_id? | **No** — must be added |
| JWT has org/role claims? | **No** — `create_access_token` accepts them but `login()` never passes them |
| Registration creates org? | **No** — user-only, must be extended |
| `BaseRepository` supports tenant filtering? | **No** — `_apply_tenant_filter()` not implemented |
| All 10 domain tables have `organization_id`? | **No** — schema change required |
| Backfill strategy defined? | **Not yet implemented** — strategy is designed |
| Migration sequence defined? | **Yes** — 4 migrations in design |

**Readiness verdict**: The auth foundation is complete and operational. Multi-tenancy requires adding ~40 new files, modifying ~50 existing files, 4–5 new migrations, and approximately 80 new tests. The codebase is structurally ready — the patterns are in place (BaseService, BaseRepository, Alembic, FastAPI DI) — but no multi-tenancy code exists yet.
