> **Status: IMPLEMENTED**

# Multi-Tenancy Phase 1: Implementation Tasks

## Task 1: Database Migration

### Objective

Create the Alembic migration that adds the `organizations` and `memberships` tables with all columns, constraints, indexes, and foreign keys. The migration must apply cleanly to both SQLite and PostgreSQL.

### Files Created

| File | Action |
|---|---|
| `database/migrations/versions/20260613_0006_create_organizations_memberships.py` | Create |

### Files Modified

None.

### Dependencies

- Current alembic head is `20260612_0005`. This migration chains from it.

### Verification Steps

```text
python -m alembic upgrade head
python -m alembic check
python -m alembic downgrade -1
python -m alembic upgrade head
```

### Tests Required

- Existing migration test (`tests/integration/test_migrations.py`) will verify the revision and table presence when updated in Task 14.

### Expected Commit Message

```text
feat(db): create organizations and memberships tables

Add Alembic migration 20260613_0006 creating two new tables:

- organizations: id, name, slug (unique), status with CHECK constraint
- memberships: id, user_id (FK→users), organization_id (FK→organizations),
               role with CHECK constraint, unique composite index
- All indexes, FKs with CASCADE, and op.f() constraint wrappers
  for PostgreSQL compatibility
```

---

## Task 2: Organization Model

### Objective

Create the `Organization` SQLAlchemy model with the centralized slug generation function. Follow existing patterns (`UUIDPrimaryKeyMixin`, `TimestampMixin`, `Base`, `Mapped[...]`, `mapped_column`).

### Files Created

| File | Action |
|---|---|
| `app/models/organization.py` | Create |

### Files Modified

| File | Change |
|---|---|
| `app/models/__init__.py` | Add `Organization` import and `__all__` export |

### Dependencies

- Task 1 (migration must exist)

### Verification Steps

```text
python -c "from app.models.organization import Organization; print(Organization.__tablename__)"
python -c "from app.models.organization import generate_slug, generate_unique_slug; print('slug functions OK')"
python -m compileall app/models/
```

### Tests Required

None in this task — model tests are in Task 12.

### Expected Commit Message

```text
feat(models): add Organization model with slug generation

- Organization model with name, slug, status, timestamps
- generate_slug() and generate_unique_slug() helpers
- CheckConstraint on status, unique index on slug
```

---

## Task 3: Membership Model

### Objective

Create the `Membership` SQLAlchemy model with role constraint and composite unique index. No `User.memberships` relationship yet (Phase 2 adds that when auth is extended).

### Files Created

| File | Action |
|---|---|
| `app/models/membership.py` | Create |

### Files Modified

| File | Change |
|---|---|
| `app/models/__init__.py` | Add `Membership` import and `__all__` export |

### Dependencies

- Task 1 (migration must exist)
- Task 2 (`Organization` model exists for relationship)

### Verification Steps

```text
python -c "from app.models.membership import Membership; print(Membership.__tablename__)"
python -m compileall app/models/
```

### Tests Required

None in this task — model tests are in Task 12.

### Expected Commit Message

```text
feat(models): add Membership model with role constraint

- Membership model with user_id, organization_id, role, timestamps
- Unique composite index on (user_id, organization_id)
- CheckConstraint on role values
- CASCADE foreign keys to users and organizations
```

---

## Task 4: Organization Repository

### Objective

Create `OrganizationRepository` extending `BaseRepository[Organization]` with custom slug lookup and user-scoped listing methods.

### Files Created

| File | Action |
|---|---|
| `app/repositories/organization_repository.py` | Create |

### Files Modified

| File | Change |
|---|---|
| `app/repositories/__init__.py` | Add `OrganizationRepository` import and `__all__` export |

### Dependencies

- Task 2 (Organization model exists)

### Verification Steps

```text
python -c "from app.repositories.organization_repository import OrganizationRepository; print('OK')"
python -m compileall app/repositories/
```

### Tests Required

None in this task — repository tests are in Task 12.

### Expected Commit Message

```text
feat(repos): add OrganizationRepository

- get_by_slug: slug lookup
- list_by_user: join through memberships
``` 

---

## Task 5: Membership Repository

### Objective

Create `MembershipRepository` extending `BaseRepository[Membership]` with composite lookup, org-scoped listing, user-scoped listing, and owner counting.

### Files Created

| File | Action |
|---|---|
| `app/repositories/membership_repository.py` | Create |

### Files Modified

