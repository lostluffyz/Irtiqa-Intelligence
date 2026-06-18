> **Status: IMPLEMENTED**

# Evidence Records System Audit

## 1. Architecture Consistency

### Finding 1: Transaction Boundary Gap Between Agent and Service

**Severity: High**

The design positions evidence creation at the agent/workflow layer: `BaseAgent.execute()` calls `EvidenceService.record_evidence_batch()` *after* `_run()` succeeds. However, `_run()` calls existing services (e.g., `TechnologyService.create()`) which each own their own transaction via `session_scope()`. By the time evidence is recorded, the output entity transaction is already committed. This means:

- If evidence recording fails, the output entity exists but has no evidence trail (the design acknowledges this and says "log the error but do not fail").
- There is no atomicity guarantee between entity creation and evidence creation.
- The "traceable" goal is weakened because evidence can silently fail without the entity being rolled back.

**Recommended fix:** Either:
1. Extend `BaseService._run_in_transaction()` to accept an optional evidence callback that runs before commit, OR
2. Document this gap explicitly as a known limitation, with a plan to introduce a unit-of-work pattern that spans entity creation and evidence recording when the project needs atomicity.

---

### Finding 2: Score Refresh Workflow Creates Evidence After Score Persistence

**Severity: Medium**

The `score_refresh` workflow creates `IntelligenceScore` records through `IntelligenceScoreService`, which commits its own transaction. The evidence linking those scores to their contributing technologies and signals is then created in a second transaction. Same gap as Finding 1, but more acute here because `score_refresh` is a workflow that runs as a single logical unit — the evidence should be part of the same unit of work.

**Recommended fix:** Document that evidence for workflow outputs is eventually consistent (at-least-once semantics), not atomic. Move to atomic when a cross-service unit-of-work abstraction is introduced.

---

### Finding 3: `score_refresh` Output Registration vs. Evidence Timing

**Severity: Medium**

The `score_refresh` workflow currently returns created score IDs through `WorkflowResult.output_ids["intelligence_scores"]`. If evidence recording happens after the workflow step completes (in `WorkflowRunner`), the output IDs are already committed to the result. Evidence created later is not reflected in the workflow result. Downstream consumers that read workflow results may see scores with zero evidence if evidence recording is delayed or fails.

**Recommended fix:** Create evidence records inside the workflow step (before returning `WorkflowResult`), not in `WorkflowRunner`. The design already says "Workflow steps call `EvidenceService.record_evidence_batch()`" which is correct — implement accordingly.

---

## 2. Repository Pattern Consistency

### Finding 4: `create_many` Accepts `list[dict]` — Inconsistent with BaseRepository

**Severity: Medium**

The existing `BaseRepository.add()` accepts a model instance (`entity: ModelT`). The design's `create_many` accepts `list[dict]`:

```python
create_many(session, records: list[dict]) -> list[EvidenceRecord]
```

This breaks the established repository pattern where repositories operate on ORM entities, not raw dicts. Every other repository in the codebase constructs model instances at the service layer and passes them to `add()`.

**Recommended fix:** Change `create_many` to accept `list[EvidenceRecord]` and construct the model instances in the service layer before calling the repository. This matches the existing pattern:
```python
# Service layer constructs entities
records = [EvidenceRecord(**data) for data in evidence_items]
# Repository persists
repository.add_all(session, records)
```

---

### Finding 5: `delete_by_target` Returns `int` — Inconsistent with BaseRepository

**Severity: Low**

The existing `BaseRepository.delete()` is void-returning (`def delete(self, entity: ModelT) -> None`). The design's `delete_by_target` returns `int` (the count of deleted rows). This is a different pattern. Not fundamentally wrong — batch delete naturally benefits from a row count — but it should be explicitly noted as a departure from the existing pattern.

**Recommended fix:** Document that `delete_by_target` intentionally deviates from `BaseRepository.delete()`'s void return because it's a bulk operation.

---

## 3. Service Layer Consistency

### Finding 6: `EvidenceService` Does Not Extend `BaseService`

**Severity: Low**

