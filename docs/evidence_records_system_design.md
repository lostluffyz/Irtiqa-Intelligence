# Evidence Records System Design

## 1. Purpose

This document defines an Evidence Records System for Irtiqa Intelligence. The system provides a unified, queryable provenance layer that links every intelligence output (scores, signals, findings, messages) to the specific source evidence that produced it.

Currently, evidence is scattered across multiple tables in ad-hoc fields: `intelligence_scores.rationale` (free-text), `intent_signals.source_url`, `technologies.website_id`, and `agent_runs.output_summary`. This works for basic audit but breaks down when a user needs to ask "Why was this score 82.5?" — the answer requires scanning multiple tables, parsing text fields, and manually reconstructing the evidence chain.

A dedicated evidence records system makes every intelligence decision traceable, auditable, and explainable without requiring text parsing or manual investigation.

## 2. Current Project State

### Existing Evidence References

| Entity | Evidence Fields | Limitation |
|---|---|---|
| `websites` | `raw_html`, `extracted_text` | Full content stored, but no link to which passages triggered which decisions |
| `technologies` | `website_id`, `agent_run_id`, `confidence`, `detection_method` | Links to source website, but no excerpt showing why the detection was made |
| `intent_signals` | `website_id`, `technology_id`, `source_url`, `strength`, `confidence` | Links to source URL, but no excerpt of the text that triggered the signal |
| `intelligence_scores` | `technology_id`, `agent_run_id`, `rationale` (text) | Rationale is human-readable but not programmatically queryable |
| `outreach_messages` | `intelligence_score_id`, `agent_run_id`, `personalization_angle` | Links to parent score, but not to which specific evidence drove which angle |
| `agent_runs` | `input_summary`, `output_summary` | Summaries are text fields, not structured evidence links |

### Current Provenance Flow

```text
Deep Scraper Agent
  └─ writes to: websites (raw_html, extracted_text)
     └─ Technographic Agent reads from: websites.extracted_text
        └─ writes to: technologies (via TechnologyService)
           └─ Intent Signal Agent reads from: websites.extracted_text, technologies
              └─ writes to: intent_signals (via IntentSignalService)
                 └─ Intelligence Scoring Agent reads from: technologies, intent_signals
                    └─ writes to: intelligence_scores (via IntelligenceScoreService)
                       └─ Personalization Agent reads from: intelligence_scores, technologies
                          └─ writes to: outreach_messages (via OutreachMessageService)
```

Each step in this chain discards the specific evidence references. By the time a score is produced, the link back to the specific text passage that contributed to it is lost.

### Existing Patterns to Reuse

- **SQLAlchemy models**: `Base`, `UUIDPrimaryKeyMixin`, `TimestampMixin` in `app/models/`
- **Repository layer**: `BaseRepository` in `app/repositories/` with CRUD operations
- **Service layer**: `BaseService` in `app/services/` with transaction ownership via `session_scope()`
- **API layer**: Router endpoints in `app/api/v1/endpoints/` with service dependencies
- **Schemas**: Pydantic v2 Create/Update/Read/List schemas in `app/schemas/`
- **Background jobs**: `JobService`, `JobRunner` for async evidence processing
- **Agent interface**: `BaseAgent.execute()` returns `AgentResult` with `output_ids` mapping entity types to created IDs

### Known Gap

The project_handoff.md explicitly acknowledges: "No dedicated `source_observations` or evidence table exists." This design fills that gap.

## 3. Evidence System Goals

### Primary Goals

1. **Provenance** — Every intelligence score, signal, finding, and message must be traceable to the specific evidence that produced it.
2. **Queryability** — Answer "What evidence supports this score?" and "Which outputs used this evidence?" without parsing text fields.
3. **Auditability** — Show the complete decision trail for any output, from raw source through each processing step.
4. **Minimal disruption** — Add the evidence layer alongside existing entities without breaking existing CRUD APIs, agent execution, or workflow behavior.
5. **Database portability** — SQLite-first with PostgreSQL compatibility through SQLAlchemy portable types.

### Non-Goals

- No full-text search engine (no Elasticsearch).
- No vector embeddings or similarity search (no vector database).
- No cloud storage for evidence blobs.
- No retrospective backfill of existing records (new records only).
- No replacement of existing entity relationships — evidence supplements, not supplants.

## 4. Architecture Integration

### Where Evidence Records Fit

The evidence records system sits between agents and their output targets. Instead of agents writing directly to `technologies`, `intent_signals`, `intelligence_scores`, or `outreach_messages` and discarding the provenance, agents also create evidence records that capture what they saw and how they used it.

```text
Agent
  │
  ├─ writes output entity (e.g. Technology, IntentSignal, IntelligenceScore)
  │     └─ via existing Service layer (unchanged)
  │
  └─ writes evidence_records (new)
        └─ maps: source → relationship → target
             e.g. "website.extracted_text passage X"
                   → "supports"
                   → "technology Y with confidence 0.92"
```

### Transaction Boundary Design

Evidence records are created in a **separate transaction** from the output entities they reference. The agent or workflow first commits the output entity through the existing service layer, then commits the evidence in a subsequent transaction. This means:

- Entity creation and evidence recording are **not atomic**. If evidence recording fails, the entity exists without an evidence trail.
- Evidence recording uses at-least-once semantics. Evidence may be duplicated if retried (SHA-256 deduplication mitigates this within a target scope).
- This design is an explicit trade-off. Making evidence recording atomic would require either:
  - Storing evidence data inside the existing service transaction (mixing concerns), or
  - Introducing a cross-service unit-of-work abstraction (premature at current stage).

This limitation is accepted for the current project stage. A future unit-of-work abstraction can make entity+evidence creation atomic without changing the evidence_records table structure.

