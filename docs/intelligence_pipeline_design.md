# Intelligence Pipeline Design

## 1. Purpose

This document defines a single end-to-end Intelligence Pipeline workflow that chains all five Irtiqa agents into a coordinated data flow. The pipeline accepts a company URL and produces a complete intelligence profile: websites, technologies, intent signals, intelligence scores, and personalized outreach messages — all linked through the Evidence Records System for full provenance.

Currently, the five agents exist as independent units. Each can be executed individually through its Python API, but there is no workflow that orchestrates them in sequence. The `score_refresh` workflow demonstrates the orchestration pattern for scoring alone, but the full pipeline (scrape → detect → signal → score → personalize) does not exist.

This pipeline is the capstone of the backend foundation phase. It proves all components work together as a system.

## 2. Current Architecture Review

### Completed Components

| Component | Status | Used by Pipeline |
|---|---|---|
| Deep Scraper Agent | Implemented, 363 lines | Step 1 |
| Technographic Agent | Implemented, 294 lines | Step 2 |
| Intent Signal Agent | Implemented, 397 lines | Step 3 |
| Intelligence Scoring Agent | Implemented, 106 lines | Step 4 |
| Personalization Agent | Implemented, 292 lines (174 agent + 118 templates) | Step 5 |
| Background Job Foundation | Implemented (JobRunner, JobScheduler, JobService) | Orchestration |
| Evidence Records System | Implemented | Provenance |
| Workflow Framework | Implemented (Workflow base, WorkflowRunner) | Pipeline container |
| Agent Context/Result | Implemented | Input/output contracts |
| CRUD API | Implemented for all entities | Trigger and results |
| CI/CD | Implemented | Quality gate |

### Gap: Registries Are Not Wired

Both `AgentRegistry` and `WorkflowRegistry` are defined but **never populated in production code**. The `JobRunner._run_agent_job()` method calls `self.agent_registry.get(job.target_name)` to resolve agents by name, and `JobRunner._run_workflow_job()` calls `self.workflow_registry.get(context.workflow_name)`. Neither registry contains any entries outside of unit tests.

This means:
- Background jobs for individual agents would fail at runtime with "Agent is not registered."
- Background jobs for workflows (including the new pipeline) would fail with "Workflow is not registered."
- The Agent Registry and Workflow Registry must be populated during application startup before the pipeline can execute through the job system.

### Agent Execution Patterns

Each agent follows the same lifecycle through `BaseAgent.execute()`:

1. Validate context
2. Create `agent_run` record (pending)
3. Execute `_run()` (agent-specific logic)
4. Mark `agent_run` as succeeded or failed
5. Record evidence (optional, non-blocking)
6. Return `AgentResult` with output_ids

This uniform lifecycle makes sequential chaining predictable. Each step produces outputs that the next step consumes through the service layer (not through shared memory).

### Background Job Foundation

The `JobRunner` supports both `agent` and `workflow` job types:
- **Agent jobs**: Resolve agent class from `AgentRegistry`, construct `AgentContext`, call `agent.execute()`, record result.
- **Workflow jobs**: Resolve workflow class from `WorkflowRegistry`, construct `WorkflowContext`, call `WorkflowRunner.run()`, record result.

Both paths require populated registries, which currently do not exist in production.

### Evidence Records System

Every agent execution can produce evidence records linking inputs to outputs. The pipeline will produce evidence at each step:
- Deep Scraper: links scraped pages to company
- Technographic: links technology detections to websites
- Intent Signal: links signals to technologies and text excerpts
- Intelligence Scoring: links scores to technologies and signals
- Personalization: links messages to scores and signals

These evidence records are queryable through the evidence API endpoints.

## 3. Pipeline Goals