The design says `EvidenceService` "follows the existing `BaseService` pattern" but doesn't declare it as `class EvidenceService(BaseService):`. `BaseService` is generic over `(ModelT, RepositoryT)` and provides generic create/read/update/delete methods. `EvidenceService` has custom methods (`record_evidence`, `record_evidence_batch`, `get_target_evidence`, etc.) that don't map to the generic CRUD pattern. The service could extend `BaseService` for the model infrastructure (transaction management, error handling, logging) or be a standalone class that reuses `session_scope()` independently.

**Recommended fix:** Declare `EvidenceService` as extending `BaseService[EvidenceRecord, EvidenceRepository]` to inherit `_run_in_transaction()`, `_validate_*()`, and structured error handling. The existing `BaseService.get()` can serve as `get(evidence_id)`. Custom query methods are added alongside.

---

### Finding 7: `EvidenceCreateParams` Is Undefined

**Severity: High**

The `record_evidence_batch` method signature references `EvidenceCreateParams`:

```python
def record_evidence_batch(self, records: list[EvidenceCreateParams]) -> list[EvidenceRecord]:
```

But `EvidenceCreateParams` is never defined anywhere in the document. It's not a Pydantic schema (the design says no `EvidenceCreate` schema for API consumption) nor a TypedDict. The agent integration section defines an `EvidenceItem` TypedDict for `AgentRunOutput.evidence`, but `EvidenceService.record_evidence_batch` requires a different type.

**Recommended fix:** Define `EvidenceCreateParams` as a TypedDict or dataclass in the design (or use the existing `EvidenceItem` type consistently across both the agent and service boundaries).

---

## 4. Agent Integration Risks

### Finding 8: `AgentRunOutput.evidence` TypedDict Field Is Required, Not Optional

**Severity: Critical**

The design states: "Existing agent implementations that don't return evidence continue to work unchanged — `BaseAgent.execute()` simply skips the evidence recording step when the list is empty." However, `TypedDict` in Python does not support default values or optional keys without PEP 655's `NotRequired` (Python 3.11+):

```python
class AgentRunOutput(TypedDict):
    output_ids: dict[str, list[str]]
    evidence: list[EvidenceItem]   # ← REQUIRED for ALL agents
    summary: str
    stats: dict[str, Any]
```

All 5 existing agents that construct `AgentRunOutput` will fail to type-check because they don't include `evidence`. Mypy strict mode (which the project uses) will report errors for every `AgentRunOutput(...)` call.

**Recommended fix:** Use `from typing import NotRequired` (Python 3.11+) or `from typing_extensions import NotRequired`:

```python
from typing import NotRequired  # Python 3.11+

class AgentRunOutput(TypedDict):
    output_ids: dict[str, list[str]]
    evidence: NotRequired[list[EvidenceItem]]  # ← Optional, defaults to []
    summary: str
    stats: dict[str, Any]
```

Then in `BaseAgent.execute()`:
```python
evidence_list = run_output.get("evidence", [])
if evidence_list:
    evidence_service.record_evidence_batch(evidence_list)
```

---

### Finding 9: `EvidenceItem` Missing `source_type` and `agent_run_id`

**Severity: Medium**

The `EvidenceItem` TypedDict defined for `AgentRunOutput.evidence` includes:
```python
class EvidenceItem(TypedDict):
    source_detail: str
    evidence_type: str
    evidence_value: str
    relationship_type: str
    target_type: str
    target_id: str
    confidence: float
```

But the `evidence_records` table also requires `source_type` (e.g., `website`, `agent_run`) as a non-nullable column. Agents must specify what type of source produced the evidence — this is missing from `EvidenceItem`. Similarly, `agent_run_id` is on the table but not in the TypedDict — `BaseAgent.execute()` would need to inject it after receiving evidence from `_run()`.