### Integration Points

| Component | Integration | Change Required |
|---|---|---|
| `BaseAgent._run()` | Agents return `AgentRunOutput` with `output_ids`. Evidence creation happens after `_run()` in `execute()` using the returned IDs and agent-specific evidence data. | Modify `BaseAgent.execute()` to call a new `EvidenceService` after `_run()` succeeds. |
| `BaseService` | Evidence creation is a separate concern from entity persistence. Services should not create evidence records. | None — evidence is created at the agent/workflow layer, not the service layer. |
| `ScoreRefreshPolicy` | The policy computes scores from technologies and intent signals. Each score component is based on specific evidence. | Modify `score_refresh` workflow to create evidence records linking each score to the specific technologies and signals that contributed. |
| `WorkflowRunner` | Workflows orchestrate multiple steps. Evidence can span steps. | Evidence creation in workflow steps via service calls. |

### Layer Positioning

```text
┌──────────────────────────────────────────────┐
│              Agents / Workflows               │
│  Creates output entities + evidence records   │
├──────────────────────────────────────────────┤
│                Service Layer                  │
│  EvidenceService (new) + existing services    │
├──────────────────────────────────────────────┤
│              Repository Layer                 │
│  EvidenceRepository (new) + existing repos    │
├──────────────────────────────────────────────┤
│              Database (SQLite/PG)             │
│  evidence_records (new table) + existing      │
└──────────────────────────────────────────────┘
```

## 5. Data Model Design

### Table: `evidence_records`

A single table that stores all evidence links. A polymorphic design using content-type and source-type discriminator columns avoids multiple join tables while remaining portable across SQLite and PostgreSQL.

**Why a single table instead of per-entity evidence tables:**

- Cross-entity queries ("show evidence across all output types for this company") are simple single-table queries.
- New output types don't require new evidence tables.
- The schema is simpler to migrate, test, and maintain.
- Total evidence volume at this project stage does not warrant table-per-entity sharding.

### Centralized Constants

All discriminator values used in the `evidence_records` table are defined as module-level constants in `app/models/evidence_record.py`. This ensures a single source of truth across model check constraints, service validation, API query filtering, and agent integration code.

```python
# ── Evidence types ──────────────────────────────────────
EVIDENCE_TYPE_HTML_SNIPPET = "html_snippet"
EVIDENCE_TYPE_TEXT_EXCERPT = "text_excerpt"
EVIDENCE_TYPE_URL_MATCH = "url_match"
EVIDENCE_TYPE_SIGNATURE_MATCH = "signature_match"
EVIDENCE_TYPE_COMPUTED_METRIC = "computed_metric"
EVIDENCE_TYPE_AGENT_SUMMARY = "agent_summary"

VALID_EVIDENCE_TYPES = frozenset({
    EVIDENCE_TYPE_HTML_SNIPPET,
    EVIDENCE_TYPE_TEXT_EXCERPT,
    EVIDENCE_TYPE_URL_MATCH,
    EVIDENCE_TYPE_SIGNATURE_MATCH,
    EVIDENCE_TYPE_COMPUTED_METRIC,
    EVIDENCE_TYPE_AGENT_SUMMARY,
})

# ── Relationship types ──────────────────────────────────
RELATIONSHIP_SUPPORTS = "supports"
RELATIONSHIP_CONTRADICTS = "contradicts"
RELATIONSHIP_CONTRIBUTES_TO = "contributes_to"
RELATIONSHIP_GENERATES = "generates"

VALID_RELATIONSHIP_TYPES = frozenset({
    RELATIONSHIP_SUPPORTS,
    RELATIONSHIP_CONTRADICTS,
    RELATIONSHIP_CONTRIBUTES_TO,
    RELATIONSHIP_GENERATES,
})

# ── Source entity types ─────────────────────────────────
SOURCE_TYPE_WEBSITE = "website"
SOURCE_TYPE_AGENT_RUN = "agent_run"
SOURCE_TYPE_JOB = "job"

VALID_SOURCE_TYPES = frozenset({
    SOURCE_TYPE_WEBSITE,
    SOURCE_TYPE_AGENT_RUN,
    SOURCE_TYPE_JOB,
})

# ── Target entity types ─────────────────────────────────
TARGET_TYPE_TECHNOLOGY = "technology"
TARGET_TYPE_INTENT_SIGNAL = "intent_signal"
TARGET_TYPE_INTELLIGENCE_SCORE = "intelligence_score"
TARGET_TYPE_OUTREACH_MESSAGE = "outreach_message"

VALID_TARGET_TYPES = frozenset({
    TARGET_TYPE_TECHNOLOGY,
    TARGET_TYPE_INTENT_SIGNAL,
    TARGET_TYPE_INTELLIGENCE_SCORE,
    TARGET_TYPE_OUTREACH_MESSAGE,
})

# ── Evidence value maximum length (characters) ──────────
EVIDENCE_VALUE_MAX_LENGTH = 5000
```

The model's SQLAlchemy `CheckConstraint` definitions reference these sets. The service layer uses the same constants for validation. Agent code imports `EVIDENCE_TYPE_*` and `RELATIONSHIP_*` constants rather than using raw strings. This matches the existing project pattern (e.g., `AGENT_STATUS_SUCCEEDED`, `SCORE_VERSION`).

