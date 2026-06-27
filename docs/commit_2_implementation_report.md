# Commit 2 Implementation Report: Discovery Engine ORM Models

## Date: 2026-06-27

## Summary
Successfully implemented the Discovery Engine ORM models (Commit 2) as specified in the lead discovery engine architecture. All models, relationships, and tests pass. Zero schema drift detected.

## Changes Made

### New Files
1. **`app/models/discovery_search.py`** — New `DiscoverySearch` model for ICP search criteria
   - Columns: `id`, `organization_id`, `name`, `description`, `criteria`, `status`, `last_run_at`, `total_discovered`, `created_at`, `updated_at`
   - Check constraint: `status IN ('active', 'archived')`
   - Index: `ix_discovery_searches_organization_id`
   - Relationships: `organization` → Organization, `discovery_runs` → DiscoveryRun (cascade delete), `companies` → Company

2. **`app/models/discovery_run.py`** — New `DiscoveryRun` model for execution tracking
   - Columns: `id`, `organization_id`, `search_id`, `status`, `sources_queried`, `companies_found`, `companies_created`, `companies_skipped`, `started_at`, `finished_at`, `error_message`, `created_at`, `updated_at`
   - Check constraint: `status IN ('running', 'succeeded', 'failed')`
   - Indexes: `ix_discovery_runs_organization_id`, `ix_discovery_runs_search_id`, `ix_discovery_runs_status`
   - Relationships: `organization` → Organization, `search` → DiscoverySearch

### Modified Files
3. **`app/models/company.py`** — Extended with discovery provenance columns
   - Added `discovered_via` (String(100), nullable)
   - Added `discovery_search_id` (String(36), FK to discovery_searches.id, SET NULL)
   - Added `discovery_score` (Float, default=0.0, nullable=False)
   - Added `CheckConstraint` for `discovery_score` range `[0.0, 1.0]` — resets schema drift from Commit 1
   - Added `discovery_search` relationship to DiscoverySearch

4. **`app/models/organization.py`** — Added discovery relationships
   - Added `discovery_searches` relationship (cascade delete)
   - Added `discovery_runs` relationship (cascade delete)

5. **`app/models/__init__.py`** — Exported new models
   - Added `DiscoverySearch` and `DiscoveryRun` to imports and `__all__`

6. **`tests/unit/test_models.py`** — Updated model tests
   - Added `discovery_searches` and `discovery_runs` to `Base.metadata.tables` check
   - Added `DiscoverySearch` and `DiscoveryRun` to primary key and timestamp test
   - Updated `test_company_relationships_are_declared` to include `discovery_search`

7. **`tests/integration/test_migrations.py`** — Updated migration tests
   - Added `discovery_searches` and `discovery_runs` to `EXPECTED_TABLES`

## Verification Results

| Check | Result |
|-------|--------|
| Single Alembic head | ✅ 20260618_0008 |
| `alembic check` (schema drift) | ✅ No new upgrade operations detected |
| pytest (all 516 tests) | ✅ 489 passed, 27 skipped, 0 failures |
| Model metadata matches migration | ✅ All tables and columns match |
| Check constraints match | ✅ Status and score constraints validated |
| Downgrade test | ✅ All application tables removed on downgrade |

## Design Notes

- All models follow existing ORM conventions: `UUIDPrimaryKeyMixin`, `TimestampMixin`, `Base`
- `TYPE_CHECKING` guards prevent circular imports between `DiscoverySearch` and `Company`
- Foreign key names follow the pattern `fk_{table}_{abbrev}` established in the existing code
- Relationships use appropriate cascade strategies aligned with migration ON DELETE rules:
  - `discovery_searches.id` → `discovery_runs.search_id`: CASCADE
  - `discovery_searches.id` → `companies.discovery_search_id`: SET NULL (no cascade on companies)
  - `organizations.id` → `discovery_searches.organization_id`: CASCADE
  - `organizations.id` → `discovery_runs.organization_id`: CASCADE
- The `discovery_score` CHECK constraint resolves the schema drift introduced in Commit 1
