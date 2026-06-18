> **Status: IMPLEMENTED**

# Multi-Tenancy Phase 3: Tenant Isolation for Business Entities — Architecture Audit

## 1. Current State Summary

### What Phase 2 Delivered

Phase 2 integrated organizations into the auth flow without touching domain entity isolation:

| Component | Phase 2 State |
|---|---|
| Auth (`register`/`login`) | Creates org + owner membership; JWT carries `org`/`role` claims |
| `get_current_organization()` | FastAPI dependency returning verified `TenantContext` |
| `require_role()` | Service-level permission check |
| `_apply_tenant_filter()` | Defined in `BaseRepository` but **never called** |
| Domain models (Company, Contact, etc.) | **No `organization_id` column** |
| Domain services | **No `organization_id` parameter** |
| Domain endpoints | **No tenant scoping — no auth checks** |

### Current Gap

```text
Request → HTTPBearer → get_current_user() → user dict
         → get_current_organization() → TenantContext  ← phase 2
         → Route handler has TenantContext but ignores it  ← phase 3 gap
         → Service has no tenant parameter                ← phase 3 gap
         → Repository has no tenant filter                ← phase 3 gap
         → SQL returns ALL rows across ALL tenants        ← DATA LEAK
```

---

## 2. Entity-by-Entity Analysis

### 2.1 Company

| Aspect | Analysis |
|---|---|
| **`organization_id` needed?** | **Yes.** Company is the root entity. Every company belongs to an organization. |
| **Current state** | No `organization_id`. Has unique constraint on `domain` (cross-tenant uniqueness problem). |
| **Within-org uniqueness** | Two orgs could want the same `domain`. The global unique constraint on `domain` must become `(organization_id, domain)`. |
| **Migration** | Add column `organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id)` + backfill for existing companies (requires assigning each company to an org — Phase 1/2 data). Drop global `ix_companies_domain` unique index; create `(organization_id, domain)` unique index. |
| **Repository changes** | `CompanyRepository`: add `organization_id` parameter to `get_by_domain`, `search_by_name`, `list_by_status`. Wire `_apply_tenant_filter()` into these + inherited `list()`. |
| **Service changes** | `CompanyService`: add `organization_id` to all method signatures. Require `require_role("member", ...)` in `create()`, `require_role("admin", ...)` in `delete()`. |
| **API changes** | Every endpoint needs `tenant: TenantContext = Depends(get_current_organization)`. `CompanyCreate` schema gains `organization_id` (injected from tenant context, not user input). |
| **Query performance** | Index on `(organization_id, company_id)` for single-company lookups plus composite `(organization_id, domain)` for unique check. Existing single-column indexes remain but add org_id as leading column where possible. |
| **Security risk** | **Critical.** Currently any authenticated user can list ALL companies, read any company by ID, create companies with no org association. Cross-tenant data leakage is trivial via any list or get-by-id call. |
| **Data leakage risk** | **High.** `GET /companies` returns all companies across all tenants. `GET /companies/{id}` requires no membership check — any user with a valid token can read any company. |

### 2.2 Contact

| Aspect | Analysis |
|---|---|
| **`organization_id` needed?** | **Yes.** Contact belongs to a Company, which belongs to an Org. Two strategies: (A) denormalize `organization_id` on Contact for fast filtering, (B) filter through Company join. **Recommendation: Strategy A** (denormalize) for query performance. |
| **Current state** | Has `company_id` FK to Company. Email is globally unique — must become `(organization_id, email)` unique. |
| **Unique constraint** | Global `ix_contacts_email` unique must be dropped and replaced with `(organization_id, email)` unique. |
| **Migration** | Add `organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id)` with backfill from `Company.organization_id`. Drop global email unique; create org-scoped unique. Create index on `(organization_id, company_id)`. |
| **Repository changes** | `ContactRepository`: add `organization_id` to `get_by_email`, `list_by_company`, `list_by_status`. Wire tenant filter. |
| **Service changes** | `ContactService`: accept `organization_id` in all methods. `require_role("member", ...)` for create. `_before_create` must check org-scoped email uniqueness. |
| **API changes** | Endpoints require `get_current_organization()`. Injection of `organization_id` from tenant context into create. |
| **Query performance** | Denormalized `organization_id` enables direct WHERE-clause filtering without joining through Company. Index on `(organization_id, company_id)` makes the common "list contacts in my org for this company" query efficient. |
| **Security risk** | **Critical.** Same as Company — any user can list/read any contact. Cross-tenant contact enumeration. |
| **Data leakage risk** | **High.** Email addresses are PII-level data. Currently readable cross-tenant. |