**Columns:**

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | `String(36)` PK | No | UUID primary key |
| `source_type` | `String(100)` | No | Discriminator: `website`, `agent_run`, `job` |
| `source_id` | `String(36)` | No | FK to the source entity (polymorphic, no declarative FK) |
| `source_detail` | `Text` | Yes | Free-text description of the source (e.g., "extracted_text paragraph 3", "line 42 of raw_html") |
| `source_location_type` | `String(50)` | Yes | Structured location method: `css_selector`, `xpath`, `line_number`, `paragraph_index`, `url_fragment` |
| `source_location_value` | `String(500)` | Yes | Structured location value (e.g., `#main > p:nth-child(3)`, `/html/body/div[2]/p`, `42`, `3`) |
| `evidence_type` | `String(150)` | No | Type — uses centralised `EVIDENCE_TYPE_*` constants |
| `evidence_value` | `Text` | No | The actual evidence excerpt (max ~5000 characters). Full raw content remains in source tables. |
| `evidence_hash` | `String(64)` | Yes | SHA-256 hex digest of `evidence_value` for deduplication across runs |
| `relationship_type` | `String(100)` | No | Relationship — uses centralised `RELATIONSHIP_*` constants |
| `target_type` | `String(100)` | No | Target discriminator — uses centralised `TARGET_TYPE_*` constants |
| `target_id` | `String(36)` | No | FK to the target entity (polymorphic, no declarative FK) |
| `confidence` | `Float` | No | Confidence in this evidence (0.0–1.0), mirrors the confidence on the target entity |
| `agent_run_id` | `String(36)` | Yes | Declarative FK to `agent_runs.id` with `ondelete="SET NULL"` |
| `company_id` | `String(36)` | Yes | FK to `companies.id` — denormalized for efficient per-company queries |
| `contact_id` | `String(36)` | Yes | FK to `contacts.id` — denormalized for efficient per-contact queries |
| `created_at` | `DateTime(timezone=True)` | No | When this evidence was recorded |

**Indexes:**

| Index | Columns | Purpose |
|---|---|---|
| Primary | `id` | PK lookup |
| `ix_evidence_target` | `target_type`, `target_id` | Find all evidence for a target entity |
| `ix_evidence_source` | `source_type`, `source_id` | Find all targets produced from a source |
| `ix_evidence_type` | `evidence_type` | Filter by evidence category |
| `ix_evidence_relationship` | `relationship_type` | Filter by relationship |
| `ix_evidence_agent_run` | `agent_run_id` | Evidence by agent run |
| `ix_evidence_company` | `company_id` | Evidence by company (denormalized) |
| `ix_evidence_contact` | `contact_id` | Evidence by contact (denormalized) |
| `ix_evidence_hash` | `evidence_hash` | Deduplication |
| `ix_evidence_target_type` | `target_type` | Evidence count by entity type |
| `ix_evidence_created_at` | `created_at` | Time-ordered queries |
| `ix_evidence_source_location` | `source_location_type`, `source_location_value` | Structured source location lookups |

**Foreign key notes:**

- `source_id` and `target_id` are polymorphic references — they may point to records in multiple tables (`websites`, `agent_runs`, `technologies`, etc.). Declarative `ForeignKey` constraints are not applied to these columns. Application-layer validation in the service layer ensures referential integrity. This is consistent with the existing pattern in `agent_runs.job_id`.
- `agent_run_id` is **not** polymorphic — it always references `agent_runs.id`. It uses a declarative `ForeignKey("agent_runs.id", ondelete="SET NULL")`. This is consistent with how other models declare `agent_run_id` (e.g., `technologies.agent_run_id`, `intent_signals.agent_run_id`).
- `company_id` and `contact_id` are denormalized query shortcuts. No declarative foreign keys are applied — application-layer validation ensures they match the referenced entities.

### Check Constraints

```text
evidence_type IN (
    'html_snippet', 'text_excerpt', 'url_match',
    'signature_match', 'computed_metric', 'agent_summary'
)
relationship_type IN (
    'supports', 'contradicts', 'contributes_to', 'generates'
)
confidence >= 0.0 AND confidence <= 1.0
```

## 6. Repository Design

### EvidenceRepository

Follows the existing `BaseRepository` pattern in `app/repositories/base.py`.

**Methods:**

| Method | Signature | Description |
|---|---|---|
| `add` | `(session, entity: EvidenceRecord) → EvidenceRecord` | Add a single evidence record. Accepts a model instance (consistent with `BaseRepository.add()`). |
| `add_all` | `(session, entities: list[EvidenceRecord]) → list[EvidenceRecord]` | Bulk add for batch evidence recording. Accepts model instances (consistent with SQLAlchemy `session.add_all()`). |
| `get` | `(session, record_id) → EvidenceRecord | None` | Get by ID |
| `list_by_target` | `(session, target_type, target_id) → list[EvidenceRecord]` | All evidence for a target entity |
| `list_by_source` | `(session, source_type, source_id) → list[EvidenceRecord]` | All targets produced from a source |
| `list_by_agent_run` | `(session, agent_run_id) → list[EvidenceRecord]` | Evidence by agent run |
| `list_by_company` | `(session, company_id) → list[EvidenceRecord]` | Evidence by company |
| `list_by_entity_type` | `(session, target_type, limit, offset) → list[EvidenceRecord]` | Paginated evidence by entity type |
| `count_by_target` | `(session, target_type, target_id) → int` | Evidence count for a target |
| `delete` | `(session, record_id) → bool` | Delete a single evidence record |
| `delete_by_target` | `(session, target_type, target_id) → int` | Delete all evidence for a target. Returns count of deleted rows (intentionally deviates from void-returning `BaseRepository.delete()` for bulk operation feedback). |

**Repository convention:**

- Accepts `Session` in constructor (matches existing pattern).
- Does not commit transactions (matches existing pattern).
- Returns ORM entities (matches existing pattern).
- Does not import API, service, workflow, or agent layers (matches existing pattern).
- Accepts model instances (`EvidenceRecord`), not raw dicts, consistent with `BaseRepository.add()`. Model construction happens at the service layer.

