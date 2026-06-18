> **Status: IMPLEMENTED**

# PostgreSQL Compatibility Verification — Implementation Checklist

## Phase 1 — Environment Audit

### 1.1 Verify current PostgreSQL support
- [ ] Confirm `psycopg[binary]` is declared in `pyproject.toml` under `[project.optional-dependencies] postgres`.
- [ ] Install `pip install -e ".[postgres]"` and verify no dependency resolution errors.
- [ ] Confirm `DATABASE_URL` in `app/core/config.py` accepts any connection string (currently defaults to `sqlite:///database/irtiqa.db`).
- [ ] Verify `DatabaseSettings.is_sqlite` property correctly detects `sqlite` prefix in the URL.

### 1.2 Verify engine configuration
- [ ] Read `app/database/engine.py` — confirm `is_sqlite` check already gates `check_same_thread` and SQLite PRAGMAs.
- [ ] Verify `create_engine()` call does not explicitly pass a `poolclass` — confirm SQLAlchemy's dialect-default pool class is acceptable (`NullPool` for SQLite, `QueuePool` for PostgreSQL).
- [ ] Verify `pool_pre_ping` is read from config and passed to `create_engine()` (already done at line 18).
- [ ] Verify SQLAlchemy dialect-default pool class behavior for SQLite and PostgreSQL.
- [ ] Confirm no explicit poolclass configuration is required.

### 1.3 Verify test infrastructure readiness
- [ ] Confirm `tests/conftest.py` currently uses SQLite-only fixtures (temporary database).
- [ ] Identify where a PostgreSQL test fixture should be added (gated on `DATABASE_URL` / postgres dependency).

**Files affected:**
- `app/database/engine.py` — review only; no changes expected.
- `app/core/config.py` — no changes expected (already supports any `DATABASE_URL`).
- `pyproject.toml` — no changes expected (postgres group already declared).

**Validation steps:**
- `python -c "from app.database.engine import create_database_engine; e = create_database_engine(); print(e.url)"` — succeeds with default SQLite URL.
- `DATABASE_URL=postgresql://... python -c "from app.database.engine import create_database_engine; e = create_database_engine(); print(e.url)"` — succeeds with PostgreSQL URL.

**Risks and edge cases:**
- Engine config change must not break existing SQLite behavior.
- `pool_pre_ping=True` with PostgreSQL is safe but adds a connection check on every checkout.
- SQLAlchemy dialect-default pool classes should be preserved unless a real PostgreSQL compatibility issue is discovered.

---

## Phase 2 — Engine Configuration Verification

### 2.1 Review SQLite-specific settings
- [ ] Confirm `check_same_thread=False` is only applied when `is_sqlite` is true (already gated in `engine.py:12-13`).
- [ ] Confirm `PRAGMA foreign_keys=ON` is only applied when `is_sqlite` is true (already gated in `engine.py:33-34`).
- [ ] Confirm `PRAGMA journal_mode=WAL` is only applied when `is_sqlite` is true (already gated in `engine.py:37-38`).
- [ ] Confirm `PRAGMA busy_timeout` is only applied when `is_sqlite` is true (already gated in `engine.py:35-36`).

### 2.2 Identify dialect-gated behavior
- [ ] List every code path that branches on `is_sqlite` (currently only in `engine.py`).
- [ ] Verify no code outside `app/database/` branches on the database dialect.
- [ ] Confirm `app/models/`, `app/repositories/`, `app/services/`, `app/workflows/`, `app/agents/`, `app/jobs/`, and `app/api/` contain no dialect-specific logic.

### 2.3 Verify pooling strategy
- [ ] Verify that `create_engine()` uses SQLAlchemy's dialect-default pool classes without explicit override.
- [ ] Confirm SQLAlchemy's SQLite dialect returns `NullPool` by default (SQLite dialect `get_pool_class()` behavior).
- [ ] Confirm SQLAlchemy's PostgreSQL dialect returns `QueuePool` with `pool_size=5`, `max_overflow=10` by default (`PGDialect.get_pool_class()` behavior).
- [ ] Ensure `pool_pre_ping` is forwarded regardless of dialect (already done at `engine.py:18`).
- [ ] Do NOT add explicit `poolclass` — preserve SQLAlchemy dialect defaults unless a real compatibility issue is found during verification.