### 2.3 IntentSignal

| Aspect | Analysis |
|---|---|
| **`organization_id` needed?** | **Yes.** IntentSignal belongs to a Company (and optionally Contact, Website, Technology). **Recommendation: denormalize** `organization_id` for fast filtering (same rationale as Contact). |
| **Current state** | Has `company_id` FK to Company. No org scoping. |
| **Migration** | Add `organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id)` with backfill from `Company.organization_id`. Create index on `(organization_id, company_id, signal_type, observed_at)` to match existing composite query pattern. |
| **Repository changes** | `IntentSignalRepository`: add `organization_id` to `list_by_company`, `list_by_contact`, `list_by_type`. Wire tenant filter. |
| **Service changes** | `IntentSignalService`: accept `organization_id` in all methods. Already no `create()` override (uses base) — base service's `create()` must gain `organization_id`. |
| **API changes** | Endpoints require `get_current_organization()`. Injection of org_id from tenant. |
| **Query performance** | Existing index on `(company_id, signal_type, observed_at)` is already efficient for per-company queries. Adding `organization_id` as leading column in composite index maintains efficiency while adding tenant gate. |
| **Security risk** | **High.** Current `list_by_type()` is a cross-tenant query with no filter. Any user can enumerate intent signals globally. |
| **Data leakage risk** | **High.** Intent signals contain competitive intelligence data. Cross-tenant leakage exposes signal strategies. |

### 2.4 OutreachMessage

| Aspect | Analysis |
|---|---|
| **`organization_id` needed?** | **Yes.** OutreachMessage belongs to Company (and optionally Contact, IntelligenceScore, AgentRun). **Recommendation: denormalize** `organization_id`. |
| **Current state** | Has `company_id` FK to Company. No org scoping. |
| **Migration** | Add `organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id)` with backfill. Create index on `(organization_id, company_id, channel, status)`. |
| **Repository changes** | `OutreachMessageRepository`: add `organization_id` to `list_by_company`, `list_by_contact`, `list_by_status`. Wire tenant filter. |
| **Service changes** | `OutreachMessageService`: accept `organization_id` in all methods. |
| **API changes** | Endpoints require `get_current_organization()`. |
| **Query performance** | Existing indexes plus new `organization_id` leading column composite indexes. |
| **Security risk** | **High.** Outreach messages contain customer communication content (messages, personalization angles). Cross-tenant leakage of outreach strategies is a competitive risk. |
| **Data leakage risk** | **Critical.** Message bodies and personalized content are potentially PII/sensitive. Currently accessible cross-tenant. |

### 2.5 EvidenceRecord

| Aspect | Analysis |
|---|---|
| **`organization_id` needed?** | **Yes.** EvidenceRecord has a `company_id` (denormalized, no FK), which provides the link to Organization. **Recommendation: add `organization_id`** as first-class column. |
| **Current state** | Polymorphic entity: links to source entities and target entities via type+id pairs. Has denormalized `company_id` (no FK) and `contact_id` (no FK). Agent-run link via real FK. |
| **Special concern** | EvidenceRecord is **the most complex** because it's polymorphic — evidence can target intelligence_scores, technologies, intent_signals, outreach_messages. The `company_id` field is a denormalized shortcut. We should add `organization_id` as a proper FK. |
| **Migration** | Add `organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id)` with backfill from company_id → Company.organization_id. However, company_id is nullable — for records without company_id, the org_id must be derived from the source entity chain. Existing records: backfill where company_id IS NOT NULL; handle NULL company_id records as a separate pass. |
| **Repository changes** | `EvidenceRepository`: add `organization_id` to `list_by_target`, `list_by_source`, `list_by_agent_run`, `list_by_company`, `list_by_entity_type`, `count_by_target`, `delete_by_target`. Wire tenant filter. |
| **Service changes** | `EvidenceService`: accept `organization_id` in `record_evidence`, `record_evidence_batch` (inject from context), `get_target_evidence`, `get_source_targets`, `get_company_evidence`, `get_agent_run_evidence`, `get_evidence_summary`, `delete_target_evidence`. |
| **API changes** | Evidence endpoints require `get_current_organization()`. |
| **Query performance** | Index on `(organization_id, target_type, target_id)` and `(organization_id, source_type, source_id)`. The existing target/source composite indexes remain but org_id becomes leading column. |
| **Security risk** | **High.** Evidence is polymorphic — one could query evidence for any entity across orgs if the target_id is known. The polymorphic nature makes authorization bypasses harder to catch by inspection. |
| **Data leakage risk** | **Critical.** `list_by_entity_type()` returns ALL evidence of a given type across ALL tenants — a direct cross-tenant leak. Evidence values can contain scraped HTML, PII, and competitive data. |

