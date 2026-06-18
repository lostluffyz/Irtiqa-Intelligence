> **Status: IMPLEMENTED**

# CI/CD Pipeline Design Audit: PostgreSQL in CI

## 1. Audit Scope

This document audits the decision in `docs/ci_cd_pipeline_design.md` to exclude PostgreSQL verification from GitHub Actions CI. It evaluates whether that decision is correct given the current project state and the project's architectural commitment to PostgreSQL compatibility.

## 2. Current PostgreSQL Verification State

The following facts were established during the PostgreSQL Compatibility Verification milestone and confirmed by the repository:

| Fact | Evidence |
|---|---|
| PostgreSQL 18 is the verified target | Verified locally, documented in project_state.md |
| 24 PostgreSQL compatibility tests exist | `tests/integration/test_postgresql_compatibility.py` |
| All 4 Alembic migrations apply cleanly on PostgreSQL | Verified round-trip (upgrade + downgrade) |
| Alembic `check` reports no drift on PostgreSQL | Confirmed in project handoff |
| 307 of 308 tests pass against PostgreSQL (1 intentional skip) | Full suite against PostgreSQL reported 307 passed |
| psycopg is declared as an optional dependency | `[project.optional-dependencies] postgres` in pyproject.toml |
| PostgreSQL test marker already exists | `postgresql_required` skipif in `tests/conftest.py` |
| PostgreSQL test fixtures already exist | `postgresql_engine`, `postgresql_session`, `postgresql_alembic_config` |

**What the 24 PostgreSQL tests verify:**

- Engine configuration (`QueuePool`, pool size, no SQLite PRAGMAs)
- Migration application (table creation, schema-vs-metadata parity, check constraints)
- CRUD operations (company creation, unique domain enforcement, foreign key enforcement, status constraints, confidence range constraints)
- Repository operations (company, contact repositories against PostgreSQL)
- Service layer (create, conflict detection, not-found, check constraint rejection)
- Cascading behavior (CASCADE delete, SET NULL on agent_run)
- Datetime handling (timezone-aware round-trip, naive datetime acceptance)
- Transaction rollback behavior
- UUID-as-string persistence
- Full entity graph persistence (companies through outreach_messages)
- Job lifecycle (create, query)

These tests are not trivial smoke tests. They exercise the full stack — engine config, migrations, repositories, services, and jobs — against PostgreSQL.

## 3. The Central Question

If CI does not run these 24 tests, **do they provide any gate value?**

Answer: **No.** A test that never runs in CI provides zero regression detection. It is documentation, not a gate.

The original design document acknowledged this but argued the risk was acceptable because:

> *"SQLite is the development target; PostgreSQL verification is a periodic compatibility check."*

This section examines whether that framing is correct for the current project state.

## 4. Risk Analysis: Silent PostgreSQL Breakage

### 4.1 Can PostgreSQL Support Silently Break While SQLite CI Stays Green?

**Yes.** The following classes of changes would pass all 284 SQLite tests but break some or all of the 24 PostgreSQL tests:

**Schema-level changes:**
- Adding a column with a default expression that works in SQLite but not PostgreSQL (e.g., SQLite-specific functions, non-standard SQL)
- Adding a check constraint using SQLite-only syntax
- Modifying an Alembic migration in a way that applies cleanly to SQLite but fails on PostgreSQL
- Introducing a PostgreSQL-reserved word as a column or table name
- Changing a column type to one SQLite handles permissively but PostgreSQL enforces strictly

**Type-level changes:**
- Introducing a type that SQLAlchemy maps differently on each dialect
- Changing datetime handling in a way that PostgreSQL's timezone-aware columns reject
- Modifying UUID handling in a way that PostgreSQL's native UUID type (if adopted) would break

**Engine-level changes:**
- Adding `visit_compiled()` or dialect-specific constructs that work on `aiosqlite` but not `psycopg`
- Changing pool configuration in a way that only affects PostgreSQL

**Migration-level changes:**
- Editing an existing migration (instead of adding a new one) that only gets tested against SQLite
- Adding a migration that depends on data that exists in SQLite but not PostgreSQL

### 4.2 Is This a Theoretical or Practical Risk?

**Both.** At this stage it is theoretical — no such regression has occurred. But the history of multi-dialect SQLAlchemy projects shows that dialect-specific breakage is a recurring pattern. Every migration, every new model, every repository enhancement is a point where SQLite and PostgreSQL can diverge.