## 7. Service Design

### EvidenceService

Extends the existing `BaseService[EvidenceRecord, EvidenceRepository]` in `app/services/base.py`. The generic base class provides `get()`, `_run_in_transaction()`, `_validate_*()`, and structured error handling. Custom evidence-specific methods are added alongside the inherited ones.

### EvidenceItem

A single TypedDict shared across the agent boundary and the service boundary. This replaces the separately-proposed `EvidenceCreateParams` — one type for recording, one implementation.

```python
from typing import NotRequired, TypedDict
from typing_extensions import NotRequired  # Python 3.11+: from typing import NotRequired


class EvidenceItem(TypedDict):
    """A single evidence record to be persisted.

    ``source_type`` is the discriminator for the origin entity
    (website, agent_run, job).  ``target_type`` and ``target_id``
    identify the output entity this evidence supports.

    ``company_id`` and ``contact_id`` are omitted here; they are
    injected automatically by ``BaseAgent.execute()`` from the
    ``AgentContext``.  ``agent_run_id`` is also injected by
    ``BaseAgent.execute()`` after the agent run record is created.
    """

    source_type: str
    source_detail: str
    source_location_type: NotRequired[str | None]
    source_location_value: NotRequired[str | None]
    evidence_type: str
    evidence_value: str
    relationship_type: str
    target_type: str
    target_id: str
    confidence: float
```

**Methods:**

| Method | Signature | Description |
|---|---|---|
| `record_evidence` | `(source_type, source_id, source_detail, evidence_type, evidence_value, relationship_type, target_type, target_id, confidence, agent_run_id, company_id, contact_id, source_location_type=None, source_location_value=None) → EvidenceRecord` | Single evidence record creation with validation. Generates SHA-256 `evidence_hash` automatically. |
| `record_evidence_batch` | `(items: list[EvidenceItem], agent_run_id: str, company_id: str | None, contact_id: str | None) → list[EvidenceRecord]` | Batch creation within a single transaction. Injects ``agent_run_id``, ``company_id``, and ``contact_id`` into every item. Compute SHA-256 hashes and performs deduplication within the batch. |
| `get_target_evidence` | `(target_type, target_id) → list[EvidenceRecord]` | All evidence for a target, ordered by type then created_at |
| `get_source_targets` | `(source_type, source_id) → list[EvidenceRecord]` | All targets produced from a source |
| `get_company_evidence` | `(company_id, target_type=None, limit=100, offset=0) → list[EvidenceRecord]` | Per-company evidence query with optional type filter |
| `get_agent_run_evidence` | `(agent_run_id) → list[EvidenceRecord]` | All evidence from a single agent run |
| `get_evidence_summary` | `(target_type, target_id) → EvidenceSummary` | Aggregated counts and types for a target |
| `delete_target_evidence` | `(target_type, target_id) → int` | Remove evidence for a target |

**Service convention:**

- Owns transaction boundaries via `session_scope()` (matches existing pattern).
- Uses `EvidenceRepository` for data access (matches existing pattern).
- Uses centralized logging via `irtiqa.services` namespace (matches existing pattern).
- Uses structured errors from `app/core/errors.py` (matches existing pattern).
- Validates evidence_type, relationship_type, source_type, and target_type against the centralized constant sets before persisting.

**Evidence hash deduplication:**

`record_evidence_batch` computes SHA-256 of each item's `evidence_value`. If a record with the same `evidence_hash` and `target_type`/`target_id` already exists, the duplicate record is skipped. Deduplication is scoped per target — the same evidence content may legitimately support multiple targets.

### Integration with BaseAgent.execute()

The `BaseAgent.execute()` method is extended to call `EvidenceService.record_evidence_batch()` after `_run()` succeeds. Concrete agents return additional structured data from `_run()` that describes what evidence was used. This requires an extension to `AgentRunOutput`:

```python
from typing import Any, NotRequired, TypedDict


class EvidenceItem(TypedDict):
    """A single evidence item returned by an agent's ``_run()``.

    ``source_type``, ``source_detail``, ``evidence_type``,
    ``evidence_value``, ``relationship_type``, ``target_type``,
    ``target_id``, and ``confidence`` are populated by the agent.

    ``source_location_type`` and ``source_location_value`` are
    optional structured references (e.g., CSS selector + value).

    ``company_id``, ``contact_id``, and ``agent_run_id`` are NOT
    included here — they are injected by ``BaseAgent.execute()``
    from ``AgentContext`` and the agent run record.
    """

    source_type: str
    source_detail: str
    source_location_type: NotRequired[str | None]
    source_location_value: NotRequired[str | None]
    evidence_type: str
    evidence_value: str
    relationship_type: str
    target_type: str
    target_id: str
    confidence: float


class AgentRunOutput(TypedDict):
    """Return type for ``BaseAgent._run()``.

    ``evidence`` is optional via ``NotRequired``. Agents that do not
    produce evidence omit the key entirely.
    """

    output_ids: dict[str, list[str]]
    evidence: NotRequired[list[EvidenceItem]]
    summary: str
    stats: dict[str, Any]
```

The `BaseAgent.execute()` method is modified to:

1. Call `_run(context)` as before — agents create output entities and return IDs.
2. Extract `evidence` from the returned `run_output` via `run_output.get("evidence", [])`.
3. If evidence is non-empty, call `EvidenceService.record_evidence_batch()` passing:
   - `items`: the evidence list from the agent
   - `agent_run_id`: the ID of the newly created agent run record
   - `company_id`: from `context.company_id`
   - `contact_id`: from `context.contact_id`