| File | Change |
|---|---|
| `app/repositories/__init__.py` | Add `MembershipRepository` import and `__all__` export |

### Dependencies

- Task 3 (Membership model exists)

### Verification Steps

```text
python -c "from app.repositories.membership_repository import MembershipRepository; print('OK')"
python -m compileall app/repositories/
```

### Tests Required

None in this task — repository tests are in Task 12.

### Expected Commit Message

```text
feat(repos): add MembershipRepository

- get_by_user_and_org: composite lookup
- list_by_org, list_by_user: scoped listing
- count_owners: role-specific count
```

---

## Task 6: Organization Service

### Objective

Create `OrganizationService` extending `BaseService[Organization, OrganizationRepository]` with create (auto-slug), get, update, list_by_user. The create method generates a unique slug and creates the organization.

### Files Created

| File | Action |
|---|---|
| `app/services/organization_service.py` | Create |

### Files Modified

| File | Change |
|---|---|
| `app/services/__init__.py` | Add `OrganizationService` import and `__all__` export |

### Dependencies

- Task 2 (Organization model)
- Task 4 (OrganizationRepository)

### Verification Steps

```text
python -c "from app.services.organization_service import OrganizationService; print('OK')"
python -m compileall app/services/
```

### Tests Required

- `test_organization_service_create` — creates org with auto-generated slug
- `test_organization_service_list_by_user` — user-scoped listing

### Expected Commit Message

```text
feat(services): add OrganizationService

- create with auto-slug generation and collision resolution
- get, update, delete, list_by_user
- Uses generate_unique_slug() at the service layer
```

---

## Task 7: Membership Service

### Objective

Create `MembershipService` extending `BaseService[Membership, MembershipRepository]` with create, get, list_by_org, list_by_user, update_role, remove, transfer_ownership. Enforces last-owner protection invariants.

### Files Created

| File | Action |
|---|---|
| `app/services/membership_service.py` | Create |

### Files Modified

| File | Change |
|---|---|
| `app/services/__init__.py` | Add `MembershipService` import and `__all__` export |

### Dependencies

- Task 3 (Membership model)
- Task 5 (MembershipRepository)
- Task 6 (OrganizationService needed for transfer_ownership)

### Verification Steps

```text
python -c "from app.services.membership_service import MembershipService; print('OK')"
python -m compileall app/services/
```

### Tests Required

- `test_membership_service_create` — adds member
- `test_membership_service_update_role` — changes role
- `test_membership_service_remove_last_owner_blocked` — last owner protected
- `test_membership_service_transfer_ownership` — role swap
- `test_membership_service_remove_member` — removes member

### Expected Commit Message

```text
feat(services): add MembershipService with owner protection

- create, get, list_by_org, list_by_user, update_role, remove
- transfer_ownership: atomically swaps owner→admin, target→owner
- Enforces: org must have at least one owner at all times
- Prevents: removing or downgrading the last owner
```

---

## Task 8: Pydantic Schemas

### Objective

Create `OrganizationCreate`, `OrganizationUpdate`, `OrganizationRead`, `OrganizationList`, `MembershipRead`, `MembershipList`, `RoleUpdateRequest`, `TransferOwnershipRequest` schemas following existing Pydantic v2 conventions.

### Files Created

| File | Action |
|---|---|
| `app/schemas/organization.py` | Create |
| `app/schemas/membership.py` | Create |

### Files Modified

| File | Change |
|---|---|
| `app/schemas/__init__.py` | Add all new schema exports |

### Dependencies

- Task 2 (Organization model for field types)
- Task 3 (Membership model for field types)

### Verification Steps

```text
python -c "from app.schemas.organization import OrganizationCreate, OrganizationRead, OrganizationList; print('org schemas OK')"
python -c "from app.schemas.membership import MembershipRead, MembershipList; print('membership schemas OK')"
python -m compileall app/schemas/
```

### Tests Required

None in this task — schema serialization tests are in Task 12.

### Expected Commit Message

```text
feat(schemas): add Organization and Membership Pydantic schemas

- OrganizationCreate, OrganizationUpdate, OrganizationRead, OrganizationList
- MembershipRead, MembershipList, RoleUpdateRequest, TransferOwnershipRequest
- Following existing IrtiqaSchema conventions
```

---

## Task 9: Dependency Providers

### Objective

Add `get_organization_service()` and `get_membership_service()` FastAPI dependency providers.

### Files Created

None.

### Files Modified