The project explicitly requires "PostgreSQL compatibility through SQLAlchemy and Alembic" (AGENTS.md). If that compatibility is not verified in CI, the guarantee is unenforceable.

### 4.3 What Is the Consequence of a Silent Breakage?

At the current project stage (no PostgreSQL deployment, no production user relying on PostgreSQL), a silent breakage has no immediate operational impact. The consequence is **knowledge debt**: when the project eventually provisions PostgreSQL, the team discovers the breakage then — during a time-sensitive migration — rather than incrementally as each change is made.

The cost of fixing a regression committed 200 commits ago is higher than fixing one caught on the PR that introduced it.

## 5. Option Comparison

### Option A: SQLite-Only CI (Original Design)

| Dimension | Assessment |
|---|---|
| **Complexity** | Very low. ~30 lines of YAML, one job, no services. |
| **Runtime** | ~3-5 minutes. |
| **Maintenance** | Near zero. No service container to version-pin or troubleshoot. |
| **Regression detection** | Cannot detect PostgreSQL-specific regressions. 24 tests are dead code in CI. |
| **Long-term value** | Decreases over time. As the schema and codebase grow, PostgreSQL divergence accumulates undetected. |
| **Correctness guarantee** | "Works on SQLite." No statement about PostgreSQL. |

### Option B: SQLite CI + PostgreSQL Service Container

| Dimension | Assessment |
|---|---|
| **Complexity** | Low-to-moderate. Add ~20 lines of service container config, one extra pip install flag, and 3 extra run steps. Standard GitHub Actions pattern — well documented, widely used. |
| **Runtime** | ~5-8 minutes. PostgreSQL container adds ~15-30s startup (health check), ~5-10s for `alembic upgrade head`, ~30-60s for 24 tests. Total added: ~2 minutes max. |
| **Maintenance** | Low. PostgreSQL 18 Docker image is stable. Version bumps are infrequent (years). No custom PostgreSQL configuration required. |
| **Regression detection** | Catches all 24 PostgreSQL-specific regressions on every commit. Tests that exist actually gate merges. |
| **Long-term value** | Increases over time. Every schema change, every migration, every repository enhancement is verified against both databases from day one. As the project grows, this guardrail becomes more valuable, not less. |
| **Correctness guarantee** | "Works on SQLite AND PostgreSQL." Enforceable. |

### Side-by-Side Summary

| Criterion | Option A (SQLite only) | Option B (SQLite + PostgreSQL) |
|---|---|---|
| YAML size | ~30 lines | ~55 lines |
| Total runtime | ~4 min | ~6 min |
| Service containers | 0 | 1 (PostgreSQL 18) |
| Tests executed in CI | 284 | 308 |
| PostgreSQL regression risk | Real and undetected | Prevented |
| Extras installed | `[dev]` | `[dev,postgres]` |
| CI minutes per run | Low | Low + ~2 min |
| Maintenance burden | Negligible | Low (version pin, rare) |

## 6. Recommendation

**Adopt Option B: SQLite CI + PostgreSQL service container.**

Rationale:

1. **The tests exist and are proven.** 24 PostgreSQL tests already pass. The only missing piece is a CI service container to host them. The investment in writing these tests is fully realized only when they run automatically.

2. **The cost is low.** ~2 minutes of additional runtime and ~20 lines of YAML. This is a fraction of a typical CI pipeline.

3. **The risk is real.** PostgreSQL compatibility can silently break while SQLite CI stays green. The project is architected for PostgreSQL compatibility as a requirement (AGENTS.md), not a nice-to-have. An unenforceable requirement is not a requirement.

4. **The value compounds.** Every schema migration, every new model, every repository change from this point forward will be verified against PostgreSQL automatically. The earlier this is in place, the more regressions it prevents before they accumulate.

5. **The complexity is standard.** GitHub Actions service containers for PostgreSQL are a well-documented, widely used pattern. This is not novel infrastructure — it is established convention.

6. **PostgreSQL is installed and verified at version 18.** There is no discovery risk. The exact version is known and can be pinned.

### Counterargument and Response

**Counterargument**: "The project doesn't use PostgreSQL yet. A regression has no production impact. Adding PostgreSQL to CI is premature optimization."

**Response**: This argument confuses *production deployment* with *compatibility verification*. The project has already invested in PostgreSQL compatibility — 24 tests exist, migrations have been validated, the project architecture requires it. The only gap is that these tests never run automatically. This is not premature; it is completing an already-started investment. A regression caught in CI costs minutes. A regression caught during first PostgreSQL provisioning costs days of archaeology across hundreds of commits.