**Files affected:**
- `app/database/engine.py` — no changes expected. Review only.

**Validation steps:**
- Create engine with default SQLite URL: `engine.pool.__class__.__name__ == 'NullPool'`.
- Create engine with PostgreSQL URL: `engine.pool.__class__.__name__ == 'QueuePool'`.
- No `PRAGMA` warnings or errors emitted for PostgreSQL connections.

**Risks and edge cases:**
- SQLAlchemy's dialect-default pool classes are already correct for both databases. Explicit override adds maintenance surface with zero compatibility benefit.
- If a future deployment requires non-default pool settings (e.g., larger `pool_size`), that should be configured through deployment-specific engine configuration, not through this milestone.

---

## Phase 3 — Migration Verification

### 3.1 Set up PostgreSQL test database
- [ ] Start local PostgreSQL instance (version 15 or 16).
- [ ] Create a dedicated test database: `CREATE DATABASE irtiqa_test;`.
- [ ] Set `DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa_test`.
- [ ] Confirm `python -m alembic upgrade head` succeeds against PostgreSQL.
- [ ] Confirm `python -m alembic check` reports no new operations.

### 3.2 Verify upgrade path for each migration
- [ ] Migration `20260531_0001` — verify all 9 tables are created with correct columns, indexes, and foreign keys.
- [ ] Migration `20260531_0002` — verify check constraints are applied to `companies.status`, `contacts.status`, `technologies.confidence`, `intent_signals.strength`, `intent_signals.confidence`, `intelligence_scores.*`, `outreach_messages.status`, `outreach_messages.confidence`, `agent_runs.status`.
- [ ] Migration `20260603_0003` — verify `raw_html` (Text, nullable) and `extracted_text` (Text, nullable) columns are added to `websites`.
- [ ] Migration `20260609_0003` — verify `jobs` table is created with check constraints (`status`, `job_type`, `retry_count <= max_retries`, `max_retries >= 0`), indexes (`ix_jobs_status_scheduled_at`, `ix_jobs_target_name`, `ix_jobs_agent_run_id`), and FK to `agent_runs`.

### 3.3 Verify downgrade path
- [ ] `alembic downgrade -1` from head — verify `jobs` table is removed.
- [ ] `alembic downgrade -1` — verify `raw_html`, `extracted_text` columns are removed from `websites`.
- [ ] `alembic downgrade -1` — verify check constraints are removed.
- [ ] `alembic downgrade -1` — verify all 9 tables are removed.
- [ ] `alembic upgrade head` — re-apply all migrations cleanly.

### 3.4 Verify Alembic behaviors
- [ ] `alembic check` at head reports no new upgrade operations.
- [ ] `alembic current` shows `20260609_0003` (latest revision).
- [ ] `alembic history` shows linear chain: `20260531_0001` ← `20260531_0002` ← `20260603_0003` ← `20260609_0003`.

**Files affected:**
- No migration files should be modified — verification only.

**Validation steps:**
- `python -m alembic upgrade head` — 0 errors.
- `python -m alembic check` — "No new upgrade operations detected."
- `python -m alembic downgrade -1` — 4 times to reach base; each succeeds.
- `python -m alembic upgrade head` — re-applies all 4 migrations cleanly.

**Risks and edge cases:**
- Two migrations have `0003` suffix (`20260603_0003` and `20260609_0003`). The `Revises` chain is correct and unique, but the duplicate suffix is non-standard. If any tooling assumes lexicographic ordering, it may sort `20260609_0003` before `20260603_0003`. Verify `alembic` processes them in correct order (already ensured by `Revises`).
- PostgreSQL enforces check constraints on existing data. Any migration that inserts data violating constraints will fail. Current migrations are pure DDL (no data inserts), so this is safe.

---

## Phase 4 — Model Verification