| File | Change |
|---|---|
| `app/api/dependencies.py` | Add `OrganizationService`, `MembershipService` imports and `get_organization_service()`, `get_membership_service()` providers |

### Dependencies

- Task 6 (OrganizationService exists)
- Task 7 (MembershipService exists)

### Verification Steps

```text
python -c "
from app.api.dependencies import get_organization_service, get_membership_service
s1 = get_organization_service()
s2 = get_membership_service()
print('OrganizationService:', type(s1).__name__)
print('MembershipService:', type(s2).__name__)
"
```

### Tests Required

None — dependency providers are tested implicitly by API integration tests.

### Expected Commit Message

```text
feat(api): add OrganizationService and MembershipService dependencies
```

---

## Task 10: Organization API Endpoints

### Objective

Create the `/organizations` endpoints: create, list, get, update, delete with authentication and role-based permission checks. Role checks use the temporary membership-lookup pattern (will be replaced by `get_current_organization` in Phase 2).

### Files Created

| File | Action |
|---|---|
| `app/api/v1/endpoints/organizations.py` | Create |

### Files Modified

| File | Change |
|---|---|
| `app/api/v1/router.py` | Import and register `organizations_router` |

### Dependencies

- Task 8 (schemas exist)
- Task 9 (dependency providers exist)
- Task 6 (OrganizationService exists)
- Task 7 (MembershipService exists for role lookup)

### Verification Steps

```text
python -c "from app.api.v1.endpoints.organizations import router; print(len(router.routes), 'routes')"
python -m compileall app/api/
```

### Tests Required

Integration tests in Task 13.

### Expected Commit Message

```text
feat(api): add Organization CRUD endpoints

- POST /organizations (create org, any auth user)
- GET /organizations (list user's orgs)
- GET /organizations/{org_id} (get org details, viewer+)
- PATCH /organizations/{org_id} (update org, admin+)
- DELETE /organizations/{org_id} (delete org, owner only)
- Authorization via temporary membership lookup
```

---

## Task 11: Membership API Endpoints

### Objective

Create the membership management endpoints nested under `/organizations/{org_id}/members`. Includes add member, list members, change role, remove member, and transfer ownership.

### Files Created

| File | Action |
|---|---|
| `app/api/v1/endpoints/memberships.py` (or combined into `organizations.py`) | Create |

### Files Modified

| File | Change |
|---|---|
| `app/api/v1/router.py` | Import and register memberships router (if separate file) |

### Dependencies

- Task 10 (organization routes exist, path pattern established)
- Task 7 (MembershipService exists)
- Task 8 (membership schemas exist)

### Verification Steps

```text
python -c "from app.api.v1.endpoints.organizations import router; print([r.path for r in router.routes])"
python -m compileall app/api/
```

### Tests Required

Integration tests in Task 13.

### Expected Commit Message

```text
feat(api): add Membership management endpoints

- GET /organizations/{org_id}/members (list, viewer+)
- POST /organizations/{org_id}/members (add, admin+)
- PATCH /organizations/{org_id}/members/{user_id} (change role, admin+)
- DELETE /organizations/{org_id}/members/{user_id} (remove, admin+)
- POST /organizations/{org_id}/transfer (ownership, owner only)
```

---

## Task 12: Unit Tests

### Objective

Create all unit tests for Organization and Membership models, repositories, and services.

### Files Created

| File | Tests |
|---|---|
| `tests/unit/test_organization_model.py` | Organization model tests |
| `tests/unit/test_membership_model.py` | Membership model tests |
| `tests/unit/test_organization_service.py` | OrganizationService tests |
| `tests/unit/test_membership_service.py` | MembershipService tests |

### Files Modified

None.

### Dependencies

- Task 2 (Organization model)
- Task 3 (Membership model)
- Task 4 (OrganizationRepository)
- Task 5 (MembershipRepository)
- Task 6 (OrganizationService)
- Task 7 (MembershipService)

### Tests to Implement

**Model tests (8):**

| Test | Description |
|---|---|
| `test_organization_model_create` | Organization instance with valid data |
| `test_organization_slug_generation` | `generate_slug` handles various inputs |
| `test_organization_slug_collision` | `generate_unique_slug` appends suffix on collision |
| `test_organization_model_constraints` | Invalid status raises IntegrityError |
| `test_membership_model_create` | Membership instance with valid data |
| `test_membership_model_constraints` | Invalid role raises IntegrityError |
| `test_membership_unique_user_org` | Duplicate user+org raises IntegrityError |
| `test_membership_relationships` | FK to user and org persist correctly |

