> **Status: IMPLEMENTED**

# Intelligence Pipeline Design Audit

## 1. Registry Wiring

### Finding 1.1: Registries Already Exist in main.py — Design Proposes Duplicate Instances

**Severity: High**

The design says registries "must be populated during application startup" and proposes creating new `AgentRegistry()` and `WorkflowRegistry()` instances in the code example under "Agent Registry Assessment." However, `app/main.py` **already** creates both registry instances and passes them to `JobRunner`:

```python
# app/main.py (existing code, lines 66-75)
agent_registry = AgentRegistry()
workflow_registry = WorkflowRegistry()

job_runner = JobRunner(
    job_service=job_service,
    agent_registry=agent_registry,
    workflow_registry=workflow_registry,
    poll_interval=5.0,
)
```

These instances exist but are empty — no `.register()` calls are made anywhere in production code. The design's proposed code creates **new** instances that would be separate from the ones already wired into `JobRunner`. Adding `.register()` calls to the instances in `main.py` is sufficient; creating new instances is incorrect.

**Impact**: If an implementation follows the design literally and creates separate registry instances, the pipeline would fail with "Workflow is not registered" because `JobRunner` uses the empty originals from `main.py`.

**Recommended fix**: Replace the "Registry Wiring" section's code example with instructions to add `.register()` calls to the **existing** registry instances in `app/main.py`, not to create new ones.

---

### Finding 1.2: Registry Ownership and Lifecycle Are Defined but Duplicated

**Severity: Low**

The design recommends registries be populated in `app/workflows/__init__.py` OR `app/main.py`. These are different locations with different lifecycle semantics:
- `app/workflows/__init__.py` is imported at module load time (eager, before the app exists).
- `app/main.py` is called during `create_app()` (within the lifespan, after config is loaded).

The existing empty registries are in `app/main.py`. Adding registration there is the correct location because:
1. It's consistent with where the registries are already created.
2. It runs within the lifespan, matching the existing pattern.
3. It has access to any configuration needed (though none is needed for registration).

**Impact**: Low — an implementer would figure this out when they see the existing `main.py` code. But the ambiguity could cause confusion on the first attempt.

**Recommended fix**: Pin the location to `app/main.py` explicitly. Remove the `app/workflows/__init__.py` option.

---

### Finding 1.3: AgentRegistry Is Not Actually Needed for the Pipeline Design

**Severity: Low**

The design's "Agent Registry Assessment" correctly notes that the pipeline imports agents statically (not through AgentRegistry). AgentRegistry is only needed for ad-hoc agent job scheduling through `JobRunner._run_agent_job()`, which is a future use case, not part of this pipeline.

Including AgentRegistry wiring in the pipeline deliverables adds scope that is not required for the pipeline to function:
- 5 additional `agent_registry.register()` calls
- No tests that validate agent dispatch through JobRunner
- Code that won't be executed by the pipeline

**Impact**: Low — the extra code is harmless and provides future value, but it's not part of the pipeline milestone.

**Recommended fix**: Either (a) remove AgentRegistry wiring from the pipeline deliverables and add it as a separate task, or (b) keep it as documented future work. If kept, note that it's for future agent job dispatch, not for the pipeline.

---

## 2. JobRunner Dispatch Compatibility

### Finding 2.1: WorkflowResult.agent_run_id Does Not Match JobRunner Expectations

**Severity: Critical**

The `JobRunner._run_workflow_job()` accesses `result.agent_run_id` (singular):

```python
# app/jobs/runner.py, line 161
if result.agent_run_id:
    self.job_service.update(job.id, ..., agent_run_id=result.agent_run_id)
```

But `WorkflowResult` (in `app/workflows/result.py`) only defines `agent_run_ids` (plural, a list):

```python
agent_run_ids: list[str] = Field(default_factory=list)
```

There is no `agent_run_id` field. Accessing `result.agent_run_id` would raise an `AttributeError` on any `WorkflowResult` that hasn't been dynamically assigned that attribute.

**This is a pre-existing bug** — the existing `score_refresh` workflow also sets `agent_run_ids=[agent_run.id]` (plural) in its `WorkflowResult`, so the same failure would occur for any workflow job dispatched through `JobRunner`.

**Impact**: The pipeline (and score_refresh) cannot complete through the job system. The `JobRunner._run_workflow_job()` fails when trying to link the agent run to the job record.

