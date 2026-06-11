# Evidence Records System: Implementation Tasks

## Phase 1: Database Migration

### Objective

Create the Alembic migration that adds the `evidence_records` table to the database schema. The migration must apply cleanly to both SQLite and PostgreSQL with all columns, indexes, and check constraints defined in the design.

### Files Affected

| File | Action |
|---|---|
| `database/migrations/versions/20260611_0004_create_evidence_records.py` | Create |

### Tasks

1.1. Determine the current Alembic head revision and chain position. Verify the next migration number does not conflict with existing revisions.

1.2. Create the migration file with the following structure:

- **Table**: `evidence_records`
- **Columns**: `id` (UUID PK), `source_type`, `source_id`, `source_detail`, `source_location_type`, `source_location_value`, `evidence_type`, `evidence_value`, `evidence_hash`, `relationship_type`, `target_type`, `target_id`, `confidence`, `agent_run_id` (declarative FK to `agent_runs.id` with `ondelete="SET NULL"`), `company_id`, `contact_id`, `created_at`.
- **Column types**: All use SQLAlchemy portable types (`String`, `Text`, `Float`, `DateTime`) per the design.
- **Check constraints**: `evidence_type IN (...)`, `relationship_type IN (...)`, `confidence >= 0.0 AND confidence <= 1.0`. Use the exact string values from the design's Centralized Constants section.
- **Indexes**: 11 indexes matching the design: `ix_evidence_target`, `ix_evidence_source`, `ix_evidence_type`, `ix_evidence_relationship`, `ix_evidence_agent_run`, `ix_evidence_company`, `ix_evidence_contact`, `ix_evidence_hash`, `ix_evidence_target_type`, `ix_evidence_created_at`, `ix_evidence_source_location`.
- **Downgrade**: Drop the `evidence_records` table.

1.3. Use `op.f()` wrapper on constraint names to ensure PostgreSQL compatibility (same pattern as existing migration `20260609_0003_add_jobs_table.py`).

1.4. Verify the migration uses `recreate="auto"` (not `recreate="always"`) for any batch operations, matching the fix applied in `20260531_0002`.

### Verification Steps

- Run `python -m alembic upgrade head` and confirm zero errors.
- Run `python -m alembic check` and confirm "No new upgrade operations detected."
- Run `python -m alembic downgrade -1` and confirm the table is removed.
- Run `python -m alembic upgrade head` again and confirm the table is recreated.
- Run `python -m alembic check` again and confirm no drift.

### Success Criteria

- [ ] Migration applies cleanly to SQLite
- [ ] Migration downgrade removes the table
- [ ] Migration re-applies cleanly (round-trip)
- [ ] All 11 indexes exist after migration
- [ ] All 3 check constraints are enforced
- [ ] Alembic `check` reports zero drift after upgrade
- [ ] Existing tests (`python -m pytest`) still pass with 284 SQLite + 24 skipped PostgreSQL

### Risks

- **Constraint naming on PostgreSQL**: Constraint names must use `op.f()` wrapper. Without it, PostgreSQL auto-generates different constraint names than SQLite, causing migration inconsistencies.
- **SQLite ALTER TABLE limitations**: Since this is a new table (not an ALTER TABLE), SQLite's limited ALTER TABLE support is not triggered. No risk.

---

## Phase 2: SQLAlchemy Model

### Objective

Create the `EvidenceRecord` SQLAlchemy model and the centralized constants module. The model must match the migration table definition exactly and follow existing model patterns (`UUIDPrimaryKeyMixin`, `TimestampMixin`, `Base`).

### Files Affected

| File | Action |
|---|---|
| `app/models/evidence_record.py` | Create |
| `app/models/__init__.py` | Modify (export `EvidenceRecord`) |

### Tasks

2.1. Create `app/models/evidence_record.py` with:

- **Imports**: `Base`, `UUIDPrimaryKeyMixin`, `TimestampMixin` from `app.models.base`. Import `ForeignKey`, `Index`, `CheckConstraint`, etc. from SQLAlchemy.
- **Centralized constants**: All discriminator value constants as defined in the design:
  - `EVIDENCE_TYPE_*` (6 values) + `VALID_EVIDENCE_TYPES`
  - `RELATIONSHIP_*` (4 values) + `VALID_RELATIONSHIP_TYPES`
  - `SOURCE_TYPE_*` (3 values) + `VALID_SOURCE_TYPES`
  - `TARGET_TYPE_*` (4 values) + `VALID_TARGET_TYPES`
  - `EVIDENCE_VALUE_MAX_LENGTH = 5000`
