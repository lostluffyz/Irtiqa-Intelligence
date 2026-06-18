> **Status: IMPLEMENTED**

# CI/CD Pipeline Design

## 1. Purpose

This document defines the minimum viable CI/CD pipeline for Irtiqa Intelligence at its current stage. The pipeline exists to enforce code quality, prevent regressions, and provide automated feedback on every push and pull request — without introducing deployment infrastructure or operational complexity that the project does not yet need.

The pipeline is scoped to the current repository state: a Python 3.11+ FastAPI backend with SQLite as the primary database, an Alembic-managed schema, ruff and mypy declared as dev dependencies, and a full test suite producing 308 passing tests (284 SQLite + 24 PostgreSQL). PostgreSQL compatibility is verified in every CI run using a GitHub Actions PostgreSQL 18 service container.

## 2. Current Project State

### Repository Snapshot

- **Language**: Python 3.11+
- **Framework**: FastAPI (app factory pattern)
- **Database**: SQLite-first with SQLAlchemy 2.0 ORM and Alembic migrations
- **Package Manager**: pip via pyproject.toml (no lockfile)
- **Linting**: ruff configured with E, F, I, UP, B rule sets
- **Type Checking**: mypy configured with strict mode and SQLAlchemy plugin
- **Testing**: pytest with pytest-asyncio (308 tests)
- **CI**: None
- **Deployment**: None
- **Platform**: GitHub

### Declared Dependencies

Core runtime: alembic, beautifulsoup4, fastapi, httpx, lxml, pydantic-settings, python-dotenv, sqlalchemy, uvicorn.

Development only: mypy, pytest, pytest-asyncio, respx, ruff.

PostgreSQL verification: psycopg[binary] (optional dependency group).

### Test Breakdown (most recent run)

- 284 SQLite tests pass in isolated temporary databases
- 24 PostgreSQL compatibility tests pass (against a local PostgreSQL instance)
- Alembic `check` reports no schema drift
- `compileall` passes on `app/` and `tests/`

### Key Files

```text
.github/                          (does not exist yet)
pyproject.toml                    (project metadata, tool configs)
alembic.ini                       (migration configuration)
tests/conftest.py                 (shared fixtures, database setup)
tests/unit/                       (unit tests)
tests/integration/                (integration tests)
tests/integration/test_postgresql_compatibility.py  (24 PostgreSQL tests)
```

### What Does NOT Exist

- No `.github/workflows/` directory
- No Docker, docker-compose, or container configuration
- No deployment manifests (Terraform, CloudFormation, Helm)
- No cloud infrastructure (AWS, GCP, Azure)
- No lockfile (requirements.txt, Pipfile.lock, poetry.lock)
- No coverage reporting configuration
- No pre-commit hooks
- No .python-version file

## 3. CI/CD Goals

### Primary Goals

1. **Prevent regressions** — Every push and pull request must pass the existing test suite before merging.
2. **Enforce code quality** — Linting (ruff) and type checking (mypy) must pass on every change.
3. **Verify schema integrity** — Alembic must confirm no undetected model drift on every change.
4. **Confirm compilation** — `compileall` must validate all .py files in `app/` and `tests/`.
5. **Verify PostgreSQL compatibility** — 24 PostgreSQL-specific tests must pass on every change using a Docker PostgreSQL 18 service container in GitHub Actions.
6. **Provide fast feedback** — The pipeline should complete within 7 minutes for typical changes.

### Explicitly Out of Scope

- No deployment pipeline (no staging, production, or release workflows)
- No Docker image building
- No cloud provider integration
- No container registry
- No infrastructure provisioning
- No artifact publishing
- No scheduled CI runs (only push and pull_request triggers)
- No coverage thresholds or gate (currently unconfigured; can be added later)
- No branch protection rule management (configured in GitHub UI, not in YAML)

## 4. Workflow Architecture

The pipeline uses a single GitHub Actions workflow with two jobs. This keeps the configuration minimal while providing clear failure isolation between validation and testing.