### 2.6 AgentRun

| Aspect | Analysis |
|---|---|
| **`organization_id` needed?** | **Yes.** AgentRun optionally links to Company and Contact. Runs are scoped to an organization even when company_id is null (system-level runs still belong to an org). |
| **Current state** | Optional `company_id` (SET NULL on delete). No org scoping. |
| **Special concern** | Agent runs are created by the system (via `AgentRunService.start_workflow_run()`). The `company_id` is optional because some runs are org-level or system-level, not company-specific. `organization_id` should be required, not optional. |
| **Migration** | Add `organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id)`. Backfill from `company_id → Company.organization_id`. For records with NULL company_id: require manual assignment to a default org or flag as system records. |
| **Repository changes** | `AgentRunRepository`: add `organization_id` to `list_by_agent`, `list_by_status`, `list_by_workflow`. Wire tenant filter. |
| **Service changes** | `AgentRunService`: accept `organization_id` in `start_workflow_run` and `create()`. `mark_succeeded`/`mark_failed` operate on already-scoped runs. |
| **API changes** | Endpoints require `get_current_organization()`. |
| **Query performance** | Index on `(organization_id, agent_name, status)` for common "show me my org's runs of agent X by status" query pattern. |
| **Security risk** | **High.** Agent runs expose which agents/workflows are being used, their status, input summaries, and error messages. Cross-tenant visibility of internal operations. |
| **Data leakage risk** | **Medium.** Input/output summaries may contain business context. Error messages may leak infrastructure details. |

### 2.7 IntelligenceScore

| Aspect | Analysis |
|---|---|
| **`organization_id` needed?** | **Yes.** IntelligenceScore belongs to Company (and optionally Contact). Scores are org-scoped. |
| **Current state** | Has `company_id` FK to Company. No org scoping. `list_top_scores()` is a global cross-tenant leaderboard. |
| **Special concern** | `list_top_scores()` is currently unscoped — it's used for the "top scores" dashboard. Post-Phase 3, this must be scoped to the requesting org. If cross-org comparison is a product requirement, it needs an explicit opt-in mechanism. |
| **Migration** | Add `organization_id VARCHAR(36) NOT NULL REFERENCES organizations(id)` with backfill. Create index on `(organization_id, company_id, total_score)`. |
| **Repository changes** | `IntelligenceScoreRepository`: add `organization_id` to `latest_for_company`, `latest_for_contact`, `latest_for_target`, `list_top_scores`. Wire tenant filter. |
| **Service changes** | `IntelligenceScoreService`: accept `organization_id` in all methods. `list_top_scores` becomes org-scoped (breaking change — dashboard needs update). |
| **API changes** | Endpoints require `get_current_organization()`. |
| **Query performance** | Existing composite index `(company_id, total_score)` is used by scoring queries. Add org_id as leading column. |
| **Security risk** | **Critical.** `list_top_scores()` currently exposes every org's highest-scoring companies and their detailed scores. This is a direct cross-tenant competitive intelligence leak — Org A can see Org B's top prospects and their scores. |
| **Data leakage risk** | **Critical.** Scores are the core product value. Full cross-tenant visibility is a business-ending data leak. |

### 2.8 Job

| Aspect | Analysis |
|---|---|
| **`organization_id` needed?** | **Yes, but differently.** Jobs are a system-internal entity created by the job scheduler. Jobs reference an `agent_run_id`. The organization context comes from the agent run that created the job. |
| **Current state** | No `company_id`. No `organization_id`. Has optional `agent_run_id` FK. |
| **Special concern** | Jobs are created by the scheduler, not by user-facing API calls. The `schedule_agent()` and `schedule_workflow()` methods receive an `AgentContext`/`WorkflowContext` which **already contains `organization_id`** (per Phase 2 design). The org_id must flow from the context into the job record. |
| **Current context objects** | Check: do `AgentContext` and `WorkflowContext` already have `organization_id`? They should per Phase 2 design §9. If not, Phase 3 must add it. |
| **Migration** | Add `organization_id VARCHAR(36) REFERENCES organizations(id)` (nullable for backward compatibility with existing pending jobs). Backfill from `agent_run_id → AgentRun.organization_id`. |
| **Repository changes** | `JobRepository`: add `organization_id` to `get_pending_jobs`, `get_job_by_agent_run_id`. The job runner's `get_next_jobs()` call must be scoped OR remain unscoped (system worker claims any pending job regardless of org — this is the correct behavior for a multi-tenant job runner). Only user-facing queries need scoping. |
| **Service changes** | `JobService.list_jobs()` and `cancel_job()` accept `organization_id`. `schedule_agent()`/`schedule_workflow()` extract org_id from context and store it. `get_next_jobs()` remains unscoped (system-level). `claim_job()` remains unscoped (system-level). |
| **API changes** | Job listing/cancellation endpoints require `get_current_organization()`. Scheduling endpoints get org_id from the calling agent's context. |
| **Query performance** | Index on `(organization_id, status, scheduled_at)` for org-scoped job listing. The existing `(status, scheduled_at)` index remains for the system worker. |
| **Security risk** | **Medium.** Job CRUD from user-facing API must be scoped. The job runner (internal) should remain unscoped to service all orgs. If user-facing job listing is not scoped, Org A can see Org B's scheduled jobs. |
| **Data leakage risk** | **Medium.** Job payloads may contain company_id, contact_id, correlation_id — PII-adjacent data. User-facing job listing must be scoped. |

