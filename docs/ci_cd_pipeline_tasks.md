# CI/CD Pipeline Implementation Tasks

## Phase 1: Workflow Foundation

### Objective

Create the `.github/workflows/` directory structure and the `ci.yml` workflow file with the correct trigger configuration, job skeleton, and job dependency chain. This phase establishes the pipeline shell before any steps are added.

### Files Affected

| File | Action |
|---|---|
| `.github/workflows/ci.yml` | Create |

### Tasks

1.1. Create `.github/workflows/` directory at the repository root.

1.2. Create `.github/workflows/ci.yml` with the following structural elements:

- Workflow name: `CI`
- Trigger on `push` to `main`
- Trigger on `pull_request` to `main`
- Define two empty job stubs: `validate` and `test`
- Set `test: needs: validate` dependency
- Set both jobs to `runs-on: ubuntu-latest`
- Pin Python version to `3.11` in `actions/setup-python@v5` for both jobs

Do not add service containers or run steps in this phase.

1.3. Commit the file to a new feature branch (e.g., `ci-pipeline`).

1.4. Push the branch and open a draft pull request against `main`.

1.5. Confirm the pull request triggers both jobs to appear in the GitHub Actions checks list with "Waiting" or "Queued" status.

### Success Criteria

- [ ] `.github/workflows/ci.yml` exists on the feature branch
- [ ] Workflow triggers on push to the feature branch
- [ ] Workflow triggers on PR against main
- [ ] Both `validate` and `test` jobs appear in the Actions tab
- [ ] `test` job shows `needs: validate` dependency in the GitHub UI

---

## Phase 2: Validate Job

### Objective

Implement the `validate` job with ruff linting, mypy type checking, and compileall syntax verification. This is the fast-feedback gate — all three checks must pass before any tests run.

### Files Affected

| File | Action |
|---|---|
| `.github/workflows/ci.yml` | Modify (add validate job steps) |

### Tasks

2.1. Add the following steps to the `validate` job in order:

**Step 1 — Checkout repository**
- Action: `actions/checkout@v4`

**Step 2 — Setup Python 3.11**
- Action: `actions/setup-python@v5`
- Version: `3.11`
- Pip caching: optional (add if the workflow runtime approaches 7 minutes due to dependency install)

**Step 3 — Install dependencies**
- Command: `pip install .[dev]`
- Do not install PostgreSQL extras (`[postgres]` is not needed in the validate job)

**Step 4 — Run ruff check**
- Command: `python -m ruff check app tests`
- Uses existing pyproject.toml configuration (E, F, I, UP, B selects; line-length 100)
- Do not pass `--fix` — the pipeline reports violations; developer fixes locally

**Step 5 — Run mypy**
- Command: `python -m mypy app tests`
- Uses existing strict configuration with sqlalchemy mypy plugin
- Pipeline must fail on any type error

**Step 6 — Run compileall**
- Command: `python -m compileall app tests`
- Verifies zero syntax errors in application and test modules

2.2. Push to the feature branch and confirm each step runs.

2.3. If any step fails, add the correction (missing stub package, syntax fix, etc.) to the change set and re-push.

### Success Criteria

- [ ] `ruff check` step passes with zero violations on `app/` and `tests/`
- [ ] `mypy` step passes with zero type errors on `app/` and `tests/`
- [ ] `compileall` step passes with zero syntax errors on `app/` and `tests/`
- [ ] All three steps report success in the GitHub Actions check run
- [ ] If any step fails, the job reports a red X and stops further job execution

---

## Phase 3: Test Job

### Objective

Implement the `test` job with alembic schema drift detection and SQLite test execution against isolated temporary databases.

### Files Affected

| File | Action |
|---|---|
| `.github/workflows/ci.yml` | Modify (add test job steps, service container) |

### Tasks

3.1. Add a `services:` block to the `test` job with the PostgreSQL 18 service container (see Phase 4 for detailed configuration). The container must be defined now because the test job includes it, but only the PostgreSQL-specific steps in Phase 4 will use it at this point.

3.2. Add the following steps to the `test` job above the PostgreSQL-specific steps:

**Step 1 — Checkout repository**
- Action: `actions/checkout@v4`

**Step 2 — Setup Python 3.11**
- Action: `actions/setup-python@v5`
- Version: `3.11`
- Pip caching: optional

**Step 3 — Install dependencies**
- Command: `pip install .[dev,postgres]`
- Include `postgres` extras up front to avoid a second pip install later

**Step 4 — Run alembic check**
- Command: `python -m alembic check`
- Confirms no schema drift against SQLite migration history
- Does not require a running database server

**Step 5 — Run SQLite tests**
- Command: `python -m pytest`
- Executes the full test suite against isolated temporary SQLite databases
- PostgreSQL-specific tests are automatically skipped via the `postgresql_required` marker (DATABASE_URL is not set to a PostgreSQL URL at this step)
- Expected result: 284 passed

3.3. Push to the feature branch and confirm the test job runs after validate passes.