4. If evidence recording fails, log the error as a warning but do not fail the agent execution — evidence is supplementary, not critical. The agent's `AGENT_STATUS_SUCCEEDED` status is preserved.
5. Include evidence count in agent run stats.

**company_id and contact_id injection:** These are not duplicated in `EvidenceItem` because `BaseAgent.execute()` always has access to `context.company_id` and `context.contact_id`. Injecting them centrally:
- Prevents every agent from having to repeat the same two fields in every evidence item.
- Ensures consistency — all evidence for a given agent run shares the same company/contact context.
- Allows agents to create evidence items without knowing about the denormalized schema.

**Evidence recording failure behavior:**

```python
evidence_list = run_output.get("evidence", [])
if evidence_list:
    try:
        evidence_service.record_evidence_batch(
            items=evidence_list,
            agent_run_id=agent_run_id,
            company_id=context.company_id,
            contact_id=context.contact_id,
        )
    except Exception:
        self.logger.warning(
            "Evidence recording failed, agent execution continues",
            extra={
                "agent_name": self.name,
                "agent_run_id": agent_run_id,
                "evidence_count": len(evidence_list),
            },
            exc_info=True,
        )
```

This is tested explicitly (see Testing Strategy).

### Integration with Score Refresh Workflow

The `score_refresh` workflow is modified to create evidence records linking each `IntelligenceScore` to:

- The specific `Technology` records that contributed to `technographic_score`
- The specific `IntentSignal` records that contributed to `intent_score`
- The `Company` and `Contact` fields that contributed to `fit_score` and `engagement_score`

Each evidence record uses:
- `source_type = "agent_run"`, `source_id = <the score_refresh agent_run_id>`
- `target_type = "intelligence_score"`, `target_id = <the score ID>`
- `evidence_type = "computed_metric"` for technology and signal references
- `relationship_type = "contributes_to"`

## 8. API Design

### Endpoints

All evidence endpoints follow existing CRUD API patterns (path, response format, error handling).

| Method | Path | Description |
|---|---|---|
| `GET` | `/evidence/by-target/{target_type}/{target_id}` | List evidence for a specific target entity. Query params: `limit`, `offset`. |
| `GET` | `/evidence/by-source/{source_type}/{source_id}` | List targets produced from a source. Query params: `limit`, `offset`. |
| `GET` | `/evidence/by-company/{company_id}` | All evidence for a company. Query params: `target_type` (optional filter), `limit`, `offset`. |
| `GET` | `/evidence/by-agent-run/{agent_run_id}` | All evidence from an agent run. |
| `GET` | `/evidence/summary/{target_type}/{target_id}` | Aggregated evidence summary for a target. |
| `GET` | `/evidence/{evidence_id}` | Single evidence record detail. |
| `DELETE` | `/evidence/{evidence_id}` | Delete a single evidence record. Returns 204. |

**List response format** (matching existing pattern):
```json
{
    "items": [ ... ],
    "total": 42,
    "limit": 100,
    "offset": 0
}
```

**EvidenceSummary response schema:**

```json
{
    "target_type": "intelligence_score",
    "target_id": "550e8400-e29b-41d4-a716-446655440000",
    "total_evidence": 42,
    "by_evidence_type": {
        "computed_metric": 5,
        "signature_match": 12,
        "text_excerpt": 25
    },
    "by_relationship_type": {
        "contributes_to": 18,
        "supports": 24
    },
    "highest_confidence": 0.95,
    "lowest_confidence": 0.42
}
```

Following existing Pydantic v2 schema conventions, `EvidenceSummary` is defined as a read-only response schema:

```python
class EvidenceSummary(IrtiqaSchema):
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=36, max_length=36)
    total_evidence: int = Field(ge=0)
    by_evidence_type: dict[str, int]
    by_relationship_type: dict[str, int]
    highest_confidence: float = Field(ge=0.0, le=1.0)
    lowest_confidence: float = Field(ge=0.0, le=1.0)
```

**No POST/PATCH endpoints for evidence creation** — evidence records are created internally by agents and workflows, not through the API. The API is read-only by default with delete capability for data management.

### Evidence Schemas

Following existing Pydantic v2 schema conventions:

- `EvidenceRead` — full evidence record with all fields (used in detail response)
- `EvidenceList` — `items`, `total`, `limit`, `offset` wrapper
- `EvidenceSummary` — aggregated counts by `evidence_type` and `relationship_type`

No `EvidenceCreate` or `EvidenceUpdate` schemas for API consumption (evidence is created internally only).

### API Dependency Provider

Following existing pattern in `app/api/dependencies.py`:

```python
def get_evidence_service() -> EvidenceService:
    return EvidenceService()
```

## 9. Evidence Lifecycle

### Creation

1. **Agent execution**: Agent's `_run()` creates output entities via existing services, returns `AgentRunOutput` with `output_ids` and new `evidence` list.
2. **Agent framework**: `BaseAgent.execute()` calls `EvidenceService.record_evidence_batch()` after `_run()` succeeds.
3. **Workflow execution**: Workflow steps call `EvidenceService.record_evidence_batch()` for composite outputs (e.g., intelligence scores based on multiple inputs).
4. **Job execution**: Background jobs that run agents or workflows inherit the same evidence recording through the agent/workflow framework.

### Storage

- Evidence records are stored in the `evidence_records` table.
- SHA-256 hashes enable deduplication across runs.
- Evidence values are excerpts, not full documents. Full raw content remains in the source tables (`websites.raw_html`, etc.).

### Query

- Evidence is queried through the EvidenceRepository or EvidenceService.
- API endpoints expose targeted queries (by target, source, company, agent run).
- Evidence follows the target entity's lifecycle — if a target entity is deleted, evidence records remain (the target ID becomes an orphan reference, but the provenance trail is preserved).