---

## 3. Cross-Cutting Concerns

### 3.1 Unique Constraint Conflicts

Every entity with a globally-unique constraint will break under multi-tenancy:

| Model | Current Unique Field | Phase 3 Fix |
|---|---|---|
| `Company` | `domain` (global) | `(organization_id, domain)` — drop global unique index |
| `Contact` | `email` (global) | `(organization_id, email)` — drop global unique index |
| Organization | `slug` (already org-scoped by `generate_unique_slug`) | Already handled — no change needed |

**All other entities use composite/foreign-key indexes, not global unique constraints.**

### 3.2 Polymorphic EvidenceRecord

EvidenceRecord is the most complex case because:
- `company_id` is denormalized (no FK) and nullable
- Source/target are polymorphic (type+id pairs)
- The `organization_id` must be determinable from the source entity chain
- Backfill for NULL company_id records requires source-entity traversal

**Strategy:** For `record_evidence()` and `record_evidence_batch()`, the `company_id` parameter (already passed by callers) determines the org via Company lookup. For records without company_id, organization_id should be passed explicitly by the caller (e.g., agent runs already have org context).

### 3.3 Job Scheduler Isolation

Jobs have a **dual nature**:
1. **System-level**: The job runner polls for pending jobs globally. This must remain unscoped — a single worker pool serves all orgs.
2. **User-facing**: Job listing/cancellation by users must be org-scoped.

**Implementation:** The job runner (`get_next_jobs()`, `claim_job()`) operates unscoped. The user-facing `list_jobs()` and `cancel_job()` accept `organization_id`. Jobs store `organization_id` for user-facing queries but the worker ignores it.

### 3.4 Score Ranking / Cross-Org Queries

`IntelligenceScoreService.list_top_scores()` is a designed feature that becomes a data leak under org isolation. Three options:

| Option | Description | Trade-off |
|---|---|---|
| **A: Remove** | Make `list_top_scores()` org-scoped only | Simple but loses cross-org ranking feature |
| **B: Permission-gate** | Add a `cross_org` permission flag on memberships | Allows admin/analyst roles to see cross-org |
| **C: Request-scoped** | Default to org-scoped; optional `?global=true` query param gated by `owner` role | Flexible but more complex |

**Recommendation: Option C** — default-safe (org-scoped), with explicit opt-in for cross-org queries.

---

## 4. Migration Plan

### 4.1 Schema Migration

**Migration file:** `database/migrations/versions/20260616_0007_add_organization_id_to_domain_tables.py`