- **`EvidenceRecord` class**: Extends `UUIDPrimaryKeyMixin`, `TimestampMixin`, `Base`. Table name: `evidence_records`.
- **Columns**: All columns from the migration, using `Mapped[...]` and `mapped_column` with the same types and constraints.
- **Foreign keys**: `agent_run_id` uses `ForeignKey("agent_runs.id", ondelete="SET NULL")`. `source_id` and `target_id` omit declarative FK (polymorphic). `company_id` and `contact_id` omit declarative FK (denormalized).
- **Relationships**: Add `relationship()` back-references for related entities where appropriate (e.g., `agent_run`, `company`, `contact`). Use `TYPE_CHECKING` imports for forward references.
- **`__table_args__`**: All 3 check constraints referencing the constant sets, plus all 11 indexes.

2.2. Update `app/models/__init__.py` to import and export `EvidenceRecord`.

2.3. Verify that `VALID_EVIDENCE_TYPES`, `VALID_RELATIONSHIP_TYPES`, etc. are `frozenset` instances (immutable, hashable).

### Verification Steps

- Run `python -m compileall app` and confirm zero syntax errors.
- Run `python -m pytest tests/unit/test_models.py` and confirm existing model tests still pass.
- Confirm the model can be imported: `python -c "from app.models import EvidenceRecord; print(EvidenceRecord.__tablename__)"`.
- Verify that all constants are accessible: `python -c "from app.models.evidence_record import EVIDENCE_TYPE_HTML_SNIPPET, VALID_EVIDENCE_TYPES, EVIDENCE_VALUE_MAX_LENGTH"`.

### Success Criteria

- [ ] `EvidenceRecord` model compiles without errors
- [ ] All centralized constants are defined as module-level names
- [ ] `VALID_*` sets are `frozenset` instances
- [ ] Check constraint values in the model match the migration exactly
- [ ] Column types match the migration exactly
- [ ] Existing model imports continue to work

### Risks

- **Constant name conflicts**: Prefix all constants with `EVIDENCE_*` to avoid collision with existing project constants.
- **Circular imports**: `EvidenceRecord` has relationships to `AgentRun`, `Company`, `Contact`. Use `TYPE_CHECKING` guard and string-based `relationship()` backrefs to match existing patterns.

---

## Phase 3: Repository

### Objective

Create `EvidenceRepository` following the existing `BaseRepository` pattern. The repository provides evidence-specific query methods while inheriting generic CRUD from `BaseRepository`.

### Files Affected

| File | Action |
|---|---|
| `app/repositories/evidence_repository.py` | Create |

### Tasks

3.1. Create `app/repositories/evidence_repository.py` with:

- **Class**: `EvidenceRepository(BaseRepository[EvidenceRecord])`.
- **`add`**: Calls `self.session.add(entity)`, returns entity. (Inherited from `BaseRepository` — override only if custom behavior is needed.)
- **`add_all`**: Calls `self.session.add_all(entities)`, returns entities list. New method not on `BaseRepository`.
- **`list_by_target`**: Query filtered by `target_type` AND `target_id`, ordered by `evidence_type` then `created_at`.
- **`list_by_source`**: Query filtered by `source_type` AND `source_id`, ordered by `created_at`.
- **`list_by_agent_run`**: Query filtered by `agent_run_id`.
- **`list_by_company`**: Query filtered by `company_id` with optional `target_type` filter.
- **`list_by_entity_type`**: Paginated query filtered by `target_type`.
- **`count_by_target`**: Count query filtered by `target_type` AND `target_id`.
- **`delete_by_target`**: Bulk delete filtered by `target_type` AND `target_id`. Returns row count.
- **`delete`**: Inherited from `BaseRepository.delete()`.

3.2. Use `select()` and `func.count()` from SQLAlchemy for all queries, matching the existing repository pattern.

3.3. Use `self.logger` for debug logging on all query methods, matching existing repository convention.

3.4. Do NOT import or reference any service, API, workflow, or agent modules.

### Verification Steps

- Run `python -m compileall app` and confirm zero errors.
- Verify the class follows the exact same pattern as `CompanyRepository` or `TechnologyRepository`.

### Success Criteria

- [ ] `EvidenceRepository` extends `BaseRepository[EvidenceRecord]`
- [ ] All 10 custom query methods are implemented
- [ ] Methods accept `Session` via constructor (not per-method)
- [ ] Repository does not commit transactions
- [ ] Repository does not import any layer above it

### Risks

- **Polymorphic query performance**: The `list_by_target` and `list_by_source` methods filter on string-type discriminator columns. The composite indexes `ix_evidence_target` and `ix_evidence_source` cover these queries.
- **Ordering consistency**: `list_by_target` orders by `evidence_type` then `created_at`. This ordering must be stable for pagination.

---

## Phase 4: Service

### Objective

Create `EvidenceService` extending `BaseService[EvidenceRecord, EvidenceRepository]`. The service implements evidence recording (single and batch), query methods, hash deduplication, and validation.

### Files Affected

