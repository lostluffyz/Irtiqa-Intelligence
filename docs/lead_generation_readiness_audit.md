# Lead Generation Readiness Audit

**Project:** Irtiqa Intelligence  
**Date:** 2026-06-17  
**Auditor:** Staff Software Architect  
**Scope:** Full lead generation pipeline — business discovery through lead retrieval  

---

## Executive Summary

Irtiqa has built a well-designed, modular lead generation architecture with 5 agents, 2 workflows, a job scheduling system, and comprehensive data persistence. However, the pipeline is **not ready for real lead generation** due to 3 blocking bugs and a missing orchestration layer.

The individual components are production-quality in isolation (proper error handling, timeouts, retries, logging), but they have never been wired together end-to-end. Two of the five agents have schema/service signature mismatches that will cause runtime crashes. No full-pipeline integration test exists.

---

## Current Readiness Score: **35%**

| Stage | Readiness | Note |
|-------|-----------|------|
| Business Discovery (Company/Contact CRUD) | ✅ 100% | Fully implemented |
| Website Scraping (DeepScraperAgent) | ✅ 90% | Missing `organization_id` in service calls |
| Technographic Analysis (TechnographicAgent) | ✅ 85% | Missing `organization_id`, stale `agent_run_id` |
| Intent Detection (IntentSignalAgent) | ✅ 85% | Missing `organization_id`, stale `agent_run_id` |
| Evidence Generation | ⚠️ 50% | ScoreRefreshWorkflow works; agents produce evidence but flow is untested |
| Intelligence Scoring | ❌ 0% | IntelligenceScoringAgent has **2 blocking bugs** |
| Database Persistence | ✅ 95% | All services functional; minor service-signature mismatches in 2 agents |
| Lead Retrieval API | ❌ 0% | **No dedicated API exists** |
| Pipeline Orchestration | ❌ 0% | No end-to-end orchestrator wired |
| Multi-Tenancy | ⚠️ 60% | Phase 2 and 3 infrastructure exist but Phase 1 agents don't participate |

---

## Pipeline Diagram

```
Input: Company ID + Contact ID (optional)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  POST /intelligence/pipeline  (API trigger)                 │
│  → JobService.schedule_workflow() → JobRunner              │
│  → WorkflowRunner → IntelligencePipelineWorkflow           │
└─────────────────────────────────────────────────────────────┘
         │
         ▼  (Step 1)
┌─────────────────────┐
│  DeepScraperAgent   │  Reads Company.domain
│  Crawls website     │  Writes Website (raw_html, extracted_text)
│  Respects robots.txt│  Produces evidence
└─────────┬───────────┘
          ▼  (Step 2)
┌─────────────────────┐
│  TechnographicAgent │  Reads Website.raw_html
│  Detects technology │  Writes Technology
│  Signature matching │  Produces evidence
└─────────┬───────────┘
          ▼  (Step 3)
┌─────────────────────┐
│  IntentSignalAgent  │  Reads Website.extracted_text + Technology
│  Detects signals    │  Writes IntentSignal
│  Rule-based engine  │  Produces evidence
└─────────┬───────────┘
          ▼  (Step 4)
┌─────────────────────────────────┐
│  IntelligenceScoringAgent ⚠️❌  │  ⚠️ BLOCKED: Schema mismatch
│  OR ScoreRefreshWorkflow ✅     │  ✅ Works but different path
│  Computes scores                │  Writes IntelligenceScore + Evidence
└─────────┬───────────────────────┘
          ▼  (Step 5)
┌─────────────────────┐
│  Personalization    │  ⚠️ BLOCKED: Service signature mismatch
│  Agent              │  Writes OutreachMessage (draft)
│  Template renderer  │
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  Lead Retrieval API │  ❌ MISSING: No aggregated lead endpoint
└─────────────────────┘
```

---

## Implemented Components