```sql
-- 1. Company
ALTER TABLE companies ADD COLUMN organization_id VARCHAR(36) NOT NULL;
ALTER TABLE companies ADD CONSTRAINT fk_companies_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id);
DROP INDEX ix_companies_domain;
CREATE UNIQUE INDEX ix_companies_org_domain
    ON companies(organization_id, domain);
CREATE INDEX ix_companies_organization_id ON companies(organization_id);

-- 2. Contact
ALTER TABLE contacts ADD COLUMN organization_id VARCHAR(36) NOT NULL;
ALTER TABLE contacts ADD CONSTRAINT fk_contacts_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id);
DROP INDEX ix_contacts_email;
CREATE UNIQUE INDEX ix_contacts_org_email
    ON contacts(organization_id, email);
CREATE INDEX ix_contacts_org_company ON contacts(organization_id, company_id);

-- 3. IntentSignal
ALTER TABLE intent_signals ADD COLUMN organization_id VARCHAR(36) NOT NULL;
ALTER TABLE intent_signals ADD CONSTRAINT fk_intent_signals_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id);
CREATE INDEX ix_intent_signals_org_company_type_observed
    ON intent_signals(organization_id, company_id, signal_type, observed_at);

-- 4. OutreachMessage
ALTER TABLE outreach_messages ADD COLUMN organization_id VARCHAR(36) NOT NULL;
ALTER TABLE outreach_messages ADD CONSTRAINT fk_outreach_messages_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id);
CREATE INDEX ix_outreach_messages_org_company
    ON outreach_messages(organization_id, company_id);

-- 5. EvidenceRecord
ALTER TABLE evidence_records ADD COLUMN organization_id VARCHAR(36);
ALTER TABLE evidence_records ADD CONSTRAINT fk_evidence_records_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id);
CREATE INDEX ix_evidence_org_target
    ON evidence_records(organization_id, target_type, target_id);
CREATE INDEX ix_evidence_org_source
    ON evidence_records(organization_id, source_type, source_id);

-- 6. AgentRun
ALTER TABLE agent_runs ADD COLUMN organization_id VARCHAR(36) NOT NULL;
ALTER TABLE agent_runs ADD CONSTRAINT fk_agent_runs_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id);
CREATE INDEX ix_agent_runs_org_agent_status
    ON agent_runs(organization_id, agent_name, status);

-- 7. IntelligenceScore
ALTER TABLE intelligence_scores ADD COLUMN organization_id VARCHAR(36) NOT NULL;
ALTER TABLE intelligence_scores ADD CONSTRAINT fk_intelligence_scores_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id);
DROP INDEX ix_intelligence_scores_company_total;
CREATE INDEX ix_intelligence_scores_org_company_total
    ON intelligence_scores(organization_id, company_id, total_score);

-- 8. Job
ALTER TABLE jobs ADD COLUMN organization_id VARCHAR(36);
ALTER TABLE jobs ADD CONSTRAINT fk_jobs_org
    FOREIGN KEY (organization_id) REFERENCES organizations(id);
CREATE INDEX ix_jobs_org_status_scheduled
    ON jobs(organization_id, status, scheduled_at);
```

**Backfill strategy:**
- For entities with a `company_id` FK: `UPDATE t SET organization_id = (SELECT c.organization_id FROM companies c WHERE c.id = t.company_id)`
- For EvidenceRecord with NULL company_id: `UPDATE evidence_records SET organization_id = (SELECT ar.organization_id FROM agent_runs ar WHERE ar.id = evidence_records.agent_run_id) WHERE company_id IS NULL AND agent_run_id IS NOT NULL`
- For remaining NULL organization_id records: flag for manual review
- For Job: backfill from `agent_run_id` → AgentRun.organization_id, nullable for in-flight jobs

### 4.2 Development Impact (No Prod Data)

**No backfill needed in dev.** The existing test database can be dropped and recreated with the new migration. For development, the NOT NULL constraint is safe because:
- All new records are created through the API/services that will inject `organization_id`
- Existing test data can be reseeded

---

## 5. Implementation Plan

### Commit 1: Model + Migration (organization_id columns)

| File | Change |
|---|---|
| `app/models/company.py` | Add `organization_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False)` |
| `app/models/contact.py` | Add `organization_id` column |
| `app/models/intent_signal.py` | Add `organization_id` column |
| `app/models/outreach_message.py` | Add `organization_id` column |
| `app/models/evidence_record.py` | Add `organization_id` column (nullable for polymorphic edge cases) |
| `app/models/agent_run.py` | Add `organization_id` column |
| `app/models/intelligence_score.py` | Add `organization_id` column |
| `app/models/job.py` | Add `organization_id` column (nullable for pending jobs without agent_run) |
| `database/migrations/versions/...0007...py` | New Alembic migration with all ALTER TABLE + index statements |
| `tests/unit/test_models.py` | Verify org_id is required on new entity creation |

**Verification:** `python -m compileall app/models/`, `python -m pytest tests/`

**Risk:** Migration is additive — no data loss. Tables with NOT NULL require backfill or a default org for existing records in production (not applicable for dev).

**Dependencies:** None (models are independent).

---

### Commit 2: Repository Tenant Filtering