```text
Push / Pull Request
        │
        ▼
┌─────────────────────────────────────┐
│  Job 1: validate                    │
│  ├── checkout                       │
│  ├── setup Python                   │
│  ├── install dependencies           │
│  ├── ruff check                     │
│  ├── mypy app tests                 │
│  └── compileall app tests           │
└─────────────────────────────────────┘
        │ (must pass)
        ▼
┌─────────────────────────────────────┐
│  Job 2: test                        │
│  ├── checkout                       │
│  ├── setup Python                   │
│  ├── install dependencies           │
│  ├── alembic check                  │
│  ├── pytest (SQLite, 284 tests)     │
│  ├── alembic upgrade head (PG)      │
│  └── pytest (PostgreSQL, 24 tests)  │
└─────────────────────────────────────┘
        │ (must pass)
        ▼
    ✅ Pipeline passed
```

The `test` job also runs a PostgreSQL 18 service container alongside the runner. This container is started by GitHub Actions before any step runs, and is available throughout the job. The SQLite tests run first with no database environment variables set, then PostgreSQL-specific steps execute with `DATABASE_URL` pointing at the service container.

### Job Dependency Rationale

- **validate** runs first: linting, type checking, and compilation are fast (typically under 60 seconds) and catch the most common errors. If validation fails, the slower test job is never started, saving CI minutes.
- **test** runs second: migration verification, SQLite test execution, and PostgreSQL compatibility verification take longer (typically 4-6 minutes). This job depends on validate having passed.

### Why Not a Single Job

Separating validation and testing into two jobs provides clear failure attribution in the GitHub UI. A developer sees immediately whether a PR failed on linting/typing or on tests without collapsing output logs. The dependency chain (`test: needs: validate`) enforces ordering while keeping each job's purpose explicit.

## 5. GitHub Actions Design

### Workflow File

A single YAML file located at `.github/workflows/ci.yml`.

### Trigger Configuration

```yaml
on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]
```

Rationale:
- `push` on `main` catches direct commits and merges.
- `pull_request` on `main` provides pre-merge validation for all PRs.
- Path filtering is deliberately omitted: any file change can break linting or tests. If the project grows large enough that documentation-only or markdown-only changes trigger unnecessary CI, path filters can be added later.

### Runner

`ubuntu-latest` — GitHub's standard Linux runner. The project has no platform-specific dependencies that require Windows or macOS.

### Python Version

`3.11` — matches the `requires-python = ">=3.11"` constraint in pyproject.toml. Pin to 3.11 explicitly rather than using a range or `3.x` to ensure deterministic CI behavior. Update when the project formally adopts a newer Python version.

### Job 1: validate

Steps:

1. **Checkout repository** — `actions/checkout@v4`.
2. **Setup Python 3.11** — `actions/setup-python@v5` with `python-version: "3.11"`. Caching pip is optional at this stage (dependency install is fast) but can be added if the workflow approaches the 7-minute goal without it.
3. **Install dependencies** — `pip install .[dev]`. This installs the core package plus the `dev` extras (ruff, mypy, pytest, etc.). PostgreSQL extras are not needed in the validate job.
4. **Run ruff check** — `python -m ruff check app tests`. Uses the existing configuration from pyproject.toml (select E, F, I, UP, B; line-length 100). No `--fix` in CI — the pipeline reports violations; the developer fixes locally.
5. **Run mypy** — `python -m mypy app tests`. Uses the existing strict configuration with sqlalchemy mypy plugin. The pipeline fails if mypy reports any type errors.
6. **Run compileall** — `python -m compileall app tests`. Verifies all application and test modules compile without syntax errors.

### Job 2: test

Depends on: `validate` (must have completed successfully).

**Service container**: The job defines a PostgreSQL 18 service container via the `services` block. GitHub Actions starts the container with a health check (`pg_isready`) and maps port 5432 to the runner. The container runs for the entire job lifetime and is accessible at `localhost:5432`.

Container configuration:
- Image: `postgres:18`
- Database: created with a name matching the `DATABASE_URL` used in the PostgreSQL step (e.g., `irtiqa_ci`)
- Credentials: purpose-specific user and password (e.g., `postgres`/`postgres`)
- Port: `5432:5432`
- Health check: `pg_isready` with appropriate interval, timeout, and retry count

Steps:

1. **Checkout repository** — `actions/checkout@v4`.
2. **Setup Python 3.11** — `actions/setup-python@v5` with `python-version: "3.11"`.
3. **Install dependencies** — `pip install .[dev,postgres]`. PostgreSQL extras (`psycopg[binary]`) are required for the PostgreSQL step; installing them up front avoids a second `pip install` call.
4. **Run alembic check** — `python -m alembic check`. Confirms no schema drift. This command reads `alembic.ini` and the SQLAlchemy models. It does not require a running database server — Alembic compares model metadata against migration history only. For SQLite, this is sufficient because migrations define the target schema.
5. **Run SQLite tests** — `python -m pytest`. Executes the full test suite against isolated temporary SQLite databases. The existing conftest.py uses SQLite by default when `DATABASE_URL` is not set to a PostgreSQL connection string. No CI-specific pytest configuration is required. PostgreSQL-specific tests are skipped automatically by the `postgresql_required` marker because `DATABASE_URL` is not set to a PostgreSQL URL at this step.
6. **Apply migrations to PostgreSQL** — `python -m alembic upgrade head` with `DATABASE_URL` set to the service container's connection string. The PostgreSQL container starts with an empty database; migrations must be applied before running the compatibility tests.
7. **Run PostgreSQL compatibility tests** — `python -m pytest tests/integration/test_postgresql_compatibility.py -v` with `DATABASE_URL` set to the service container's connection string. The `postgresql_required` marker evaluates to "do not skip" because `psycopg` is importable and `DATABASE_URL` starts with `postgresql`.

### Full YAML Skeleton

```yaml
name: CI

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install .[dev]
      - run: python -m ruff check app tests
      - run: python -m mypy app tests
      - run: python -m compileall app tests

  test:
    needs: validate
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:18
        env:
          POSTGRES_DB: irtiqa_ci
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install .[dev,postgres]
      - run: python -m alembic check
      - run: python -m pytest
      - name: Apply migrations to PostgreSQL
        run: python -m alembic upgrade head
        env:
          DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/irtiqa_ci
      - name: PostgreSQL compatibility tests
        run: python -m pytest tests/integration/test_postgresql_compatibility.py -v
        env:
          DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/irtiqa_ci
```

### Workflow Name and Badge

The workflow is named `CI`. After the workflow file exists, a status badge can be added to `README.md`:

```markdown
[![CI](https://github.com/Luffyz/irtiqa-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/Luffyz/irtiqa-intelligence/actions/workflows/ci.yml)
```

The badge should be placed at the top of README.md, below the project title. This step is optional but recommended for at-a-glance CI status.

### Expected Runner

All steps run on `ubuntu-latest`. No self-hosted runners, no matrix builds, no operating system matrix. A single runner is sufficient for the current project size and test suite.

## 6. Test Strategy

### What the Pipeline Tests

The pipeline runs tests against two database targets:

**SQLite tests** (284 tests, primary development target):

- Model metadata integrity
- ORM relationship persistence
- Repository CRUD operations
- Service layer business logic and transaction behavior
- Schema validation (create, update, read, list)
- API endpoint behavior (health, CRUD, error responses)
- Workflow foundation (context, result, state, registry, runner, scoring, retry)
- Agent interface (context, result, registry, lifecycle)
- Deep Scraper Agent, Technographic Agent, Intent Signal Agent, Intelligence Scoring Agent, Personalization Agent
- Background Job Foundation (scheduler, runner, retry policy, errors, lifecycle, API)
- Logging configuration and behavior
- Structured error hierarchy
- Database hardening constraints
- Migration and schema alignment
- session_scope commit and rollback

**PostgreSQL compatibility tests** (24 tests, verified against PostgreSQL 18 service container):

- Engine configuration (QueuePool, pool sizing, SQLite PRAGMA exclusion)
- Migration application (table creation, schema-vs-metadata parity, check constraints)
- CRUD operations (company creation, unique domain enforcement, foreign key enforcement, status and range constraints)
- Repository operations (company and contact queries)
- Service layer (create, conflict detection, not-found handling, constraint rejection)
- Cascading behavior (CASCADE delete, SET NULL on agent_run)
- Datetime handling (timezone-aware round-trip, naive datetime acceptance)
- Transaction rollback behavior
- UUID-as-string persistence
- Full entity graph persistence (companies through outreach_messages)
- Job lifecycle (create, query)

### What the Pipeline Does NOT Test

- Visual or UI behavior (no frontend)
- External API integrations (none implemented)
- Performance or load behavior (no benchmarks)

### Test Isolation

The existing conftest.py creates isolated temporary SQLite databases for each test session. No test artifacts persist between runs. The pipeline does not require any special cleanup steps.

### Expected Test Count

The most recent full test run reported 308 passed (284 SQLite + 24 PostgreSQL). In CI, with the PostgreSQL service container available:

- SQLite step: **284 passed**
- PostgreSQL step: **24 passed**
- Full pipeline: **308 passed**