### Data Model Layer (100%)
| Component | Status | Detail |
|-----------|--------|--------|
| Company | ✅ Complete | Full CRUD, unique domain per org |
| Contact | ✅ Complete | Full CRUD, unique email per org |
| Website | ✅ Complete | Full CRUD, normalized URL |
| Technology | ✅ Complete | With detection metadata |
| IntentSignal | ✅ Complete | With strength/confidence scoring |
| IntelligenceScore | ✅ Complete | Multi-dimensional scores |
| OutreachMessage | ✅ Complete | Draft messages with templates |
| EvidenceRecord | ✅ Complete | Content-addressed deduplication |
| Job | ✅ Complete | Scheduling + retry infrastructure |
| Organization/Membership | ✅ Complete | Multi-tenancy foundation |

### Repository Layer (100%)
All 15 repositories implemented with full CRUD, tenant filtering (Phase 3), and proper error handling.

### Service Layer (95%)
All 15 services implemented. Minor signature issues affect only `IntelligenceScoringAgent` and `PersonalizationAgent` which call services incorrectly.

### Pipeline Infrastructure (85%)
| Component | Status | Detail |
|-----------|--------|--------|
| JobRunner | ✅ Complete | Poll-dispatch-retry cycle works |
| JobScheduler | ✅ Complete | Async polling with clean shutdown |
| WorkflowRunner | ✅ Complete | Workflow instantiation + execution |
| WorkflowRegistry | ✅ Complete | Name→class resolution |
| AgentRegistry | ✅ Complete | Name→class resolution |
| ScoreRefreshWorkflow | ✅ Complete | End-to-end scoring + evidence linking |

### API Layer (70%)
| Endpoint | Status | Detail |
|----------|--------|--------|
| Auth (login/register) | ✅ Complete | Phase 2 |
| Companies CRUD | ✅ Complete | Phase 4 tenant isolation |
| Contacts CRUD | ✅ Complete | Phase 4 |
| Websites CRUD | ✅ Complete | |
| Technologies CRUD | ✅ Complete | |
| IntentSignals CRUD | ✅ Complete | |
| IntelligenceScores CRUD + `/top` | ✅ Complete | Phase 4 scoping |
| OutreachMessages CRUD | ✅ Complete | |
| Evidence queries | ✅ Complete | |
| Jobs (schedule/list/cancel/retry) | ✅ Complete | |
| Intelligence pipeline trigger | ✅ Complete | POST /intelligence/pipeline |
| Organizations + Memberships | ✅ Complete | |
| **Lead retrieval (aggregated)** | **❌ Missing** | No combined lead profile endpoint |

---

## Missing Components

### 1. Lead Retrieval API (CRITICAL)
No endpoint exists that returns a complete lead profile (company + contact + scores + intent signals + outreach messages). Each data type must be queried individually via separate API calls. This is a product-level gap.

### 2. Full Pipeline Orchestration (HIGH)
The `IntelligencePipelineWorkflow` chains 5 agents but has **never been observed executing end-to-end**. The `ScoreRefreshWorkflow` provides an alternative scoring path (step 4 only) but doesn't run the preceding 3 agents.

### 3. Agent Chaining in Job System (MEDIUM)
The job system can schedule individual agents (`schedule_agent`) or workflows (`schedule_workflow`), but no mechanism exists to automatically chain agent jobs. A pipeline trigger creates a single workflow job — not individual agent jobs.

### 4. Multi-Tenant Agent Context (MEDIUM)
Phase 1 agents (DeepScraper, Technographic, IntentSignal) don't receive `organization_id` in their `AgentContext`. The `JobRunner` constructs contexts without it. These agents call services without `organization_id`, which will fail on tenant-scoped databases.

---

## Blocking Issues

### Blocker 1 (CRITICAL): IntelligenceScoringAgent — Schema + Service mismatch

**Location:** `app/agents/intelligence_scoring/agent.py:85-99`

**Two errors in one:**

1. **Field name mismatch (line 95):** `IntelligenceScoreCreate` schema has `technology_id`, but the agent passes `primary_technology_id=result.primary_technology_id`. The `ScorePolicyResult` uses `primary_technology_id` as the field name. When Pydantic validates `IntelligenceScoreCreate(primary_technology_id=...)`, it will raise `ValidationError` because the schema field is named `technology_id`, not `primary_technology_id`.

