# Lead Discovery Engine — Architecture Review

> **Status: PLANNED** — Revised design based on senior architecture review.

## 1. Architecture Concerns

### Concern 1: `discovery_sources` table is unnecessary infrastructure

The original design creates a dedicated table to track API rate limits per provider. This is over-engineered for an MVP:

- Rate limit state is **ephemeral** — daily counters reset every 24 hours and are meaningless after a restart.
- SQLite doesn't need a table for a few integer counters. A simple in-memory dict on the service object handles this.
- Adding a table means a migration, a model, a repository, a service, API endpoints to "configure sources" — all to manage 4 integers.
- The existing `DiscoverySettings` config dataclass already declares `daily_limit` per source. The config IS the source registry.

**Verdict:** Delete `discovery_sources` table entirely. Use in-memory rate tracking in `DiscoverySettings` or a simple class-level dict on the agent.

### Concern 2: Google Custom Search is a weak primary source

- Requires a Google Cloud project + API key + Custom Search Engine ID — 3 configuration items for 100 queries/day.
- Returns web pages, not companies. Must parse HTML snippets to extract company names/domains — unreliable.
- Google has deprecated the free tier's usefulness for programmatic use; results are heavily personalized and inconsistent.
- At 100/day with batch sizes of 20-50 queries per run, you get 2-5 runs/day before hitting limits.

**Recommended replacement:** SEC EDGAR is the strongest free source — unlimited, no API key, structured data. For non-US companies, OpenCorporates with the free tier (500/month). For technology-specific discovery, BuiltWith's free lookup. Google News RSS for intent-based discovery (funding rounds, hiring).

**Revised source priority:**

| Priority | Source | Why |
|----------|--------|-----|
| 1 | SEC EDGAR full-text search | Unlimited, no key, structured filings data |
| 2 | Google News RSS | Unlimited, no key, detects funding/hiring/product signals |
| 3 | OpenCorporates search | 500/mo free, structured company data |
| 4 | BuiltWith free lookup | Tech-specific discovery from domain |
| 5 | Google Custom Search | Optional, degraded to fallback only |

### Concern 3: `discovery_candidates` should not be a separate table

The original design creates `discovery_candidates` as a holding area before companies are created. This duplicates data that already lives in `companies`:

- Companies already have `status='needs_review'` — a natural fit for "discovered but not yet enriched."
- Companies already have `organization_id` — tenant isolation works.
- The `(organization_id, domain)` unique constraint already prevents duplicates.
- Creating a separate candidates table means: a separate model, repository, service, schema, API endpoints, and a dedup step that crosses two tables.

**Better approach:** Use the existing `companies` table with a small extension:

1. Add `discovered_via` column to `companies` (values: `NULL`, `'discovery_pipeline'`). This distinguishes manually-created companies from discovered ones.
2. Add `discovery_search_id` column to `companies` (FK to `discovery_searches`). Links back to the search that found the company.
3. New companies discovered via the pipeline are created with `status='active'` and `discovered_via='discovery_pipeline'`. The pipeline immediately enriches them.

This eliminates: `discovery_candidates` table, `DiscoveryCandidateService`, deduplication logic (the DB constraint handles it), and the accept/reject API endpoints. The intelligence pipeline already handles the enrich → score flow for any company.

### Concern 4: 12 endpoints is too many for MVP

The original design has 12 new endpoints. Several are unnecessary:

| Endpoint | MVP? | Reason |
|----------|------|--------|
| `POST /discovery/searches` | ✅ | Core: save an ICP |
| `GET /discovery/searches` | ✅ | Core: list saved searches |
| `GET /discovery/searches/{id}` | ✅ | Core: view a search |
| `PATCH /discovery/searches/{id}` | ✅ | Core: update criteria |
| `DELETE /discovery/searches/{id}` | ⚠️ | Nice-to-have, defer to Phase 2 |
| `POST /discovery/searches/{id}/run` | ✅ | Core: trigger discovery |
| `GET /discovery/runs` | ✅ | Core: view run history |
| `GET /discovery/runs/{id}` | ✅ | Core: check run status |
| `GET /discovery/runs/{id}/candidates` | ❌ | Eliminated (candidates are companies now) |
| `POST /discovery/candidates/{id}/accept` | ❌ | Eliminated (auto-enrich on discovery) |
| `POST /discovery/candidates/{id}/reject` | ❌ | Eliminated (use company archive status) |
| `GET /discovery/sources` | ❌ | Eliminated (rate limits are in-memory) |
| `POST /discovery/sources` | ❌ | Eliminated (sources configured via env vars) |

