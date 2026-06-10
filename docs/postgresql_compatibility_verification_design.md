# PostgreSQL Compatibility Verification Design

## 1. Purpose

### Why PostgreSQL verification is required now
The Background Job Foundation milestone completed all core backend infrastructure. The entire platform — nine tables, Alembic migrations, repositories, services, workflows, agents, jobs, and the API layer — has been built and tested exclusively against SQLite. Before the platform can be deployed in production environments that require PostgreSQL (multi-writer, high-concurrency, managed deployments), every layer must be verified against a live PostgreSQL instance. This milestone validates that the codebase's SQLAlchemy models, Alembic migrations, repository queries, service transaction boundaries, workflow execution, agent execution, and background job infrastructure all function correctly under PostgreSQL semantics.

### Relationship to completed Background Job Foundation milestone
The Background Job Foundation introduced the `jobs` table, `JobRepository`, `JobService`, `JobRunner`, `JobScheduler`, retry policies, and job API endpoints. All of these interact with the database through SQLAlchemy. Verifying the jobs infrastructure against PostgreSQL is a critical part of this milestone because background jobs perform real agent and workflow execution that exercises multiple tables, transactions, and state transitions. The Background Job Foundation also added check constraints and indexes on the `jobs` table that must be validated under PostgreSQL's stricter constraint enforcement.

## 2. Scope

### Models
All nine SQLAlchemy ORM models must be verified:
- `Company`, `Contact`, `Website`, `Technology`, `IntentSignal`, `IntelligenceScore`, `OutreachMessage`, `AgentRun`, `Job`

Verification includes:
- Column types map correctly between SQLite and PostgreSQL.
- `String(36)` UUID columns function correctly under PostgreSQL (no native UUID type required yet).
- `DateTime(timezone=True)` columns preserve timezone-aware timestamps.
- `Text` columns for JSON payloads, error messages, and long text fields.
- Relationship declarations (`relationship()`) load and persist correctly.
- `Mapped[...]` / `mapped_column` conventions produce equivalent DDL on both databases.

### Alembic migrations
All existing migration revisions must be verified against PostgreSQL:
- `20260531_0001_initial_schema.py` — creates all base tables, indexes, and foreign keys.
- `20260531_0002_database_hardening.py` — adds check constraints for status, confidence, strength, and score ranges.
- `20260603_0003_add_website_content_columns.py` — adds `raw_html` and `extracted_text` columns to `websites`.
- `20260609_0003_add_jobs_table.py` — creates `jobs` table with check constraints, indexes, and foreign key to `agent_runs`.

Verification includes:
- `alembic upgrade head` succeeds against PostgreSQL.
- `alembic check` reports no new operations after upgrade.
- Migration downgrade removes all tables cleanly.
- Check constraints are enforced by PostgreSQL (not silently ignored as in SQLite without PRAGMA).
- Index definitions produce equivalent query plans.

### Repositories
All ten repositories must be verified:
- `BaseRepository`, `CompanyRepository`, `ContactRepository`, `WebsiteRepository`, `TechnologyRepository`, `IntentSignalRepository`, `IntelligenceScoreRepository`, `OutreachMessageRepository`, `AgentRunRepository`, `JobRepository`

Verification includes:
- All existing query methods return correct results under PostgreSQL.
- Parameterized filters, sorting, and pagination (limit/offset) work identically.
- `get_pending_jobs()` with `scheduled_at <= now()` comparison works with PostgreSQL datetime semantics.
- `claim_job()` atomic update with rowcount check works (PostgreSQL returns correct `rowcount`).
- Unique constraint violations produce catchable exceptions.
- Foreign key violations produce catchable exceptions.

### Services
All service classes must be verified:
- `BaseService`, `CompanyService`, `ContactService`, `WebsiteService`, `TechnologyService`, `IntentSignalService`, `IntelligenceScoreService`, `OutreachMessageService`, `AgentRunService`, `JobService`

Verification includes:
- `session_scope()` commits, rollbacks, and close behavior works identically.
- Transaction rollback on database errors leaves no partial state.
- Service-level duplicate detection and not-found handling work with PostgreSQL error codes.
- `JobService.schedule_agent()`, `schedule_workflow()`, `cancel_job()`, `retry_job()`, `claim_job()` produce correct state transitions.

### Workflows
- `score_refresh` workflow execution produces correct intelligence scores.
- `WorkflowRunner.run()` transaction behavior works under PostgreSQL.
- Agent run observability (creating/updating `agent_runs` records) works correctly.