3.4. If `python -m alembic check` fails in CI (fresh checkout with no database file), investigate the `alembic.ini` `sqlalchemy.url` setting. If the URL references a file that does not exist in CI (e.g., `sqlite:///database/irtiqa.db`), add a per-step `env:` override for `DATABASE_URL` on the `alembic check` step only, or adjust `alembic.ini` to use a non-file-based URL. Do not set `DATABASE_URL` at the job level — the design requires per-step scoping to prevent the PostgreSQL connection string from leaking into other steps.

3.5. Verify that the PostgreSQL compatibility tests are correctly skipped during the SQLite step. Check the pytest output for the test selection count: the summary must show exactly 284 tests selected and 0 tests skipped for the SQLite step. If 308 tests are selected (indicating the PostgreSQL tests were not skipped), investigate whether an environment variable is leaking or the `postgresql_required` marker is misconfigured before proceeding to Phase 4.

### Success Criteria

- [ ] `alembic check` step passes with zero schema drift detected
- [ ] `python -m pytest` reports 284 passed tests (SQLite)
- [ ] Pytest output confirms exactly 284 tests selected (not 308), verifying the `postgresql_required` marker correctly skips all PostgreSQL compatibility tests
- [ ] All PostgreSQL-specific tests are silently skipped (not run, not failed)
- [ ] The `test` job only runs if the `validate` job passed
- [ ] `test` job with SQLite steps completes within 5 minutes

---

## Phase 4: PostgreSQL Verification

### Objective

Add the PostgreSQL 18 service container (if not already added in Phase 3) and the PostgreSQL-specific steps: migration application and compatibility test execution.

### Files Affected

| File | Action |
|---|---|
| `.github/workflows/ci.yml` | Modify (add service container, add PostgreSQL steps) |

### Tasks

4.1. If not already done in Phase 3, add the `services:` block to the `test` job:

- Image: `postgres:18`
- Database name: `irtiqa_ci`
- User: `postgres`
- Password: `postgres`
- Port mapping: `5432:5432`
- Health check: `pg_isready` with `--health-interval 10s`, `--health-timeout 5s`, `--health-retries 5`

4.2. Add the following steps after the SQLite pytest step (step 5 from Phase 3):

**Step 6 — Apply migrations to PostgreSQL**
- Command: `python -m alembic upgrade head`
- Environment variable: `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/irtiqa_ci`
- The container starts with an empty database; migrations must be applied before compatibility tests run

**Step 7 — Run PostgreSQL compatibility tests**
- Command: `python -m pytest tests/integration/test_postgresql_compatibility.py -v`
- Environment variable: `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/irtiqa_ci`
- Expected result: 24 passed

4.3. Verify that `DATABASE_URL` is scoped per-step (using `env:` under the step, not a global job-level environment variable). This prevents the PostgreSQL connection string from leaking into the SQLite test step.

4.4. Push to the feature branch and confirm all seven test job steps complete successfully.

### Success Criteria

- [ ] PostgreSQL 18 service container starts and reports healthy via `pg_isready`
- [ ] `alembic upgrade head` applies all 4 migrations to PostgreSQL with zero errors
- [ ] `python -m pytest tests/integration/test_postgresql_compatibility.py -v` reports 24 passed
- [ ] Full pipeline reports 308 total tests passed (284 SQLite + 24 PostgreSQL)
- [ ] `DATABASE_URL` does not leak into SQLite step (SQLite step still reports 284 passed)
- [ ] If PostgreSQL container fails to start, the step shows a clear container error

---

## Phase 5: README Integration

### Objective

Add the CI status badge to `README.md` so the repository shows build status at a glance.

### Files Affected

| File | Action |
|---|---|
| `README.md` | Modify (add badge) |

### Tasks

5.1. Add the following badge markdown to `README.md`, placed below the project title and above any other content:

```markdown
[![CI](https://github.com/Luffyz/irtiqa-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/Luffyz/irtiqa-intelligence/actions/workflows/ci.yml)
```

5.2. Confirm the badge resolves to a visible image in the rendered README.

5.3. After merging the workflow file to `main`, the badge will display the current CI status. Before the first CI run on main, it will show "no status" or "unknown."

### Success Criteria

- [ ] Badge markdown is present in README.md
- [ ] Badge renders as a clickable image linking to the Actions page
- [ ] Badge is placed directly below the project title

---

## Phase 6: Documentation Updates

### Objective

Update project documentation to reflect that CI now exists and PostgreSQL verification runs automatically on every push and pull request.

### Files Affected

| File | Action |
|---|---|
| `docs/project_state.md` | Modify |
| `docs/project_handoff.md` | Modify |
| `docs/codex_bootstrap.md` | Modify |

### Tasks

6.1. Update `docs/project_state.md`:

- Change "No CI configuration exists yet" under Open Issues to "CI configuration exists."
- Update the "Repository Health Summary" section to reflect that CI is operational.
- Update "Next Steps" to reflect that CI is complete and move to the next priority.
- Update the test count description to note that CI runs both SQLite and PostgreSQL tests automatically.