### 4.1 Verify all 9 models against PostgreSQL
- [ ] Company — confirm `String(36)` UUID PK, unique `domain` index, status check constraint.
- [ ] Contact — confirm `String(36)` UUID PK, unique nullable `email` index, FK to `companies`.
- [ ] Website — confirm `String(36)` UUID PK, unique `normalized_url` index, `Text` columns for raw/extracted content.
- [ ] Technology — confirm composite unique index on `(company_id, name, category)`, `confidence` range check.
- [ ] IntentSignal — confirm `strength` and `confidence` range checks, composite index on `(company_id, signal_type, observed_at)`.
- [ ] IntelligenceScore — confirm score range checks (0.0–100.0), confidence range check (0.0–1.0).
- [ ] OutreachMessage — confirm status check constraint, confidence range check.
- [ ] AgentRun — confirm status check constraint, FK to `companies` and `contacts`.
- [ ] Job — confirm check constraints for `status`, `job_type`, `retry_count <= max_retries`, `max_retries >= 0`, FK to `agent_runs`.

### 4.2 Verify constraints
- [ ] Insert a row with an invalid status value and confirm PostgreSQL rejects it (integrity error).
- [ ] Insert a row with an out-of-range confidence value and confirm PostgreSQL rejects it.
- [ ] Insert a row with a UUID that violates FK and confirm PostgreSQL rejects it.

### 4.3 Verify relationships
- [ ] ORM relationship `company.contacts` loads correctly.
- [ ] ORM relationship `company.websites` loads correctly.
- [ ] ORM relationship `agent_run.jobs` loads correctly (back_populates).
- [ ] Cascading deletes work as expected (`CASCADE` where configured, `SET NULL` where configured).

### 4.4 Verify UUID handling
- [ ] Confirm `String(36)` columns accept and return lowercase 36-character hex UUID strings.
- [ ] Confirm `uuid.uuid4()` generated values stored as strings work identically in queries (`WHERE id = ?`).
- [ ] Confirm no code assumes case-insensitive UUID comparison.

### 4.5 Verify datetime handling
- [ ] Confirm `DateTime(timezone=True)` columns store and retrieve timezone-aware timestamps under PostgreSQL.
- [ ] Confirm naive datetimes are rejected by PostgreSQL (error expected on insert).
- [ ] Confirm all existing model timestamp fields (`created_at`, `updated_at`, `observed_at`, `scored_at`, `generated_at`, `started_at`, `finished_at`, `scheduled_at`, `completed_at`) use timezone-aware values.

**Files affected:**
- No model files should be modified — verification only.

**Validation steps:**
- Connect model metadata to PostgreSQL engine: `Base.metadata.create_all(bind=pg_engine)` succeeds.
- `inspect(pg_engine).get_table_names()` returns all 9 tables.
- Insert and select a row for each model succeeds.

**Risks and edge cases:**
- `DateTime(timezone=True)` in SQLite stores as text without timezone enforcement. Code may generate naive datetimes that work in SQLite but fail in PostgreSQL. This is the highest-risk area.
- `String(36)` for UUIDs works in PostgreSQL but creates a text column, not a native `UUID` column. All ORM operations work identically, but native UUID database functions are unavailable.

---

## Phase 5 — Repository Verification

### 5.1 Verify all repository queries against PostgreSQL
- [ ] `CompanyRepository` — CRUD operations, find by domain, list with filters, count.
- [ ] `ContactRepository` — CRUD operations, list by company, unique email handling.
- [ ] `WebsiteRepository` — CRUD operations, find by normalized URL, list by company.
- [ ] `TechnologyRepository` — CRUD operations, find by company+name+category, list by company/website/agent_run.
- [ ] `IntentSignalRepository` — CRUD operations, list by company/contact/signal_type, range filtering by strength/confidence.
- [ ] `IntelligenceScoreRepository` — CRUD operations, list by company/contact, latest score queries.
- [ ] `OutreachMessageRepository` — CRUD operations, list by company/contact/channel/status.
- [ ] `AgentRunRepository` — CRUD operations, list by agent_name/workflow_name/status.
- [ ] `JobRepository` — CRUD operations, `get_pending_jobs()`, `get_job_by_agent_run_id()`.