| File | Action |
|---|---|
| `app/services/evidence_service.py` | Create |
| `app/repositories/__init__.py` | Modify (export `EvidenceRepository`) |
| `app/services/__init__.py` | Modify (export `EvidenceService`) |

### Tasks

4.1. Create `app/services/evidence_service.py` with:

- **Class**: `EvidenceService(BaseService[EvidenceRecord, EvidenceRepository])`.
- **`record_evidence`**: Accepts individual field parameters, constructs `EvidenceRecord`, validates discriminator values against the centralized constant sets before persisting, computes SHA-256 hash of `evidence_value`, calls `repository.add()`.
- **`record_evidence_batch`**: Accepts `list[EvidenceItem]` (TypedDict), `agent_run_id`, `company_id`, `contact_id`. Injects the three IDs into each item. Computes SHA-256 hashes. Calls `repository.add_all()` within a single transaction via `_run_in_transaction()`. Skips duplicates (same `evidence_hash` + same `target_type`/`target_id`).
- **`get_target_evidence`**: Delegates to `repository.list_by_target()`.
- **`get_source_targets`**: Delegates to `repository.list_by_source()`.
- **`get_company_evidence`**: Delegates to `repository.list_by_company()`.
- **`get_agent_run_evidence`**: Delegates to `repository.list_by_agent_run()`.
- **`get_evidence_summary`**: Queries all evidence for a target, aggregates counts by `evidence_type` and `relationship_type`, computes highest and lowest confidence. Returns `EvidenceSummary`.
- **`delete_target_evidence`**: Delegates to `repository.delete_by_target()`.

4.2. SHA-256 hashing implementation:

```python
import hashlib

def _compute_evidence_hash(self, value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
```

4.3. Validation logic in `record_evidence` and `record_evidence_batch`:

- Check `source_type` in `VALID_SOURCE_TYPES` — raise `ValidationError` if not.
- Check `evidence_type` in `VALID_EVIDENCE_TYPES` — raise `ValidationError` if not.
- Check `relationship_type` in `VALID_RELATIONSHIP_TYPES` — raise `ValidationError` if not.
- Check `target_type` in `VALID_TARGET_TYPES` — raise `ValidationError` if not.
- Check `confidence` is between 0.0 and 1.0 — raise `ValidationError` if not.
- Check `evidence_value` length ≤ `EVIDENCE_VALUE_MAX_LENGTH` — truncate or raise `ValidationError`.

4.4. Use `irtiqa.services` logger namespace (inherited from `BaseService`).

4.5. Use structured errors from `app/core/errors.py` (`EntityNotFoundError`, `ValidationError`, `ServiceError`).

### Verification Steps

- Run `python -m compileall app` and confirm zero errors.
- Verify the class can be instantiated: `python -c "from app.services import EvidenceService; s = EvidenceService(); print(type(s).__name__)"`.

### Success Criteria

- [ ] `EvidenceService` extends `BaseService[EvidenceRecord, EvidenceRepository]`
- [ ] All 8 service methods are implemented
- [ ] Discriminator values are validated against centralized constant sets
- [ ] SHA-256 hashing is applied correctly
- [ ] Deduplication prevents duplicate hashes within the same target scope
- [ ] `record_evidence_batch` injects `agent_run_id`, `company_id`, `contact_id` into every record
- [ ] All service operations use `_run_in_transaction()`

### Risks

- **SHA-256 consistency**: Evidence hash must be computed from the same normalized input every time. Use `.encode("utf-8")` consistently. Do not apply whitespace stripping or case normalization unless intentional.
- **Deduplication scope**: The dedup check queries by `evidence_hash` + `target_type` + `target_id`. This is correct per the design, but the risk is documented: same evidence content supporting multiple targets will be stored N times.

---

## Phase 5: Schemas and Shared Types

### Objective

Create Pydantic v2 schemas for the evidence API layer and the `EvidenceItem` TypedDict shared between agents and the service. All schemas follow existing conventions (`IrtiqaSchema`, `TimestampedReadSchema`, `ListSchema`).

### Files Affected

| File | Action |
|---|---|
| `app/schemas/evidence.py` | Create |

### Tasks

5.1. Create `app/schemas/evidence.py` with:

**`EvidenceItem` (TypedDict):**
```python
from typing import NotRequired, TypedDict

class EvidenceItem(TypedDict):
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

**`EvidenceRead` (Pydantic):**
- Extends `IrtiqaSchema` with `from_attributes=True`.
- All columns from `EvidenceRecord` as string, float, datetime, or optional fields.
- UUID fields validated as `min_length=36, max_length=36`.
- Confidence validated as `Field(ge=0.0, le=1.0)`.

**`EvidenceList` (Pydantic):**
- Extends `ListSchema`.
- `items: list[EvidenceRead]`.

**`EvidenceSummary` (Pydantic):**
- Extends `IrtiqaSchema`.
- Fields: `target_type`, `target_id`, `total_evidence`, `by_evidence_type: dict[str, int]`, `by_relationship_type: dict[str, int]`, `highest_confidence`, `lowest_confidence`.

5.2. Import `EvidenceItem` in service and agent files from `app.schemas.evidence`.

### Verification Steps

- Run `python -m compileall app` and confirm zero errors.
- Run `python -m pytest` and confirm existing tests pass.
- Verify schema imports: `python -c "from app.schemas.evidence import EvidenceRead, EvidenceList, EvidenceSummary, EvidenceItem"`.

### Success Criteria

- [ ] `EvidenceItem` TypedDict is defined with `NotRequired` for optional fields
- [ ] `EvidenceRead` includes all evidence_records columns
- [ ] `EvidenceList` wraps `items`, `total`, `limit`, `offset`
- [ ] `EvidenceSummary` has all 6 fields matching the design
- [ ] All schemas are importable without errors

### Risks

- **TypedDict vs Pydantic**: `EvidenceItem` is a TypedDict (not a Pydantic model) because it's constructed by agents and passed to services without needing Pydantic validation at the boundary. This is intentional.
- **`NotRequired` import**: Use `from typing import NotRequired` (Python 3.11+). If the project targets Python 3.11+, this is standard library. Verify `requires-python` in `pyproject.toml` (`>=3.11` — already set).

---

## Phase 6: API Endpoints

### Objective

Create evidence read-only API endpoints and register them in the router. Add the `get_evidence_service` dependency provider. All endpoints follow existing CRUD API conventions.

### Files Affected

| File | Action |
|---|---|
| `app/api/v1/endpoints/evidence.py` | Create |
| `app/api/dependencies.py` | Modify (add dependency) |
| `app/api/v1/router.py` | Modify (register routes) |

### Tasks

6.1. Create `app/api/v1/endpoints/evidence.py` with the following endpoints:

| Method | Path | Handler | Description |
|---|---|---|---|
| `GET` | `/evidence/by-target/{target_type}/{target_id}` | `list_evidence_by_target` | Query params: `limit` (default 100), `offset` (default 0). Returns `EvidenceList`. |
| `GET` | `/evidence/by-source/{source_type}/{source_id}` | `list_evidence_by_source` | Query params: `limit`, `offset`. Returns `EvidenceList`. |
| `GET` | `/evidence/by-company/{company_id}` | `list_evidence_by_company` | Query params: `target_type` (optional), `limit`, `offset`. Returns `EvidenceList`. |
| `GET` | `/evidence/by-agent-run/{agent_run_id}` | `list_evidence_by_agent_run` | Returns `EvidenceList`. |
| `GET` | `/evidence/summary/{target_type}/{target_id}` | `get_evidence_summary` | Returns `EvidenceSummary`. |
| `GET` | `/evidence/{evidence_id}` | `get_evidence` | Returns single `EvidenceRead`. Raises 404 if not found. |
| `DELETE` | `/evidence/{evidence_id}` | `delete_evidence` | Returns 204. Raises 404 if not found. |

6.2. Follow existing endpoint patterns:

- Use `Depends(get_evidence_service)` for service injection.
- Use Pydantic schemas as response models (`response_model=EvidenceList`, `response_model=EvidenceRead`, `response_model=EvidenceSummary`).
- Use `status.HTTP_204_NO_CONTENT` for delete.
- Use existing `IrtiqaSchema` validation for path and query parameters.
- Include `_validate_identifier`, `_validate_limit`, `_validate_offset` patterns from existing CRUD endpoints.

6.3. Add `get_evidence_service` dependency in `app/api/dependencies.py`:

```python
def get_evidence_service() -> EvidenceService:
    return EvidenceService()
```

6.4. Register the evidence router in `app/api/v1/router.py`. Use the existing pattern:
```python
from app.api.v1.endpoints.evidence import router as evidence_router
router.include_router(evidence_router, prefix="/evidence", tags=["evidence"])
```

### Verification Steps

- Run `python -m compileall app` and confirm zero errors.
- Confirm the router imports without errors: `python -c "from app.api.v1.endpoints.evidence import router"`.

### Success Criteria

- [ ] All 7 endpoints are implemented with correct paths and methods
- [ ] Evidence service dependency is registered
- [ ] Evidence router is mounted at `/evidence`
- [ ] List endpoints return paginated `EvidenceList` responses
- [ ] Summary endpoint returns `EvidenceSummary`
- [ ] Delete endpoint returns 204
- [ ] Non-existent evidence returns 404
- [ ] Invalid target_type returns 422
- [ ] No POST/PATCH endpoints exist (evidence is internal-only)

### Risks

- **Path parameter validation**: `target_type` and `source_type` are path parameters. They should be validated against the centralized constant sets at the API layer to return 422 early.
- **Evidence not found**: Use `service.get()` and raise `EntityNotFoundError` with proper HTTP 404 handling through the existing exception handler.

---

## Phase 7: Agent Integration

### Objective

Modify `BaseAgent` to support evidence recording after agent execution. Extend `AgentRunOutput` with an optional `evidence` field. All five existing agents continue to work without modification.

### Files Affected

| File | Action |
|---|---|
| `app/agents/base.py` | Modify (extend `AgentRunOutput`, update `execute()`) |

### Tasks

7.1. Modify `AgentRunOutput` in `app/agents/base.py`:

Add `NotRequired` import at the top of the file:
```python
from typing import NotRequired  # Python 3.11+
```

Add optional `evidence` field to `AgentRunOutput`:
```python
class AgentRunOutput(TypedDict):
    output_ids: dict[str, list[str]]
    evidence: NotRequired[list[EvidenceItem]]
    summary: str
    stats: dict[str, Any]