**Recommended fix**: Either:
1. Fix `JobRunner._run_workflow_job()` to read `result.agent_run_ids[0]` (first agent run ID from the workflow result), or
2. Add both `agent_run_id` (singular, set to the last step's agent_run_id) and `agent_run_ids` (plural) to `WorkflowResult`.

This fix belongs to the JobRunner, not to the pipeline. It's a prerequisite for the pipeline to function.

---

### Finding 2.2: JobRunner Checks `result.agent_run_id` — Pipeline Returns 5 IDs

**Severity: Medium**

Even with Fix 2.1 applied (reading the first ID from `agent_run_ids`), the JobRunner only stores **one** `agent_run_id` on the job record:

```python
# app/jobs/runner.py, line 166
self.job_service.update(job.id, ..., agent_run_id=result.agent_run_id)
```

The pipeline produces 5 agent_run IDs (one per step). Only the last one (or first one, depending on the fix) would be stored. The other 4 agent_run IDs would only be accessible through the `WorkflowResult`, not through the `jobs` table.

**Impact**: Medium — the job record loses the reference to 4 of the 5 agent runs. Finding the other agent runs for a pipeline run requires querying by `workflow_name="intelligence_pipeline"` on the agent_runs service, not through the job's FK.

**Recommended fix**: Accept this limitation for the current stage. The `agent_run_ids` field on `WorkflowResult` preserves all 5 IDs for programmatic access. A future improvement could add a `pipeline_run_details` endpoint that joins the job, all 5 agent_runs, and their evidence.

---

## 3. WorkflowRegistry Lifecycle

### Finding 3.1: Registries Are Created in `main.py` Lifespan, Not at Module Level

**Severity: Informational**

The design says "The registry should be populated during application startup, in the FastAPI lifespan function." This matches the existing code in `app/main.py` where registries are created inside the lifespan. The registry wiring should add `.register()` calls to these existing instances.

Confirmed: ✅ The design's recommendation matches the existing pattern.

---

## 4. AgentRegistry Lifecycle

### Finding 4.1: Same as Finding 1.3 — AgentRegistry Exists but Is Unused

**Severity: Low**

Confirmed: ✅ The AgentRegistry is unused in production. The design correctly identifies this gap and recommends populating it. No additional findings.

---

## 5. Scoring Path Duplication

### Finding 5.1: Pipeline Uses IntelligenceScoringAgent, Not ScoreRefreshWorkflow

**Severity: Informational**

The pipeline calls the `IntelligenceScoringAgent` (an agent) at Step 4, not the `ScoreRefreshWorkflow` (a workflow). Both use the same `DeterministicScoreRefreshPolicy`. The agent and workflow paths are independent — they don't conflict because scores are append-only.

The IntelligenceScoringAgent's `_run()` method:
1. Fetches company, contact, technologies, intent signals
2. Calls `policy.score(ScoreRefreshInput(...))`
3. Creates an `IntelligenceScore` record
4. Returns output_ids

The ScoreRefreshWorkflow does the same thing but in a workflow context. The pipeline's approach is correct — using the agent (not the workflow) maintains consistency with the pipeline's agent-based step architecture. ✅

---

### Finding 5.2: IntelligenceScoringAgent Returns Incorrect Format

**Severity: Critical** (pre-existing bug)

The `IntelligenceScoringAgent._run()` returns:

```python
return {"intelligence_scores": [score.id]}
```

This is NOT an `AgentRunOutput` TypedDict. `BaseAgent.execute()` expects `output_ids`, `summary`, and `stats` keys:

```python
run_output = await self._run(context)
...
return AgentResult(
    output_ids=run_output["output_ids"],   # KeyError: 'output_ids'
    summary=run_output["summary"],         # KeyError if reached
    stats=run_output["stats"],             # KeyError if reached
)
```

The existing agent tests (`test_intelligence_scoring_agent_company_only`) call `_run()` directly, not `execute()`, so this bug is never triggered in CI.

**Impact**: The pipeline fails at Step 4 with a `KeyError` when trying to execute the IntelligenceScoringAgent through `BaseAgent.execute()`.

**Recommended fix**: Fix the `IntelligenceScoringAgent._run()` to return:
```python
return AgentRunOutput(
    output_ids={"intelligence_scores": [score.id]},
    summary=f"Created intelligence score {score.id}",
    stats={"total_score": score.total_score, "confidence": score.confidence},
)
```

This fix is required before the pipeline can function. It's a pre-existing bug in the agent, not introduced by the pipeline design.

---

## 6. Pipeline Traceability Through agent_runs and jobs

### Finding 6.1: Each Step Creates an agent_run — All 5 Are Traceable

**Severity: Informational**

The design correctly describes that each pipeline step calls `BaseAgent.execute()`, which creates an `agent_run` record. Each agent_run has:
- `agent_name`: unique per step (deep_scraper, technographic, etc.)
- `workflow_name`: `"intelligence_pipeline"` (passed in AgentContext)
- Input/output summaries, status, timestamps

All 5 agent_runs share the same `workflow_name`, making them queryable as a group. ✅

---

### Finding 6.2: Job → Agent Run Link Is Broken (Pre-Existing)

**Severity: High** (same root cause as Finding 2.1)

The `jobs` table has an `agent_run_id` FK that can only store one agent_run per job. The pipeline creates 5. The JobRunner code that attempts to link a job to its agent run uses `result.agent_run_id` which doesn't exist on `WorkflowResult`.

**Impact**: The job-agnostic link fails. Pipeline runs cannot be traced from the job record to its agent runs.

**Recommended fix**: Fix the JobRunner to handle `agent_run_ids` (plural). The pipeline itself handles tracking correctly through `workflow_name` filtering on agent_runs.

---

## 7. Retry Semantics

### Finding 7.1: Retry-From-Scratch Creates Duplicate Data

**Severity: Medium**

The design correctly documents that retry-from-scratch creates new records for scores, messages, and signals (where upsert is not supported). The retry policy table shows up to 4 retries with exponential backoff.

The cumulative effect of `max_retries=3` + retry-from-scratch means:
- Each re-run creates 5 new agent_run records
- Each re-run creates N new outreach messages (no dedup)
- Each re-run creates a new intelligence score (append-only)

After 3 retries of a pipeline that fails at step 4 each time, there would be:
- 5 + 10 + 15 = 30 agent_run records (some from completed steps in partial runs)
- 0 outreach messages (never reached step 5)
- 0 + 1 + 2 = 3 intelligence scores (re-ran step 4 each time)

This is acceptable behavior — the design acknowledges it. But the "Data Idempotency" section claims "existing agents handle duplicates" which overstates the situation. Only the Technographic Agent (unique constraint) and Deep Scraper (upsert by URL) handle duplicates. The other three agents create new records on each run.

**Impact**: Low — the behavior matches the design's append-only philosophy for scores and the purpose-specific nature of outreach messages. But the "Data Idempotency" section should be more precise about which agents are truly idempotent.

**Recommended fix**: Update the "Data Idempotency" section to clearly distinguish idempotent steps (Deep Scraper, Technographic) from append-only steps (Scoring, Signal, Personalization).

---

## 8. API Surface Consistency

### Finding 8.1: Design States Two Conflicting Things About Endpoints

**Severity: Medium**

Section 8 ("Job Integration Design") says: "No new endpoints are needed. The pipeline is triggered through the existing background job API."

Section 14 ("API Surface Changes") then defines two new endpoints:
- `POST /intelligence/pipeline` — convenience wrapper
- `GET /intelligence/pipeline/{job_id}` — query endpoint

These directly contradict each other. Either new endpoints are needed (Section 14) or they are not (Section 8).

**Impact**: Medium — an implementer must decide which approach to follow. The convenience endpoint in Section 14 is the better approach because it provides a cleaner API than requiring callers to construct raw job payloads.

**Recommended fix**: Remove the "No new endpoints are needed" statement from Section 8, or reframe it as "The pipeline can be triggered through the existing job API, but a convenience endpoint is also provided."

---

### Finding 8.2: GET /intelligence/pipeline/{job_id} Path Conflicts with Existing Routes

**Severity: Medium**

The design proposes `GET /intelligence/pipeline/{job_id}` as a new endpoint. The existing API structure uses prefix-based routing:
- `/evidence/...`
- `/companies/...`
- `/jobs/...`

The `/intelligence` prefix does not exist in the current router. Adding it requires either:
- A new router file at `app/api/v1/endpoints/intelligence.py`
- Registering the router with a new prefix

This is feasible but the design doesn't note the router registration work beyond "register intelligence pipeline routes."

**Impact**: Low — this is standard FastAPI routing work. Noted for completeness.

**Recommended fix**: No change needed. Router registration is standard implementation work.

---

## 9. Existing Tests and Architecture Patterns

### Finding 9.1: Tests Run Against SQLite, But Pipeline Requires HTTP

**Severity: Medium**

The Deep Scraper Agent (pipeline Step 1) makes real HTTP requests. The existing unit tests mock HTTP with `respx`. Integration tests for the full pipeline would either:
1. Need to mock all HTTP responses (tests the workflow logic, not the actual scraping), or
2. Need to run against a test HTTP server (tests the actual scraping against controlled content).

The design lists `test_pipeline_end_to_end` as an integration test but doesn't specify the HTTP mocking strategy.

**Impact**: Medium — without a clear mocking strategy, the end-to-end test either makes real HTTP requests (slow, flaky, depends on external sites) or doesn't test scraping at all.

**Recommended fix**: Document that the end-to-end integration test uses `respx` to mock HTTP responses (matching the existing `test_deep_scraper` pattern), and verifies that all 5 agents execute in sequence against seeded database data.

---

### Finding 9.2: All Existing Architecture Patterns Are Preserved

**Severity: Informational**

Confirmed: ✅ The pipeline reuses:
- `Workflow` base class (same as score_refresh)
- `BaseAgent` lifecycle (same as all existing agents)
- `EvidenceService` (same as evidence records system)
- `JobService` / `JobRunner` / `JobScheduler` (same as background job foundation)
- `WorkflowRunner` / `WorkflowRegistry` (same as workflow framework)

No new infrastructure, databases, queues, or deployment components are introduced.

---

## 10. Hidden Migration or Schema Changes

### Finding 10.1: No Schema Changes Required

**Severity: Informational**

The pipeline uses only existing tables:
- `companies`, `contacts`, `websites` (pre-existing)
- `technologies`, `intent_signals` (pre-existing)
- `intelligence_scores`, `outreach_messages` (pre-existing)
- `agent_runs`, `jobs` (pre-existing)
- `evidence_records` (implemented in prior milestone)

No new columns, tables, or indexes are introduced. ✅

---

### Finding 10.2: WorkflowRunner and WorkflowRegistry Are Already Stable

**Severity: Informational**

The `WorkflowRunner` class and `WorkflowRegistry` class are already implemented and tested. No modifications are needed to run the pipeline through them (once the registries are populated and the `agent_run_id` bug in JobRunner is fixed). ✅

---

## Summary

### Critical Findings (Must Fix Before Implementation)

| # | Finding | Fix |
|---|---|---|
| 2.1 | `JobRunner` reads `result.agent_run_id` but `WorkflowResult` only has `agent_run_ids` (plural). AttributeError on every workflow job dispatch. | Fix `JobRunner._run_workflow_job()` to read `agent_run_ids[0]` or add singular field. |
| 5.2 | `IntelligenceScoringAgent._run()` returns `{"intelligence_scores": [score.id]}` instead of `AgentRunOutput` — causes `KeyError` in `BaseAgent.execute()`. | Fix agent return to include all required `AgentRunOutput` keys. |

### High Findings (Should Fix Before Implementation)

| # | Finding | Fix |
|---|---|---|
| 1.1 | Design proposes creating new registry instances; existing `main.py` already creates them. | Change design to modify existing instances in `main.py`, not create new ones. |
| 6.2 | Job → agent_run link stores only 1 ID; pipeline produces 5. | Fix JobRunner to handle `agent_run_ids` (plural). Accept limitation for remaining 4 IDs. |

### Medium Findings (Fix During Implementation)

| # | Finding | Fix |
|---|---|---|
| 5.1 | Scoring path — IntelligenceScoringAgent vs ScoreRefreshWorkflow | ✅ No issue — agent-based approach is correct. |
| 7.1 | Retry creates duplicate data for 3 of 5 steps; "idempotency" overstates behavior. | Update "Data Idempotency" section to distinguish idempotent vs append-only steps. |
| 8.1 | Sections 8 and 14 contradict each other on new endpoint requirement. | Remove "No new endpoints" claim from Section 8. |
| 8.2 | Router registration for `/intelligence` prefix not fully specified. | Note as standard implementation work. |
| 9.1 | End-to-end test needs HTTP mocking strategy (respx). | Document `respx` pattern matching existing Deep Scraper tests. |

### Low Findings (Document During Implementation)

| # | Finding | Fix |
|---|---|---|
| 1.2 | Registry wiring location ambiguous (__init__.py vs main.py). | Pin to `app/main.py`. |
| 1.3 | AgentRegistry wiring expands scope beyond pipeline requirement. | Document as future work. |
| 3.1 | Registry lifecycle matches existing pattern. | ✅ No change needed. |
| 4.1 | AgentRegistry exists but unused. | ✅ No change for pipeline. |
| 6.1 | All 5 steps create agent_run records. | ✅ Confirmed correct. |
| 9.2 | All architecture patterns preserved. | ✅ No change needed. |
| 10.1 | No schema changes required. | ✅ No change needed. |
| 10.2 | WorkflowRunner and WorkflowRegistry stable. | ✅ No change needed. |

---

## Ready for Implementation?

**No — two critical bugs and one high-priority design error must be resolved first.**

### Prerequisites

1. **Critical: Fix `JobRunner._run_workflow_job()` agent_run_id access** — The `WorkflowResult` has `agent_run_ids` (plural) but JobRunner reads `agent_run_id` (singular). This affects all workflow job dispatch, not just the pipeline.

2. **Critical: Fix `IntelligenceScoringAgent._run()` return format** — The agent returns `{"intelligence_scores": [score.id]}` which is not a valid `AgentRunOutput`. Any code path that calls `agent.execute()` (including the pipeline, the job system, or manual execution) will fail with `KeyError`.

3. **High: Fix registry wiring approach in design** — The design proposes creating new registry instances but `main.py` already instantiates them. Implementation must modify the existing instances, not replace them.

All three issues are fixable without changing the pipeline architecture. Once these are resolved, the design is implementable.