**MVP: 7 endpoints.** The accept/reject/source-management flow is unnecessary when discovered companies go directly into the companies table and get enriched automatically.

### Concern 5: Evidence generation is already built in

The original design doesn't leverage the existing evidence system. But every agent already records evidence automatically via `BaseAgent.execute()` → `EvidenceService.record_evidence_batch()`. The DiscoveryAgent should follow the same pattern:

- Each source method returns `EvidenceItem` entries with `source_type='agent_run'`, `evidence_type='url_match'` or `'text_excerpt'`, and `source_location_value` pointing to the URL or API response that found the company.
- This gives full provenance tracking without any new infrastructure.
- The existing `GET /evidence/by-company/{company_id}` endpoint surfaces discovery evidence automatically.

### Concern 6: Discovery score before enrichment is valuable but should be lightweight

The original design defers all scoring to the intelligence pipeline. But users need a quick way to prioritize which discovered companies to investigate first. A lightweight `discovery_score` on the company record (computed at discovery time from available data) would help.

**Recommended:** Add a `discovery_score` Float column to `companies` (default 0.0). Computed at discovery time based on:

- Name match quality against search criteria (0.0-0.4)
- Industry match (0.0-0.2)
- Size match (0.0-0.2)
- Source reliability (0.0-0.2)

This is a simple deterministic calculation — no external API needed. The `LeadRetrievalService` can use it for pre-enrichment filtering.

### Concern 7: Discovery pipeline should NOT chain to intelligence_pipeline in MVP

The original design has the discovery pipeline automatically trigger `intelligence_pipeline` for every discovered company. This is expensive:

- Each company requires 5 agent calls (scrape, tech detect, intent, score, personalize).
- At 100 companies per discovery run, that's 500 agent executions.
- The Deep Scraper makes real HTTP requests — rate limits, timeouts, robots.txt compliance.
- If the pipeline fails for one company, the entire batch is affected.

**Better MVP approach:** Discovery pipeline creates companies with `status='needs_review'`. Users review the list. They trigger `intelligence_pipeline` individually or in small batches via the existing `POST /intelligence/pipeline` endpoint. The intelligence pipeline already handles single-company enrichment.

This decouples discovery (finding companies) from enrichment (scoring them). Users get faster feedback and control.

---

## 2. Recommended Design Changes

### Change 1: Eliminate `discovery_candidates` table

Use `companies` table with `discovered_via` and `discovery_search_id` columns. Companies are created directly by the discovery agent. No separate candidate lifecycle.

### Change 2: Eliminate `discovery_sources` table

Rate limits tracked in-memory via `DiscoverySettings` config. Source availability checked at runtime. No database state needed.

### Change 3: Keep `discovery_searches` table

This is the core value: persisting ICP search criteria. Essential for recurring discovery runs.

### Change 4: Keep `discovery_runs` table

This provides observability: what was searched, when, how many companies found, success/failure. Essential for debugging and monitoring.

### Change 5: Prioritize unlimited free sources

SEC EDGAR (unlimited, no key) and Google News RSS (unlimited, no key) as primary sources. OpenCorporates as secondary. Google Custom Search demoted to optional fallback.

### Change 6: Don't auto-enrich in discovery pipeline

Discovery creates companies with `status='needs_review'` and `discovered_via='discovery_pipeline'`. Users review and trigger enrichment manually via existing pipeline. The `discovery_score` field helps prioritize.

### Change 7: Record evidence via existing agent mechanism

DiscoveryAgent uses the same `EvidenceItem` pattern as all other agents. No new evidence infrastructure needed.

---

