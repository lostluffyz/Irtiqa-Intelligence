> **Status: IMPLEMENTED**

# Intelligence Pipeline: Implementation Tasks

## Prerequisites: Runtime Stabilization (Already Implemented)

The following fixes from `docs/intelligence_pipeline_audit.md` have already been applied:

| Audit Finding | Fix | Status |
|---|---|---|
| `JobRunner._run_workflow_job()` read `result.agent_run_id` (None) — changed to `agent_run_ids[0]` | `app/jobs/runner.py` | ✅ Complete |
| `IntelligenceScoringAgent._run()` returned bare dict instead of `AgentRunOutput` | `app/agents/intelligence_scoring/agent.py` | ✅ Complete |
| Registries existed but were empty — all agents and `ScoreRefreshWorkflow` registered | `app/main.py` | ✅ Complete |
| Added `execute()` lifecycle tests for Technographic, IntelligenceScoring, Personalization agents | 4 new tests | ✅ Complete |
| Added workflow dispatch test verifying `agent_run_ids[0]` usage | 1 new test | ✅ Complete |

The pipeline tasks below assume these fixes are already in place.

---

## Phase 1: Pipeline Workflow

### Objective

Create the `IntelligencePipelineWorkflow` class that executes all five agents in sequence and aggregates their results. The workflow follows the existing `ScoreRefreshWorkflow` pattern: synchronous `execute()` with structured error handling.

### Files Affected

| File | Action |
|---|---|
| `app/workflows/intelligence_pipeline.py` | Create |
| `app/main.py` | Modify (register pipeline workflow) |

### Tasks

1.1. Create `app/workflows/intelligence_pipeline.py` with:

- **Class**: `IntelligencePipelineWorkflow(Workflow)` with `name = "intelligence_pipeline"`.
- **`__init__`**: Accept `**services` (same as `ScoreRefreshWorkflow`), call `super().__init__(**services)`, set `self.logger = get_logger(f"workflows.{self.name}")`.
- **`execute(self, context: WorkflowContext)`**: The main pipeline method containing all 5 steps.

1.2. Implement each step as an inner function call within `execute()`:

**Step 1 — Deep Scraper Agent:**
- Create `AgentContext` with `agent_name="deep_scraper"`, `company_id=context.company_id`, `workflow_name="intelligence_pipeline"`, options for `crawl_depth` and `max_pages` from `context.options`.
- Create `DeepScraperAgent(**services)` passing all service dependencies.
- Call `await agent.execute(context)`.
- Check for `AGENT_STATUS_FAILED` — if failed, raise `WorkflowError`.
- Collect `output_ids["websites"]` from result.

**Step 2 — Technographic Agent:**
- Create `AgentContext` with `agent_name="technographic"`, `company_id=context.company_id`, `workflow_name="intelligence_pipeline"`.
- Create `TechnographicAgent(**services)`.
- Call `await agent.execute(context)`.
- Check for `AGENT_STATUS_FAILED`.
- Collect `output_ids["technologies"]`.

**Step 3 — Intent Signal Agent:**
- Create `AgentContext` with `agent_name="intent_signal"`, `company_id=context.company_id`, `workflow_name="intelligence_pipeline"`.
- Create `IntentSignalAgent(**services)`.
- Call `await agent.execute(context)`.
- Check for `AGENT_STATUS_FAILED`.
- Collect `output_ids["intent_signals"]`.

**Step 4 — Intelligence Scoring Agent:**
- Create `AgentContext` with `agent_name="intelligence_scoring_agent"`, `company_id=context.company_id`, `contact_id=context.contact_id`, `workflow_name="intelligence_pipeline"`.
- Create `IntelligenceScoringAgent(**services)`.
- Call `await agent.execute(context)`.
- Check for `AGENT_STATUS_FAILED`.
- Collect `output_ids["intelligence_scores"]`.

**Step 5 — Personalization Agent:**
- Create `AgentContext` with `agent_name="personalization_agent"`, `company_id=context.company_id`, `contact_id=context.contact_id`, `workflow_name="intelligence_pipeline"`.
- Create `PersonalizationAgent(**services)`.
- Call `await agent.execute(context)`.
- Check for `AGENT_STATUS_FAILED`.
- Collect `output_ids["outreach_messages"]`.

**IMPORTANT**: Each agent call must use `await` because `BaseAgent.execute()` is async. The pipeline workflow must be async-compatible.

1.3. Return `WorkflowResult` with:

- `workflow_name="intelligence_pipeline"`
- `status=WorkflowStatus.SUCCEEDED`
- `company_id` and `contact_id` from context
- `agent_run_ids=[...]` (list of all agent_run_ids from results)
- `output_ids` containing all 5 output ID lists
- `steps` containing one `WorkflowStepResult` per agent
- `finished_at` set to current time