1. **Single-trigger execution** — A single API call or job submission triggers the complete pipeline for a company.
2. **Sequential dependencies** — Each agent starts only after its upstream data is available (e.g., Technographic runs after Deep Scraper produces website text).
3. **Observable progress** — Each pipeline step creates an `agent_run` record so operators can track status per step.
4. **Provenance throughout** — Every output is linked to its evidential inputs through the Evidence Records System.
5. **Resumable on failure** — A failed step can be retried; completed steps are not re-executed unless the pipeline is restarted.
6. **Same-infrastructure reuse** — No new databases, queues, caches, or infrastructure. The existing codebase contains everything needed.

## 4. Pipeline Inputs

The pipeline accepts a single required input and one optional input:

| Field | Type | Required | Source |
|---|---|---|---|
| `company_id` | UUID string | Yes | Existing company in the database |
| `contact_id` | UUID string | No | Existing contact in the database |

The pipeline does not accept raw URLs directly. A company must exist in the `companies` table with at least one website URL before the pipeline can begin. The company can be created through the existing `POST /companies` and `POST /websites` CRUD endpoints.

**Future consideration**: A convenience endpoint that accepts a domain name, creates the company and website records, and triggers the pipeline can be added later. This is not part of the current design because the task says "Design only for the current repository state."

## 5. Pipeline Outputs

After successful execution, the pipeline produces:

| Output | Table | Step |
|---|---|---|
| Website pages | `websites` (raw_html, extracted_text) | Deep Scraper |
| Technology detections | `technologies` | Technographic |
| Intent signals | `intent_signals` | Intent Signal |
| Intelligence scores | `intelligence_scores` | Intelligence Scoring |
| Outreach messages | `outreach_messages` | Personalization |
| Agent run records | `agent_runs` | All 5 steps |
| Evidence records | `evidence_records` | All 5 steps |

Each step's `agent_run` record is linked to the pipeline's parent job through the existing `jobs → agent_runs` relationship.

## 6. Workflow Architecture

### Pipeline Workflow Class

A new workflow class `IntelligencePipelineWorkflow` extends the existing `Workflow` base class:

```text
class IntelligencePipelineWorkflow(Workflow):
    name = "intelligence_pipeline"
```

The workflow is synchronous (matching the existing `score_refresh` pattern) and runs inside a single `execute()` method. Each step is a method call that:
1. Constructs the appropriate agent with its service dependencies
2. Calls `agent.execute(context)` 
3. Checks the result status
4. Proceeds to the next step or fails

### Step Execution Model

Each pipeline step is a call to `BaseAgent.execute()` — not a new workflow or a background job. The pipeline itself runs as a **single workflow job** in the Background Job Foundation. This avoids:
- Nesting jobs within jobs (complex state management)
- Waiting for intermediate scheduler polling (latency)
- Maintaining intermediate result storage between steps

If the pipeline needs to run for hours (e.g., Deep Scraper crawling thousands of pages), it can be broken into individual agent jobs in a future iteration. For the current project stage where companies have a small number of pages, synchronous step execution within a single workflow is the simplest and most observable pattern.

### Execution Flow

```text
JobScheduler picks up pipeline job
  │
  ▼
JobRunner dispatches to WorkflowRunner
  │
  ▼
WorkflowRunner resolves IntelligencePipelineWorkflow from WorkflowRegistry
  │
  ▼
IntelligencePipelineWorkflow.execute()
  ├── Step 1: Deep Scraper Agent
  │     ▶ Creates/updates Website records
  │     ▶ Returns output_ids (website IDs)
  │
  ├── Step 2: Technographic Agent
  │     ▶ Reads extracted_text from websites
  │     ▶ Creates Technology records
  │     ▶ Returns output_ids (technology IDs)
  │
  ├── Step 3: Intent Signal Agent
  │     ▶ Reads extracted_text and technologies
  │     ▶ Creates IntentSignal records
  │     ▶ Returns output_ids (signal IDs)
  │
  ├── Step 4: Intelligence Scoring Agent
  │     ▶ Reads technologies and intent signals
  │     ▶ Creates IntelligenceScore records
  │     ▶ Returns output_ids (score IDs)
  │
  ├── Step 5: Personalization Agent
  │     ▶ Reads scores, signals, technologies, company
  │     ▶ Creates OutreachMessage records
  │     ▶ Returns output_ids (message IDs)
  │
  └── Returns WorkflowResult with all output_ids
```