### Cleanup

- No automatic TTL or archival. Evidence is append-only.
- Manual deletion via API for data management use cases.
- If a company is deleted, evidence records referencing that company can be queried by `company_id` but are not cascade-deleted. The evidence trail outlives the company.

### Relationship to Agent Runs

Every evidence record is linked to an `agent_run_id`. This provides the full audit trail:

```text
AgentRun
  └─ creates evidence_records
       ├─ links to output entities (technologies, intent_signals, etc.)
       └─ describes what was seen and how it was used
```

## 10. Query and Retrieval Strategy

### Common Query Patterns

**Q: "Why is this intelligence score 82.5?"**

```python
# Get the score
score = intelligence_score_service.get(score_id)

# Get all evidence supporting it
evidence = evidence_service.get_target_evidence(
    target_type="intelligence_score",
    target_id=score_id,
)
# Returns: [
#   {evidence_type: "computed_metric", source_detail: "technology HubSpot confidence=0.92", relationship: "contributes_to"},
#   {evidence_type: "computed_metric", source_detail: "intent_signal CRM detected strength=0.75", relationship: "contributes_to"},
#   ...
# ]
```

**Q: "Which outputs used this technology detection?"**

```python
evidence = evidence_service.get_source_targets(
    source_type="technology",
    source_id=technology_id,
)
# Returns all intelligence_scores, intent_signals, etc. that cited this technology
```

**Q: "Show all evidence collected for this company by agent type."**

```python
evidence = evidence_service.get_company_evidence(
    company_id=company_id,
    target_type="intelligence_score",  # optional filter
)
```

**Q: "What did this agent run produce and what did it use?"**

```python
evidence = evidence_service.get_agent_run_evidence(agent_run_id)
# All evidence records indexed by this specific agent run
```

### No Full-Text Search

Evidence values are stored as plain text excerpts. The existing `LIKE` queries on the `evidence_value` column satisfy the current need. Full-text search (FTS5 for SQLite, `tsvector` for PostgreSQL) can be added later if the evidence volume grows beyond basic filtering.

### No Retrospective Backfill

The evidence system applies to new records created after implementation. Existing records in `technologies`, `intent_signals`, `intelligence_scores`, and `outreach_messages` will not have associated evidence records. This is acceptable because:

- The evidence system is additive — new records get evidence, old records remain functional with their existing ad-hoc references.
- The existing `rationale`, `source_url`, and foreign key fields still provide basic provenance for old records.
- A backfill migration would require replaying agent execution, which is not feasible for deterministic outputs.

## 11. Testing Strategy

### Unit Tests

| Test | Scope | Description |
|---|---|---|
| `test_evidence_model` | Model | Column defaults, indexes, constraints, UUID generation, timestamps |
| `test_evidence_model_constants` | Model | Centralized constant sets match check constraint values |
| `test_evidence_constraints` | Model | Check constraints for `evidence_type`, `relationship_type`, `confidence` range |
| `test_evidence_repository_add` | Repository | Add single evidence record via model instance |
| `test_evidence_repository_add_all` | Repository | Batch add via model instances (consistent with BaseRepository) |
| `test_evidence_repository_query` | Repository | `list_by_target`, `list_by_source`, `list_by_agent_run`, `list_by_company` |
| `test_evidence_repository_query_pagination` | Repository | List methods respect limit/offset |
| `test_evidence_repository_query_empty` | Repository | Query returns empty list when no matches exist |
| `test_evidence_repository_delete` | Repository | Delete by ID, delete by target |
| `test_evidence_repository_count` | Repository | Count by target |
| `test_evidence_service_record` | Service | Single record creation with hash deduplication |
| `test_evidence_service_batch` | Service | Batch creation within single transaction |
| `test_evidence_service_batch_injection` | Service | `record_evidence_batch` injects `agent_run_id`, `company_id`, `contact_id` into every record |
| `test_evidence_service_query` | Service | All query methods return correct records |
| `test_evidence_service_validation` | Service | Invalid types, missing required fields, invalid confidence values |
| `test_evidence_service_hash_dedup` | Service | Duplicate evidence_value hash within target scope is rejected |
| `test_evidence_service_hash_cross_target` | Service | Same evidence_value for different targets is accepted (not deduplicated) |
| `test_evidence_schemas` | Schema | EvidenceRead serialization, EvidenceList pagination |
| `test_evidence_summary_schema` | Schema | EvidenceSummary response schema serialization |
| `test_agent_evidence_integration` | Agent | BaseAgent.execute() creates evidence records after _run() |
| `test_agent_execute_succeeds_when_evidence_fails` | Agent | Agent returns AGENT_STATUS_SUCCEEDED even when EvidenceService raises; evidence failure is logged as warning |
| `test_score_refresh_evidence` | Workflow | Score refresh workflow creates evidence linking scores to technologies and signals |

### Integration Tests

| Test | Description |
|---|---|
| `test_evidence_api_list_by_target` | GET /evidence/by-target/{target_type}/{target_id} returns correct records |
| `test_evidence_api_list_by_source` | GET /evidence/by-source/{source_type}/{source_id} returns correct records |
| `test_evidence_api_by_company` | GET /evidence/by-company/{company_id} returns company-scoped records |
| `test_evidence_api_by_agent_run` | GET /evidence/by-agent-run/{agent_run_id} returns run-scoped records |
| `test_evidence_api_summary` | GET /evidence/summary/{target_type}/{target_id} returns EvidenceSummary response |
| `test_evidence_api_detail` | GET /evidence/{evidence_id} returns single record |
| `test_evidence_api_delete` | DELETE /evidence/{evidence_id} returns 204 |
| `test_evidence_api_not_found` | GET /evidence/nonexistent-id returns 404 |
| `test_evidence_api_invalid_params` | Invalid target_type returns 422 |
| `test_evidence_api_list_pagination` | limit/offset params work for list endpoints |
| `test_evidence_api_empty_list` | GET /evidence/by-target/ with no matches returns empty items list |
| `test_evidence_postgresql` | PostgreSQL compatibility for evidence_records table |