1.4. Error handling:

- Wrap all 5 steps in a single `try/except` block (matching `ScoreRefreshWorkflow` pattern).
- If an agent raises an `Exception`, catch it, log it, and return a `FAILED` `WorkflowResult` with the error.
- If an agent returns `AGENT_STATUS_FAILED`, raise `WorkflowError` with the agent's error message.

1.5. Register the pipeline workflow in `app/main.py`:

Add the import:
```python
from app.workflows.intelligence_pipeline import IntelligencePipelineWorkflow
```

Add the registration alongside the existing `ScoreRefreshWorkflow`:
```python
workflow_registry.register(ScoreRefreshWorkflow)
workflow_registry.register(IntelligencePipelineWorkflow)  # NEW
```

### Service Dependencies

Each agent in the pipeline requires specific service dependencies. The pipeline workflow must pass them through to the agents. The services required are:

| Service | Used By |
|---|---|
| `CompanyService` | Steps 1, 4, 5 |
| `ContactService` | Steps 4, 5 |
| `WebsiteService` | Steps 1, 2 |
| `TechnologyService` | Steps 2, 3, 4, 5 |
| `IntentSignalService` | Steps 3, 4, 5 |
| `IntelligenceScoreService` | Steps 4, 5 |
| `OutreachMessageService` | Step 5 |
| `AgentRunService` | All 5 steps |

The pipeline does not create these services — it receives them through `**services` from `WorkflowRunner` (which gets them from `JobRunner.workflow_services`).

### Verification Steps

- `python -c "from app.workflows.intelligence_pipeline import IntelligencePipelineWorkflow; print('Import OK')"`
- `python -c "from app.main import create_app; app = create_app(); print('App builds OK')"`
- `python -m compileall app`

### Success Criteria

- [ ] `IntelligencePipelineWorkflow` imports without errors
- [ ] `create_app()` succeeds (registers all workflows)
- [ ] Workflow compiles without syntax or type errors
- [ ] Workflow is registered in `WorkflowRegistry` alongside `ScoreRefreshWorkflow`
- [ ] `main.py` does not create new registry instances (uses existing ones)

### Rollback

- Delete `app/workflows/intelligence_pipeline.py`
- Remove the `IntelligencePipelineWorkflow` import and registration from `app/main.py`

---

## Phase 2: API Endpoints

### Objective

Create the `POST /intelligence/pipeline` and `GET /intelligence/pipeline/{job_id}` endpoints. These are thin wrappers around existing `JobService` methods. No new infrastructure is introduced.

### Files Affected

| File | Action |
|---|---|
| `app/api/v1/endpoints/intelligence.py` | Create |
| `app/api/v1/router.py` | Modify (register intelligence routes) |

### Tasks

2.1. Create `app/api/v1/endpoints/intelligence.py` with:

**`POST /intelligence/pipeline` — Trigger pipeline execution:**

- Accept a JSON body with:
  - `company_id` (required, string)
  - `contact_id` (optional, string)
  - `options` (optional, dict) — may contain `crawl_depth`, `max_pages`
- Validate that `company_id` is a non-empty string.
- Call `JobService.schedule_workflow()` with:
  - `name="intelligence_pipeline"`
  - `context` containing `company_id`, `contact_id`, `options`
- Return `202 Accepted` with `{"job_id": ..., "status": "scheduled", "target_name": "intelligence_pipeline"}`.

**`GET /intelligence/pipeline/{job_id}` — Query pipeline status:**

- Call `JobService.get(job_id)`.
- If not found, return 404.
- Return the job record including `status`, `scheduled_at`, `completed_at`, `retry_count`, `last_error`, `agent_run_id`, and any linked agent run information.

2.2. Follow existing endpoint patterns:

- Use `APIRouter(prefix="/intelligence", tags=["intelligence"])`.
- Use `Depends(get_job_service)` for `JobService` injection.
- Use existing error handling (404 for missing job, 422 for invalid input).
- Response models use existing `JobRead` schema or a custom pipeline status schema.

2.3. Register the router in `app/api/v1/router.py`:

```python
from app.api.v1.endpoints.intelligence import router as intelligence_router
router.include_router(intelligence_router)
```

2.4. Use `POST` for the trigger endpoint (creates a job) and `GET` for status queries (read-only). The response schema for `POST` should be a new Pydantic model:

```python
class PipelineTriggerResponse(IrtiqaSchema):
    job_id: str = Field(min_length=36, max_length=36)
    status: str = Field(default="scheduled")
    target_name: str = Field(default="intelligence_pipeline")
```