**Repository tests (6):**

| Test | Description |
|---|---|
| `test_organization_repository_get_by_slug` | Slug lookup returns correct org |
| `test_organization_repository_list_by_user` | User has correct orgs |
| `test_membership_repository_get_by_user_and_org` | Composite lookup |
| `test_membership_repository_list_by_org` | Org-scoped member list |
| `test_membership_repository_list_by_user` | User-scoped membership list |
| `test_membership_repository_count_owners` | Owner count is accurate |

**Service tests (8):**

| Test | Description |
|---|---|
| `test_organization_service_create` | Org created with auto-slug |
| `test_organization_service_create_slug_collision` | Collision resolved with suffix |
| `test_organization_service_list_by_user` | User's orgs returned |
| `test_organization_service_delete` | Org deleted (CASCADE removes memberships) |
| `test_membership_service_create` | Member added to org |
| `test_membership_service_update_role` | Role changed successfully |
| `test_membership_service_remove_last_owner_blocked` | Last owner cannot be removed |
| `test_membership_service_transfer_ownership` | Target becomes owner, source becomes admin |

**Total: 22 unit tests.**

### Verification Steps

```text
python -m pytest tests/unit/test_organization_model.py -v
python -m pytest tests/unit/test_membership_model.py -v
python -m pytest tests/unit/test_organization_service.py -v
python -m pytest tests/unit/test_membership_service.py -v
python -m pytest tests/unit/   # confirm existing still pass
```

### Expected Commit Message

```text
test: add Organization and Membership unit tests

22 unit tests covering:
- Model creation, constraints, relationships (8)
- Repository queries, slug lookup, owner counting (6)
- Service create, update, delete, owner protection (8)
```

---

## Task 13: Integration Tests

### Objective

Create API integration tests for all Organization and Membership endpoints. Use the existing `TestClient` + `api_session_factory` pattern from other integration tests.

### Files Created

| File | Tests |
|---|---|
| `tests/integration/api/test_organizations.py` | Organization and membership API tests |

### Files Modified

None.

### Dependencies

- Task 10 (Organization endpoints exist)
- Task 11 (Membership endpoints exist)
- Task 9 (dependency providers exist)

### Tests to Implement

**Organization API tests (5):**

| Test | Description |
|---|---|
| `test_create_organization` | POST /organizations returns 201 with org data |
| `test_list_organizations` | GET /organizations returns user's orgs |
| `test_get_organization` | GET /organizations/{id} returns org details |
| `test_update_organization` | PATCH /organizations/{id} updates name |
| `test_delete_organization` | DELETE /organizations/{id} returns 204 |

**Membership API tests (7):**

| Test | Description |
|---|---|
| `test_add_member` | POST /organizations/{id}/members returns 201 |
| `test_list_members` | GET /organizations/{id}/members returns member list |
| `test_change_member_role` | PATCH updates role correctly |
| `test_remove_member` | DELETE removes member |
| `test_transfer_ownership` | POST /transfer swaps roles |
| `test_remove_last_owner_blocked` | Last owner removal returns 409 |
| `test_unauthorized_access` | No auth returns 401 |

**Total: 12 integration tests.**

### Verification Steps

```text
python -m pytest tests/integration/api/test_organizations.py -v
python -m pytest   # confirm no regressions
```

### Expected Commit Message

```text
test: add Organization and Membership API integration tests

12 integration tests covering:
- Org CRUD (create, list, get, update, delete) — 5 tests
- Membership management (add, list, role, remove, transfer) — 7 tests
- Authorization enforcement and owner protection
```

---

## Task 14: Documentation and Final Verification

### Objective

Update project documentation, test metadata, and run final verification.

### Files Created

None.

### Files Modified

| File | Change |
|---|---|
| `tests/unit/test_models.py` | Add `Organization`, `Membership` to metadata table set and PK/timestamp test list |
| `tests/integration/test_migrations.py` | Add `organizations`, `memberships` to `EXPECTED_TABLES`. Update revision assertion to `20260613_0006`. |
| `docs/project_state.md` | Mark Phase 1 complete, update test count, update architecture status |
| `docs/project_handoff.md` | Mark Phase 1 complete, add org/membership to architecture |

### Dependencies

- All prior tasks complete.

### Verification Steps

```text
python -m pytest
python -m alembic check
python -m compileall app tests
```

### Expected Commit Message