| File | Change |
|---|---|
| `app/repositories/base.py` | Add `organization_id` parameter to `BaseRepository.list()`, wire `_apply_tenant_filter()` and `_check_tenant_filter()` |
| `app/repositories/company_repository.py` | Add `organization_id` to `get_by_domain`, `search_by_name`, `list_by_status` |
| `app/repositories/contact_repository.py` | Add `organization_id` to `get_by_email`, `list_by_company`, `list_by_status` |
| `app/repositories/intent_signal_repository.py` | Add `organization_id` to `list_by_company`, `list_by_contact`, `list_by_type` |
| `app/repositories/outreach_message_repository.py` | Add `organization_id` to `list_by_company`, `list_by_contact`, `list_by_status` |
| `app/repositories/evidence_repository.py` | Add `organization_id` to `list_by_target`, `list_by_source`, `list_by_agent_run`, `list_by_company`, `list_by_entity_type`, `count_by_target`, `delete_by_target` |
| `app/repositories/agent_run_repository.py` | Add `organization_id` to `list_by_agent`, `list_by_status`, `list_by_workflow` |
| `app/repositories/intelligence_score_repository.py` | Add `organization_id` to `latest_for_company`, `latest_for_contact`, `latest_for_target`, `list_top_scores` |
| `app/repositories/job_repository.py` | Add `organization_id` to `get_job_by_agent_run_id` (NOT `get_pending_jobs` — system worker remains unscoped) |
| `tests/unit/test_repository_tenant_filter.py` | Extend existing tests to cover all entity repositories |

**Pattern for each repository method:**
```python
def get_by_domain(self, domain: str, organization_id: str) -> Company | None:
    statement = select(Company).where(Company.domain == domain)
    statement = self._apply_tenant_filter(statement, organization_id)
    return self.scalar_one_or_none(statement)
```

**BaseRepository.list() update:**
```python
def list(self, *, organization_id: str | None = None, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
    statement = select(self.model)
    statement = self._apply_tenant_filter(statement, organization_id)
    self._check_tenant_filter(statement, organization_id)
    statement = statement.offset(offset).limit(limit)
    return self.session.scalars(statement).all()
```

**Verification:** `python -m compileall app/repositories/`, run all repository filter tests.

**Risk:** `BaseRepository.list()` signature change is backward-incompatible for existing callers. However, all callers must add `organization_id` anyway — this is a Phase 3 requirement.

---

### Commit 3: Service Tenant Scoping

| File | Change |
|---|---|
| `app/services/base.py` | Add `organization_id` to `BaseService.create()` and `BaseService.list()` signatures |
| `app/services/company_service.py` | Add `organization_id` to `get_by_domain`, `search_by_name`, `list_by_status`, `_before_create` uses org-scoped uniqueness check |
| `app/services/contact_service.py` | Add `organization_id` to `get_by_email`, `list_by_company`, `list_by_status`, `_before_create` scoped |
| `app/services/intent_signal_service.py` | Add `organization_id` to `list_by_company`, `list_by_contact`, `list_by_type` |
| `app/services/outreach_message_service.py` | Add `organization_id` to `list_by_company`, `list_by_contact`, `list_by_status` |
| `app/services/evidence_service.py` | Add `organization_id` to `record_evidence`, `record_evidence_batch`, `get_target_evidence`, `get_source_targets`, `get_company_evidence`, `get_agent_run_evidence`, `get_evidence_summary`, `delete_target_evidence` |
| `app/services/agent_run_service.py` | Add `organization_id` to `start_workflow_run`, `list_by_agent`, `list_by_status`, `list_by_workflow` |
| `app/services/intelligence_score_service.py` | Add `organization_id` to `latest_for_company`, `latest_for_contact`, `latest_for_target`, `list_top_scores` (default scoped) |
| `app/services/job_service.py` | Add `organization_id` to `list_jobs`, `cancel_job`. Extract org_id from context in `schedule_agent`/`schedule_workflow`. `get_next_jobs` and `claim_job` remain unscoped. |
| `tests/unit/test_*_service.py` | Add org-scoped test variants |

**Service pattern:**
```python
def create(self, organization_id: str, **values: Any) -> ModelT:
    return super().create(organization_id=organization_id, **values)

def list_by_company(self, company_id: str, organization_id: str, *, limit: int = 100) -> Sequence[Contact]:
    self._validate_identifier(company_id, field_name="company_id")
    self._validate_limit(limit)
    def operation(session):
        return self._repository(session).list_by_company(company_id, organization_id=organization_id, limit=limit)
    return self._run_in_transaction("list_by_company", operation)
```

**Verification:** `python -m compileall app/services/`, run unit tests.

**Risk:** Service method signatures change for ALL callers (endpoints, other services, background agents, workflows). This is the highest-touch commit.

---

### Commit 4: Endpoint + Auth Integration