### Verification Steps

- `python -c "from app.api.v1.endpoints.intelligence import router; print(len(router.routes), 'routes')"`
- `python -c "from app.main import create_app; create_app(); print('App with intelligence routes OK')"`
- `python -m compileall app`

### Success Criteria

- [ ] `POST /intelligence/pipeline` returns 202 with job_id
- [ ] `GET /intelligence/pipeline/{job_id}` returns job status
- [ ] Missing job_id returns 404
- [ ] Router is registered in `app/api/v1/router.py`
- [ ] App factory creates successfully

### Rollback

- Delete `app/api/v1/endpoints/intelligence.py`
- Remove the intelligence router import and `include_router` from `app/api/v1/router.py`

---

## Phase 3: Unit Tests

### Objective

Create unit tests for the pipeline workflow. Tests use mocked services and agents to verify the pipeline logic without external dependencies.

### Files Affected

| File | Action |
|---|---|
| `tests/unit/workflows/test_intelligence_pipeline.py` | Create |

### Tasks

3.1. Create `tests/unit/workflows/test_intelligence_pipeline.py` with the following tests:

**`test_pipeline_step_execution`:**
- Create a `mock_services` dict with `MagicMock` instances for all required services.
- Create a mock context with a valid `company_id`.
- Run `workflow.execute(context)`.
- Verify output_ids contain all 5 expected keys: `websites`, `technologies`, `intent_signals`, `intelligence_scores`, `outreach_messages`.

**`test_pipeline_fails_on_step_failure`:**
- Make one agent's `execute()` return `AGENT_STATUS_FAILED`.
- Run `workflow.execute(context)`.
- Assert the result status is `FAILED`.
- Assert the error message contains the agent's error.

**`test_pipeline_aggregates_output_ids`:**
- Run workflow with mock data.
- Verify each step's output IDs are aggregated into the final `WorkflowResult.output_ids`.

**`test_pipeline_agent_run_ids`:**
- Run workflow with mock data.
- Verify `WorkflowResult.agent_run_ids` contains 5 entries (one per step).

**`test_pipeline_requires_company` (if applicable):**
- Create context with empty/missing `company_id`.
- Verify the pipeline raises a validation error before executing any agents.

**`test_pipeline_evidence_creation`:**
- Run workflow with mock data.
- Verify each agent's `execute()` was called with a context containing `workflow_name="intelligence_pipeline"`.

3.2. Mocking strategy:

- Mock individual agent `execute()` methods at the agent class level using `patch()`.
- Each mock returns a pre-built `AgentResult` with `AGENT_STATUS_SUCCEEDED`, a dummy `agent_run_id`, and the expected `output_ids`.
- The `AgentContext` must include `workflow_name="intelligence_pipeline"` for each step.
- Mock services: `CompanyService`, `ContactService`, `WebsiteService`, `TechnologyService`, `IntentSignalService`, `IntelligenceScoreService`, `OutreachMessageService`, `AgentRunService`.

3.3. Do NOT mock `IntelligencePipelineWorkflow.execute()` itself — the purpose of these tests is to validate the pipeline's orchestration logic, not individual agent behavior.

### Verification Steps

- `python -m pytest tests/unit/workflows/test_intelligence_pipeline.py -v`
- `python -m pytest` (confirm all existing tests still pass)

### Success Criteria

- [ ] All 6 unit tests pass
- [ ] Each test validates a distinct pipeline behavior
- [ ] Pipeline output aggregation is verified
- [ ] Failure handling is verified
- [ ] Agent run tracking is verified
- [ ] Existing 320 tests continue to pass

### Test Count Estimate

- 6 unit tests in `tests/unit/workflows/test_intelligence_pipeline.py`

### Rollback

- Delete `tests/unit/workflows/test_intelligence_pipeline.py`

---

## Phase 4: Integration Tests

### Objective

Create integration tests that verify the full pipeline through the API and job system. These tests use a real database (temporary SQLite) and mock HTTP to avoid external dependencies.

### Files Affected

| File | Action |
|---|---|
| `tests/integration/api/test_intelligence_pipeline.py` | Create |

### Tasks

4.1. Create `tests/integration/api/test_intelligence_pipeline.py` with:

**`test_pipeline_end_to_end`:**
- Seed the database with a `Company`, `Contact`, and `Website` records.
- Mock HTTP responses for the Deep Scraper Agent using `respx` (matching the existing test pattern in `tests/unit/agents/deep_scraper/test_agent.py`).
- Call `POST /intelligence/pipeline` with the company_id.
- Verify the response returns 202 with a job_id.
- Poll `GET /intelligence/pipeline/{job_id}` until status is `succeeded` or `failed`.
- Verify the result contains output_ids for all 5 entity types.
- Verify the total entity count is as expected.