## 7. Agent Execution Sequence

### Step 1: Deep Scraper Agent

**Purpose**: Crawl the company's website(s) and extract structured page content.

**Service dependencies**: `CompanyService`, `WebsiteService`

**Input context**:
```python
AgentContext(
    agent_name="deep_scraper",
    company_id=company_id,
    contact_id=None,
    workflow_name="intelligence_pipeline",
    options={
        "crawl_depth": 2,
        "max_pages": 50,
        "page_limit": 50,
    },
)
```

**Output**: `output_ids["websites"]` — list of created/updated Website UUIDs.

**Evidence**: Creates `evidence_records` with `source_type="website"` and `target_type="website"` for each crawled page, linking the page content to the company.

**Failure behavior**: If the company has no websites or the website is unreachable, the pipeline should fail with a clear error rather than silently skipping.

### Step 2: Technographic Agent

**Purpose**: Detect technologies from the extracted website text.

**Service dependencies**: `TechnologyService`, `WebsiteService`

**Input context**:
```python
AgentContext(
    agent_name="technographic",
    company_id=company_id,
    options={"min_confidence": 0.5},
)
```

**Output**: `output_ids["technologies"]` — list of created Technology UUIDs.

**Evidence**: Creates `evidence_records` linking each technology detection to the website it was detected on, with `evidence_type="signature_match"` or `"html_snippet"`.

### Step 3: Intent Signal Agent

**Purpose**: Detect buying intent and operational signals from extracted text and detected technologies.

**Service dependencies**: `TechnologyService`, `WebsiteService`, `IntentSignalService`

**Input context**:
```python
AgentContext(
    agent_name="intent_signal",
    company_id=company_id,
)
```

**Output**: `output_ids["intent_signals"]` — list of created IntentSignal UUIDs.

**Evidence**: Creates `evidence_records` linking each signal to the technology or text excerpt that triggered it.

### Step 4: Intelligence Scoring Agent

**Purpose**: Compute fit, intent, technographic, and engagement scores.

**Service dependencies**: `CompanyService`, `ContactService`, `TechnologyService`, `IntentSignalService`, `IntelligenceScoreService`, `AgentRunService`

The scoring agent uses the existing `DeterministicScoreRefreshPolicy` from the `score_refresh` workflow. The policy reads `technologies` and `intent_signals` for the company and produces scores.

**Input context**:
```python
AgentContext(
    agent_name="intelligence_scoring",
    company_id=company_id,
    contact_id=contact_id,
)
```

**Output**: `output_ids["intelligence_scores"]` — list of created IntelligenceScore UUIDs.

**Evidence**: Creates `evidence_records` linking each score to the technologies and intent signals that contributed. This reuses the evidence creation already implemented in the `score_refresh` workflow.

### Step 5: Personalization Agent

**Purpose**: Generate personalized outreach messages based on all accumulated intelligence.

**Service dependencies**: `CompanyService`, `ContactService`, `TechnologyService`, `IntentSignalService`, `IntelligenceScoreService`, `OutreachMessageService`

**Input context**:
```python
AgentContext(
    agent_name="personalization",
    company_id=company_id,
    contact_id=contact_id,
)
```

**Output**: `output_ids["outreach_messages"]` — list of created OutreachMessage UUIDs.

**Evidence**: Creates `evidence_records` linking each message to the intelligence score, technology, and signals that drove the personalization angle.

### Pipeline Step Result Aggregation

The workflow aggregates all output_ids across steps into a single `WorkflowResult`:

```python
WorkflowResult(
    workflow_name="intelligence_pipeline",
    status=WorkflowStatus.SUCCEEDED,
    company_id=company_id,
    contact_id=contact_id,
    agent_run_ids=[...],  # 5 agent run IDs
    output_ids={
        "websites": [...],
        "technologies": [...],
        "intent_signals": [...],
        "intelligence_scores": [...],
        "outreach_messages": [...],
    },
    steps=[...],  # 5 WorkflowStepResult entries
)
```

## 8. Job Integration Design

### Triggering

The pipeline is triggered through the existing background job API. No new endpoints are needed.

```http
POST /jobs
{
    "job_type": "workflow",
    "target_name": "intelligence_pipeline",
    "payload": {
        "company_id": "uuid-string",
        "contact_id": "uuid-string-or-null",
        "options": {
            "crawl_depth": 2,
            "max_pages": 50
        }
    }
}
```

This uses the existing `JobService.schedule_workflow()` method. The `JobRunner._run_workflow_job()` dispatches to `WorkflowRunner`, which resolves `intelligence_pipeline` from the `WorkflowRegistry`.

### Registry Requirement

The pipeline workflow must be registered in the `WorkflowRegistry` during application startup. This is the same requirement as the existing `score_refresh` workflow — the registry is already designed for this purpose but is not yet wired.

### Existing API Integration

The pipeline can also be triggered from the existing `POST /agent-runs` endpoint pattern, but the primary trigger should be through the job system because:
- Jobs provide retry, scheduling, and monitoring.
- Jobs create an observable record of the pipeline run.
- The `jobs` table already has `agent_runs` links for observability.

## 9. Evidence Recording Strategy

### Per-Step Evidence

Each pipeline step creates evidence records through the same mechanism already implemented:

1. The agent's `_run()` returns `AgentRunOutput` with an optional `evidence` list.
2. `BaseAgent.execute()` calls `EvidenceService.record_evidence_batch()`.
3. Failure to record evidence does not fail the step.

### Evidence Types by Step

| Step | Evidence Type | Relationship | Source | Target |
|---|---|---|---|---|
| Deep Scraper | `html_snippet` | `generates` | `agent_run` | `website` |
| Technographic | `signature_match` | `supports` | `agent_run` | `technology` |
| Intent Signal | `text_excerpt` | `contributes_to` | `agent_run` | `intent_signal` |
| Scoring | `computed_metric` | `contributes_to` | `agent_run` | `intelligence_score` |
| Personalization | `agent_summary` | `supports` | `agent_run` | `outreach_message` |

### Pipeline-Level Evidence

In addition to per-step evidence, the pipeline can create a single evidence record linking the final outreach message to the entire pipeline result, summarizing the chain:

```text
OutreachMessage
  └─ supports ← evidence_record ← source=agent_run (personalization step)
```

This is already handled by the Personalization Agent's existing evidence logic. No additional pipeline-level evidence is required.

## 10. Failure Handling Strategy

### Per-Step Failure

If any step fails (agent returns `AGENT_STATUS_FAILED`), the pipeline stops at that step and returns a `WorkflowResult` with `FAILED` status. The `WorkflowResult` includes:
- The `agent_run_id` of the failed step (can be inspected via `GET /agent-runs/{id}`)
- The error message from the failed agent
- The output_ids from any prior steps that succeeded

### Recovery

The pipeline is designed for **retry from scratch** (not partial re-execution). If a pipeline fails at step 3, the operator can:

1. Investigate the failure via the failed `agent_run` record and its error message.
2. Fix the root cause (e.g., add missing data, fix configuration).
3. Re-submit the pipeline job with the same `company_id`.
4. The pipeline re-executes all 5 steps.

This is the simplest recovery strategy and matches the existing `score_refresh` pattern. Incremental/partial re-execution would require each agent to be idempotent and to skip already-processed data. This can be added later if retry-from-scratch proves too slow.