```

7.2. Modify `BaseAgent.execute()` after `_run()` succeeds:

```python
run_output = await self._run(context)
duration_ms = (time.perf_counter() - start_time) * 1000.0

# ── Evidence recording (non-blocking) ──────────────
evidence_list = run_output.get("evidence", [])
if evidence_list:
    try:
        evidence_service = EvidenceService()
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

7.3. Include `evidence_count` in agent execution stats when evidence is recorded.

7.4. Do NOT modify the `_run()` abstract method signature or any concrete agent implementation. Agents that do not return `evidence` in their `AgentRunOutput` continue to work — `run_output.get("evidence", [])` returns an empty list and evidence recording is skipped.

### Verification Steps

- Run `python -m compileall app` and confirm zero errors.
- Run `python -m mypy app/agents/base.py` and confirm zero type errors (ensure `NotRequired` is recognized).
- Verify that existing agents still construct `AgentRunOutput` without the `evidence` key.

### Success Criteria

- [ ] `AgentRunOutput` has `evidence` as `NotRequired`
- [ ] `BaseAgent.execute()` calls `EvidenceService.record_evidence_batch()` after `_run()` succeeds
- [ ] Evidence recording failure is caught and logged as a warning (not propagated)
- [ ] Evidence count is included in agent stats
- [ ] All 5 existing agents compile without changes to their `_run()` implementations
- [ ] mypy strict mode passes on `app/agents/base.py`

### Risks

- **EvidenceService import in base.py**: Adding `EvidenceService` import to `base.py` creates a new dependency at the agent foundation layer. Use a lazy import inside the `execute()` method (or import at module level) — lazy import avoids circular dependencies if `EvidenceService` transitively imports anything from `app.agents`.
- **EvidenceItem import**: Import `EvidenceItem` from `app.schemas.evidence` (not from the model module) to keep the agent layer decoupled from the database model.

---

## Phase 8: Workflow Integration (score_refresh)

### Objective

Modify the `score_refresh` workflow to create evidence records linking each `IntelligenceScore` to its contributing `Technology` and `IntentSignal` records. Evidence creation happens inside the workflow step, before returning `WorkflowResult`.

### Files Affected

| File | Action |
|---|---|
| `app/workflows/score_refresh.py` | Modify (add evidence creation) |

### Tasks

8.1. Import `EvidenceService` and `EvidenceItem` in `score_refresh.py`.

8.2. After creating each `IntelligenceScore` via `IntelligenceScoreService.create()`, construct a list of `EvidenceItem` records:

For each technology that contributed to `technographic_score`:
```python
EvidenceItem(
    source_type=SOURCE_TYPE_AGENT_RUN,
    source_detail=f"Technology: {tech.name} (category={tech.category}, confidence={tech.confidence})",
    evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
    evidence_value=f"technology={tech.id}, name={tech.name}, confidence={tech.confidence}",
    relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
    target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
    target_id=score_id,
    confidence=tech.confidence,
)
```

For each intent signal that contributed to `intent_score`:
```python
EvidenceItem(
    source_type=SOURCE_TYPE_AGENT_RUN,
    source_detail=f"Intent signal: {signal.signal_name} (type={signal.signal_type}, strength={signal.strength})",
    evidence_type=EVIDENCE_TYPE_COMPUTED_METRIC,
    evidence_value=f"intent_signal={signal.id}, name={signal.signal_name}, strength={signal.strength}",
    relationship_type=RELATIONSHIP_CONTRIBUTES_TO,
    target_type=TARGET_TYPE_INTELLIGENCE_SCORE,
    target_id=score_id,
    confidence=signal.confidence,
)
```

8.3. Call `EvidenceService.record_evidence_batch()` after all scores are created and before the workflow returns `WorkflowResult`. Use the workflow's `agent_run_id` and the company/contact context from the workflow input.

