# Background Job Foundation — Implementation Checklist

## Phase 1: Schema & Model Layer

### 1.1 Alembic Migration
- [ ] Create `database/migrations/versions/20260609_0003_add_jobs_table.py`
- [ ] Define `jobs` table with all columns per design
- [ ] Add check constraints: `status` values (`pending`, `running`, `succeeded`, `failed`, `cancelled`), `job_type` values, `retry_count` ≤ `max_retries`, `max_retries` ≥ 0
- [ ] Add indexes: `ix_jobs_status_scheduled_at`, `ix_jobs_target_name`, `ix_jobs_agent_run_id`
- [ ] Add `agent_run_id` foreign key → `agent_runs.id` (nullable, `SET NULL` on delete)
- [ ] Verify `alembic upgrade head` succeeds
- [ ] Verify `alembic check` reports no new operations after upgrade

### 1.2 ORM Model
- [ ] Create `app/models/job.py` with `Job` class
- [ ] Inherit from `Base` and `TimestampMixin`
- [ ] Use `Mapped[...]` / `mapped_column` conventions
- [ ] Export `Job` in `app/models/__init__.py`
- [ ] Verify model metadata matches migration schema

## Phase 2: Repository Layer

- [ ] Create `app/repositories/job_repository.py`
- [ ] Inherit from `BaseRepository[Job]`
- [ ] Implement `get_pending_jobs(limit: int = 10) → Sequence[Job]` (filter `status = 'pending'` and `scheduled_at <= now()` ordered by `scheduled_at` ascending)
- [ ] Implement `get_job_by_agent_run_id(agent_run_id: str) → Job | None`
- [ ] Export in `app/repositories/__init__.py`

## Phase 3: Service Layer

- [ ] Create `app/services/job_service.py`
- [ ] Inherit from `BaseService[JobRepository, Job]`
- [ ] Implement `schedule_agent(name, context, *, scheduled_at=None, max_retries=3) → Job`
- [ ] Implement `schedule_workflow(name, context, *, scheduled_at=None, max_retries=3) → Job`
- [ ] Implement `list_jobs(*, status=None, target_name=None, limit=50, offset=0) → Sequence[Job]`
- [ ] Implement `cancel_job(job_id: str) → Job` (guard: only `pending`)
- [ ] Implement `retry_job(job_id: str) → Job` (guard: only `failed`, reset to `pending`, increment retry logic)
- [ ] Implement `get_next_jobs(*, limit: int = 10) → Sequence[Job]`
- [ ] Implement `claim_job(job_id: str) → Job | None` (atomic update with status check)
- [ ] Export in `app/services/__init__.py`

## Phase 4: Job Package (Execution Layer)

### 4.1 Error Types
- [ ] Create `app/jobs/errors.py`
- [ ] Define `JobSchedulingError`, `JobExecutionError`, `JobCancellationError`
- [ ] All inherit from `IrtiqaError`, use stable codes
- [ ] Export in `app/jobs/__init__.py`

### 4.2 Retry Policy
- [ ] Create `app/jobs/retry_policy.py`
- [ ] Implement `compute_next_scheduled_at(retry_count, base_delay_seconds=60.0) → datetime`
- [ ] Exponential backoff with 10% jitter
- [ ] Unit test with deterministic seed for jitter verification

### 4.3 JobRunner
- [ ] Create `app/jobs/runner.py`
- [ ] Class `JobRunner` with `__init__(job_service, *, poll_interval=5.0)`
- [ ] `start()` / `stop()` coroutines
- [ ] `_poll_once()` — fetch next jobs, attempt claim, dispatch
- [ ] `_run_job(job)` — resolve via `AgentRegistry` or `WorkflowRunner`, execute, handle status transitions
- [ ] On success: `status = succeeded`, set `completed_at`, link `agent_run_id`
- [ ] On failure: log error, store `last_error`, if retries remain: increment `retry_count`, compute next `scheduled_at`, `status = pending`; else `status = failed`, `completed_at = now`

### 4.4 JobScheduler
- [ ] Create `app/jobs/scheduler.py`
- [ ] Class `JobScheduler` with `__init__(runner, *, poll_interval=5.0)`
- [ ] `run()` — polling loop with `asyncio.sleep`
- [ ] `shutdown()` — signal to stop clean
- [ ] Unit test: loop calls poll_once N times, shutdown breaks cleanly