### Data Idempotency

Existing agents handle duplicates:
- **Technographic Agent**: Upserts by `(company_id, name, category)` unique constraint.
- **Intent Signal Agent**: Deduplicates by signal type and content within the same run.
- **Scoring Agent**: Creates append-only scores (new scores are added, not overwritten).
- **Deep Scraper**: Updates existing websites by `normalized_url`.
- **Personalization Agent**: Creates new outreach messages per run.

Re-running the pipeline creates new records where upsert/replace is not supported (scores, messages, signals). This is acceptable — scores are designed to be append-only, and duplicate outreach messages can be filtered by `agent_run_id` in queries.

## 11. Retry Strategy

The pipeline uses the existing `compute_next_scheduled_at` retry policy from the Background Job Foundation:

| Retry | Delay | Jitter |
|---|---|---|
| 1st | ~60s | ±10% |
| 2nd | ~120s | ±12s |
| 3rd | ~240s | ±24s |
| 4th | ~480s | ±48s |

Maximum retries: **3** (default in `JobService.schedule_workflow`).

Retry is handled at the **job level**, not the step level. If the pipeline fails at step 3, the entire pipeline is retried (not just step 3). This is handled automatically by the existing `JobRunner._handle_job_failure()` method, which calls `compute_next_scheduled_at` and reschedules the job.

## 12. Monitoring and Observability

### Agent Run Records

Each step creates its own `agent_run` record with:
- `agent_name`: The agent name (e.g., `deep_scraper`)
- `workflow_name`: `intelligence_pipeline`
- `status`: `succeeded` or `failed`
- `input_summary`: Company and contact context
- `output_summary`: What was produced

These records are queryable through `GET /agent-runs` and `GET /evidence/by-agent-run/{id}`.

### Workflow Result

The pipeline's `WorkflowResult` is returned to the `WorkflowRunner`, which returns it to the `JobRunner`. The job record stores:
- `status`: `succeeded` or `failed`
- `completed_at`: Timestamp of completion
- `agent_run_id`: Link to the last agent run (the personalization step)
- Failure information is stored in the failed step's `agent_run` record

### Logging

Each step logs via the structured logging system:
- `irtiqa.agents.deep_scraper`
- `irtiqa.agents.technographic`
- `irtiqa.agents.intent_signal`
- `irtiqa.agents.intelligence_scoring`
- `irtiqa.agents.personalization`
- `irtiqa.workflows.intelligence_pipeline`

Logs include `agent_run_id`, `company_id`, and `duration_ms` for performance monitoring.

### Querying Pipeline Status

```python
# Find all agent runs for this pipeline job
agent_runs = agent_run_service.list_by_job(job_id)

# Or find agent runs by workflow_name
pipeline_runs = agent_run_service.list_by_workflow("intelligence_pipeline")

# Evidence for a specific step
evidence = evidence_service.get_agent_run_evidence(agent_run_id)
```

## 13. Data Flow Diagram