**Counterargument**: "Service containers add CI reliability risk. If the PostgreSQL container fails to start, the entire pipeline fails."

**Response**: This is true but manageable. The service container health check (`pg_isready` with retries) mitigates transient startup failures. If GitHub Actions runners cannot start PostgreSQL containers reliably, the project has a larger problem than CI configuration — every project on the platform would be affected. This is a known-working pattern.

## 7. Minimal PostgreSQL CI Setup

This section describes only what is needed to add PostgreSQL verification to the existing CI design. It supplements the design in `docs/ci_cd_pipeline_design.md` rather than replacing it.

### 7.1 Service Container

The `test` job requires a `services` block defining a PostgreSQL 18 container with:

- Image: `postgres:18`
- Environment variables: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- Port mapping: `5432:5432`
- Health check: `pg_isready` with appropriate intervals and retries

The database name, user, and password must match what the PostgreSQL step uses in `DATABASE_URL`.

### 7.2 Dependency Installation

The test job's `pip install` command must install the `postgres` extras in addition to `dev`:

```text
pip install .[dev,postgres]
```

This makes `psycopg` importable, which satisfies the `_HAS_PSYCOPG` check in `conftest.py`.

### 7.3 PostgreSQL Verification Step

After the SQLite test run completes, a dedicated step runs PostgreSQL verification:

1. **Set `DATABASE_URL`** to the PostgreSQL connection string matching the service container credentials.
2. **Run `alembic upgrade head`** — The service container starts with an empty database. Migrations must be applied before the compatibility tests run. This step uses the same `DATABASE_URL`.
3. **Run `pytest` scoped to PostgreSQL tests** — `python -m pytest tests/integration/test_postgresql_compatibility.py -v`. The `postgresql_required` marker evaluates to "do not skip" because `DATABASE_URL` starts with `postgresql` and `psycopg` is importable.

The step must use `DATABASE_URL` as an environment variable override (not a shell export) to ensure it does not leak into other steps.

### 7.4 Workflow Placement

The PostgreSQL verification step runs **after** the SQLite test step within the same `test` job. This preserves the existing job dependency chain:

```text
validate (ruff → mypy → compileall)
    │
    ▼
test (alembic check → pytest SQLite → pytest PostgreSQL)
```

Placing PostgreSQL within the existing `test` job (rather than as a third job) is intentional:

- It avoids duplicating checkout, Python setup, and dependency installation.
- It keeps the workflow file flatter.
- The `validate` job still provides fast-fail for linting/typing before any tests run.

### 7.5 What Does NOT Change

The following remain unchanged from the original design:

- **Validate job**: identical (ruff, mypy, compileall, no changes).
- **Test job checkout, Python setup, dependency install**: identical except `[postgres]` extras added.
- **Alembic check step**: identical (runs against SQLite default configuration).
- **SQLite pytest step**: identical (284 tests, no DATABASE_URL override needed).
- **Trigger configuration**: identical (push/PR to main).
- **No Docker, Kubernetes, AWS, Terraform, or deployment infrastructure**: unchanged.
- **No coverage thresholds, artifacts, or notifications**: unchanged.

### 7.6 Verification

After implementation, verify that:

1. The `validate` job passes (ruff, mypy, compileall).
2. `alembic check` passes against SQLite (no drift).
3. `python -m pytest` reports 284 passed (SQLite tests).
4. `alembic upgrade head` applies successfully against the PostgreSQL service container.
5. `python -m pytest tests/integration/test_postgresql_compatibility.py -v` reports 24 passed.
6. The full pipeline completes without the DATABASE_URL from the PostgreSQL step leaking into the SQLite step.

## 8. Updated YAML Structure

For reference, the updated test job structure with PostgreSQL included would be approximately 55 lines of YAML (up from ~30 in the original design). The increase is primarily the service container definition and the two PostgreSQL-specific run steps. No existing step is removed or significantly altered.

The two jobs (validate → test) and the single-workflow architecture are preserved.

## 9. Conclusion

The original design's decision to exclude PostgreSQL from CI was overly conservative. The PostgreSQL Compatibility Verification milestone is complete, the tests exist, the risk of silent breakage is real, and the cost of inclusion is low (approximately 20 additional YAML lines and 2 minutes of runtime). The project's architectural commitment to PostgreSQL compatibility is only enforceable when verified automatically on every change.

**Recommendation: Include PostgreSQL verification in CI as described in Section 7.**

The alternative — maintaining 24 tests that never run automatically — would leave a known detection gap that will widen as the project grows.