```text
docs: update project state and test metadata for multi-tenancy Phase 1

- Add organizations and memberships to EXPECTED_TABLES
- Update migration revision assertion
- Add Organization and Membership to model metadata tests
- Update project state and handoff documents
```

---

## Implementation Order

```text
Task  1: Migration                              ┐
Task  2: Organization model                      │ model layer
Task  3: Membership model                       ┘
Task  4: Organization repository                 ┐
Task  5: Membership repository                   │ data access layer
Task  6: Organization service                    ┐
Task  7: Membership service                      │ business logic layer
Task  8: Pydantic schemas                       ┘
Task  9: Dependency providers                   ┐
Task 10: Organization endpoints                  │ API layer
Task 11: Membership endpoints                   ┘
Task 12: Unit tests                              ┐
Task 13: Integration tests                       │ test layer
Task 14: Documentation + final verification     ┘
```

Each task is independently CI-verifiable. The workflow is:

1. `python -m compileall app/` after the model layer (Tasks 1-3)
2. `python -m compileall app/` after the data access layer (Tasks 4-5)
3. `python -m compileall app/` after the service layer (Tasks 6-7)
4. `python -m compileall app/` after schemas + API (Tasks 8-11)
5. `python -m pytest` after unit tests (Task 12)
6. `python -m pytest` after integration tests (Task 13)
7. Full verification after docs (Task 14)

---

## Files Summary (Cumulative)

### New Files (14)

| # | File | Created In |
|---|---|---|
| 1 | `database/migrations/versions/20260613_0006_create_organizations_memberships.py` | Task 1 |
| 2 | `app/models/organization.py` | Task 2 |
| 3 | `app/models/membership.py` | Task 3 |
| 4 | `app/repositories/organization_repository.py` | Task 4 |
| 5 | `app/repositories/membership_repository.py` | Task 5 |
| 6 | `app/services/organization_service.py` | Task 6 |
| 7 | `app/services/membership_service.py` | Task 7 |
| 8 | `app/schemas/organization.py` | Task 8 |
| 9 | `app/schemas/membership.py` | Task 8 |
| 10 | `app/api/v1/endpoints/organizations.py` | Tasks 10-11 |
| 11 | `tests/unit/test_organization_model.py` | Task 12 |
| 12 | `tests/unit/test_membership_model.py` | Task 12 |
| 13 | `tests/unit/test_organization_service.py` | Task 12 |
| 14 | `tests/unit/test_membership_service.py` | Task 12 |
| 15 | `tests/integration/api/test_organizations.py` | Task 13 |

### Modified Files (8)

| # | File | Created In |
|---|---|---|
| 1 | `app/models/__init__.py` | Tasks 2-3 |
| 2 | `app/repositories/__init__.py` | Tasks 4-5 |
| 3 | `app/services/__init__.py` | Tasks 6-7 |
| 4 | `app/schemas/__init__.py` | Task 8 |
| 5 | `app/api/dependencies.py` | Task 9 |
| 6 | `app/api/v1/router.py` | Tasks 10-11 |
| 7 | `tests/unit/test_models.py` | Task 14 |
| 8 | `tests/integration/test_migrations.py` | Task 14 |
| 9 | `docs/project_state.md` | Task 14 |
| 10 | `docs/project_handoff.md` | Task 14 |

---

## Test Count Summary

| Task | New Tests | Type |
|---|---|---|
| 12 | 8 | Model unit tests |
| 12 | 6 | Repository unit tests |
| 12 | 8 | Service unit tests |
| 13 | 5 | Organization API integration tests |
| 13 | 7 | Membership API integration tests |
| **Total** | **34** | |

Final test count: 375 (before) + 34 = **409 passed, 27 skipped**.

---

## Commit Boundaries

| Commit | Tasks | Verification |
|---|---|---|
| 1 | Task 1 | `alembic upgrade head`, `alembic check`, `downgrade`, `re-upgrade` |
| 2 | Tasks 2-3 | `compileall app/models/` |
| 3 | Tasks 4-5 | `compileall app/repositories/` |
| 4 | Tasks 6-7 | `compileall app/services/` |
| 5 | Tasks 8-9 | `compileall app/schemas/`, `compileall app/api/` |
| 6 | Tasks 10-11 | `compileall app/api/`, `pytest` (existing) |
| 7 | Tasks 12 | `pytest tests/unit/` |
| 8 | Tasks 13 | `pytest` |
| 9 | Task 14 | `pytest`, `alembic check`, `compileall app tests` |

**Total: 9 commits.**