### Agents
All five agents must be verified for correct database interaction:
- Deep Scraper Agent — website record creation and updates.
- Technographic Agent — technology detection persistence.
- Intent Signal Agent — intent signal creation with deduplication.
- Intelligence Scoring Agent — intelligence score creation.
- Personalization Agent — outreach message creation.

Agent verification focuses on repository/service interaction patterns, not on external fetching or rule logic. The goal is to confirm that the database operations agents depend on function identically under PostgreSQL.

### Background Job infrastructure
- `JobRunner` execution flow: claim → execute → succeed/fail → retry.
- `JobScheduler` polling: reads pending jobs, dispatches to runner.
- Retry policy: rescheduling failed jobs with updated `scheduled_at`.
- All status transitions produce correct database state.

### API layer
- All CRUD endpoints return correct responses when backed by PostgreSQL.
- List endpoints return correct pagination (limit, offset, total).
- Error responses for constraint violations, not-found, and conflict conditions use the structured error envelope.
- Job API endpoints (schedule, list, get, cancel, retry) function correctly.

## 3. Architecture Review

### Current SQLite assumptions
The codebase makes several SQLite-specific assumptions that must be reviewed:

| Assumption | Impact |
|---|---|
| `check_same_thread=False` in engine config | PostgreSQL driver does not use this; must be conditional on dialect. |
| `PRAGMA foreign_keys=ON` on every connection | PostgreSQL enforces foreign keys by default; PRAGMA is ignored/no-op. |
| `PRAGMA journal_mode=WAL` on every connection | PostgreSQL has native MVCC; PRAGMA is ignored/no-op. |
| `PRAGMA busy_timeout=5000` on every connection | PostgreSQL uses `statement_timeout` and `lock_timeout` via different mechanisms. |
| UUIDs stored as `String(36)` | Works in PostgreSQL but sacrifices native UUID index performance. |
| JSON metadata stored as `Text` | Works in PostgreSQL but cannot use JSONB operators. |
| `DateTime(timezone=True)` in SQLite | SQLite does not truly preserve timezone; PostgreSQL does. |
| Single-writer concurrency model | SQLite allows one writer; PostgreSQL allows concurrent writers. |
| No `SELECT ... FOR UPDATE` | SQLite cannot use it; PostgreSQL can for stronger claim semantics. |

### Potential PostgreSQL compatibility risks

1. **Date/time handling**: SQLite's `DateTime(timezone=True)` stores a formatted string without true timezone enforcement. PostgreSQL enforces timezone-aware timestamp columns strictly. Existing data or queries that rely on SQLite's lax behavior may fail.

2. **Check constraint enforcement**: SQLite requires `PRAGMA foreign_keys=ON` and does not enforce check constraints by default in older versions. PostgreSQL enforces all constraints strictly. A model or migration that accidentally violates a constraint will fail immediately under PostgreSQL.

3. **Case sensitivity**: SQLite's string comparison is case-insensitive for ASCII by default. PostgreSQL string comparison is case-sensitive. Queries that rely on case-insensitive matching may return different results.

4. **Integer vs boolean**: SQLite stores booleans as integers 0/1. PostgreSQL has native boolean type. SQLAlchemy's `Boolean` type handles this transparently, but any raw SQL or query-level assumption about integer representation would break.

5. **Connection pooling**: SQLite uses `NullPool` (no pooling) because pooling is irrelevant for file-based databases. PostgreSQL needs a proper connection pool (`QueuePool` or similar) configured in the engine factory.

### Transaction behavior differences
| Aspect | SQLite | PostgreSQL |
|---|---|---|
| Default isolation | `DEFERRED` (begins on first write) | `READ COMMITTED` |
| Nesting | No true nested transactions (SAVEPOINT used by SQLAlchemy) | True nested transactions via SAVEPOINT |
| DDL in transactions | Some DDL implicitly commits | DDL is transactional |
| Deadlock detection | Not applicable (single writer) | Full deadlock detection and resolution |
| `rowcount` on UPDATE | Returns number of rows matched | Returns number of rows modified (may differ from SQLite in edge cases) |

The `claim_job()` method in `JobService` relies on `rowcount` after an `UPDATE ... WHERE status = 'pending'`. This pattern must be tested under PostgreSQL to confirm it returns the expected value.

