# Commit 11 Implementation Report: Discovery Engine Background Execution

## Summary
Integrated the Discovery Engine API with the background job infrastructure using the **Progress Token pattern**. The API endpoint creates a `DiscoveryRun` record immediately (providing a tracking token), schedules a background workflow job, and returns the run to the client. The workflow resumes the existing run instead of creating a duplicate, enabling retry-safe asynchronous execution while preserving the existing API contract from Commit 6.

## Files Created
1. `tests/integration/api/test_discovery_api_background_execution.py` (6 tests)
2. `tests/unit/test_workflow_context.py` (7 tests)
3. `docs/commit_11_implementation_report.md`

## Files Modified
1. `app/api/v1/endpoints/discovery.py`
2. `app/workflows/discovery_pipeline.py`
3. `app/workflows/context.py`
4. `app/agents/context.py`
5. `tests/integration/test_discovery_pipeline_workflow.py`

## Architecture Decision: Progress Token Pattern (Option A)

The implementation uses the **Progress Token pattern**:
- API creates the `DiscoveryRun` immediately (status: `"running"`)
- API schedules a background job with the `run_id` in context
- API returns the `DiscoveryRunRead` response (unchanged contract)
- Workflow resumes the existing run if `discovery_run_id` is provided
- Workflow creates a new run if `discovery_run_id` is absent (legacy/direct invocation)

This design was chosen over making the workflow the single owner of run creation because:
1. **API contract stability**: HTTP 202 must return `DiscoveryRunRead` with `run_id` for client polling
2. **Retry safety**: Run is created once before job execution loop, avoiding duplicate creation on retries
3. **Idempotency**: Workflow can safely fetch the existing run multiple times
4. **Client experience**: Immediate tracking token without two-hop polling (job → run)

## Implementation Details

### 1. API Endpoint Changes (`app/api/v1/endpoints/discovery.py`)

**Lines 107-140** — Modified `trigger_discovery_run`:
- Added `JobService` dependency injection
- Created `DiscoveryRun` via `DiscoveryRunService.start_run()` (preserves existing behavior)
- Scheduled `discovery_pipeline` workflow job with run_id and search_id in options
- Returned `DiscoveryRunRead` (unchanged response contract)

**Imports** — Added `get_job_service`, `JobService`, `WorkflowContext`

### 2. Workflow Resume Logic (`app/workflows/discovery_pipeline.py`)

**Lines 47-56** — Added run resumption support in `execute()`:
- Check if `context.options["discovery_run_id"]` exists
- If present: fetch the existing run via `run_service.get_run()`
- If absent: create a new run via `run_service.start_run()` (legacy behavior)
- Both paths set `run_id` for subsequent workflow logic

**Benefits**:
- Supports both API-triggered (with pre-created run) and direct invocation (creates run)
- Retry-safe: fetching an existing run is idempotent
- Tenant isolation: `get_run()` validates `organization_id` matches

### 3. Context Validator Changes

**`app/workflows/context.py` (Lines 35-39)** — Relaxed validator:
- **Before**: `if self.company_id is None and self.contact_id is None: raise`
- **After**: `if self.organization_id is None and self.company_id is None and self.contact_id is None: raise`
- **Reason**: Discovery workflows are organization-scoped (no company/contact required)

**`app/agents/context.py` (Lines 16, 26, 43-46)** — Similar relaxation:
- Changed `company_id` from required to optional (`str | None`)
- Updated validator to accept organization-only contexts
- **Reason**: `DiscoveryAgent` operates at organization level, validates `organization_id` presence

### 4. Test Coverage

**New tests** (`test_discovery_api_background_execution.py`):
- `test_discovery_run_schedules_background_job` — Verifies job creation with correct payload
- `test_discovery_run_api_contract_unchanged` — Confirms API response matches Commit 6 contract
- `test_discovery_run_idempotency_no_duplicate_runs` — Validates multiple triggers create separate runs
- `test_discovery_run_archived_search_validation` — Ensures archived searches cannot be run
- `test_discovery_run_job_payload_structure` — Verifies job payload contains run_id and search_id
- `test_discovery_run_multiple_searches_independent_jobs` — Confirms independent job scheduling

**Enhanced tests** (`test_discovery_pipeline_workflow.py`):
- `test_discovery_pipeline_resumes_existing_run_when_provided` — Validates workflow resume behavior
- `test_discovery_pipeline_creates_run_when_not_provided` — Confirms legacy direct invocation works
- `test_discovery_pipeline_validates_existing_run_organization_id` — Enforces tenant isolation on resume
- `test_discovery_pipeline_supports_organization_only_context` — Tests organization-scoped execution

**New unit tests** (`test_workflow_context.py`):
- 7 tests validating `WorkflowContext` validator accepts organization-only, company-only, contact-only, or all identifiers
- Validates immutability and frozen options behavior

## Verification Results
- `python -m pytest`: **599 passed**, 27 skipped (PostgreSQL), 0 failures
- `python -m alembic check`: No new upgrade operations detected
- `git diff --check`: Passed (only CRLF info warning)

## API Contract Preservation

The `POST /discovery/searches/{search_id}/run` endpoint contract remains **identical** to Commit 6:
- **Request**: Same (no body)
- **Response**: HTTP 202 with `DiscoveryRunRead` (same shape, same fields)
- **Behavior**: Run is created immediately, status is `"running"`, client can poll `/discovery/runs/{run_id}`

**What changed internally**: Execution is now asynchronous via background job instead of synchronous workflow invocation.

## Workflow Flexibility

The workflow supports two entry points:
1. **API-triggered** (new): Run pre-created, `discovery_run_id` in context options
2. **Direct invocation** (legacy): No `discovery_run_id`, workflow creates the run

This design:
- Maintains backward compatibility for tests and admin tools
- Supports retry-safe execution from jobs (run already exists)
- Preserves single owner principle (DiscoveryRunService owns creation in both paths)

## No Database Changes

- No migrations created
- No model modifications
- No repository changes
- No schema changes to `DiscoveryRun` or `DiscoverySearch`

## Integration Wiring

The workflow was already registered in the `WorkflowRegistry` (Commit 10). This commit:
- Connects the API endpoint to `JobService.schedule_workflow()`
- Passes the run_id through job payload → workflow context → workflow execution
- No changes to `JobRunner`, `WorkflowRunner`, or job infrastructure

## Edge Cases Handled

1. **Job retry after failure**: Workflow fetches existing run (idempotent)
2. **Archived search**: API validation prevents run creation before job scheduling
3. **Tenant isolation**: Both API and workflow validate organization_id at every layer
4. **Missing run_id in context**: Workflow creates run (supports direct invocation)
5. **Wrong organization run_id**: Workflow fails with entity not found (tenant isolation)

## Notes

- The 27 skipped tests are PostgreSQL-specific tests requiring `DATABASE_URL=postgresql+psycopg://...` — consistent with all previous commits.
- No changes to provider implementations, agent logic, or external discovery sources.
- The Progress Token pattern is a standard async API design: create tracking entity → schedule work → return tracking ID → client polls status.