## 3. Revised MVP Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                    Lead Discovery Engine (MVP)                │
│                                                              │
│  ┌──────────────┐     ┌───────────────────┐                 │
│  │ ICP Search    │────▶│ Discovery Pipeline │                 │
│  │ (DB: saved)   │     │    (workflow)      │                 │
│  └──────────────┘     └────────┬──────────┘                 │
│                                │                             │
│                    ┌───────────┴───────────┐                 │
│                    ▼                       ▼                  │
│          ┌─────────────────┐    ┌──────────────────┐        │
│          │ DiscoveryAgent  │    │ EvidenceService   │        │
│          │ (BaseAgent)     │───▶│ (existing)        │        │
│          └────────┬────────┘    └──────────────────┘        │
│                   │                                          │
│      ┌────────────┼────────────┐                            │
│      ▼            ▼            ▼                             │
│  ┌────────┐ ┌──────────┐ ┌──────────────┐                  │
│  │ SEC    │ │ Google   │ │ OpenCorporate│                  │
│  │ EDGAR  │ │ News RSS │ │ s            │                  │
│  │ (free) │ │ (free)   │ │ (free tier)  │                  │
│  └────────┘ └──────────┘ └──────────────┘                  │
│      │            │            │                             │
│      └────────────┼────────────┘                            │
│                   ▼                                          │
│  ┌──────────────────────────────────────┐                   │
│  │  Companies (existing table)          │                   │
│  │  status='needs_review'               │                   │
│  │  discovered_via='discovery_pipeline' │                   │
│  │  discovery_score=0.0-1.0             │                   │
│  └──────────────────────────────────────┘                   │
│           │                                                  │
│           ▼  (user triggers manually)                        │
│  ┌──────────────────────────────────────┐                   │
│  │  Intelligence Pipeline (existing)    │                   │
│  │  scrape → tech → intent → score →    │                   │
│  │  personalize                         │                   │
│  └──────────────────────────────────────┘                   │
└──────────────────────────────────────────────────────────────┘
```

**Key simplifications:**
- No `discovery_candidates` table — companies ARE the candidates
- No `discovery_sources` table — rate limits are in-memory
- No auto-enrichment — user triggers pipeline manually
- 7 endpoints instead of 12
- 2 new tables instead of 4

---

## 4. Revised Database Design

### New Tables (2)

#### `discovery_searches`

```sql
CREATE TABLE discovery_searches (
    id                  VARCHAR(36) PRIMARY KEY,
    organization_id     VARCHAR(36) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    criteria            TEXT NOT NULL,          -- JSON
    status              VARCHAR(50) DEFAULT 'active' NOT NULL,
    last_run_at         DATETIME,
    total_discovered    INTEGER DEFAULT 0,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL
);

CREATE INDEX ix_discovery_searches_org ON discovery_searches(organization_id);
```

#### `discovery_runs`

```sql
CREATE TABLE discovery_runs (
    id                  VARCHAR(36) PRIMARY KEY,
    organization_id     VARCHAR(36) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    search_id           VARCHAR(36) NOT NULL REFERENCES discovery_searches(id) ON DELETE CASCADE,
    status              VARCHAR(50) DEFAULT 'running' NOT NULL,
    sources_queried     INTEGER DEFAULT 0,
    companies_found     INTEGER DEFAULT 0,
    companies_created   INTEGER DEFAULT 0,
    companies_skipped    INTEGER DEFAULT 0,
    started_at          DATETIME NOT NULL,
    finished_at         DATETIME,
    error_message       TEXT,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL
);

CREATE INDEX ix_discovery_runs_org ON discovery_runs(organization_id);
CREATE INDEX ix_discovery_runs_search ON discovery_runs(search_id);
```

### Modified Tables (1)

#### `companies` — add 2 columns

```sql
ALTER TABLE companies ADD COLUMN discovered_via VARCHAR(100);
-- Values: NULL (manual), 'discovery_pipeline'

ALTER TABLE companies ADD COLUMN discovery_search_id VARCHAR(36)
    REFERENCES discovery_searches(id) ON DELETE SET NULL;