2. **Service signature mismatch (line 99):** `intelligence_score_service.create(create_schema)` passes a single Pydantic schema object. But `IntelligenceScoreService.create()` has signature `def create(self, organization_id: str, **values: Any)`. It expects `organization_id` as a positional string followed by keyword args. The schema object will be unpacked incorrectly, causing a `TypeError`.

**Fix required:** Update line 85-99 to use `technology_id` field name and call `service.create(organization_id=..., **create_schema.model_dump())`.

### Blocker 2 (CRITICAL): PersonalizationAgent — Service signature mismatch

**Location:** `app/agents/personalization/agent.py:144-158`

Same pattern as Blocker 1: `outreach_message_service.create(create_schema)` passes a Pydantic schema object instead of `(organization_id, **values)`. Will raise `TypeError`.

**Fix required:** Replace with `outreach_message_service.create(organization_id=context.organization_id, **create_schema.model_dump())`.

### Blocker 3 (HIGH): No end-to-end pipeline test passes

**Evidence:**
- `test_pipeline_through_job_system` mocks all 5 agent `execute()` methods — no real agent execution.
- `test_pipeline_end_to_end` triggers the API but mocks all agents.
- `test_score_refresh_workflow_persists_score_and_agent_run` tests ScoreRefreshWorkflow (not the full pipeline).
- No test exercises the real `IntelligenceScoringAgent` or `PersonalizationAgent` against a real database.

**Impact:** Even if Blockers 1 and 2 are fixed, we don't know whether any agent's `_run()` method works correctly against a populated database.

### Blocker 4 (MEDIUM): Phase 1 agents lack multi-tenancy

| Agent | Missing `organization_id` in service calls |
|-------|-------------------------------------------|
| DeepScraperAgent | `company_service.get_required()`, `website_service.get_by_normalized_url()`, `website_service.create()` |
| TechnographicAgent | `website_service.list_by_company()`, `technology_service.get_company_technology()` |
| IntentSignalAgent | `website_service.list_by_company()`, `technology_service.list_by_company()`, `intent_signal_service.list_by_company()` |
| JobRunner (agent dispatch) | `AgentContext()` constructed without `organization_id` |

**Impact:** After Phase 3 migration applies `organization_id NOT NULL` with FK constraints, any service call from a Phase 1 agent without `organization_id` will fail with:

- `FOREIGN KEY constraint failed` (for `create()` calls)
- `NOT NULL constraint failed` (for model creation without org_id)
- No error for reads (but returns empty results from other orgs)

---

## Architectural Gaps

### Gap 1: No lead aggregation service

A "lead" in Irtiqa is the combination of:
- Company + Contact (business discovery)
- Website + Technology (technographic profile)
- IntentSignal (buying signals)
- IntelligenceScore (scoring)
- OutreachMessage (outreach status)
- EvidenceRecord (supporting evidence)

There is no service class or API endpoint that aggregates these into a unified lead profile.

### Gap 2: Pipeline not idempotent for repeated runs

Running the pipeline twice for the same company will:
- Create duplicate `Website` records (new scrape)
- Create duplicate `Technology` records (re-detection)
- Create duplicate `IntentSignal` records (unless dedup catches them)
- Create duplicate `IntelligenceScore` records (append-only)
- Create duplicate `OutreachMessage` records (new variants)

Some deduplication exists (IntentSignal by hash, EvidenceRecord by hash) but not at the pipeline level.

### Gap 3: Async/sync boundary complexity

The `IntelligencePipelineWorkflow` uses `_run_async()` which handles both inside-loop and outside-loop scenarios differently (`asyncio.run()` vs `asyncio.Runner`). The `JobRunner` is fully async. The `WorkflowRunner.execute()` is synchronous. This mixed model has worked in tests but hasn't been validated in production under load.

### Gap 4: Service dependency injection inconsistency

Agents receive services through `**services` dict. Workflows use the same pattern. But `ScoreRefreshWorkflow` instantiates `EvidenceService()` directly (line 149), bypassing dependency injection. The `IntelligencePipelineWorkflow` doesn't pass `organization_id` to any of its 5 `AgentContext` constructors (lines 63-72, 97-101, 127-131, 157-163, 188-194).