### Expected Test Count

23 unit tests + 12 integration tests = 35 tests. CI is configured to run all tests on every push and pull request. PostgreSQL evidence tests run against the PostgreSQL 18 service container.

## 12. Risks

### Risk: Evidence Recording Is Not Atomic with Entity Creation

Evidence is recorded in a separate transaction from the output entity it describes. If evidence recording fails after the entity was successfully created, the entity exists without an evidence trail. Downstream consumers that query evidence for that entity will find zero results.

**Mitigation**: This is a documented trade-off, not a bug. Entities are fully functional without evidence — the evidence layer is additive. The agent execution still reports `AGENT_STATUS_SUCCEEDED` (with a warning log) even if evidence recording fails. A future unit-of-work abstraction spanning entity creation and evidence recording can make this atomic without schema changes.

### Risk: Evidence Volume Grows Faster Than Expected

Each agent execution creates multiple evidence records. If agents are run at scale against hundreds of companies, the `evidence_records` table could grow faster than other tables.

**Mitigation**: Evidence records are lightweight (single text excerpt + UUIDs + floats). At current project scale (local SQLite), even tens of thousands of evidence records are negligible. If volume becomes a concern, the `company_id` and `evidence_type` indexes support efficient query pruning. A future cleanup job via the Background Job Foundation can archive evidence older than a configurable threshold.

### Risk: Evidence Recording Degrades Agent Performance

Calling `EvidenceService.record_evidence_batch()` after every agent run adds latency, especially for agents that produce hundreds of evidence items.

**Mitigation**: Evidence recording happens in a single transaction via `session_scope()`, making it fast. If performance becomes a concern, evidence can be recorded asynchronously via the Background Job Foundation — the agent returns evidence data in its result, and a background job persists it. For the current project stage, synchronous recording is sufficient.

### Risk: Polymorphic Queries Are Inefficient

Filtering by `target_type` and `target_id` without declarative foreign keys means the database cannot use FK-based optimizations.

**Mitigation**: The composite index `ix_evidence_target` on `(target_type, target_id)` provides efficient lookups. SQLite and PostgreSQL both handle composite index scans efficiently for this query pattern.

### Risk: Breaking Changes to BaseAgent or ScoreRefresh

Modifying `BaseAgent._run()` return type and `execute()` method affects all five existing agents. The `score_refresh` workflow also needs modification.

**Mitigation**: The `AgentRunOutput` TypedDict adds `evidence` as a `NotRequired` field. Existing agent implementations that don't return evidence pass type checking without changes — `BaseAgent.execute()` calls `run_output.get("evidence", [])` and skips evidence recording when the list is empty. The `score_refresh` workflow is modified independently.

### Risk: Duplicate Evidence Across Runs

If an agent is re-run with the same inputs, it could produce duplicate evidence records.

**Mitigation**: SHA-256 hashing of `evidence_value` combined with the `ix_evidence_hash` index enables fast deduplication within the same target scope. Deduplication is performed at the service layer before insertion.

## 13. Deliverables

### Data Layer

- `app/models/evidence_record.py` — SQLAlchemy model
- `database/migrations/versions/20260611_0005_create_evidence_records.py` — Alembic migration
- `app/repositories/evidence_repository.py` — Repository class
- `tests/unit/test_evidence_model.py` — Model tests

### Service Layer

- `app/services/evidence_service.py` — Service class with evidence management
- `tests/unit/test_evidence_service.py` — Service layer tests

### Schema Layer

- `app/schemas/evidence.py` — Pydantic v2 schemas (Read, List, Summary)
- `tests/unit/test_evidence_schemas.py` — Schema validation tests

### API Layer

- `app/api/v1/endpoints/evidence.py` — Evidence read endpoints
- `app/api/dependencies.py` — Evidence service dependency
- `app/api/v1/router.py` — Evidence route registration
- `tests/integration/api/test_evidence_api.py` — API integration tests

### Agent Integration

- `app/agents/base.py` — Modify `AgentRunOutput` and `BaseAgent.execute()` to support evidence
- `tests/unit/agents/test_base_evidence.py` — Agent evidence integration tests

### Workflow Integration

- `app/workflows/score_refresh.py` — Add evidence creation to score_refresh
- `tests/integration/test_score_refresh_evidence.py` — Score refresh evidence tests

### Documentation

- `docs/evidence_records_system_design.md` — This document

### PostgreSQL Compatibility

- `tests/integration/test_evidence_postgresql.py` — Evidence-specific PostgreSQL verification

## 14. Success Criteria

The Evidence Records System is successful when:

1. The `evidence_records` migration applies cleanly to both SQLite and PostgreSQL.
2. Alembic `check` reports no schema drift after the migration.
3. All evidence model constraints (types, relationships, confidence range) are enforced.
4. Evidence records can be created, queried by target, source, company, and agent run.
5. `BaseAgent.execute()` creates evidence records after successful `_run()` without breaking existing agents.
6. The `score_refresh` workflow creates evidence records linking each score to its contributing technologies and signals.
7. All 284 existing SQLite tests continue to pass (no regressions).
8. All 24 existing PostgreSQL compatibility tests continue to pass.
9. New evidence-specific PostgreSQL tests pass against the PostgreSQL 18 service container in CI.
10. Evidence records are queryable through the API by target, source, company, and agent run.
11. Evidence deduplication prevents duplicate records with identical content for the same target.
12. No full-text search engine, vector database, or cloud storage is introduced.