8.4. Include evidence count in the workflow step's output summary.

### Verification Steps

- Run `python -m compileall app` and confirm zero errors.
- Run `python -m pytest tests/unit/workflows/test_score_refresh.py` and confirm existing tests pass.
- Run `python -m pytest tests/integration/test_score_refresh_workflow.py` and confirm existing integration tests pass.

### Success Criteria

- [ ] `score_refresh` creates evidence records for each score-technology link
- [ ] `score_refresh` creates evidence records for each score-signal link
- [ ] Evidence creation happens inside the workflow step (before `WorkflowResult` is returned)
- [ ] Evidence count is reflected in workflow output
- [ ] Existing score refresh tests pass without modification

### Risks

- **Evidence is per-score, not per-run**: If a single workflow run creates multiple scores, evidence must be created for each score individually. The `record_evidence_batch` call should include all evidence items for all scores in a single batch call.
- **Nonexistent service dependencies**: The `score_refresh` workflow already receives services. Add `EvidenceService` alongside existing services.

---

## Phase 9: Tests

### Objective

Create all unit and integration tests for the evidence records system. Follow existing test patterns in `tests/unit/` and `tests/integration/`. All tests must pass against SQLite; PostgreSQL-specific tests run against the CI service container.

### Files Affected

| File | Action |
|---|---|
| `tests/unit/test_evidence_model.py` | Create |
| `tests/unit/test_evidence_service.py` | Create |
| `tests/unit/test_evidence_schemas.py` | Create |
| `tests/unit/agents/test_base_evidence.py` | Create |
| `tests/integration/api/test_evidence_api.py` | Create |
| `tests/integration/test_evidence_postgresql.py` | Create |
| `tests/integration/test_score_refresh_evidence.py` | Create |

### Tasks

9.1. Create `tests/unit/test_evidence_model.py`:

| Test | Description |
|---|---|
| `test_evidence_model` | Verify column defaults, indexes, UUID generation, timestamps |
| `test_evidence_model_constants` | Verify centralized constant sets match check constraint values |
| `test_evidence_constraints` | Verify check constraints reject invalid `evidence_type`, `relationship_type`, `confidence` range |
| `test_evidence_repository_add` | Create single evidence record via `add()` with model instance |
| `test_evidence_repository_add_all` | Batch create via `add_all()` with model instances |
| `test_evidence_repository_query` | Verify `list_by_target`, `list_by_source`, `list_by_agent_run`, `list_by_company` |
| `test_evidence_repository_query_pagination` | Verify list methods respect limit/offset |
| `test_evidence_repository_query_empty` | Verify query returns empty list when no matches exist |
| `test_evidence_repository_delete` | Delete by ID, delete by target |
| `test_evidence_repository_count` | Count by target |

9.2. Create `tests/unit/test_evidence_service.py`:

| Test | Description |
|---|---|
| `test_evidence_service_record` | Single record creation with SHA-256 hash |
| `test_evidence_service_batch` | Batch creation within single transaction |
| `test_evidence_service_batch_injection` | `record_evidence_batch` injects `agent_run_id`, `company_id`, `contact_id` |
| `test_evidence_service_query` | All query methods return correct records |
| `test_evidence_service_validation` | Invalid types, missing required fields, invalid confidence raise `ValidationError` |
| `test_evidence_service_hash_dedup` | Duplicate `evidence_value` hash within target scope is rejected |
| `test_evidence_service_hash_cross_target` | Same evidence for different targets is accepted |

9.3. Create `tests/unit/test_evidence_schemas.py`:

| Test | Description |
|---|---|
| `test_evidence_schemas` | `EvidenceRead` serialization, `EvidenceList` pagination |
| `test_evidence_summary_schema` | `EvidenceSummary` response schema serialization and validation |

9.4. Create `tests/unit/agents/test_base_evidence.py`:

| Test | Description |
|---|---|
| `test_agent_evidence_integration` | `BaseAgent.execute()` creates evidence records after `_run()` with mock `EvidenceService` |
| `test_agent_execute_succeeds_when_evidence_fails` | Agent returns `AGENT_STATUS_SUCCEEDED` even when `EvidenceService` raises; evidence failure logged as warning |

9.5. Create `tests/integration/api/test_evidence_api.py`:

| Test | Description |
|---|---|
| `test_evidence_api_list_by_target` | `GET /evidence/by-target/{target_type}/{target_id}` returns correct records |
| `test_evidence_api_list_by_source` | `GET /evidence/by-source/{source_type}/{source_id}` returns correct records |
| `test_evidence_api_by_company` | `GET /evidence/by-company/{company_id}` returns company-scoped records |
| `test_evidence_api_by_agent_run` | `GET /evidence/by-agent-run/{agent_run_id}` returns run-scoped records |
| `test_evidence_api_summary` | `GET /evidence/summary/{target_type}/{target_id}` returns `EvidenceSummary` |
| `test_evidence_api_detail` | `GET /evidence/{evidence_id}` returns single record |
| `test_evidence_api_delete` | `DELETE /evidence/{evidence_id}` returns 204 |
| `test_evidence_api_not_found` | `GET /evidence/nonexistent-id` returns 404 |
| `test_evidence_api_invalid_params` | Invalid `target_type` returns 422 |
| `test_evidence_api_list_pagination` | `limit`/`offset` params work for list endpoints |
| `test_evidence_api_empty_list` | `GET /evidence/by-target/` with no matches returns empty items list |

9.6. Create `tests/integration/test_evidence_postgresql.py`:

| Test | Description |
|---|---|
| `test_evidence_postgresql_migration` | Evidence_records migration applies cleanly to PostgreSQL |
| `test_evidence_postgresql_crud` | Evidence CRUD operations work against PostgreSQL |
| `test_evidence_postgresql_constraints` | Check constraints are enforced on PostgreSQL |

Use the existing `postgresql_required` marker from `tests/conftest.py` to skip these tests when no PostgreSQL service is available.

9.7. Create `tests/integration/test_score_refresh_evidence.py`:

| Test | Description |
|---|---|
| `test_score_refresh_evidence` | Score refresh workflow creates evidence records linking scores to technologies and signals |

### Verification Steps

- Run `python -m pytest tests/unit/` and confirm all unit tests pass.
- Run `python -m pytest tests/integration/` and confirm all integration tests pass (PostgreSQL tests skipped without PG service).
- Run `python -m pytest` and confirm 284 + 24 (with PG) or 284 + 24 skipped (without PG) — the count should be 284 + 24 skipped if PostgreSQL is not available.

### Success Criteria

- [ ] 23 unit tests pass against SQLite
- [ ] 12 integration tests pass against SQLite (PostgreSQL tests skip when no PG)
- [ ] `test_agent_execute_succeeds_when_evidence_fails` verifies warning-log-on-failure behavior
- [ ] `test_evidence_service_hash_dedup` verifies SHA-256 deduplication
- [ ] `test_evidence_service_hash_cross_target` verifies cross-target acceptance
- [ ] All existing 284 SQLite tests + 24 PostgreSQL tests continue to pass

### Risks

- **Test isolation**: All tests must use temporary SQLite databases (existing `conftest.py` pattern). Do not write to `database/irtiqa.db`.
- **PostgreSQL test marker**: Import `postgresql_required` from `tests.conftest.py`. PostgreSQL tests will skip automatically when `DATABASE_URL` is not set to a PostgreSQL URL.
- **Evidence fixture data**: Create evidence records through the service layer in test setup, not through direct SQLAlchemy `add()` calls, to test the service code path.

---

## Phase 10: Documentation

### Objective

Update project documentation to reflect the evidence records system. Mark the system as implemented in project state and handoff documents.

### Files Affected

| File | Action |
|---|---|
| `docs/agents.md` | Modify (add evidence section) |
| `docs/database.md` | Modify (add evidence_records schema) |
| `docs/project_state.md` | Modify (mark complete, update Open Issues) |
| `docs/project_handoff.md` | Modify (mark complete, update roadmap, update "No evidence table" gap) |

### Tasks

10.1. Update `docs/agents.md`:

- Add a section documenting that `BaseAgent.execute()` now records evidence after agent execution.
- Document the `EvidenceItem` TypedDict and how agents can return evidence from `_run()`.
- Document that evidence recording is non-blocking (failure does not fail the agent).

10.2. Update `docs/database.md`:

- Add the `evidence_records` table to the schema documentation.
- Document all columns, indexes, and check constraints.
- Document the polymorphic FK design and its rationale.
- Document the denormalized `company_id`/`contact_id` columns.

10.3. Update `docs/project_state.md`:

- Add evidence records system to the list of completed components.
- In the Open Issues section, change "No dedicated `evidence_records` table exists" to "Evidence records system implemented."
- In Repository Health Summary, add "Evidence records system."

10.4. Update `docs/project_handoff.md`:

- In Section 2 (Database Schema), add `evidence_records` to the list of tables.
- In Section 11 (Open Issues), change "No dedicated `source_observations` or evidence table exists" to "Evidence records system implemented for all new intelligence outputs."
- In the Architecture section, add evidence records as an implemented layer.
- Update the "Decision: No Evidence Table Yet" section (8) to reflect that the evidence table now exists.

### Verification Steps

- Verify each document renders correctly (no broken markdown).
- Verify links to the evidence design document work.

### Success Criteria

- [ ] `docs/agents.md` documents evidence recording in agent lifecycle
- [ ] `docs/database.md` includes evidence_records schema
- [ ] `docs/project_state.md` marks evidence system as complete
- [ ] `docs/project_handoff.md` marks evidence system as complete and removes "No evidence table" from open issues
- [ ] `docs/evidence_records_system_design.md` is not modified (reference document)