| File | Change |
|---|---|
| `app/api/v1/endpoints/companies.py` | Add `tenant: TenantContext = Depends(get_current_organization)` to every endpoint. Pass `tenant.organization_id` to service calls. |
| `app/api/v1/endpoints/contacts.py` | Same pattern |
| `app/api/v1/endpoints/intent_signals.py` | Same pattern |
| `app/api/v1/endpoints/outreach_messages.py` | Same pattern |
| `app/api/v1/endpoints/evidence.py` | Same pattern |
| `app/api/v1/endpoints/agent_runs.py` | Same pattern |
| `app/api/v1/endpoints/intelligence.py` | Same pattern |
| `app/api/v1/endpoints/jobs.py` | Same pattern — user-facing listing/cancellation endpoints only |
| `app/schemas/company.py` | Add `organization_id` to `CompanyRead` (auto-populated from service, not user input) |
| `app/schemas/contact.py` | Add `organization_id` to `ContactRead` |
| (and matching schema updates for all 8 entities) | |

**Endpoint pattern:**
```python
@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    tenant: TenantContext = Depends(get_current_organization),
    service: CompanyService = Depends(get_company_service),
) -> CompanyRead:
    company = service.create(organization_id=tenant.organization_id, **payload.model_dump())
    return CompanyRead.model_validate(company)
```

**Verification:** `python -m compileall app/api/`, `python -c "from app.main import create_app; create_app(configure_logging_on_startup=False)"`, full test suite.

**Risk:** All existing integration tests for these endpoints will fail because they don't provide `get_current_organization()` context. Tests must be updated to inject a `TenantContext` via FastAPI's `app.dependency_overrides[]`.

---

### Commit 5: CRUD Phase 1/2/3 Test Updates

| File | Change |
|---|---|
| `tests/conftest.py` | Add `organization` fixture, `tenant_context` fixture, `override_get_current_organization()` helper |
| `tests/integration/api/test_crud_phase_1.py` | Add org context to all test requests |
| `tests/integration/api/test_crud_phase_2.py` | Same |
| `tests/integration/api/test_crud_phase_3.py` | Same |
| `tests/unit/test_*_service.py` | Update all service tests to pass `organization_id` |

**Pattern for test overrides:**
```python
@pytest.fixture()
def client(api_session_factory, monkeypatch):
    from app.api.dependencies import get_current_organization
    app.dependency_overrides[get_current_organization] = lambda: TenantContext(
        organization_id=org.id,
        user_id=user.id,
        role="owner",
        is_api_key=False,
    )
```

**Verification:** Full test suite must pass.

---

## 6. Risk Analysis

### 6.1 Risk Matrix

| # | Risk | Severity | Likelihood | Mitigation | Phase |
|---|---|---|---|---|---|
| R1 | **Cross-tenant data leakage via `list_top_scores()`** | Critical | Certain | Default-scope to org; add `?global=true` gated by owner role | C4 |
| R2 | **EvidenceRecord polymorphic queries bypass tenant filter** | High | Likely | Audit all `list_by_*` methods for tenant filter; add integration tests for each polymorphic path | C2, C5 |
| R3 | **Job runner fails to claim cross-org jobs after scoping** | High | Likely | `get_next_jobs()` explicitly remains unscoped; document this invariant | C3 |
| R4 | **Unique constraint violations during backfill** | Medium | Likely | Dropping global unique indexes and creating org-scoped composites can't have conflicts in dev (no data) | C1 |
| R5 | **AgentContext/WorkflowContext lack `organization_id`** | High | Possible | Must verify Phase 2 added org_id to context objects; if not, add in C3 | C3 |
| R6 | **EvidenceRecord with NULL company_id can't be backfilled** | Medium | Possible | Make `organization_id` nullable for EvidenceRecord; fall back to agent_run traversal; manual review for orphans | C1 |
| R7 | **`BaseService.create()` signature change breaks agents/workflows** | High | Certain | Create a `create_with_org()` overload or add `organization_id` to all callers in the same commit | C3 |
| R8 | **GET endpoint returns 404 instead of 403 for cross-org access** | Low | Certain by design | Use `get_required()` (404) vs. membership check (403) — be consistent: cross-org ID guessing should 403, not 404 | C4 |

### 6.2 Data Leakage Analysis

**Pre-Phase 3 state:** Every entity endpoint returns data across all organizations. The only barrier is knowing the entity's UUID.