```text
┌────────────────────────────────────────────────────────────────────┐
│                        Background Job                              │
│            POST /jobs (job_type="workflow")                         │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│                      WorkflowRunner                                 │
│        Resolves "intelligence_pipeline" from WorkflowRegistry       │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                         ▼
┌────────────────────────────────────────────────────────────────────┐
│              IntelligencePipelineWorkflow.execute()                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Deep Scraper Agent                                             │
│     Input:  company_id                                             │
│     Reads:  websites.url, websites.normalized_url                  │
│     Writes: websites.raw_html, websites.extracted_text             │
│     Evidence: html_snippet → website                               │
│          │                                                         │
│          ▼                                                         │
│  2. Technographic Agent                                            │
│     Input:  company_id                                             │
│     Reads:  websites.extracted_text                                │
│     Writes: technologies (name, category, confidence)              │
│     Evidence: signature_match → technology                         │
│          │                                                         │
│          ▼                                                         │
│  3. Intent Signal Agent                                            │
│     Input:  company_id                                             │
│     Reads:  websites.extracted_text, technologies                  │
│     Writes: intent_signals (type, strength, confidence)            │
│     Evidence: text_excerpt → intent_signal                         │
│          │                                                         │
│          ▼                                                         │
│  4. Intelligence Scoring Agent                                     │
│     Input:  company_id, contact_id (optional)                      │
│     Reads:  technologies, intent_signals, company, contact         │
│     Writes: intelligence_scores (fit, intent, tech, engagement)    │
│     Evidence: computed_metric → intelligence_score                 │
│          │                                                         │
│          ▼                                                         │
│  5. Personalization Agent                                          │
│     Input:  company_id, contact_id (optional)                      │
│     Reads:  technologies, intent_signals, intelligence_scores      │
│     Writes: outreach_messages (channel, body, angle)               │
│     Evidence: agent_summary → outreach_message                     │
│          │                                                         │
│          ▼                                                         │
│  Return: WorkflowResult with all 5 output_ids                      │
└────────────────────────────────────────────────────────────────────┘
```

## 14. API Surface Changes

### New Endpoint: Pipeline Execution

A convenience endpoint is added to trigger the pipeline without constructing a raw job payload:

| Method | Path | Description |
|---|---|---|
| `POST` | `/intelligence/pipeline` | Trigger the intelligence pipeline for a company |

This is a thin wrapper around `JobService.schedule_workflow()` that accepts the same parameters as the workflow payload.

**Request body:**
```json
{
    "company_id": "uuid-string",
    "contact_id": "uuid-string-or-null",
    "options": {
        "crawl_depth": 2,
        "max_pages": 50
    }
}
```

**Response (202 Accepted):**
```json
{
    "job_id": "uuid-string",
    "status": "scheduled",
    "target_name": "intelligence_pipeline"
}
```

**Query endpoint:**

| Method | Path | Description |
|---|---|---|
| `GET` | `/intelligence/pipeline/{job_id}` | Get pipeline job status and results |

Returns the job record including job status, timestamps, and linked `agent_run_ids` for each step.

### Existing Endpoints Used

| Endpoint | Purpose |
|---|---|
| `GET /jobs/{job_id}` | Check pipeline job status |
| `GET /jobs/{job_id}/retry` | Retry failed pipeline |
| `GET /evidence/by-company/{company_id}` | View all evidence for the company |
| `GET /evidence/by-agent-run/{agent_run_id}` | View evidence for a specific step |
| `GET /agent-runs/{id}` | View step-level status and error |

No changes to the existing CRUD API endpoints are needed.

## 15. Test Strategy

### Unit Tests

| Test | Description |
|---|---|
| `test_pipeline_step_execution` | Each agent executes correctly when called sequentially in the pipeline |
| `test_pipeline_fails_on_step_failure` | Pipeline stops and returns FAILED when an agent fails |
| `test_pipeline_aggregates_output_ids` | WorkflowResult contains output_ids from all 5 steps |
| `test_pipeline_agent_run_ids` | WorkflowResult contains 5 agent_run_ids |
| `test_pipeline_requires_company` | Pipeline fails with clear error when company_id is missing |
| `test_pipeline_requires_website` | Pipeline fails when company has no websites |
| `test_pipeline_evidence_creation` | Evidence records created for each step |

### Integration Tests

| Test | Description |
|---|---|
| `test_pipeline_end_to_end` | Full pipeline with seeded data produces all 5 output types |
| `test_pipeline_through_job_system` | Pipeline scheduled via POST /jobs, runs, and completes |
| `test_pipeline_retry` | Failed pipeline reschedules via retry policy |
| `test_pipeline_multiple_runs` | Multiple pipeline runs for the same company create append-only records |

### Test Count

Approximately 10 unit tests + 4 integration tests = 14 new tests. Existing 316 tests continue to pass.