**`test_pipeline_through_job_system`:**
- Seed data and mock HTTP as above.
- Directly schedule a workflow job via `JobService.schedule_workflow()` with `target_name="intelligence_pipeline"`.
- Run the job through `JobRunner._run_job()`.
- Verify the job completes with status `succeeded`.

**`test_pipeline_retry`:**
- Make the first pipeline execution fail (e.g., by providing a website that returns a 500).
- Verify the job is retried through `compute_next_scheduled_at`.
- After fixing the input, verify the pipeline succeeds on retry.

**`test_pipeline_multiple_runs`:**
- Run the pipeline twice against the same company.
- Verify that scores and messages are append-only (new records each run).
- Verify that websites and technologies are updated (not duplicated) for idempotent steps.

4.2. API test setup:

- Use the existing `api_session_factory` and `client` fixture pattern from other integration tests (see `tests/integration/api/test_evidence_api.py`).
- Use `monkeypatch.setattr(database_session, "SessionLocal", factory)` to inject the test database.

4.3. HTTP mocking:

- Use `respx` (already a dev dependency) to mock HTTP responses for the Deep Scraper Agent.
- Return realistic HTML content that triggers known technology signatures and intent signals.
- Match the existing mocking pattern in `tests/unit/agents/deep_scraper/test_agent.py`.

### Verification Steps

- `python -m pytest tests/integration/api/test_intelligence_pipeline.py -v`
- `python -m pytest` (confirm 320 existing tests still pass)

### Success Criteria

- [ ] All 4 integration tests pass
- [ ] Full pipeline produces all 5 output types
- [ ] Job dispatch through `JobRunner` works correctly
- [ ] Retry mechanism is verified
- [ ] Multiple runs produce append-only records
- [ ] Existing tests have zero regressions

### Test Count Estimate

- 4 integration tests in `tests/integration/api/test_intelligence_pipeline.py`

### Rollback

- Delete `tests/integration/api/test_intelligence_pipeline.py`

---

## Phase 5: Documentation

### Objective

Update project documentation to reflect the completed pipeline milestone.

### Files Affected

| File | Action |
|---|---|
| `docs/project_state.md` | Modify |
| `docs/project_handoff.md` | Modify |
| `docs/codex_bootstrap.md` | Modify |

### Tasks

5.1. Update `docs/project_state.md`:

- Add the Intelligence Pipeline to the list of completed components.
- Update the "Next Steps" section to reflect milestone completion.
- Update the test count to reflect the new tests (320 + 10 = 330).

5.2. Update `docs/project_handoff.md`:

- Add "Intelligence Pipeline" to the completed roadmap items in Section 9.
- Update Section 10 to reflect that the pipeline is now the next deliverable (or mark it complete).
- Update the architecture summary to include the pipeline workflow.
- Update test count references from "316" to "330".

5.3. Update `docs/codex_bootstrap.md`:

- Update "What Has Been Built" to include the pipeline.
- Update the Quick Start section.
- Update the Current Status section.

5.4. Do NOT modify `docs/intelligence_pipeline_design.md` or `docs/intelligence_pipeline_tasks.md` — these are reference documents.

### Verification Steps

- Verify each document renders correctly.
- Verify no stale test count references remain.

### Success Criteria

- [ ] `docs/project_state.md` marks pipeline as complete
- [ ] `docs/project_handoff.md` marks pipeline as complete
- [ ] `docs/codex_bootstrap.md` reflects pipeline completion
- [ ] All test count references use "330" (or the current count)
- [ ] Reference documents not modified

---

## Phase 6: Final Verification

### Objective

Run the complete test suite and verify the pipeline works end-to-end.

### Files Affected

None — verification only.

### Tasks

6.1. Run the full test suite:
```text
python -m pytest
```
Expected: All tests pass. Count should be approximately 330 passed + 27 skipped (PostgreSQL).

6.2. Run migration verification:
```text
python -m alembic upgrade head
python -m alembic check
```
Expected: "No new upgrade operations detected." No schema changes were made by this milestone.

6.3. Run compilation verification:
```text
python -m compileall app tests
```
Expected: Zero syntax errors.

6.4. Verify registry wiring:
```text
python -c "
from app.main import create_app
from app.agents.registry import AgentRegistry
from app.workflows.registry import WorkflowRegistry
# Confirm registries are populated by inspecting them through main
print('Registry wiring: OK')
"
```