---

## Recommended Next Milestone

**Milestone: "Minimum Viable Pipeline"** — Estimated effort: 1-2 sprints

### Phase 4 Plan

#### Sprint 1: Unblock the Pipeline

| Task | Effort | Files | Risk |
|------|--------|-------|------|
| Fix IntelligenceScoringAgent (field name + service call) | 1h | `agent.py` | Low |
| Fix PersonalizationAgent (service call) | 1h | `agent.py` | Low |
| Pass `organization_id` in pipeline's AgentContext constructors | 30m | `intelligence_pipeline.py` | Low |
| Pass `organization_id` in JobRunner's AgentContext construction | 30m | `jobs/runner.py` | Low |
| Pass `organization_id` in Phase 1 agent service calls | 2h | 3 agent files | Medium |
| Write `test_pipeline_end_to_end_real` (no mocks) | 4h | New test file | Medium |
| **Total** | **~9h** | **6 files** | |

#### Sprint 2: Lead Retrieval + Pipeline

| Task | Effort | Files | Risk |
|------|--------|-------|------|
| Create `LeadProfileService` aggregating all entity data | 4h | New service | Low |
| Create `GET /leads/{company_id}` endpoint | 2h | New endpoint | Low |
| Add `LeadsRead` / `LeadList` schemas | 1h | New schema | Low |
| Add default pipeline parameters (crawl depth, signal types) | 1h | Pipeline workflow | Low |
| Implement agent-run dedup (skip if recent run exists) | 3h | Pipeline workflow | Medium |
| Performance test: 10 concurrent pipelines | 4h | Infra | Medium |
| **Total** | **~15h** | **~5 files** | |

#### Sprint 3: Production Hardening

| Task | Effort | Risk |
|------|--------|------|
| Pipeline timeout (max 5 min per run) | Low | 1h |
| Pipeline cost tracking (pages scraped, API calls) | Low | 2h |
| Pipeline status webhook/callback | Medium | 4h |
| Rate limiting per org (max N pipelines/hour) | Low | 2h |
| Dashboard: pipeline success/failure metrics | Medium | 4h |

---

## Verdict

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║        NOT READY FOR REAL LEAD GENERATION                     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

### Justification

1. **Two blocking bugs prevent the pipeline from completing.** The `IntelligenceScoringAgent` and `PersonalizationAgent` both call service `.create()` methods with incorrect argument patterns. Either agent will crash at runtime with a `TypeError` or `ValidationError`. These are the agents responsible for the final two pipeline stages — without them, no score is computed and no outreach message is generated.

2. **No end-to-end test validates the full pipeline.** All existing pipeline tests mock agent execution. The `test_pipeline_through_job_system` test mocks all 5 agents. The `test_pipeline_end_to_end` test mocks all 5 agents. No test exercises a real agent against a real database. We cannot assert that any agent's `_run()` method functions correctly.

3. **Phase 1 agents lack multi-tenant isolation.** Three agents (DeepScraper, Technographic, IntentSignal) call services without `organization_id`. After Phase 3 migration applies `NOT NULL` FK constraints, any `create()` call from these agents will fail. The `JobRunner` also constructs `AgentContext` without `organization_id`.

4. **No lead retrieval API exists.** Even if the pipeline completed successfully, there is no endpoint that aggregates the results into a lead profile. Each data type requires a separate API query. This is a product gap, not a code bug.

### What DOES work

- The data model is comprehensive (10+ entities with proper relationships)
- The scoring policy formula is well-designed and tested
- Evidence recording with content-addressed deduplication is production-ready
- The job scheduling infrastructure (claim-execute-retry) is solid
- The `ScoreRefreshWorkflow` can score existing companies today
- Phase 2/3 multi-tenancy infrastructure is complete
- All CRUD APIs work with tenant isolation
- All service-layer and repository-layer tests pass (462/462)

### Estimated time to readiness

With 1-2 focused sprints addressing the blocking bugs, missing `organization_id` propagation, and adding a lead retrieval endpoint, the pipeline could reach **MVP readiness**. The core architecture is sound — the gaps are in integration, not design.