ALTER TABLE companies ADD COLUMN discovery_score FLOAT DEFAULT 0.0 NOT NULL;
-- Range: 0.0 to 1.0
```

### Deleted from original design

- ~~`discovery_candidates`~~ — replaced by `companies` with `discovered_via`
- ~~`discovery_sources`~~ — rate limits handled in-memory

### Criteria JSON Shape (unchanged)

```json
{
  "industry": "fintech",
  "company_size_min": 10,
  "company_size_max": 500,
  "geography": "United States",
  "technologies": ["hubspot", "salesforce"],
  "keywords": ["Series A", "hiring engineer"],
  "exclude_domains": ["example.com"],
  "sources": ["sec_edgar", "google_news_rss", "opencorporates"]
}
```

---

## 5. Revised Endpoint List (7 endpoints)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| `POST` | `/discovery/searches` | Create ICP search | member |
| `GET` | `/discovery/searches` | List saved searches (paginated) | viewer |
| `GET` | `/discovery/searches/{search_id}` | Get search definition | viewer |
| `PATCH` | `/discovery/searches/{search_id}` | Update search criteria | member |
| `DELETE` | `/discovery/searches/{search_id}` | Delete a search | admin |
| `POST` | `/discovery/searches/{search_id}/run` | Trigger discovery run | member |
| `GET` | `/discovery/runs` | List runs for org (paginated, filterable) | viewer |
| `GET` | `/discovery/runs/{run_id}` | Get run status and stats | viewer |

**Total: 8 endpoints** (adding back DELETE since it's trivial and completes CRUD).

### Removed endpoints and rationale

| Removed Endpoint | Why |
|-----------------|-----|
| `GET /discovery/runs/{id}/candidates` | Candidates are companies — use `GET /companies?discovered_via=discovery_pipeline` |
| `POST /discovery/candidates/{id}/accept` | No accept step — companies are created directly by the discovery agent |
| `POST /discovery/candidates/{id}/reject` | Use `PATCH /companies/{id}` to set `status='archived'` |
| `GET /discovery/sources` | Rate limits are in-memory, not persisted |
| `POST /discovery/sources` | Sources configured via env vars, not API |

---

## 6. Revised Services (3 services)

### `DiscoverySearchService`

CRUD for ICP search definitions. Extends `BaseService[DiscoverySearch, DiscoverySearchRepository]`.

### `DiscoveryRunService`

Discovery run lifecycle management. Standalone service (like `LeadRetrievalService`) — not `BaseService` because it manages a specific workflow trigger, not generic CRUD.

### `DiscoveryAgent` (not a service — an agent)

Extends `BaseAgent`. Implements `_run()` with source-specific search methods. Uses existing `EvidenceService` for provenance.

**No `DiscoveryCandidateService`** — companies are created directly.
**No `DiscoverySourceService`** — rate limits are in-memory.

---

## 7. Revised Commit Plan (15 commits)

### Commit 1: Database migration
```
feat(db): add discovery engine tables and company extensions

- Create discovery_searches table
- Create discovery_runs table
- Add discovered_via, discovery_search_id, discovery_score to companies
```
Files: `database/migrations/versions/20260618_0008_create_discovery_tables.py`

### Commit 2: Models
```
feat(models): add DiscoverySearch and DiscoveryRun models

Extend Company model with discovered_via, discovery_search_id,
discovery_score columns.
```
Files: `app/models/discovery_search.py`, `app/models/discovery_run.py`, `app/models/company.py`, `app/models/__init__.py`

### Commit 3: Repositories
```
feat(repositories): add discovery search and run repositories

DiscoverySearchRepository, DiscoveryRunRepository.
Add list_by_organization support.
```
Files: `app/repositories/discovery_search_repository.py`, `app/repositories/discovery_run_repository.py`, `app/repositories/__init__.py`

### Commit 4: Schemas
```
feat(schemas): add discovery engine Pydantic schemas

DiscoverySearchCreate, DiscoverySearchUpdate, DiscoverySearchRead,
DiscoverySearchList, DiscoveryRunRead, DiscoveryRunList,
DiscoverySearchCriteria.
```
Files: `app/schemas/discovery.py`

### Commit 5: Services
```
feat(services): add discovery search and run services

DiscoverySearchService for CRUD.
DiscoveryRunService for lifecycle management.
```
Files: `app/services/discovery_search_service.py`, `app/services/discovery_run_service.py`, `app/services/__init__.py`

### Commit 6: Unit tests (models, schemas, repos, services)
```
test: add discovery engine unit tests

Model tests, schema validation tests, repository query tests,
service CRUD and lifecycle tests.
```
Files: `tests/unit/test_discovery_models.py`, `tests/unit/test_discovery_schemas.py`, `tests/integration/test_discovery_repositories.py`, `tests/integration/test_discovery_services.py`

### Commit 7: API endpoints (searches + runs)
```
feat(api): add discovery search and run API endpoints