6.5. Verify pipeline workflow execution:
```text
python -c "
from app.workflows.intelligence_pipeline import IntelligencePipelineWorkflow
from app.workflows.context import WorkflowContext
from unittest.mock import MagicMock
# Verify the workflow can be constructed and executed with mock services
workflow = IntelligencePipelineWorkflow(**mock_services)
context = WorkflowContext(
    workflow_name='intelligence_pipeline',
    company_id='test-uuid',
)
result = workflow.execute(context)
assert result.workflow_name == 'intelligence_pipeline'
print('Pipeline execution: OK')
"
```

6.6. Verify API endpoints:
```text
python -c "
from fastapi.testclient import TestClient
from app.main import create_app
app = create_app()
with TestClient(app) as client:
    r = client.post('/intelligence/pipeline', json={'company_id': 'test-id'})
    assert r.status_code in (202, 422)
print('API endpoints: OK')
"
```

### Success Criteria

- [ ] All ~330 tests pass
- [ ] No schema drift detected
- [ ] Zero compilation errors
- [ ] Registry wiring confirmed
- [ ] Pipeline workflow executes with mocked dependencies
- [ ] API endpoints respond correctly

---

## Files Expected to Be Created

- `app/workflows/intelligence_pipeline.py`
- `app/api/v1/endpoints/intelligence.py`
- `tests/unit/workflows/test_intelligence_pipeline.py`
- `tests/integration/api/test_intelligence_pipeline.py`

## Files Expected to Be Modified

- `app/main.py` (register `IntelligencePipelineWorkflow` in WorkflowRegistry)
- `app/api/v1/router.py` (register intelligence routes)
- `docs/project_state.md` (mark pipeline complete)
- `docs/project_handoff.md` (mark pipeline complete)
- `docs/codex_bootstrap.md` (update current status)

## Implementation Order

```text
Phase 1: Pipeline Workflow
  ├── Create app/workflows/intelligence_pipeline.py
  ├── Modify app/main.py (register pipeline workflow)
  └── Verify: imports, app builds, compileall

Phase 2: API Endpoints
  ├── Create app/api/v1/endpoints/intelligence.py
  ├── Modify app/api/v1/router.py (register routes)
  └── Verify: routes registered, app builds

Phase 3: Unit Tests
  ├── Create tests/unit/workflows/test_intelligence_pipeline.py
  └── Verify: 6 unit tests pass

Phase 4: Integration Tests
  ├── Create tests/integration/api/test_intelligence_pipeline.py
  └── Verify: 4 integration tests pass

Phase 5: Documentation
  ├── Modify docs/project_state.md
  ├── Modify docs/project_handoff.md
  ├── Modify docs/codex_bootstrap.md
  └── Verify: no stale references, consistent test counts

Phase 6: Final Verification
  ├── python -m pytest (~330 passed + 27 skipped)
  ├── python -m alembic check (no drift)
  ├── python -m compileall app tests (zero errors)
  ├── Registry wiring check
  ├── Pipeline execution check
  └── API endpoint check
```

## Total Test Count

| Category | Count |
|---|---|
| Existing tests | 320 |
| New unit tests (pipeline) | 6 |
| New integration tests (pipeline) | 4 |
| **Total** | **330** |
| PostgreSQL tests (skipped without PG) | 27 |

## Registry Wiring Notes

- Registries are created in `app/main.py` inside the FastAPI lifespan.
- Both `AgentRegistry` and `WorkflowRegistry` are already populated after the runtime stabilization fixes.
- The pipeline workflow must be added to the **existing** `workflow_registry` instance — do not create a new `WorkflowRegistry()`.
- No changes to `JobRunner` or how registries are passed are required.

## Workflow Execution Notes

- `IntelligencePipelineWorkflow.execute()` is **synchronous** (matching `ScoreRefreshWorkflow`).
- However, `BaseAgent.execute()` is **async**. The pipeline workflow must use `await` for each agent call.
- To use `await` in a synchronous method, the pipeline needs to run agents via `asyncio.run()` or the workflow must be async.
- The existing `ScoreRefreshWorkflow` is synchronous because it uses the scoring policy directly, not agents. The pipeline is different — it calls agents.
- **Solution**: Make `IntelligencePipelineWorkflow.execute()` an `async def` method, or wrap agent calls in `asyncio.run()`. The `WorkflowRunner` calls `execute()` directly — if changed to `async`, `WorkflowRunner` must also be updated, or the pipeline can use `asyncio.run()` internally.
- **Recommended approach**: Use `asyncio.run()` inside `execute()` for each agent call, keeping the public `execute()` method synchronous and compatible with the existing `WorkflowRunner`.