## 16. Deliverables

### Workflow Layer

- `app/workflows/intelligence_pipeline.py` — Pipeline workflow class
- `tests/unit/workflows/test_intelligence_pipeline.py` — Unit tests

### API Layer

- `app/api/v1/endpoints/intelligence.py` — Pipeline trigger and status endpoints
- `app/api/v1/router.py` — Register pipeline routes
- `tests/integration/api/test_intelligence_pipeline.py` — API integration tests

### Registry Wiring

- `app/workflows/__init__.py` — Register `IntelligencePipelineWorkflow` and `ScoreRefreshWorkflow` in `WorkflowRegistry`
- `app/main.py` — Wire `WorkflowRegistry` into application lifecycle (if needed)

### Documentation

- `docs/intelligence_pipeline_design.md` — This document
- `docs/project_state.md` — Update milestone status
- `docs/project_handoff.md` — Update milestone status

## 17. Success Criteria

1. A single `POST /jobs` with `target_name="intelligence_pipeline"` triggers all 5 agents in sequence.
2. Each step produces the correct output type (websites, technologies, intent_signals, intelligence_scores, outreach_messages).
3. Each step creates an `agent_run` record with the correct status and output summary.
4. Each step creates evidence records linking its output to its input.
5. If a step fails, the pipeline stops and returns `FAILED` without executing subsequent steps.
6. The pipeline can be retried by calling `POST /jobs/{id}/retry`.
7. The pipeline creates append-only records on re-execution (no destructive overwrites).
8. All 316 existing tests continue to pass.
9. CI runs all pipeline tests on every push and pull request.

## 18. Risks

### Risk: Pipeline Takes Too Long

The Deep Scraper Agent performs HTTP requests to crawl websites. If the target website is slow or has many pages, the pipeline could take minutes to hours.

**Mitigation**: Default crawl depth and page limits (2 / 50) keep the scraping phase bounded. If the pipeline takes longer than the job scheduler's timeout, the job can be configured with a longer timeout. For the current project stage, synchronous execution within a single workflow job is acceptable.

### Risk: Registries Not Wired

The `AgentRegistry` and `WorkflowRegistry` must be populated during application startup. If they are not wired, the pipeline (and all existing agent/workflow jobs) will fail at runtime.

**Mitigation**: The registries are populated in a dedicated startup function called from the FastAPI lifespan. This is a one-time wiring task that affects both the pipeline and all existing agent/workflow job types.

### Risk: Agent Dependencies Not Satisfied

Each pipeline step requires service dependencies (e.g., `CompanyService`, `TechnologyService`). If a dependency is missing, the agent fails to construct.

**Mitigation**: Existing agents already declare their service dependencies. The pipeline workflow passes the same services to all agents. The test suite validates that each agent constructs correctly with the standard service set.

### Risk: Deep Scraper Agent HTTP Failures

The Deep Scraper Agent makes HTTP requests and can fail due to network issues, DNS resolution failures, or HTTP errors.

**Mitigation**: The agent has built-in retries via httpx, error classification (`AgentNetworkError`, `AgentRateLimitError`, `AgentTimeoutError`), and bounded crawl limits. Pipeline retry at the job level handles transient HTTP failures.

### Risk: Pipeline Too Rigid

The 5-step sequential pipeline assumes a fixed order that may not suit all use cases.

**Mitigation**: The pipeline is designed for the most common intelligence workflow. Alternative pipelines or partial pipelines can be added later without changing this design. The workflow framework already supports multiple named workflows.

---

## Agent Registry Assessment

### Current State

The `AgentRegistry` class in `app/agents/registry.py` provides:
- `register(agent_class)` — Registers an agent class by name
- `get(agent_name)` — Resolves an agent class by name
- `names()` — Lists all registered agent names

It is **never called in production code**. All `.register()` calls exist only in unit tests.