### 5.2 Verify pagination
- [ ] `limit` and `offset` parameters return correct subsets.
- [ ] `count()` returns correct total.
- [ ] Pagination with filters (e.g., `status='active'`) returns correct counts.

### 5.3 Verify filtering
- [ ] String equality filters work correctly (PostgreSQL is case-sensitive; all existing lookups use lowercase).
- [ ] Range filters (`>=`, `<=`) work correctly for numeric columns.
- [ ] `IN` filters work correctly.
- [ ] `IS NULL` / `IS NOT NULL` filters work correctly.

### 5.4 Verify JobRepository claim semantics
- [ ] `get_pending_jobs(limit=10)` returns jobs where `status='pending'` and `scheduled_at <= now()`, ordered by `scheduled_at` ASC.
- [ ] `JobService.claim_job()` UPDATE returns `rowcount == 1` when claiming a pending job (PostgreSQL `rowcount` behavior matches SQLite).
- [ ] `JobService.claim_job()` UPDATE returns `rowcount == 0` when the job was already claimed by another caller.
- [ ] No phantom claims: two concurrent calls to `claim_job()` for the same job_id result in exactly one success.

**Files affected:**
- No repository files should be modified — verification only.

**Validation steps:**
- Existing repository test suite (`tests/integration/test_repositories.py`) passes against PostgreSQL.
- All repository queries return identical results to SQLite for the same data.

**Risks and edge cases:**
- PostgreSQL string comparison is case-sensitive. Repository queries like `WHERE name = 'Example'` will not match `'example'`. All existing lookups use consistent casing, but this must be verified.
- `rowcount` for UPDATE: PostgreSQL returns the number of rows actually modified, not the number matched. If the UPDATE sets values identical to current values, `rowcount` may be 0 even though a row matched. The `claim_job()` UPDATE changes `status` from `'pending'` to `'running'`, which is always a modification, so this should not be an issue. Test must confirm.

---

## Phase 6 — Service Verification

### 6.1 Verify transaction behavior
- [ ] `session_scope()` commits correctly: a successful service call persists changes.
- [ ] `session_scope()` rollback on exception: a failing service call leaves no partial state.
- [ ] Nested `session_scope()` calls work correctly under PostgreSQL (SAVEPOINT behavior).

### 6.2 Verify rollback behavior
- [ ] Insert two records in sequence; force failure on the second; verify first is rolled back (atomicity).
- [ ] Verify PostgreSQL error codes are correctly mapped to structured errors (not raw psycopg errors).

### 6.3 Verify JobService state transitions
- [ ] `schedule_agent()` creates a `pending` job with correct payload.
- [ ] `schedule_workflow()` creates a `pending` job with correct payload.
- [ ] `cancel_job()` transitions `pending` → `cancelled`; rejects non-pending jobs.
- [ ] `retry_job()` transitions `failed` → `pending`; rejects non-failed jobs.
- [ ] `claim_job()` transitions `pending` → `running` with correct `started_at`.
- [ ] All state transitions enforce valid status transitions (no invalid transitions).

**Files affected:**
- No service files should be modified — verification only.

**Validation steps:**
- Existing service test suite (`tests/integration/test_services.py`) passes against PostgreSQL.
- JobService state transitions produce identical results under both databases.

**Risks and edge cases:**
- PostgreSQL's `READ COMMITTED` isolation may surface race conditions between concurrent transactions that SQLite's `DEFERRED` mode hides.
- The `claim_job()` atomic update pattern (`UPDATE ... WHERE status = 'pending'`) works correctly under PostgreSQL, but deadlock detection may cause an unexpected error if two concurrent callers update jobs in different orders.

---

## Phase 7 — Workflow and Agent Verification

### 7.1 Verify score_refresh workflow
- [ ] `score_refresh` workflow execution creates `intelligence_scores` records under PostgreSQL.
- [ ] `score_refresh` workflow creates `agent_runs` observability records.
- [ ] `WorkflowRunner.run()` transaction commits all changes atomically.
- [ ] `WorkflowRunner.run()` rolls back all changes on failure.
- [ ] Scoring policy produces deterministic, bounded, versioned scores.