### Risks

- **Documentation drift**: If schema changes during implementation, update documentation immediately rather than at the end.

---

## Phase 11: Final Verification

### Objective

Run the complete test suite and verify that all 284 existing tests plus all new evidence tests pass. Verify PostgreSQL compatibility. Verify no regressions in agent or workflow behavior.

### Files Affected

None — verification only.

### Tasks

11.1. Run the full test suite:
```text
python -m pytest
```
Expected result: All tests pass. The exact count is 284 existing SQLite tests + 23 evidence unit tests + 12 evidence integration tests + 24 PostgreSQL tests (if PostgreSQL is available, otherwise skipped).

11.2. Run migration verification:
```text
python -m alembic upgrade head
python -m alembic check
```
Expected: "No new upgrade operations detected."

11.3. Run compilation verification:
```text
python -m compileall app tests
```
Expected: Zero syntax errors.

11.4. Run PostgreSQL compatibility tests (requires local PostgreSQL or CI):
```text
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa_verify python -m pytest tests/integration/test_evidence_postgresql.py -v
```
Expected: 3 passed (migration, CRUD, constraints).

11.5. Run type checking:
```text
python -m mypy app
```
Expected: No new type errors introduced. Pre-existing errors (documented debt) remain unchanged.

11.6. Verify agent backward compatibility:
- Confirm that the Deep Scraper, Technographic, Intent Signal, Intelligence Scoring, and Personalization agents all construct `AgentRunOutput` without the `evidence` key and compile without mypy errors.

### Success Criteria

- [ ] All existing 284 SQLite tests pass
- [ ] All 24 existing PostgreSQL compatibility tests pass
- [ ] All 23 new evidence unit tests pass
- [ ] All 12 new evidence integration tests pass
- [ ] Evidence PostgreSQL tests pass against PostgreSQL 18
- [ ] Alembic `check` reports no drift
- [ ] `compileall` reports zero syntax errors
- [ ] All 5 existing agents compile without changes
- [ ] No regressions in agent execution or workflow behavior

---

## Final Implementation Checklist

### Deliverables

- [ ] `.github/workflows/ci.yml` (no change — CI already configured)

### New Files (14)

- [ ] `database/migrations/versions/20260611_0004_create_evidence_records.py`
- [ ] `app/models/evidence_record.py`
- [ ] `app/repositories/evidence_repository.py`
- [ ] `app/services/evidence_service.py`
- [ ] `app/schemas/evidence.py`
- [ ] `app/api/v1/endpoints/evidence.py`
- [ ] `tests/unit/test_evidence_model.py`
- [ ] `tests/unit/test_evidence_service.py`
- [ ] `tests/unit/test_evidence_schemas.py`
- [ ] `tests/unit/agents/test_base_evidence.py`
- [ ] `tests/integration/api/test_evidence_api.py`
- [ ] `tests/integration/test_evidence_postgresql.py`
- [ ] `tests/integration/test_score_refresh_evidence.py`
- [ ] `docs/evidence_records_system_design.md` (already exists from design phase)

### Modified Files (9)

- [ ] `app/models/__init__.py` (export `EvidenceRecord`)
- [ ] `app/repositories/__init__.py` (export `EvidenceRepository`)
- [ ] `app/services/__init__.py` (export `EvidenceService`)
- [ ] `app/agents/base.py` (extend `AgentRunOutput`, update `execute()`)
- [ ] `app/api/dependencies.py` (add `get_evidence_service`)
- [ ] `app/api/v1/router.py` (register evidence endpoints)
- [ ] `app/workflows/score_refresh.py` (add evidence creation)
- [ ] `docs/agents.md` (add evidence section)
- [ ] `docs/database.md` (add evidence_records schema)
- [ ] `docs/project_state.md` (mark complete)
- [ ] `docs/project_handoff.md` (mark complete)

### Not Modified (No Changes Needed)

- `app/agents/result.py` (evidence is separate from `AgentResult`)
- `app/api/errors.py` (existing exception handlers cover evidence errors)
- `app/core/errors.py` (existing error types suffice)
- `app/main.py` (no app-level changes needed)
- `pyproject.toml` (no dependency changes needed)
- `tests/conftest.py` (no fixture changes needed)

### Test Count Summary

| Category | Count | Notes |
|---|---|---|
| Existing SQLite tests | 284 | Must continue to pass |
| Existing PostgreSQL tests | 24 | Must continue to pass |
| New evidence unit tests | 23 | Includes model, repository, service, schema, agent |
| New evidence integration tests | 12 | Includes API, PostgreSQL, score_refresh |
| **Total** | **343** | (284 + 24 + 23 + 12) |