The SQLite step runs the full suite; the `postgresql_required` marker in conftest.py causes the 24 PostgreSQL tests to self-skip because `DATABASE_URL` is not set to a PostgreSQL URL for that step. The PostgreSQL step runs only the compatibility test file with `DATABASE_URL` explicitly set, so the marker evaluates to "do not skip."

### Post-Merge Verification

No post-merge or scheduled runs are configured. The pipeline validates only on push and pull_request. This is sufficient for the current single-contributor, single-branch stage.

## 7. Failure Conditions

Each failure mode produces a clear GitHub Actions check run with the failing step highlighted. No custom error handling or notification logic is needed.

### Validate Job Failures

| Condition | Step | Outcome | User Action |
|---|---|---|---|
| Ruff reports violations | ruff check | ❌ Red X, violations listed | Run `ruff check` locally, fix issues, re-push |
| MyPy reports type errors | mypy | ❌ Red X, errors listed | Run `mypy` locally, fix type issues, re-push |
| Compile error in any .py file | compileall | ❌ Red X, file and error listed | Fix syntax error locally, re-push |

### Test Job Failures

| Condition | Step | Outcome | User Action |
|---|---|---|---|
| Alembic detects schema drift | alembic check | ❌ Red X, drift description | Generate migration (`alembic revision --autogenerate`), review, commit, re-push |
| Any SQLite test fails | pytest (SQLite) | ❌ Red X, failure output with traceback | Run tests locally with `python -m pytest`, inspect failure, fix, re-push |
| Test collection error (SQLite) | pytest (SQLite) | ❌ Red X, collection error | Fix import or module structure, re-push |
| Migrations fail on PostgreSQL | alembic upgrade head (PG) | ❌ Red X, migration error | Inspect migration for PostgreSQL-incompatible SQL or type usage, fix, re-push |
| Any PostgreSQL test fails | pytest (PostgreSQL) | ❌ Red X, failure output with traceback | Run PostgreSQL tests locally with `DATABASE_URL=... python -m pytest tests/integration/test_postgresql_compatibility.py`, inspect failure, fix, re-push |
| PostgreSQL service container fails to start | service container startup | ❌ Red X, container error | Check service container configuration and PostgreSQL 18 image availability; re-run |

### Infrastructure Failures (Non-Project)

| Condition | Outcome | Mitigation |
|---|---|---|
| GitHub Actions outage | ❌ No check runs | Re-run failed workflows when service is restored |
| Runner timeout | ❌ Workflow cancelled | Default 6-hour timeout is more than sufficient; no change needed |
| Dependency install failure | ❌ Step failed | Check PyPI availability and dependency metadata; re-run |

### Notification

No email, Slack, or external notification integration. GitHub's built-in commit status and PR check annotations provide sufficient feedback for the current stage.

## 8. Deliverables

### Files to Create

1. **`.github/workflows/ci.yml`** — Single workflow file containing the validate and test jobs as designed in Section 5.

### Files to Modify

2. **`README.md`** — Add CI status badge at the top of the file, below the project title. This is the only modification to existing files that the pipeline design requires. The badge URL depends on the GitHub repository path, which is already known (`Luffyz/irtiqa-intelligence`).

### Files Not Modified

| File | Reason |
|---|---|
| `pyproject.toml` | Ruff and mypy configuration already exists and is correct. No CI-specific config needed. |
| `alembic.ini` | No changes needed. Works in CI as-is. |
| `tests/conftest.py` | Database isolation is already implemented. No CI-specific fixture changes needed. |
| `.gitignore` | No new artifacts generated by CI that would need ignoring. |
| `docs/project_state.md` | Not part of the pipeline design; will be updated during implementation. |
| `docs/project_handoff.md` | Not part of the pipeline design; will be updated during implementation. |
| `docs/codex_bootstrap.md` | Not part of the pipeline design; will be updated during implementation. |

### Verification Steps After Implementation

1. Push the `.github/workflows/ci.yml` file to a feature branch.
2. Open a pull request against `main`.
3. Confirm the `validate` job runs and completes (ruff, mypy, compileall).
4. Confirm the `test` job runs after `validate` passes.
5. Confirm the SQLite pytest step reports 284 passed tests.
6. Confirm the `alembic upgrade head` step applies cleanly against the PostgreSQL service container.
7. Confirm the PostgreSQL compatibility step reports 24 passed tests.
8. Confirm the full pipeline reports 308 passed tests.
9. Merge the pull request.
10. Confirm the pipeline runs on the merge commit to `main`.
11. Optionally add the CI badge to `README.md`.

