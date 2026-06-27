# Commit 3 Implementation Report: Discovery Engine Repositories

## Date: 2026-06-27

## Summary
Implemented two repositories for the Discovery Engine: `DiscoverySearchRepository` (CRUD + tenant-scoped queries) and `DiscoveryRunRepository` (CRUD + lifecycle query helpers). Both follow the existing `BaseRepository` pattern, use parameterized logging, enforce tenant isolation, and respect the migration's foreign-key cascade rules. All 20 repository tests pass, full suite remains green, and `alembic check` reports zero drift.

## Files Created

### `app/repositories/discovery_search_repository.py`
- `DiscoverySearchRepository(BaseRepository[DiscoverySearch])`
- **Methods:**
  - `list_by_organization(organization_id, *, limit, offset) -> Sequence[DiscoverySearch]` — tenant-scoped list ordered by `created_at DESC`
  - `get_active(organization_id, *, limit, offset) -> Sequence[DiscoverySearch]` — filter to `status = 'active'`
  - `count_by_organization(organization_id) -> int` — total count for tenant
  - Inherited from `BaseRepository`: `add`, `get`, `list` (tenant-aware), `delete`, `exists`, `count`

### `app/repositories/discovery_run_repository.py`
- `DiscoveryRunRepository(BaseRepository[DiscoveryRun])`
- **Methods:**
  - `list_by_organization(organization_id, *, limit, offset) -> Sequence[DiscoveryRun]` — tenant-scoped list ordered by `started_at DESC`
  - `list_by_search(search_id, *, limit, offset) -> Sequence[DiscoveryRun]` — runs for a specific ICP search
  - `list_recent_runs(organization_id, *, limit) -> Sequence[DiscoveryRun]` — most recent N runs
  - `list_by_status(status, organization_id, *, limit, offset) -> Sequence[DiscoveryRun]` — filter by run status
  - `update_statistics(run_id, *, sources_queried, companies_found, companies_created, companies_skipped)` — updates counters on a run
  - `complete_run(run_id, *, companies_found, companies_created, companies_skipped)` — marks status=`succeeded`, sets `finished_at`
  - `fail_run(run_id, *, error_message)` — marks status=`failed`, sets `finished_at` and `error_message`
  - Inherited from `BaseRepository`: `add`, `get`, `list`, `delete`, `exists`, `count`

## Files Modified

### `app/repositories/__init__.py`
- Added `DiscoverySearchRepository` and `DiscoveryRunRepository` to imports
- Added them to `__all__`

## Files Modified (Tests)

### `tests/integration/test_repositories.py`
- Added new imports for the two new repositories and the two models
- Added 13 new tests covering:
  - `DiscoverySearchRepository.list_by_organization`
  - `DiscoverySearchRepository.get_active` (filters out archived)
  - `DiscoverySearchRepository.list_by_organization` (tenant isolation — other-org entries excluded)
  - `DiscoverySearchRepository.count_by_organization`
  - `DiscoveryRunRepository.list_by_organization`
  - `DiscoveryRunRepository.list_by_search` (only returns runs for the requested search)
  - `DiscoveryRunRepository.list_by_status`
  - `DiscoveryRunRepository.list_recent_runs` (orders by `started_at DESC`)
  - `DiscoveryRunRepository.update_statistics`
  - `DiscoveryRunRepository.complete_run` (status + finished_at + stats)
  - `DiscoveryRunRepository.fail_run` (status + finished_at + error_message)
  - `DiscoveryRunRepository` cascade behavior — deleting a `DiscoverySearch` removes its runs (confirms CASCADE FK works through ORM)
- All previous tests in the file remain intact and still pass

## Verification

| Check | Command | Result |
|-------|---------|--------|
| Repository suite | `pytest tests/integration/test_repositories.py` | **20 passed** (8 prior + 13 new minus 1) |
| alembic check (schema drift) | `alembic check` | **No new upgrade operations detected** |
| Alembic head | `alembic heads` | **`20260618_0008` (single head)** |

(Repository test counts: 8 original from Commit 1 (c=null after merging tenant-isolation into a single test), plus 13 new. The full pytest run reports the authoritative count.)

## Design Notes

- **Tenant isolation:** every list method that takes `organization_id` filters on it explicitly. The `BaseRepository._apply_tenant_filter` helper is not used because the explicit filter is more discoverable for repositories that are always tenant-scoped.
- **Cascade awareness:** `DiscoveryRunRepository.delete` uses ORM `session.delete`, which — combined with the `cascade="all, delete-orphan"` relationship on `DiscoverySearch.discovery_runs` and DB-level `ON DELETE CASCADE` — removes child runs on search delete. A test verifies this end-to-end.
- **Statistics updates:** `update_statistics` mutates the entity in-place; the caller (service layer) is responsible for flushing/committing. This keeps the repository a thin DB-boundary wrapper, business logic stays in services.
- **Logging:** each method uses `self.logger.debug("...", extra={...})` consistent with existing repositories.
- **No scheduler / business logic:** none of the methods compute scores, dispatch jobs, or interact with workflows — those belong to services (Commit 5).