### 7.2 Verify all 5 agents
- [ ] Deep Scraper Agent — website record creation and updates work under PostgreSQL.
- [ ] Technographic Agent — technology detection persistence works.
- [ ] Intent Signal Agent — intent signal creation with in-run deduplication and cross-run duplicate suppression works.
- [ ] Intelligence Scoring Agent — intelligence score creation works.
- [ ] Personalization Agent — outreach message creation works.

### 7.3 Verify agent_runs behavior
- [ ] Agent executions create `agent_runs` records with correct status transitions.
- [ ] Agent failures mark `agent_runs.status = 'failed'` and store `error_message`.
- [ ] Agent successes mark `agent_runs.status = 'succeeded'` and store `output_summary`.

**Files affected:**
- No workflow or agent files should be modified — verification only.

**Validation steps:**
- Existing workflow integration test (`tests/integration/test_score_refresh_workflow.py`) passes against PostgreSQL.
- Agent unit tests (which mock external calls but exercise database interactions through services) pass against PostgreSQL.

**Risks and edge cases:**
- Agents that create records relying on auto-generated UUIDs and timestamps must produce identical results under PostgreSQL.
- Deduplication in IntentSignalService relies on `get_by_company_signal_type_name()` queries. Must verify exact match semantics under PostgreSQL's case-sensitive comparison.

---

## Phase 8 — Background Job Verification

### 8.1 Verify JobRunner
- [ ] `JobRunner._run_job()` with agent target resolves via `AgentRegistry`, executes agent, transitions to `succeeded`, links `agent_run_id`.
- [ ] `JobRunner._run_job()` with workflow target resolves via `WorkflowRegistry`, executes workflow, transitions to `succeeded`.
- [ ] `JobRunner._run_job()` on failure: transitions to `failed`, stores `last_error`.
- [ ] `JobRunner._run_job()` with retries remaining: transitions to `pending`, increments `retry_count`, updates `scheduled_at`.

### 8.2 Verify JobScheduler
- [ ] `JobScheduler.run()` polls `get_next_jobs()` and dispatches to runner.
- [ ] `JobScheduler.shutdown()` stops the polling loop gracefully.

### 8.3 Verify retry behavior
- [ ] `compute_next_scheduled_at()` produces valid future timestamps under PostgreSQL.
- [ ] Retry count increments correctly across multiple retry cycles.
- [ ] Job remains `failed` when `retry_count >= max_retries` (no infinite retries).

### 8.4 Verify status transitions
- [ ] `pending` → `running` (claim), `running` → `succeeded` (success), `running` → `failed` (failure).
- [ ] `failed` → `pending` (retry), `failed` → `failed` (no retries left).
- [ ] `pending` → `cancelled` (manual cancel).
- [ ] Invalid transitions produce errors (e.g., `succeeded` → `running`).

**Files affected:**
- No job files should be modified — verification only.

**Validation steps:**
- Existing job lifecycle integration test (`tests/integration/jobs/test_job_lifecycle.py`) passes against PostgreSQL.
- Existing job API integration test (`tests/integration/jobs/test_job_api.py`) passes against PostgreSQL.

**Risks and edge cases:**
- PostgreSQL's `rowcount` on UPDATE must be verified to return 1 when `claim_job()` succeeds and 0 when the job was already claimed.
- The scheduler's polling query `SELECT ... WHERE status='pending' AND scheduled_at <= now()` uses `DateTime(timezone=True)` comparison. Must verify PostgreSQL's timezone handling doesn't shift the comparison window.

---

## Phase 9 — API Verification

### 9.1 Verify CRUD endpoints
- [ ] All `POST` endpoints create records correctly under PostgreSQL.
- [ ] All `GET /{id}` endpoints return correct records.
- [ ] All `GET` list endpoints return correct pagination (`items`, `total`, `limit`, `offset`).
- [ ] All `PATCH` endpoints update records correctly.
- [ ] All `DELETE` endpoints return `204 No Content`.
- [ ] All endpoints handle not-found cases with structured errors.