## Phase 5: Schemas

- [ ] Create `app/schemas/job.py`
- [ ] `JobCreate` (internal or admin use)
- [ ] `JobRead` (UUID, type, target, status, scheduled/start/completed, retry info, error, agent_run_id)
- [ ] `JobList` (items, total, limit, offset)
- [ ] `JobScheduleAgentRequest` (agent_name, company_id, contact_id, options, scheduled_at, max_retries)
- [ ] `JobScheduleWorkflowRequest` (workflow_name, company_id, contact_id, options, scheduled_at, max_retries)
- [ ] Export in `app/schemas/__init__.py`

## Phase 6: API Endpoints

- [ ] Create `app/api/v1/endpoints/jobs.py`
- [ ] `POST /jobs/schedule-agent` — validate request → `JobService.schedule_agent()`
- [ ] `POST /jobs/schedule-workflow` — validate request → `JobService.schedule_workflow()`
- [ ] `GET /jobs/` — list with optional `status`, `target_name` query params (paginated)
- [ ] `GET /jobs/{job_id}` — read single job
- [ ] `POST /jobs/{job_id}/cancel` — cancel if `pending`
- [ ] `POST /jobs/{job_id}/retry` — retry if `failed`
- [ ] Wire into `app/api/v1/router.py`
- [ ] Add `get_job_service()` dependency in `app/api/dependencies.py`

## Phase 7: FastAPI Lifespan Integration

- [ ] Update `app/main.py` lifespan
- [ ] Construct `JobService` (pull from DI container / app state)
- [ ] Construct `JobRunner(job_service)`
- [ ] Construct `JobScheduler(runner)`
- [ ] Start scheduler via `asyncio.create_task(scheduler.run())`
- [ ] On shutdown: signal scheduler, `await` task to complete current job gracefully
- [ ] Ensure `database/irtiqa.db` is not required for tests (use in-memory/test URL)

## Phase 8: Tests

### Unit Tests
- [ ] `tests/unit/jobs/test_retry_policy.py` — deterministic and jittered cases
- [ ] `tests/unit/jobs/test_scheduler.py` — start/stop loop
- [ ] `tests/unit/jobs/test_runner.py` — mock service, verify state transitions (pending→running→succeeded, pending→running→failed→pending→succeeded, etc.)
- [ ] `tests/unit/jobs/test_errors.py` — serialization, inheritance

### Integration Tests
- [ ] `tests/integration/jobs/test_job_lifecycle.py`:
  - Schedule agent job → verify `pending`
  - Run scheduler tick → verify `running` → mock agent success → verify `succeeded` + `agent_run_id`
  - Run scheduler tick with failing agent → verify `failed` → retry → verify `pending` with incremented `retry_count`
- [ ] `tests/integration/jobs/test_job_api.py`:
  - `POST /jobs/schedule-agent` → `201 Created`
  - `GET /jobs/{job_id}` → correct job
  - `POST /jobs/{job_id}/cancel` → `cancelled` if `pending`
  - `POST /jobs/{job_id}/cancel` → `409 Conflict` if `running` or terminal
  - `POST /jobs/{job_id}/retry` → `pending` if `failed`, `409` otherwise
  - `GET /jobs?status=failed` → correct filtering

## Phase 9: Documentation Update

- [ ] Update `docs/project_state.md` — mark Background Job Foundation as in-progress / complete
- [ ] Update `docs/project_handoff.md` — add jobs package to architecture diagram, list completed tasks
- [ ] Update `docs/codex_bootstrap.md` — update current milestone to Background Job Foundation, next to PostgreSQL/CI
- [ ] Verify all test counts are updated (add new test counts to docs)

## Phase 10: Final Verification

- [ ] `python -m pytest` — all existing + new tests pass
- [ ] `python -m alembic upgrade head` — succeeds
- [ ] `python -m alembic check` — no new operations detected
- [ ] `python -m compileall app tests` — no syntax errors
- [ ] Verify `database/irtiqa.db` is not tracked by git (should be in `.gitignore`)