---

## Files Expected to Be Created

- `app/models/evidence_record.py`
- `app/repositories/evidence_repository.py`
- `app/services/evidence_service.py`
- `app/schemas/evidence.py`
- `app/api/v1/endpoints/evidence.py`
- `database/migrations/versions/20260611_0005_create_evidence_records.py`
- `tests/unit/test_evidence_model.py`
- `tests/unit/test_evidence_service.py`
- `tests/unit/test_evidence_schemas.py`
- `tests/unit/agents/test_base_evidence.py`
- `tests/integration/api/test_evidence_api.py`
- `tests/integration/test_evidence_postgresql.py`
- `tests/integration/test_score_refresh_evidence.py`
- `docs/evidence_records_system_design.md`

## Files Expected to Be Modified

- `app/agents/base.py` (extend `AgentRunOutput` with `NotRequired` `evidence` field; update `execute()` to call `EvidenceService.record_evidence_batch()` after `_run()`; inject `company_id`/`contact_id` from `AgentContext`; wrap evidence recording in try/except with warning log)
- `app/schemas/evidence.py` (add `EvidenceItem` TypedDict shared between agent and service layers; add `EvidenceSummary` Pydantic schema; add `EvidenceRead`, `EvidenceList` schemas)
- `app/api/dependencies.py` (add `get_evidence_service` dependency)
- `app/api/v1/router.py` (register evidence endpoints)
- `app/workflows/score_refresh.py` (add evidence creation after scoring — evidence belongs inside the workflow step, not in WorkflowRunner)
- `docs/agents.md` (add evidence section)
- `docs/database.md` (add evidence_records schema documentation)
- `docs/project_state.md` (mark evidence system complete)
- `docs/project_handoff.md` (mark evidence system complete)

---

## Design Changes Applied

The following changes from `docs/evidence_records_system_audit.md` were applied to this design:

| Audit Finding | Severity | Change Applied |
|---|---|---|
| #8: `AgentRunOutput.evidence` is required, not optional | **Critical** | Changed to `NotRequired`. Existing agents that omit `evidence` pass type checking. |
| #1: Transaction boundary gap | **High** | Added "Transaction Boundary Design" subsection documenting the gap as an explicit trade-off. Added risk entry in Section 12. |
| #7: `EvidenceCreateParams` undefined | **High** | Replaced with `EvidenceItem` TypedDict shared across agent and service boundaries. `record_evidence_batch` now accepts `list[EvidenceItem]`. |
| #9: `EvidenceItem` missing `source_type` | **Medium** | Added `source_type` to `EvidenceItem` TypedDict. |
| #10: `company_id`/`contact_id` injection gap | **Medium** | Documented automatic injection by `BaseAgent.execute()` from `AgentContext`. Both fields removed from `EvidenceItem` — agents don't need to specify them. |
| #11: `agent_run_id` lacks declarative FK | **Medium** | Added `ForeignKey("agent_runs.id", ondelete="SET NULL")` to the `agent_run_id` column definition. |
| #12: `source_detail` is unstructured | **Medium** | Added `source_location_type` and `source_location_value` columns for structured source references. |
| #21: Summary endpoint response undefined | **Medium** | Defined `EvidenceSummary` Pydantic schema with full JSON response structure. |
| #22: Test count mismatch | **Medium** | Expanded test tables to 23 unit + 12 integration (35 total). Each test has a named entry. |
| #23: Agent evidence failure not tested | **Medium** | Added `test_agent_execute_succeeds_when_evidence_fails` test with mock EvidenceService. |
| #25: Type strings not centralized | **Medium** | Added full constants section with `EVIDENCE_TYPE_*`, `RELATIONSHIP_*`, `SOURCE_TYPE_*`, `TARGET_TYPE_*` sets. Check constraints reference these constant sets. |
| #4: `create_many` uses `list[dict]` | **Medium** | Changed to `add_all(session, entities: list[EvidenceRecord])` accepting model instances, consistent with `BaseRepository.add()`. |
| #6: `EvidenceService` doesn't extend `BaseService` | **Low** | Changed to `EvidenceService(BaseService[EvidenceRecord, EvidenceRepository])`. |
| #19: API paths mix params | **Low** | Changed to path params: `/evidence/by-target/{target_type}/{target_id}`, `/evidence/by-source/{source_type}/{source_id}`, `/evidence/summary/{target_type}/{target_id}`. |

## Remaining Known Limitations

1. **No atomicity between entity creation and evidence recording.** Evidence is created in a separate transaction. This is a documented trade-off. See "Transaction Boundary Design" in Section 4 and the risk entry in Section 12.

2. **No retrospective backfill.** Existing records in `technologies`, `intent_signals`, `intelligence_scores`, and `outreach_messages` will not have associated evidence records. New records created after implementation will have evidence trails.

3. **Evidence deduplication is per-target.** If the same evidence content supports multiple targets (e.g., two intelligence scores both reference the same technology detection), the evidence content is stored N times. SHA-256 deduplication prevents this only within a single target scope.

4. **Evidence type and relationship type values are frozen in check constraints.** Adding new values requires a migration with table recreation on SQLite. This is acceptable for the current project stage — the initial set of types covers all five agent types.

5. **No full-text search.** Evidence values are stored as plain text excerpts with `LIKE`-only query support. Full-text search (FTS5 for SQLite, `tsvector` for PostgreSQL) can be added later if evidence volume grows beyond basic filtering.