8 endpoints: CRUD for searches, run trigger, run listing,
run detail. All tenant-scoped.
```
Files: `app/api/v1/endpoints/discovery.py`, `app/api/dependencies.py`, `app/api/v1/router.py`

### Commit 8: API integration tests
```
test: add discovery API integration tests

CRUD endpoints, tenant isolation, pagination, error handling.
```
Files: `tests/integration/api/test_discovery_api.py`

### Commit 9: DiscoverySettings config
```
feat(config): add DiscoverySettings to configuration

Source priorities, rate limits, API keys, batch limits.
Env-driven, frozen dataclass pattern.
```
Files: `app/core/config.py`

### Commit 10: DiscoveryAgent core + SEC EDGAR source
```
feat(agents): add DiscoveryAgent with SEC EDGAR source

Base agent extending BaseAgent. SEC EDGAR full-text search
(unlimited, no API key). Evidence recording via existing system.
```
Files: `app/agents/discovery/__init__.py`, `app/agents/discovery/agent.py`, `app/agents/discovery/sources/__init__.py`, `app/agents/discovery/sources/sec_edgar.py`

### Commit 11: Google News RSS + OpenCorporates sources
```
feat(agents): add RSS and OpenCorporates discovery sources

Google News RSS for funding/hiring/product signals.
OpenCorporates for company registration data.
Add feedparser dependency.
```
Files: `app/agents/discovery/sources/google_news_rss.py`, `app/agents/discovery/sources/opencorporates.py`, `pyproject.toml`

### Commit 12: Agent unit tests
```
test: add DiscoveryAgent unit tests

Test each source with mocked HTTP.
Test rate limiting. Test error handling.
Test evidence generation.
```
Files: `tests/unit/agents/discovery/__init__.py`, `tests/unit/agents/discovery/test_agent.py`, `tests/unit/agents/discovery/test_sec_edgar.py`, `tests/unit/agents/discovery/test_google_news_rss.py`, `tests/unit/agents/discovery/test_opencorporates.py`

### Commit 13: Discovery pipeline workflow
```
feat(workflows): add discovery_pipeline workflow

Chain: search_criteria → DiscoveryAgent → create companies
with status='needs_review', discovered_via='discovery_pipeline',
discovery_score computed from match quality.
```
Files: `app/workflows/discovery_pipeline.py`, `app/main.py` (register)

### Commit 14: Integration tests for full pipeline
```
test: add discovery pipeline integration tests

Test: search → discover → companies created with correct fields.
Test: tenant isolation. Test: empty results. Test: rate limit.
```
Files: `tests/integration/test_discovery_pipeline.py`

### Commit 15: Documentation
```
docs: add discovery engine architecture and update references

Add docs/discovery_engine_architecture.md.
Update docs/api_reference.md, docs/project_state.md,
docs/project_handoff.md.
```
Files: `docs/discovery_engine_architecture.md`, `docs/api_reference.md`, `docs/project_state.md`, `docs/project_handoff.md`

---

## Appendix: Comparison — Original vs Revised

| Aspect | Original | Revised | Delta |
|--------|----------|---------|-------|
| New tables | 4 | 2 | -2 tables |
| New services | 4 | 2 | -2 services |
| New agents | 1 | 1 | Same |
| New workflows | 1 | 1 | Same |
| API endpoints | 12 | 8 | -4 endpoints |
| Company model changes | 1 column | 3 columns | +2 columns |
| Dependencies | feedparser | feedparser | Same |
| Free sources | 5 (GCSE primary) | 3 (EDGAR primary) | -2, better quality |
| Auto-enrichment | Yes | No (manual) | Simpler |
| Evidence system | New infra | Existing agent pattern | Reuse |
| Dedup logic | Custom cross-table | DB unique constraint | Simpler |
| Accept/reject flow | Custom endpoints | Company status update | Reuse |
| Source management | DB table + API | Env vars | Simpler |
| Total new files | ~35 | ~25 | -10 files |
| Total modified files | ~10 | ~8 | -2 files |
| Estimated effort | 14 days | 10 days | -4 days |