**Recommended fix:** Add `source_type` to `EvidenceItem`. Leave `agent_run_id` out of `EvidenceItem` (it's injected by `BaseAgent.execute()` from the agent run record).

---

### Finding 10: `company_id` and `contact_id` Populations Gap

**Severity: Medium**

The `evidence_records` table has denormalized `company_id` and `contact_id` columns. The `EvidenceItem` TypedDict for agents does not include these. `BaseAgent.execute()` has access to the `AgentContext` which contains `company_id` and `contact_id`, so it can inject them. But the design does not specify that `BaseAgent.execute()` should populate these from the context.

**Recommended fix:** Document that `BaseAgent.execute()` injects `company_id` and `contact_id` from `context` into each evidence item before calling `record_evidence_batch()`. This keeps agents from having to repeat this on every run.

---

## 5. Database Design Risks

### Finding 11: No Declarative Foreign Key on `agent_run_id`

**Severity: Medium**

The design correctly notes that `source_id` and `target_id` lack declarative foreign keys (polymorphic, can't have FKs to multiple tables). However, `agent_run_id` is a non-polymorphic reference to a single table (`agent_runs.id`). It should have a declarative `ForeignKey` constraint with `ON DELETE SET NULL` to match the existing pattern (e.g., `technologies.agent_run_id`). Without it, orphan evidence records can accumulate if agent runs are deleted.

**Recommended fix:** Add `ForeignKey("agent_runs.id", ondelete="SET NULL")` to the `agent_run_id` column. This is consistent with existing models where `agent_run_id` is declared as a nullable FK with SET NULL.

---

### Finding 12: `source_detail` Is Unstructured Free Text

**Severity: Medium**

The `source_detail` column is `Text` with free-text descriptions like "extracted_text paragraph 3" or "line 42 of raw_html". This is not programmatically queryable — the "queryability" goal is partially undermined because you can't filter by "all evidence from paragraph 3" without a `LIKE` match on the text. A structured approach (e.g., `source_location_type` and `source_location_value` columns) would be more queryable.

**Recommended fix:** Add optional structured location columns alongside `source_detail`:
- `source_location_type: String(50)` — e.g., `css_selector`, `xpath`, `line_number`, `paragraph_index`
- `source_location_value: String(500)` — e.g., `#main > p:nth-child(3)`, `42`, `3`

Keep `source_detail` as a human-readable description. The structured columns are indexed for queryability.

---

### Finding 13: Check Constraint Value List Is Frozen

**Severity: Low**

The `evidence_type` and `relationship_type` columns use `IN (...)` check constraints. Adding new types later requires a migration that drops and recreates the constraint. In SQLite, this means table recreation. For a startup-stage project, this is acceptable — the constraint values are stable — but should be documented as a known cost of future schema evolution.

**Recommended fix:** Document in the risks section that extending `evidence_type` or `relationship_type` requires a migration with table recreation on SQLite.

---

## 6. SQLite/PostgreSQL Compatibility

### Finding 14: SHA-256 String Length Correct

**Severity: Informational**

The design specifies `String(64)` for `evidence_hash`. SHA-256 produces 256 bits = 32 bytes = 64 hex characters. Correct on both SQLite and PostgreSQL. ✓

---

### Finding 15: Polymorphic FK Pattern Correct

**Severity: Informational**

Using string columns without declarative `ForeignKey` constraints for polymorphic references is the standard approach for SQLAlchemy projects. It works identically on SQLite and PostgreSQL. The design correctly notes this is consistent with the existing `agent_runs.job_id` pattern. ✓

---

### Finding 16: Check Constraint Syntax Is Portable

**Severity: Informational**

The check constraints use standard SQL (`IN (...)` lists and range comparisons). These work on both SQLite and PostgreSQL without dialect-specific syntax. ✓

---

## 7. Migration Risks

### Finding 17: Migration Creates a New Table — No Data Migration Needed

**Severity: Informational**

The `evidence_records` table is a new table with no dependencies on existing data. The migration is additive and non-disruptive. The migration file name uses the existing naming convention (`20260611_0005_create_evidence_records.py`). Assuming no version conflicts with existing migrations, this is low risk. ✓

---

### Finding 18: Existing Migration `20260609_0003` Is the Current Head

**Severity: Informational**

The design uses revision ID `20260611_0005`. The current head is `20260609_0003` (jobs table). The gap between `0003` and `0005` (no `0004`) is not a problem — Alembic uses the revision chain, not the sequence number. But it's worth noting that there is no `0004` in the chain, which could cause confusion during code review.

**Recommended fix:** Use `20260611_0004_create_evidence_records.py` for consistency with the existing numeric sequence, or add a comment explaining the gap.

---

## 8. API Consistency

### Finding 19: Evidence Paths Mix Query Params and Path Params

**Severity: Low**

The design uses:
- `/evidence/by-target?target_type=X&target_id=Y` — query params
- `/evidence/by-source?source_type=X&source_id=Y` — query params
- `/evidence/by-company/{company_id}` — path param
- `/evidence/by-agent-run/{agent_run_id}` — path param
- `/evidence/{evidence_id}` — path param
- `/evidence/summary?target_type=X&target_id=Y` — query params

The inconsistent mix of query params and path params for identifier-type parameters is a minor style concern. Both patterns exist in the existing API (e.g., `/companies/{company_id}` uses path params for IDs). The `/by-target` and `/by-source` endpoints could reasonably use path params for `target_type` and `source_type` — but since these are polymorphic discriminators, query params are acceptable.

**Recommended fix:** Make `target_type` and `source_type` path params for consistency: `/evidence/by-target/{target_type}/{target_id}`. Or document that query params are intentional for polymorphic discrimination.

---

### Finding 20: Evidence Service Dependency Injection Pattern

**Severity: Low**

The design shows:
```python
def get_evidence_service() -> EvidenceService:
    return EvidenceService()
```

This matches the existing dependency pattern in `app/api/dependencies.py` (e.g., `get_company_service()`). Correct. ✓

---

### Finding 21: Summary Endpoint Response Type Is Undefined

**Severity: Medium**

The design says `GET /evidence/summary` returns "aggregated counts by `evidence_type` and `relationship_type`" but does not specify the JSON response structure. This makes it impossible to write a test or implement an API client from the design alone.

**Recommended fix:** Define the summary response structure:
```json
{
    "total_evidence": 42,
    "by_evidence_type": {
        "html_snippet": 10,
        "text_excerpt": 15,
        "signature_match": 12,
        "computed_metric": 5
    },
    "by_relationship_type": {
        "supports": 30,
        "contributes_to": 12
    }
}
```

---

## 9. Testing Completeness

### Finding 22: Test Count Mismatch (24 Named vs. 35 Claimed)

**Severity: Medium**

The design says "approximately 25 unit tests + 10 integration tests = 35 tests" but only names:
- 14 unit tests (evidence model, repository, service, schema, agent, workflow)
- 10 integration tests (API endpoints, PostgreSQL)

Total named: 24. Gap: ~11 unnamed tests.

**Recommended fix:** Either adjust the estimate to 24, or add the 11 missing tests to the table:
- `test_evidence_service_company_id_injection` — agent context company_id flows to evidence
- `test_evidence_service_contact_id_injection` — agent context contact_id flows to evidence
- `test_evidence_service_source_type_validation` — invalid source_type is rejected
- `test_evidence_repository_pagination` — list methods respect limit/offset
- `test_evidence_repository_empty_results` — query methods return empty list when no matches
- `test_evidence_service_record_failure_logged` — failure is logged, not raised
- `test_evidence_api_empty_list` — GET /evidence returns empty items list
- `test_evidence_api_invalid_target_type` — invalid evidence_type returns 422 on query
- `test_evidence_api_list_pagination` — limit/offset params work
- `test_evidence_constraints_update` — no update endpoints exist
- `test_evidence_model_timestamps` — created_at is auto-set on creation

---

### Finding 23: Agent Evidence Failure Mode Not Tested

**Severity: Medium**

The design says "If evidence recording fails, log the error but do not fail the agent execution." This is a critical behavioral guarantee — the agent must succeed even when the evidence system fails. There is no test for this guarantee.

**Recommended fix:** Add a test `test_agent_execute_succeeds_when_evidence_fails` that injects a failing `EvidenceService` mock and confirms the agent still returns `AGENT_STATUS_SUCCEEDED` with evidence recording logged as a warning.

---

### Finding 24: Existing 284 Tests and 24 PostgreSQL Tests Coverage Confirmed

**Severity: Informational**

The design explicitly states that all 284 existing SQLite tests and 24 PostgreSQL tests must continue to pass. This is correctly stated as Success Criteria items 7 and 8. ✓

---

## 10. Future Maintenance Concerns

### Finding 25: Evidence Type String Values Are Not Centralized as Constants

**Severity: Medium**

The design uses string literals throughout: `"html_snippet"`, `"text_excerpt"`, `"computed_metric"`, `"supports"`, `"contributes_to"`, `"website"`, `"technology"`, etc. These strings appear in:
- Model check constraint definitions
- `EvidenceItem` in agent return types
- `EvidenceService` recording logic
- API query parameter validation

If a string value changes (e.g., renaming `supports` to `confirms`), every reference across all these layers needs updating. The existing project pattern uses module-level constants (e.g., `AGENT_STATUS_SUCCEEDED`, `SCORE_VERSION`).

**Recommended fix:** Define all discriminator values as module-level constants in the model file:
```python
# app/models/evidence_record.py
EVIDENCE_TYPE_HTML_SNIPPET = "html_snippet"
EVIDENCE_TYPE_TEXT_EXCERPT = "text_excerpt"
EVIDENCE_TYPE_URL_MATCH = "url_match"
EVIDENCE_TYPE_SIGNATURE_MATCH = "signature_match"
EVIDENCE_TYPE_COMPUTED_METRIC = "computed_metric"
EVIDENCE_TYPE_AGENT_SUMMARY = "agent_summary"

RELATIONSHIP_SUPPORTS = "supports"
RELATIONSHIP_CONTRADICTS = "contradicts"
RELATIONSHIP_CONTRIBUTES_TO = "contributes_to"
RELATIONSHIP_GENERATES = "generates"

SOURCE_TYPE_WEBSITE = "website"
SOURCE_TYPE_AGENT_RUN = "agent_run"
SOURCE_TYPE_JOB = "job"

TARGET_TYPE_TECHNOLOGY = "technology"
TARGET_TYPE_INTENT_SIGNAL = "intent_signal"
TARGET_TYPE_INTELLIGENCE_SCORE = "intelligence_score"
TARGET_TYPE_OUTREACH_MESSAGE = "outreach_message"

VALID_EVIDENCE_TYPES = {...}
VALID_RELATIONSHIP_TYPES = {...}
VALID_SOURCE_TYPES = {...}
VALID_TARGET_TYPES = {...}
```

Use these constants in check constraints, TypedDicts, service validation, and API documentation.

---

### Finding 26: No Maximum Length on `text_excerpt` Evidence Values

**Severity: Low**

The `evidence_value` column is `Text` with no documented maximum length. Agents could store arbitrarily large excerpts (e.g., entire scraped HTML pages). The design says "Evidence values are excerpts, not full documents" but provides no enforcement mechanism.

**Recommended fix:** Add a documented maximum length for evidence values at the service layer (e.g., 5000 characters for most types, with overflow indicated by `...[truncated]` suffix). This prevents the evidence table from becoming a dumping ground for large content that belongs in the source tables.

---

### Finding 27: Evidence Deduplication Scoped to Target, Not Cross-Target

**Severity: Informational**

The SHA-256 deduplication checks `evidence_hash` + `target_type` + `target_id`. This means two different intelligence scores could both reference the same technology evidence — and that's correct behavior (the evidence legitimately supports both scores). But it also means the same exact evidence content could be stored N times for N targets. The design explicitly accepts this as a trade-off. ✓

---

## Summary Table

| Finding | Severity | Section |
|---|---|---|
| 1: Transaction boundary gap between agent and evidence | **High** | Architecture |
| 2: Score refresh evidence timing | **Medium** | Architecture |
| 3: Score refresh output registration vs. evidence | **Medium** | Architecture |
| 4: `create_many` uses dicts instead of model instances | **Medium** | Repository |
| 5: `delete_by_target` returns int, inconsistent with BaseRepository | **Low** | Repository |
| 6: `EvidenceService` doesn't extend `BaseService` | **Low** | Service |
| 7: `EvidenceCreateParams` is undefined | **High** | Service |
| 8: `AgentRunOutput.evidence` is required, not optional | **Critical** | Agent |
| 9: `EvidenceItem` missing `source_type` column | **Medium** | Agent |
| 10: `company_id`/`contact_id` denormalization gap | **Medium** | Agent |
| 11: `agent_run_id` lacks declarive foreign key | **Medium** | Database |
| 12: `source_detail` is unstructured free text | **Medium** | Database |
| 13: Check constraint value list is frozen | **Low** | Database |
| 14: SHA-256 string length correct | Informational | Compatibility |
| 15: Polymorphic FK pattern correct | Informational | Compatibility |
| 16: Check constraint syntax is portable | Informational | Compatibility |
| 17: Migration creates new table, no data migration | Informational | Migration |
| 18: Migration revision gap (0003 → 0005, no 0004) | **Low** | Migration |
| 19: API paths mix query params and path params | **Low** | API |
| 20: Service dependency injection pattern correct | Informational | API |
| 21: Summary endpoint response type is undefined | **Medium** | API |
| 22: Test count mismatch (24 named vs. 35 claimed) | **Medium** | Testing |
| 23: Agent evidence failure mode not tested | **Medium** | Testing |
| 24: Existing test preservation confirmed | Informational | Testing |
| 25: Evidence type strings not centralized as constants | **Medium** | Maintenance |
| 26: No maximum length for evidence excerpts | **Low** | Maintenance |
| 27: Deduplication scope is per-target | Informational | Maintenance |

---

## Final Verdict

### Critical Issues (Must Fix Before Implementation)

| Finding | Issue | Fix |
|---|---|---|
| #8 | `AgentRunOutput.evidence` is a required TypedDict field, making `evidence` mandatory for all 5 existing agents. Breaks mypy strict mode on every agent that constructs `AgentRunOutput`. | Use `NotRequired` from `typing` (Python 3.11+) or `typing_extensions`. |

### High Issues (Should Fix Before Implementation)

| Finding | Issue | Fix |
|---|---|---|
| #1 | Evidence recording happens in a separate transaction after entity creation. No atomicity guarantee. | Extend `BaseService._run_in_transaction()` with an evidence callback, or document the gap. |
| #7 | `EvidenceCreateParams` is referenced in the service signature but never defined. | Define as a TypedDict or reuse `EvidenceItem` across the agent/service boundary. |

### Medium Issues (Fix During Implementation)

| Finding | Issue | Fix |
|---|---|---|
| #2, #3 | Score refresh evidence timing and registration gaps | Create evidence inside workflow steps, not in WorkflowRunner |
| #4 | `create_many` uses `list[dict]` — inconsistent with `BaseRepository.add()` | Change to `list[EvidenceRecord]` |
| #9, #10 | `EvidenceItem` missing `source_type`, `company_id`/`contact_id` injection gap | Add to TypedDict; document that `execute()` injects from context |
| #11 | `agent_run_id` lacks declarative FK | Add `ForeignKey("agent_runs.id", ondelete="SET NULL")` |
| #12 | `source_detail` is unstructured free text | Add structured `source_location_type` and `source_location_value` columns |
| #21 | Summary response structure undefined | Define JSON structure in design |
| #22 | Test count mismatch | Add missing tests or adjust estimate |
| #23 | Agent evidence failure mode not tested | Add mock-based test |
| #25 | Type strings not centralized | Define module-level constants |

### Readiness Verdict

**Not ready for implementation.** One critical issue (Finding 8: `NotRequired` on `AgentRunOutput.evidence`) and two high issues (Findings 1 and 7: transaction gap and undefined type) must be resolved before any code is written. If these three issues are fixed, the remaining medium issues can be addressed during implementation without blocking.