### Constraint/index considerations
- SQLAlchemy `CheckConstraint` definitions are portable and will be enforced by PostgreSQL.
- Composite unique indexes on nullable columns behave differently: SQLite allows multiple `NULL` values, PostgreSQL allows multiple `NULL` values in unique indexes (standard SQL behavior). This is compatible for current patterns.
- Index types: PostgreSQL supports additional index types (GIN, GiST, BRIN) but current B-tree indexes are fully compatible.
- Partial/conditional indexes cannot be used until they are verified against both databases.

### UUID handling
Current approach: `String(36)` with `UUID()` default generator.

| Concern | Assessment |
|---|---|
| Storage efficiency | `String(36)` is ~36 bytes vs 16 bytes for native PostgreSQL `UUID`. Acceptable for current scale. |
| Index performance | String indexes are slower than native UUID indexes. Not a concern at current data volumes. |
| Migration path | Future migration can alter column type to PostgreSQL `UUID` using `USING` clause. Documented in `docs/database.md`. |
| Application code | All UUIDs are generated in Python (`uuid.uuid4()`) and stored as strings. No code changes needed for PostgreSQL compatibility. |

### JSON/Text field compatibility
Current approach: JSON payloads (e.g., `job.payload`, `websites.raw_html`, `websites.extracted_text`) are stored as `Text`.

| Concern | Assessment |
|---|---|
| Functionality | `Text` columns work identically on both databases. |
| Queryability | PostgreSQL cannot use JSONB operators on `Text` columns. Acceptable because no code queries into JSON structure via SQL. |
| Migration path | Future migration can alter to `JSONB` for PostgreSQL. Documented in `docs/database.md`. |
| Risk | Low — no code depends on JSON-specific database features. |

### Foreign-key behavior
| Aspect | SQLite | PostgreSQL |
|---|---|---|
| Enforcement | Requires `PRAGMA foreign_keys=ON` per connection | Enforced by default |
| `ON DELETE CASCADE` | Supported | Supported |
| `ON DELETE SET NULL` | Supported | Supported |
| Self-referencing FKs | Supported | Supported |
| Circular FKs | Not allowed | Not allowed |

All foreign keys are defined in SQLAlchemy models with explicit `ondelete` clauses. The same DDL is generated for both databases. PostgreSQL will enforce them without needing a connection-level PRAGMA.

## 4. Verification Strategy

### What must be tested

1. **Migration test against PostgreSQL**: Run all Alembic migrations against a live PostgreSQL database. Verify `alembic upgrade head`, `alembic check`, and `alembic downgrade -1` produce correct results.

2. **Model metadata verification**: Connect SQLAlchemy model metadata to a PostgreSQL engine and verify `Base.metadata.create_all()` succeeds and produces the expected schema.

3. **Repository integration tests against PostgreSQL**: Run the existing repository test suite against a PostgreSQL database. All repository query methods, filters, sorting, pagination, and edge cases must pass.

4. **Service integration tests against PostgreSQL**: Run the existing service test suite against PostgreSQL. All service methods, transaction boundaries, error handling, and state transitions must pass.

5. **Workflow tests against PostgreSQL**: Run the `score_refresh` workflow integration tests against PostgreSQL.

6. **Job lifecycle tests against PostgreSQL**: Run the job lifecycle integration tests (schedule → run → succeed/fail → retry → cancel) against PostgreSQL.

7. **API integration tests against PostgreSQL**: Run the existing API integration tests against a PostgreSQL-backed FastAPI `TestClient`.

8. **Engine configuration verification**: Confirm that the SQLite-specific PRAGMAs (`check_same_thread`, `PRAGMA foreign_keys`, `PRAGMA journal_mode`, `PRAGMA busy_timeout`) are only applied when the database URL starts with `sqlite`, and that PostgreSQL engine configuration uses appropriate pool settings (`QueuePool`, `pool_pre_ping`).

### What constitutes successful verification

- All 284+ existing tests pass when run against PostgreSQL.
- All 284+ existing tests continue to pass when run against SQLite (no regression).
- `alembic upgrade head` and `alembic check` succeed against PostgreSQL.
- Migration downgrade removes all tables cleanly on PostgreSQL.
- SQLite-specific PRAGMAs are not applied to PostgreSQL connections.
- PostgreSQL engine uses appropriate pool settings without errors.
- No code changes break SQLite compatibility (SQLite remains primary development DB).

### Required PostgreSQL test environment