### 9.2 Verify job endpoints
- [ ] `POST /jobs/schedule-agent` creates a pending job.
- [ ] `POST /jobs/schedule-workflow` creates a pending job.
- [ ] `GET /jobs/` lists jobs with optional `status`/`target_name` filtering.
- [ ] `GET /jobs/{job_id}` returns job details.
- [ ] `POST /jobs/{job_id}/cancel` cancels pending jobs.
- [ ] `POST /jobs/{job_id}/retry` retries failed jobs.
- [ ] Error responses use structured error envelope for conflict, not-found, and validation failures.

### 9.3 Verify error responses
- [ ] Constraint violations (unique constraint, FK violation) return structured errors (not raw database errors).
- [ ] Invalid request payloads return `422 Unprocessable Entity`.
- [ ] Not-found resources return `404` with structured error body.
- [ ] Conflict conditions (e.g., cancel a running job) return `409` with structured error body.

**Files affected:**
- No API files should be modified — verification only.

**Validation steps:**
- Existing API integration tests (`tests/integration/api/test_crud_phase_1.py`, `test_crud_phase_2.py`, `test_crud_phase_3.py`) pass against PostgreSQL-backed FastAPI app.
- Existing job API tests pass against PostgreSQL-backed FastAPI app.

**Risks and edge cases:**
- FastAPI `TestClient` uses the ASGI transport. The PostgreSQL-backed app must use `create_app()` with the PostgreSQL engine injected via dependency overrides or environment variable.
- The `get_db_session()` dependency creates sessions from the global `SessionLocal`, which is bound to the global `engine`. Test isolation requires a per-test engine override.
- This phase is gated on the PostgreSQL test fixture being available.

---

## Phase 10 — PostgreSQL Test Infrastructure

### 10.1 PostgreSQL fixtures
- [ ] Add `tests/conftest.py` fixture `postgresql_engine` that connects via `DATABASE_URL` environment variable.
- [ ] Add `tests/conftest.py` fixture `postgresql_session` that yields a session bound to the PostgreSQL engine.
- [ ] Add `tests/conftest.py` fixture `postgresql_test_db` that creates a temporary database, runs Alembic migrations, yields, and drops the database on teardown.

### 10.2 Conditional test execution
- [ ] Gate all PostgreSQL tests behind `pytest.mark.skipif` checking `DATABASE_URL` starts with `postgresql`.
- [ ] Gate PostgreSQL tests behind import check for `psycopg` (skip if optional dependency not installed).
- [ ] Ensure `pytest --collect-only` works without PostgreSQL installed.

### 10.3 CI-friendly setup
- [ ] Document required environment variables for CI: `DATABASE_URL`, `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`.
- [ ] Ensure the test fixture creates and drops the test database programmatically (no manual setup).
- [ ] Ensure tests leave no residual state (all tables dropped after teardown).

**Files affected:**
- `tests/conftest.py` — add PostgreSQL fixtures and conditional execution logic.

**Validation steps:**
- `python -m pytest tests/integration/` — SQLite tests run; PostgreSQL tests are skipped (no `DATABASE_URL` override).
- `DATABASE_URL=postgresql://... python -m pytest tests/integration/` — PostgreSQL tests run; SQLite tests also run (both use their respective engines).
- `DATABASE_URL=postgresql://... python -m pytest tests/` — all 284+ tests run against PostgreSQL.

**Risks and edge cases:**
- Creating and dropping databases programmatically requires a PostgreSQL superuser or CREATEDB privilege. Document this requirement.
- The PostgreSQL test fixture should use a separate `irtiqa_test` database to avoid corrupting the development database.
- Test isolation is critical: each test module should get a fresh database state via migration re-run or transaction rollback.

---

## Phase 11 — Documentation Updates

### 11.1 Update docs/database.md
- [ ] Add "PostgreSQL Setup" section with connection string format and required environment variables.
- [ ] Add "Running PostgreSQL Integration Tests" section with `DATABASE_URL` configuration instructions.
- [ ] Add "PostgreSQL Optional Dependency" section with `pip install -e ".[postgres]"`.
- [ ] Verify existing "Migration Path to PostgreSQL" section is still accurate.