6.2. Update `docs/project_handoff.md`:

- Update Section 7 (Coding Standards): change "No CI pipeline exists yet" to "CI pipeline is configured with GitHub Actions."
- Update Section 9 (Current Roadmap): move "Add CI and quality gates" from pending to completed.
- Update Section 5 (Repository Health Summary): add CI as an operational component.
- Update "Open Issues" to remove "No CI configuration exists yet."

6.3. Update `docs/codex_bootstrap.md`:

- Update "Not implemented" section to remove "CI."
- Update "Current Status" to reflect CI completion.
- Update "What Should Be Built Next" to move past CI.

6.4. Do NOT modify `docs/ci_cd_pipeline_design.md` or `docs/ci_cd_pipeline_tasks.md` — these are reference documents that should remain as-is after implementation.

### Success Criteria

- [ ] `docs/project_state.md` no longer lists "No CI configuration exists yet" as an open issue
- [ ] `docs/project_handoff.md` no longer states "No CI pipeline exists yet"
- [ ] `docs/codex_bootstrap.md` no longer lists "CI" under "Not implemented"
- [ ] All three docs reflect that CI runs on every push and PR with SQLite + PostgreSQL verification
- [ ] All three docs mention PostgreSQL service container CI setup
- [ ] `docs/ci_cd_pipeline_design.md` is not modified

---

## Phase 7: Validation and Testing

### Objective

Verify the complete pipeline end-to-end on GitHub Actions, confirm all steps pass, and merge to main.

### Files Affected

None — this phase is verification only.

### Tasks

7.1. Push all changes to the feature branch (combined single commit).

7.2. Open a pull request against `main` (or update the existing draft PR).

7.3. Observe the running workflow in the GitHub Actions checks tab. Verify each step in order:

| Step | Job | Expected Result |
|---|---|---|
| Checkout | validate | ✅ Succeeds |
| Setup Python | validate | ✅ Succeeds |
| Install dependencies | validate | ✅ Succeeds |
| ruff check | validate | ✅ Zero violations |
| mypy | validate | ✅ Zero type errors |
| compileall | validate | ✅ Zero syntax errors |
| Checkout | test | ✅ Succeeds |
| Setup Python | test | ✅ Succeeds |
| Install dependencies | test | ✅ Succeeds (`[dev,postgres]`) |
| alembic check | test | ✅ No schema drift |
| pytest (SQLite) | test | ✅ 284 passed |
| alembic upgrade head (PG) | test | ✅ All 4 migrations applied |
| pytest (PostgreSQL) | test | ✅ 24 passed |

7.4. If any step fails:
- Determine which step failed from the GitHub UI check annotation
- Fix the root cause locally
- Re-push to the same branch
- Wait for the re-triggered workflow
- Repeat until all steps pass

7.5. Once all steps pass, merge the pull request to `main`.

7.6. After merge, verify the workflow triggers on the merge commit and completes successfully.

7.7. Verify the CI badge in README.md resolves and displays a green checkmark.

### Known Risks During Validation

| Risk | Check | Action If True |
|---|---|---|
| `alembic check` fails because `database/irtiqa.db` does not exist in CI | Run `python -m alembic check` in a fresh clone locally first | Add a per-step `env:` override for `DATABASE_URL` on the `alembic check` step only, or update `alembic.ini` |
| `pip install .[dev,postgres]` fails due to missing system dependencies | Check psycopg binary wheel availability | Add `libpq-dev` or equivalent; or pin `psycopg[binary]` version |
| PostgreSQL container fails to start due to runner Docker issue | Observe container error in Actions log | Re-run the workflow; if persistent, reduce `--health-retries` threshold or increase interval |

### Success Criteria

- [ ] All 7 steps in the validate and test jobs pass on the feature branch PR
- [ ] All 7 steps pass on the merge commit to main
- [ ] Full test count: 308 passed (284 SQLite + 24 PostgreSQL)
- [ ] Pipeline completes within 7 minutes
- [ ] CI badge displays green status on README.md
- [ ] All three documentation files are updated

---

## Expected Files Created

- `.github/workflows/ci.yml`

## Expected Files Modified

- `README.md` (add CI status badge)
- `docs/project_state.md` (update CI status, test count, open issues)
- `docs/project_handoff.md` (update coding standards, roadmap, health summary)
- `docs/codex_bootstrap.md` (update current status, not-implemented list)

## Expected Verification Commands

These commands should produce the same results locally as in CI. Run them before pushing to avoid CI failures.

```text
# Validate job commands
python -m ruff check app tests
python -m mypy app tests
python -m compileall app tests

# Test job — SQLite
python -m alembic check
python -m pytest

# Test job — PostgreSQL (requires local PostgreSQL)
python -m alembic upgrade head
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa_verify python -m pytest tests/integration/test_postgresql_compatibility.py -v
```