- **Local PostgreSQL instance**: A PostgreSQL server (version 15 or 16) running locally for development and CI verification.
- **Test database**: A dedicated database (e.g., `irtiqa_test`) that is created and dropped per test run.
- **Connection string**: Configurable via `DATABASE_URL` environment variable, defaulting to SQLite for normal development.
- **Python dependencies**: `psycopg2-binary` (or `psycopg` v3) declared in `[project.optional-dependencies] postgres` in `pyproject.toml`.
- **Test fixture**: A pytest fixture that creates a temporary PostgreSQL database, runs migrations, yields the session, and drops the database on teardown. This fixture must be gated on the `postgres` optional dependency being installed.

## 5. Risk Assessment

### High-risk areas

| Area | Risk | Rationale |
|---|---|---|
| **Date/time compatibility** | High | SQLite's lax datetime handling may mask timezone-related bugs. PostgreSQL enforces timezone-aware timestamps strictly. Any code that stores naive datetimes will fail. |
| **CONSTRAINT enforcement** | High | PostgreSQL enforces all check constraints unconditionally. Any model or migration that produces data violating constraints (e.g., out-of-range scores, invalid status values) will fail under PostgreSQL but may succeed under SQLite. |
| **Claim job atomic update** | High | `JobService.claim_job()` relies on `UPDATE ... WHERE status = 'pending'` and checks `rowcount`. PostgreSQL's `rowcount` behavior for UPDATE must be verified to match expectations. |
| **Transaction isolation** | High | Service transaction boundaries use `session_scope()`. PostgreSQL's `READ COMMITTED` default may surface race conditions that SQLite's deferred transactions hide. |

### Medium-risk areas

| Area | Risk | Rationale |
|---|---|---|
| **UUID string comparison** | Medium | PostgreSQL string comparison is case-sensitive. UUIDs stored as `String(36)` are lowercase-hex, so no issues expected, but any code comparing UUIDs case-insensitively would break. |
| **Connection pooling** | Medium | SQLite uses `NullPool`. PostgreSQL needs `QueuePool`. The engine factory in `app/database/engine.py` must conditionally configure pooling based on dialect. |
| **String comparison semantics** | Medium | SQLite is case-insensitive for ASCII by default. PostgreSQL is case-sensitive. Queries using `WHERE name = 'example'` may behave differently if data has inconsistent casing. |
| **Index creation performance** | Medium | PostgreSQL builds indexes differently from SQLite. Migration times may increase for large datasets, but this milestone uses empty test databases. |
| **Alembic batch mode** | Medium | The `add_jobs_table.py` migration uses SQLite batch mode. PostgreSQL does not need batch mode. The migration must handle both dialects correctly. |

### Low-risk areas

| Area | Risk | Rationale |
|---|---|---|
| **Foreign key behavior** | Low | All FKs use standard `CASCADE`/`SET NULL` patterns that behave identically on both databases. |
| **JSON text columns** | Low | No code queries into JSON structure via SQL. Text columns work identically. |
| **Boolean representation** | Low | SQLAlchemy's `Boolean` type abstracts the 0/1 vs true/false difference. No raw SQL uses boolean literals. |
| **Limit/offset pagination** | Low | SQLAlchemy's `.limit()` and `.offset()` are dialect-agnostic. |
| **Aggregate functions** | Low | Current queries use standard SQL aggregate functions (COUNT, SUM, AVG) that are fully portable. |
| **Model metadata loading** | Low | `inspect(engine).get_table_names()` and similar metadata queries are portable through SQLAlchemy. |

## 6. Deliverables

### Guiding principle

No architectural changes are expected. The codebase was designed for PostgreSQL compatibility from the start (SQLAlchemy portable types, Alembic migrations, no SQLite-only SQL in domain logic). This milestone is a **verification** exercise, not a redesign.

If PostgreSQL verification reveals a genuine cross-database incompatibility, the fix must be **minimal and dialect-gated** — scoped to the specific line or configuration that causes the issue, with no changes to domain models, services, workflows, agents, or API contracts. A genuine cross-database issue is one where the same SQLAlchemy operation produces a different or incorrect result under PostgreSQL compared to SQLite, and the fix does not alter the application's domain behavior.

### Expected code changes

The only expected code changes are to engine configuration and test infrastructure:

| File | Change |
|---|---|
| `app/database/engine.py` | Conditionally configure pool class (`NullPool` for SQLite, `QueuePool` for PostgreSQL). Gate SQLite PRAGMAs behind a dialect check. |
| `tests/conftest.py` | Add PostgreSQL test fixture (conditional on `DATABASE_URL` / postgres dependency). |

`app/core/config.py` and `pyproject.toml` already support PostgreSQL — `DATABASE_URL` accepts any connection string, and the `postgres` optional dependency group is already declared. No changes needed.

No changes to models, repositories, services, workflows, agents, jobs, schemas, API endpoints, or Alembic migrations are expected. If verification reveals a genuine cross-database issue, only the minimal dialect-gated fix may be introduced.

### Expected tests

| Test file | Description |
|---|---|
| `tests/integration/test_postgresql_compatibility.py` | Run all existing migrations against PostgreSQL, verify schema, verify downgrade. |
| `tests/integration/test_postgresql_repositories.py` | Run repository test suite against PostgreSQL (identical assertions to existing SQLite tests). |
| `tests/integration/test_postgresql_services.py` | Run service test suite against PostgreSQL (identical assertions to existing SQLite tests). |
| `tests/integration/test_postgresql_workflows.py` | Run `score_refresh` workflow test against PostgreSQL. |
| `tests/integration/test_postgresql_jobs.py` | Run job lifecycle tests against PostgreSQL. |
| `tests/integration/test_postgresql_api.py` | Run API integration tests against PostgreSQL-backed FastAPI app. |

Each test file must be gated: only run when the `postgres` optional dependency is installed and `DATABASE_URL` points to a PostgreSQL instance. The tests must not be required for normal SQLite development workflows.

### Expected documentation updates

| Document | Change |
|---|---|
| `docs/database.md` | Add PostgreSQL setup instructions, connection string format, and verification commands. Add section on running PostgreSQL integration tests. |
| `docs/project_state.md` | Mark PostgreSQL Compatibility Verification as completed. Update next milestone. Update test count. |
| `docs/project_handoff.md` | Add PostgreSQL verification to completed tasks. Update repository architecture diagram if new files added. Update next milestone. |
| `docs/codex_bootstrap.md` | Update current milestone status. Add PostgreSQL section with setup and test commands. |
| `README.md` | Add PostgreSQL optional dependency installation instructions. Add note on running PostgreSQL tests. |

## 7. Success Criteria

The milestone is complete when all of the following conditions are met:

1. **Migration verification**: `alembic upgrade head` and `alembic check` succeed against a live PostgreSQL database. `alembic downgrade -1` removes all tables cleanly.

2. **Full test suite passes on PostgreSQL**: All existing tests (284+ at time of milestone start) pass when run against PostgreSQL using the conditional PostgreSQL test fixture.

3. **No SQLite regression**: All existing tests continue to pass when run against SQLite with no code changes that break SQLite compatibility.

4. **Engine configuration**: SQLite-specific PRAGMAs are only applied to SQLite connections. PostgreSQL connections use appropriate pool settings without errors. No warnings or errors from SQLAlchemy engine initialization for either dialect.

5. **Engine factory is dialect-aware**: The engine factory in `app/database/engine.py` conditionally selects pool class (`NullPool` for SQLite, `QueuePool` for PostgreSQL) and applies dialect-specific connection settings.

6. **No architectural changes**: The verification must pass without modifying any domain logic, models, repositories, services, workflows, agents, schemas, API endpoints, or Alembic migrations. The only code changes allowed are to engine configuration (`app/database/engine.py`) and test infrastructure (`tests/conftest.py`). If a genuine cross-database incompatibility is found, the fix must be minimal and dialect-gated, scoped to the specific line or configuration causing the issue, with zero changes to domain behavior or architecture.

7. **PostgreSQL optional dependency declared**: `pyproject.toml` includes `psycopg2-binary` (or equivalent) in the `postgres` optional dependency group. Installing with `pip install -e ".[postgres]"` provides all required dependencies for PostgreSQL verification.

8. **Documentation updated**: All four documentation files (`docs/database.md`, `docs/project_state.md`, `docs/project_handoff.md`, `docs/codex_bootstrap.md`, and optionally `README.md`) are updated to reflect the completed milestone and provide PostgreSQL setup and testing instructions.

9. **No runtime behavior differences**: The application runs correctly with both `DATABASE_URL=sqlite:///database/irtiqa.db` and `DATABASE_URL=postgresql://...`. No code paths branch on the database dialect except where explicitly required for engine configuration and connection settings.