The `WorkflowRegistry` class in `app/workflows/registry.py` provides the same interface. It is also never populated in production code.

The `JobRunner` depends on both registries:
```python
# In JobRunner._run_agent_job():
agent_cls = self.agent_registry.get(job.target_name)

# In JobRunner._run_workflow_job():
runner = WorkflowRunner(self.workflow_registry, ...)
runner.run(context)
```

Without populated registries, no agent or workflow can be dispatched through the job system.

### Assessment

**Should AgentRegistry be used?** **Yes** — for agent jobs dispatched through the Background Job Foundation, the registry is required. The `JobRunner._run_agent_job()` method already depends on it. However, the intelligence pipeline runs as a workflow job (not an agent job), so the pipeline does not require AgentRegistry — it requires WorkflowRegistry.

**Should AgentRegistry be removed?** **No** — the registry provides a valid abstraction for resolving agents by name. It should be kept for future use cases where individual agents are scheduled as background jobs (e.g., running only the Technographic Agent on an existing company without crawling).

**Should dynamic agent resolution be required?** **Not for the pipeline**. The pipeline workflow imports agents directly (static resolution) because the pipeline defines a fixed sequence. Dynamic resolution (through AgentRegistry) is needed for ad-hoc agent job scheduling, not for the pipeline itself.

**Recommendation for WorkflowRegistry:**

The `WorkflowRegistry` must be populated. The pipeline workflow and the existing `score_refresh` workflow must be registered. The registry should be populated during application startup, in the FastAPI lifespan function.

**Recommendation for AgentRegistry:**

The `AgentRegistry` should be populated with all 5 agents. This is a low-risk addition (the registry class is already tested) and enables the existing JobRunner to dispatch individual agent jobs. Future agent jobs can be scheduled without code changes.

```python
# Registry wiring (location: app/workflows/__init__.py or app/main.py init)
from app.agents.deep_scraper import DeepScraperAgent
from app.agents.technographic import TechnographicAgent
from app.agents.intent_signal import IntentSignalAgent
from app.agents.intelligence_scoring import IntelligenceScoringAgent
from app.agents.personalization import PersonalizationAgent
from app.agents.registry import AgentRegistry

agent_registry = AgentRegistry()
agent_registry.register(DeepScraperAgent)
agent_registry.register(TechnographicAgent)
agent_registry.register(IntentSignalAgent)
agent_registry.register(IntelligenceScoringAgent)
agent_registry.register(PersonalizationAgent)

from app.workflows.score_refresh import ScoreRefreshWorkflow
from app.workflows.intelligence_pipeline import IntelligencePipelineWorkflow
from app.workflows.registry import WorkflowRegistry

workflow_registry = WorkflowRegistry()
workflow_registry.register(ScoreRefreshWorkflow)
workflow_registry.register(IntelligencePipelineWorkflow)
```

Both registries are then passed to `JobRunner` when it is constructed (which already accepts `agent_registry` and `workflow_registry` parameters).

---

## Files Expected to Be Created

- `app/workflows/intelligence_pipeline.py`
- `app/api/v1/endpoints/intelligence.py`
- `tests/unit/workflows/test_intelligence_pipeline.py`
- `tests/integration/api/test_intelligence_pipeline.py`
- `docs/intelligence_pipeline_design.md`

## Files Expected to Be Modified

- `app/workflows/__init__.py` (register workflows in WorkflowRegistry)
- `app/api/v1/router.py` (register intelligence pipeline routes)
- `app/api/dependencies.py` (add intelligence pipeline dependencies if needed)
- `app/main.py` or app startup (wire AgentRegistry and WorkflowRegistry into FastAPI lifespan)
- `app/jobs/runner.py` or app startup (pass populated registries to JobRunner)
- `docs/project_state.md` (mark pipeline milestone)
- `docs/project_handoff.md` (mark pipeline milestone)
- `docs/codex_bootstrap.md` (update next task)