## 9. Success Criteria

The pipeline is successful when:

1. Every push to main triggers a workflow run that completes within 7 minutes.
2. Every pull request against main triggers a workflow run that blocks merge until green.
3. Ruff reports zero violations on `app/` and `tests/`.
4. MyPy strict mode reports zero type errors on `app/` and `tests/`.
5. `compileall` confirms zero syntax errors in `app/` and `tests/`.
6. `alembic check` confirms zero schema drift against SQLite.
7. `pytest` reports all 284 SQLite tests as passed (zero failures).
8. `alembic upgrade head` applies successfully to the PostgreSQL 18 service container with zero errors.
9. `pytest` reports all 24 PostgreSQL compatibility tests as passed (zero failures) when pointed at the PostgreSQL service container.
10. The pipeline provides clear failure output for each failing step without requiring log inspection to determine which check failed.
11. No Docker image building, Kubernetes, AWS, Terraform, or deployment infrastructure is introduced.
12. No changes to the application code, test code, or database configuration are required.

## 10. Risks

### Risk: Pipeline Runtime Exceeds 7 Minutes

The current test suite reports 308 tests (284 SQLite + 24 PostgreSQL). Test execution against SQLite typically completes within 2-4 minutes. The PostgreSQL service container startup adds ~15-30 seconds, migration application adds ~5-10 seconds, and the 24 PostgreSQL tests add ~30-60 seconds. The validate job (ruff, mypy, compileall) typically completes in under 60 seconds.

**Mitigation**: Pip caching can be added to `actions/setup-python@v5` if dependency installation becomes a bottleneck. If PostgreSQL container startup proves slow, the health check retry interval can be tuned. No other mitigation is expected to be needed at the current test count.

### Risk: PostgreSQL Service Container Fails to Start

The test job depends on a Docker PostgreSQL 18 container launched by GitHub Actions. Runner-level Docker issues, image pull failures, or health check timeouts could cause the container to never reach ready state, failing the entire test job.

**Mitigation**: The `--health-cmd pg_isready` with 5 retries and 10-second intervals (up to ~50 seconds total timeout) handles transient startup delays. Container startup failures are infrastructure-level issues that affect all GitHub Actions projects equally. Re-running the workflow resolves transient failures.

### Risk: Alembic Check Fails in CI

Workflow runs in a fresh checkout with no `database/irtiqa.db` file. Alembic check does not require a local database file at the tip of the migration chain — it validates model-to-migration consistency only. However, if `alembic.ini` references a `sqlalchemy.url` that expects an existing database file, the check command may fail.

**Mitigation**: Verify that `python -m alembic check` succeeds in a fresh clone (no database file) during the verification phase. If it fails, `alembic.ini` may need a dummy `sqlalchemy.url` or the command may need an environment variable override. This is unlikely given the existing SQLAlchemy engine configuration, but must be confirmed before declaring the pipeline complete.

### Risk: Dependency Install Succeeds Locally but Fails in CI

Local development may have packages installed globally or in a virtual environment with pre-existing dependencies. A fresh CI environment may surface missing or conflicting dependencies.

**Mitigation**: The `pyproject.toml` declares all known dependencies. Installing via `pip install .[dev]` in a fresh environment will expose any gaps. Fix gaps by adding any missing dependencies to `pyproject.toml` before finalizing the pipeline.

### Risk: MyPy Strict Mode Produces Errors in CI But Not Locally

MyPy may report different results depending on installed stub packages or environment state. A fresh CI environment may surface type errors that local configurations hide.

**Mitigation**: Run `python -m mypy app tests` in a clean virtual environment locally before pushing. If errors appear only in CI, install missing stub packages (`types-*`) as dev dependencies.

### Risk: Pipeline Becomes a Maintenance Burden

As the project grows, pipeline configuration can accumulate complexity (matrix builds, caching, artifact upload, deployment stages) that exceeds the project's actual needs.

**Mitigation**: This design explicitly scopes the pipeline to the current project state. No speculative future architecture is included. When the project grows, the pipeline should be extended deliberately, not preemptively.

---

## Files Expected to Be Created

- `.github/workflows/ci.yml`

## Files Expected to Be Modified

- `README.md` (add CI status badge)