| Endpoint | Pre-Phase 3 | Post-Phase 3 |
|---|---|---|
| `GET /companies` | Lists ALL companies | Lists only caller's org companies |
| `GET /companies/{id}` | Reads any company | 403 if not caller's org |
| `GET /contacts` | Lists ALL contacts | Lists only caller's org contacts |
| `GET /intelligence-scores/top` | Global leaderboard | Org-scoped by default |
| `GET /evidence?company_id=X` | Reads evidence for any company | 403 if company not in caller's org |
| `GET /agent-runs` | Lists ALL runs | Lists only caller's org runs |
| `GET /jobs` | Lists ALL jobs | Lists only caller's org jobs |

### 6.3 Security Risks

| Concern | Assessment |
|---|---|
| **Authorization bypass via UUID enumeration** | Low risk after Phase 3 — membership check on every endpoint prevents cross-org read |
| **EvidenceRecord polymorphic target injection** | Medium — an attacker could query evidence for any `target_type`/`target_id` pair. The `organization_id` filter on the repository closes this. |
| **Job scheduling privilege escalation** | Low — job scheduling is internal (agent/workflow contexts), not user-facing API. |
| **Score data leakage via `list_top_scores`** | **Critical before Phase 3.** Org-scoped default closes this. |

---

## 7. Testing Strategy

### 7.1 Unit Tests

| Test | Verification |
|---|---|
| Models: org_id required on create | Every entity model rejects missing org_id |
| Models: org_id immutable after create | Attempted update raises error |
| Repo: `_apply_tenant_filter` called in every repository method | Each method with org_id injects WHERE clause |
| Repo: unscoped query generates warning | `_check_tenant_filter` logs for missing org_id |
| Repo: cross-org ID query returns None | `get_by_id` with wrong org_id returns None |
| Service: create requires org_id | Service.create() without org_id fails |
| Service: list returns only org entities | Two orgs with data; list returns only caller's |
| Service: get with wrong org raises | `get_required()` with cross-org ID raises 404/403 |
| Job: `get_next_jobs` unscoped | Worker sees jobs from all orgs |
| Job: `list_jobs` scoped | User sees only their org's jobs |

### 7.2 Integration Tests

| Test | Verification |
|---|---|
| POST /companies creates org-scoped | Company created in caller's org |
| GET /companies returns org-scoped | List shows only caller's org |
| GET /companies/{id} 403 for cross-org | Other org's company returns 403 |
| Evidence: polymorphic target scoped | Querying evidence for cross-org target returns 403 |
| Scores: top list default scoped | Default scope returns only caller's org |
| Scores: top list global gated | `?global=true` requires owner role |
| Jobs: user listing scoped | User sees only own org's jobs |
| Jobs: worker polling unscoped | Worker claims jobs from any org |

### 7.3 Test Count Estimate

| Layer | Tests |
|---|---|
| Model + migration validation | ~8 |
| Repository tenant filter (8 entities) | ~24 |
| Service scoping (8 entities × 3 methods) | ~24 |
| API endpoints (8 entities × CRUD) | ~32 |
| Cross-tenant access denial | ~16 |
| Job isolation (scoped + unscoped) | ~6 |
| Edge cases (null org_id, backfill) | ~8 |
| **Total new tests** | **~118** |

---

## 8. Commit Dependency Graph

```text
Commit 1: Models + Migration (no deps)
  ├── app/models/*.py
  └── database/migrations/...

Commit 2: Repository Filters (needs C1 models)
  ├── app/repositories/base.py
  ├── app/repositories/*.py
  └── tests/unit/test_repository_tenant_filter.py (extend)

Commit 3: Service Scoping (needs C2 repositories)
  ├── app/services/base.py
  ├── app/services/*.py
  └── tests/unit/test_*_service.py

Commit 4: Endpoint Auth (needs C3 services)
  ├── app/api/v1/endpoints/*.py
  ├── app/schemas/*.py
  └── tests integration (partial)

Commit 5: Test Updates (needs C4 endpoints working)
  ├── tests/conftest.py (fixtures)
  ├── tests/integration/api/test_crud_phase_*.py
  ├── tests/unit/test_*_service.py (complete)
  └── python -m pytest (all must pass)
```

---

## 9. Summary

| Metric | Count |
|---|---|
| Models to modify | 8 |
| New migrations | 1 |
| Repository files to modify | 9 (base + 8 entity repos) |
| Service files to modify | 9 (base + 8 entity services) |
| Endpoint files to modify | 8 |
| Schema files to modify | 8 |
| Test files to modify/create | ~10 |
| **Total files changed** | **~45** |
| **Estimated new tests** | **~118** |
| **Build commits** | **5** |
| **Database migration risk** | **Low** (additive columns, no data loss) |
| **Data leakage risk closed** | **Critical → None** (with correct implementation) |