### 11.2 Update docs/project_state.md
- [ ] Mark PostgreSQL Compatibility Verification as completed.
- [ ] Update test count from 284 to new count (284 + new PostgreSQL test files).
- [ ] Update next milestone recommendation (CI and Quality Gates).
- [ ] Add note that PostgreSQL verification passed with no architectural changes.

### 11.3 Update docs/project_handoff.md
- [ ] Add PostgreSQL Compatibility Verification to completed tasks list.
- [ ] Update repository architecture diagram if new test files were added.
- [ ] Update next milestone to "CI and Quality Gates" or as specified.
- [ ] Update Section 9 (Current Roadmap) and Section 10 (Next Recommended Task).

### 11.4 Update docs/codex_bootstrap.md
- [ ] Update current milestone status to "PostgreSQL Compatibility Verification — Completed".
- [ ] Add PostgreSQL section with setup commands and test execution instructions.
- [ ] Update "Quick Start for the Next Task" section.

### 11.5 Update README.md
- [ ] Add `pip install -e ".[postgres]"` to setup instructions.
- [ ] Add "Running PostgreSQL Tests" section.
- [ ] Document `DATABASE_URL` environment variable.

**Files affected:**
- `docs/database.md`
- `docs/project_state.md`
- `docs/project_handoff.md`
- `docs/codex_bootstrap.md`
- `README.md`

**Validation steps:**
- All documentation references to migration files, model counts, test counts, and milestone names are accurate after updates.
- No stale references to "pending" or "in-progress" state for this milestone.

**Risks and edge cases:**
- Documentation must not promise features not yet implemented (e.g., CI pipeline, automated migration testing).
- Test count in documentation must match actual `python -m pytest` output after PostgreSQL tests are added.

---

## Phase 12 — Final Verification

### 12.1 Full SQLite test suite
- [ ] `python -m pytest` — all existing tests pass (284+).
- [ ] `python -m alembic upgrade head` — succeeds on SQLite.
- [ ] `python -m alembic check` — no new operations detected on SQLite.
- [ ] `python -m compileall app database tests` — no syntax errors.

### 12.2 Full PostgreSQL test suite
- [ ] `DATABASE_URL=postgresql://... python -m pytest` — all 284+ tests pass against PostgreSQL.
- [ ] `DATABASE_URL=postgresql://... python -m alembic upgrade head` — succeeds on PostgreSQL.
- [ ] `DATABASE_URL=postgresql://... python -m alembic check` — no new operations detected on PostgreSQL.

### 12.3 Migration verification
- [ ] `alembic downgrade -1` (4 times) then `alembic upgrade head` — round-trip succeeds on PostgreSQL.
- [ ] `alembic downgrade -1` (4 times) then `alembic upgrade head` — round-trip succeeds on SQLite.

### 12.4 Regression verification
- [ ] No existing SQLite test is broken by engine configuration changes.
- [ ] No existing SQLite test requires PostgreSQL to be installed.
- [ ] `pytest --collect-only` works without PostgreSQL (all PostgreSQL tests skipped).

### 12.5 SQLite regression verification
- [ ] `DATABASE_URL=sqlite:///database/irtiqa.db` application starts and functions normally.
- [ ] All existing CRUD, workflow, agent, and job operations work with SQLite.
- [ ] `session_scope()` commits and rollbacks work correctly.

**Validation steps:**
- `python -m pytest` exit code 0.
- `DATABASE_URL=postgresql://... python -m pytest` exit code 0.
- `python -m alembic upgrade head && python -m alembic check` succeeds on both databases.
- `python -m compileall app database tests` reports no errors.

**Risks and edge cases:**
- The PostgreSQL test suite must be gated so it does not run when `DATABASE_URL` is not set to PostgreSQL.
- The SQLite test suite must remain the default and must not require any PostgreSQL dependencies.
- Final verification must confirm that no domain code (models, repositories, services, workflows, agents, jobs, schemas, API endpoints, migrations) was changed — only `engine.py` and `conftest.py`.
