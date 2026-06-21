# Lead Discovery Engine — Design Document

> **Status: PLANNED**

## 1. Problem Definition

The Irtiqa Intelligence platform can enrich and score companies, but **users must already know the company domain** before triggering the intelligence pipeline. There is no way to discover new companies that match an ideal customer profile (ICP).

### What Exists Today

| Capability | Status |
|---|---|
| Enrich a known company (scrape, detect tech, find intent, score, generate outreach) | ✅ Implemented |
| Retrieve and review scored leads | ✅ Implemented |
| Discover new companies by industry, technology, or behavior | ❌ Missing |
| Bulk find companies matching an ICP | ❌ Missing |
| Auto-enrich newly discovered companies | ❌ Missing |
| Monitor for new companies entering a target segment | ❌ Missing |

### The Gap

The intelligence pipeline is **reactive** — it requires `POST /intelligence/pipeline` with a known `company_id`. There is no proactive discovery mechanism. Users must manually find companies, create company records, then trigger the pipeline. This defeats the purpose of a lead intelligence platform.

### User Stories

1. **As a salesperson**, I want to enter "companies in the fintech industry with 50-200 employees that recently raised Series A" and get a list of enriched, scored leads.
2. **As a marketer**, I want to discover all companies that recently adopted HubSpot or Salesforce in my target industry.
3. **As a growth engineer**, I want to periodically discover new companies matching my ICP and automatically enrich them.
4. **As an SDR**, I want to find contacts at discovered companies with intent signals.

---

## 2. Current Gaps in the Platform

### Gap 1: No Company Discovery

The platform has no mechanism to find companies that match criteria. Every company in the system was created manually via `POST /companies`.

### Gap 2: No External Data Sources

The Deep Scraper Agent only crawls a company's own website. It cannot search the web for companies matching criteria. There are no integrations with free data providers.

### Gap 3: No ICP Definition

There is no structured way to define an "ideal customer profile" (industry + size + technology + geography + signals). Users cannot save and reuse search criteria.

### Gap 4: No Batch Discovery Workflow

The intelligence pipeline processes one company at a time. There is no batch workflow that discovers → creates → enriches → scores a set of companies.

### Gap 5: No Discovery Observability

There is no tracking of where leads came from, what search criteria found them, or when they were last refreshed.

---

## 3. Lead Discovery Engine Architecture

### High-Level Design

```text
┌──────────────────────────────────────────────────────────────┐
│                    Lead Discovery Engine                      │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  ICP Search  │  │   Discovery  │  │   Auto-Enrich     │  │
│  │  Agent       │──│   Agent      │──│   Agent           │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
│        │                 │                    │               │
│        ▼                 ▼                    ▼               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Discovery Pipeline Workflow              │   │
│  │   search_criteria → find_companies → deduplicate →   │   │
│  │   create_companies → enrich (reuse intelligence      │   │
│  │   pipeline) → score → ready for review                │   │
│  └──────────────────────────────────────────────────────┘   │
│        │                                                     │
│        ▼                                                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Free Provider Integrations               │   │
│  │  Google Custom Search · RSS Feeds · OpenCorporates   │   │
│  │  SEC EDGAR · GitHub API · Hunter.io (25/mo free)     │   │
│  │  Website scraping (reuses Deep Scraper)               │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Zero-cost primary**: All core discovery uses free APIs or web scraping.
2. **Reuses existing infrastructure**: Intelligence pipeline for enrichment, existing models for persistence, job system for scheduling.
3. **Graceful degradation**: If a free provider is rate-limited or unavailable, the engine continues with remaining sources.
4. **Deterministic where possible**: Search criteria and deduplication are deterministic. Only external API calls introduce non-determinism.
5. **Tenant-scoped**: All discoveries are scoped to the user's organization.

---

## 4. Database Changes Required

### New Tables

#### `discovery_searches`

Stores ICP search criteria that users save for recurring or one-shot discovery.

```sql
CREATE TABLE discovery_searches (
    id                  VARCHAR(36) PRIMARY KEY,
    organization_id     VARCHAR(36) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    criteria            TEXT NOT NULL,          -- JSON: {industry, company_size, geography, technologies, keywords, exclude_domains}
    status              VARCHAR(50) DEFAULT 'active' NOT NULL,
    last_run_at         DATETIME,
    total_discovered    INTEGER DEFAULT 0,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL
);

CREATE INDEX ix_discovery_searches_org ON discovery_searches(organization_id);
CREATE INDEX ix_discovery_searches_status ON discovery_searches(status);
```

**`criteria` JSON shape:**
```json
{
  "industry": "fintech",
  "company_size_min": 10,
  "company_size_max": 500,
  "geography": "United States",
  "technologies": ["hubspot", "salesforce"],
  "keywords": ["Series A", "hiring engineer"],
  "exclude_domains": ["example.com"],
  "source_types": ["google_search", "google_news", "crunchbase_rss"]
}
```

#### `discovery_runs`

Tracks each execution of a discovery search.

```sql
CREATE TABLE discovery_runs (
    id                  VARCHAR(36) PRIMARY KEY,
    organization_id     VARCHAR(36) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    search_id           VARCHAR(36) NOT NULL REFERENCES discovery_searches(id) ON DELETE CASCADE,
    status              VARCHAR(50) DEFAULT 'running' NOT NULL,
    sources_queried     INTEGER DEFAULT 0,
    candidates_found    INTEGER DEFAULT 0,
    companies_created   INTEGER DEFAULT 0,
    companies_skipped    INTEGER DEFAULT 0,     -- already existed
    started_at          DATETIME NOT NULL,
    finished_at         DATETIME,
    error_message       TEXT,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL
);

CREATE INDEX ix_discovery_runs_org ON discovery_runs(organization_id);
CREATE INDEX ix_discovery_runs_search ON discovery_runs(search_id);
CREATE INDEX ix_discovery_runs_status ON discovery_runs(status);
```

#### `discovery_candidates`

Raw discovered companies before deduplication and enrichment.

```sql
CREATE TABLE discovery_candidates (
    id                  VARCHAR(36) PRIMARY KEY,
    organization_id     VARCHAR(36) NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    run_id              VARCHAR(36) NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
    source_type         VARCHAR(100) NOT NULL,   -- 'google_search', 'news_rss', 'crunchbase', 'opencorporates', etc.
    source_url          VARCHAR(1000),
    discovered_domain   VARCHAR(255),
    company_name        VARCHAR(255),
    industry_hint       VARCHAR(150),
    size_hint           VARCHAR(100),
    geography_hint      VARCHAR(255),
    raw_data            TEXT,                    -- JSON blob from the source
    matched_company_id  VARCHAR(36) REFERENCES companies(id) ON DELETE SET NULL,  -- set if dedup matched existing
    status              VARCHAR(50) DEFAULT 'new' NOT NULL,  -- 'new', 'deduplicated', 'enriched', 'rejected'
    confidence          FLOAT DEFAULT 0.0 NOT NULL,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL
);

CREATE INDEX ix_discovery_candidates_org ON discovery_candidates(organization_id);
CREATE INDEX ix_discovery_candidates_run ON discovery_candidates(run_id);
CREATE INDEX ix_discovery_candidates_status ON discovery_candidates(status);
CREATE INDEX ix_discovery_candidates_domain ON discovery_candidates(discovered_domain);
```

**`status` values:** `new`, `deduplicated`, `enriched`, `rejected`

#### `discovery_sources`

Tracks free provider usage for rate limit management.

```sql
CREATE TABLE discovery_sources (
    id                  VARCHAR(36) PRIMARY KEY,
    source_name         VARCHAR(100) NOT NULL,
    source_type         VARCHAR(100) NOT NULL,
    api_key_hash        VARCHAR(128),          -- stored hashed, optional
    requests_today      INTEGER DEFAULT 0,
    daily_limit         INTEGER DEFAULT 0,
    last_request_at     DATETIME,
    is_enabled          BOOLEAN DEFAULT 1,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL
);

CREATE UNIQUE INDEX uq_discovery_sources_name ON discovery_sources(source_name);
```

### Schema Changes to Existing Tables

**`companies`** — add one column:

```sql
ALTER TABLE companies ADD COLUMN discovered_via VARCHAR(100);
-- Values: NULL (manual), 'discovery_pipeline', 'import'
```

**`jobs`** — no schema change needed. The existing `jobs` table already supports `job_type='workflow'` with a JSON payload, so discovery pipeline jobs use the same mechanism.

### Migration

Single Alembic migration: `20260618_0008_create_discovery_tables.py`

Creates 4 new tables + adds `discovered_via` column to `companies`.

---

## 5. Services Required

### `DiscoverySearchService`

```python
class DiscoverySearchService(BaseService[DiscoverySearch, DiscoverySearchRepository]):
    """CRUD for ICP search definitions."""

    def create(self, organization_id: str, **values) -> DiscoverySearch: ...
    def list(self, *, organization_id: str, ...) -> Sequence[DiscoverySearch]: ...
    def get_required(self, search_id: str) -> DiscoverySearch: ...
    def update(self, search_id: str, **values) -> DiscoverySearch: ...
    def delete(self, search_id: str) -> None: ...
```

Follows existing `BaseService` pattern exactly. Validates criteria JSON on create/update.

### `DiscoveryRunService`

```python
class DiscoveryRunService:
    """Manages discovery execution lifecycle."""

    def start_run(self, *, organization_id: str, search_id: str) -> DiscoveryRun: ...
    def complete_run(self, run_id: str, *, stats: dict) -> None: ...
    def fail_run(self, run_id: str, *, error_message: str) -> None: ...
    def list_runs(self, *, organization_id: str, search_id: str | None = None, ...) -> Sequence[DiscoveryRun]: ...
    def get_run(self, run_id: str) -> DiscoveryRun | None: ...
```

Does not extend `BaseService` (similar to `LeadRetrievalService` — specialized lifecycle management).

### `DiscoveryCandidateService`

```python
class DiscoveryCandidateService:
    """Manages raw discovered candidates."""

    def create_candidate(self, *, organization_id: str, run_id: str, ...) -> DiscoveryCandidate: ...
    def deduplicate(self, organization_id: str, candidates: list[DiscoveryCandidate]) -> list[DiscoveryCandidate]: ...
    def reject_candidate(self, candidate_id: str) -> None: ...
    def list_by_run(self, run_id: str, *, status: str | None = None, ...) -> Sequence[DiscoveryCandidate]: ...
```

### `DiscoverySourceService`

```python
class DiscoverySourceService:
    """Tracks provider usage and rate limits."""

    def can_request(self, source_name: str) -> bool: ...
    def record_request(self, source_name: str) -> None: ...
    def get_usage(self, source_name: str) -> dict: ...
    def ensure_source(self, source_name: str, source_type: str, daily_limit: int) -> None: ...
```

---

## 6. API Endpoints Required

### Discovery Searches

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/discovery/searches` | Create an ICP search (201) |
| `GET` | `/discovery/searches` | List saved searches (paginated) |
| `GET` | `/discovery/searches/{search_id}` | Get a search definition |
| `PATCH` | `/discovery/searches/{search_id}` | Update search criteria |
| `DELETE` | `/discovery/searches/{search_id}` | Delete a search (204) |
| `POST` | `/discovery/searches/{search_id}/run` | Trigger a discovery run (202) |

### Discovery Runs

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/discovery/runs` | List all runs for the org (paginated) |
| `GET` | `/discovery/runs/{run_id}` | Get run status and stats |

### Discovery Candidates

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/discovery/runs/{run_id}/candidates` | List candidates from a run (paginated, filterable by status) |
| `POST` | `/discovery/candidates/{candidate_id}/accept` | Convert candidate to company + trigger enrichment (201) |
| `POST` | `/discovery/candidates/{candidate_id}/reject` | Mark candidate as rejected (204) |

### Discovery Sources

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/discovery/sources` | List configured sources and usage stats |

### Query Parameters

**`GET /discovery/searches`**: `limit`, `offset`, `status`
**`GET /discovery/runs`**: `limit`, `offset`, `search_id`, `status`
**`GET /discovery/runs/{run_id}/candidates`**: `limit`, `offset`, `status` (new/deduplicated/enriched/rejected)

---

## 7. Agent Changes Required

### New Agent: `DiscoveryAgent`

A new agent that searches external sources for companies matching criteria.

```python
class DiscoveryAgent(BaseAgent):
    name = "discovery_agent"
    version = "1.0"

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        # 1. Load search criteria from context.options
        # 2. Query enabled sources in priority order:
        #    a. Google Custom Search API (100/day free)
        #    b. Google News RSS (unlimited, free)
        #    c. OpenCorporates API (free tier: 500/mo)
        #    d. SEC EDGAR full-text search (unlimited, free)
        # 3. For each source, rate-limit check via DiscoverySourceService
        # 4. Parse results into DiscoveryCandidate records
        # 5. Deduplicate against existing companies in the org
        # 6. Return candidate IDs in output_ids["discovery_candidates"]
```

**Key design decisions:**

- The agent does NOT create companies. It only discovers candidates. The user (or batch workflow) decides which to accept.
- Each source is a separate method (`_search_google`, `_search_news_rss`, `_search_opencorporates`, `_search_edgar`).
- Source methods are independently testable.
- If a source fails, the agent logs the failure and continues with other sources.

### No Changes to Existing Agents

Existing agents (Deep Scraper, Technographic, Intent Signal, Intelligence Scoring, Personalization) remain unchanged. The discovery pipeline reuses them for enrichment via the existing `intelligence_pipeline` workflow.

---

## 8. Workflow Changes Required

### New Workflow: `discovery_pipeline`

```text
search_criteria
  │
  ▼
DiscoveryAgent → find candidates via free sources
  │
  ▼
Deduplicate candidates against existing org companies
  │
  ▼
User reviews candidates (or auto-accept if batch mode)
  │
  ▼
For each accepted candidate:
  ├── Create Company record (discovered_via='discovery_pipeline')
  └── Trigger intelligence_pipeline workflow
        ├── Deep Scraper → websites
        ├── Technographic → technologies
        ├── Intent Signal → intent_signals
        ├── Intelligence Scoring → intelligence_scores
        └── Personalization → outreach_messages
```

### No Changes to Existing Workflows

`score_refresh` and `intelligence_pipeline` remain unchanged. The discovery pipeline calls `intelligence_pipeline` as a sub-workflow for each accepted company.

---

## 9. Free-Provider Strategy

### Primary Sources (No API Key Required)

| Source | Free Limit | Data Provided | Implementation |
|--------|-----------|---------------|----------------|
| Google Custom Search API | 100 queries/day | Company search results by keyword, industry, technology | `httpx.AsyncClient` + API key from env |
| Google News RSS | Unlimited | Company news, funding announcements, hiring posts | Feed parsing via `feedparser` (add to deps) |
| SEC EDGAR Full-Text Search | Unlimited | Public company filings, 10-K, 10-Q data | HTTP GET to `efts.sec.gov/LATEST/search-index` |
| OpenCorporates API | 500 lookups/month | Company registration, industry, size, location | REST API, API key from env |

### Secondary Sources (Limited Free Tier)

| Source | Free Limit | Data Provided | Implementation |
|--------|-----------|---------------|----------------|
| Hunter.io | 25 searches/month | Email patterns, company verification | REST API, API key from env |
| GitHub API | 5,000 requests/hour | Companies with active repos, tech signals | REST API, optional token |
| BuiltWith Free Lookup | 100 lookups/month | Technology detection from domain | HTTP scraping |

### Rate Limit Management

The `discovery_sources` table tracks daily/monthly usage. Before each API call, the `DiscoverySourceService.can_request()` method checks if the limit has been reached. If so, the agent skips that source and logs a warning.

```python
# Example rate limit config
SOURCES = {
    "google_custom_search": {"daily_limit": 100, "monthly_limit": None},
    "open_corporates": {"daily_limit": 50, "monthly_limit": 500},
    "hunter_io": {"daily_limit": 1, "monthly_limit": 25},
    "sec_edgar": {"daily_limit": None, "monthly_limit": None},  # unlimited
    "google_news_rss": {"daily_limit": None, "monthly_limit": None},  # unlimited
}
```

### Environment Variables

Added to `app/core/config.py` as a new `DiscoverySettings` dataclass:

```python
@dataclass(frozen=True)
class DiscoverySettings:
    google_search_api_key: str | None = None
    google_search_engine_id: str | None = None
    hunter_api_key: str | None = None
    opencorporates_api_key: str | None = None
    github_token: str | None = None
    enabled_sources: str = "google_search,google_news_rss,sec_edgar"  # comma-separated
    max_candidates_per_run: int = 100
    auto_enrich_on_accept: bool = True
```

---

## 10. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Free API rate limits exhausted | High | Medium | Rate limit tracking in `discovery_sources` table; graceful degradation; log skipped sources |
| Google Custom Search requires billing for production use | Medium | High | Design for 100/day free tier as baseline; optional paid upgrade path |
| Web scraping of directories may violate ToS | Medium | High | Use only officially free APIs; respect robots.txt (existing pattern); no scraping of paywalled content |
| Deduplication false negatives (same company, different domain) | Medium | Medium | Match on normalized name + domain; show candidates for manual review |
| Discovery results are noisy / low quality | High | Medium | Confidence scoring on candidates; user reviews before acceptance; require minimum industry match |
| Large batch runs overwhelm the job system | Low | Medium | Rate limit batch size; use existing job queue with concurrency limits |
| Free provider APIs change or deprecate | Medium | Low | Abstract each source behind an interface; add/remove sources without changing core logic |
| SQLite performance with large candidate sets | Low | Low | Index on domain + org; candidates are ephemeral (archived after processing) |

---

## 11. Sprint Breakdown

### Sprint 1: Foundation (Days 1-3)

**Goal:** Database schema, models, repositories, basic CRUD.

- Create Alembic migration for 4 new tables + `companies.discovered_via` column
- Create SQLAlchemy models: `DiscoverySearch`, `DiscoveryRun`, `DiscoveryCandidate`, `DiscoverySource`
- Create repositories: `DiscoverySearchRepository`, `DiscoveryRunRepository`, `DiscoveryCandidateRepository`, `DiscoverySourceRepository`
- Create Pydantic schemas: Create/Update/Read/List for each new entity
- Create services: `DiscoverySearchService`, `DiscoveryCandidateService`
- Add CRUD API endpoints for discovery searches
- Add unit tests for models, schemas, repositories
- Add integration tests for services and API endpoints

### Sprint 2: Discovery Agent + Free Sources (Days 4-6)

**Goal:** Agent that searches free sources and produces candidates.

- Add `DiscoverySettings` to config
- Create `DiscoverySourceService` with rate limit tracking
- Create `DiscoveryAgent` extending `BaseAgent`
- Implement `_search_google_custom_search` source method
- Implement `_search_google_news_rss` source method (add `feedparser` dependency)
- Implement `_search_sec_edgar` source method
- Implement `_search_opencorporates` source method
- Register `DiscoveryAgent` in agent registry
- Add unit tests for each source method (with mocked HTTP)
- Add integration tests for `DiscoveryAgent` end-to-end

### Sprint 3: Discovery Pipeline Workflow + Deduplication (Days 7-9)

**Goal:** Workflow that chains discovery → dedup → candidate creation.

- Create `DiscoveryRunService` with lifecycle management
- Implement candidate deduplication logic (domain match + fuzzy name match)
- Create `discovery_pipeline` workflow in `app/workflows/discovery_pipeline.py`
- Wire workflow to use `DiscoveryAgent` + deduplication + candidate creation
- Register workflow in workflow registry
- Add API endpoint: `POST /discovery/searches/{search_id}/run`
- Add API endpoint: `GET /discovery/runs/{run_id}/candidates`
- Add API endpoint: `POST /discovery/candidates/{candidate_id}/accept`
- Add API endpoint: `POST /discovery/candidates/{candidate_id}/reject`
- Add API endpoints for listing runs
- Add integration tests for the full discovery pipeline

### Sprint 4: Auto-Enrich + Accept Flow (Days 10-12)

**Goal:** Accept a candidate → create company → trigger intelligence pipeline.

- Implement `accept_candidate` logic: creates `Company` with `discovered_via='discovery_pipeline'`
- Chain to `intelligence_pipeline` workflow for automatic enrichment
- Add API endpoint: `POST /discovery/sources` (admin: configure sources)
- Add `GET /discovery/sources` (view usage stats)
- Add source health check logging
- Add integration tests for accept → enrich → score flow
- Add end-to-end test: search → discover → dedup → accept → enrich → score

### Sprint 5: Polish + Documentation (Days 13-14)

**Goal:** Documentation, edge cases, performance.

- Write `docs/discovery_engine_architecture.md`
- Update `docs/api_reference.md` with discovery endpoints
- Update `docs/project_state.md` with new components
- Update `docs/project_handoff.md` with discovery engine
- Add rate limit reset scheduling (daily counter reset)
- Add candidate archival (auto-archive rejected/old candidates after 30 days)
- Performance testing with large candidate sets
- Full test suite verification

---

## 12. Commit-by-Commit Implementation Plan

### Commit 1: Database migration for discovery tables
```
feat(db): add discovery engine tables migration

Add migration 20260618_0008_create_discovery_tables.py:
- discovery_searches (ICP search criteria)
- discovery_runs (execution tracking)
- discovery_candidates (raw discovered companies)
- discovery_sources (rate limit tracking)
- Add discovered_via column to companies table
```

**Files:**
- `database/migrations/versions/20260618_0008_create_discovery_tables.py`

### Commit 2: SQLAlchemy models
```
feat(models): add discovery engine SQLAlchemy models

Add DiscoverySearch, DiscoveryRun, DiscoveryCandidate,
DiscoverySource models with relationships and indexes.
Add discovered_via to Company model.
```

**Files:**
- `app/models/discovery_search.py`
- `app/models/discovery_run.py`
- `app/models/discovery_candidate.py`
- `app/models/discovery_source.py`
- `app/models/company.py` (add column)
- `app/models/__init__.py` (export)

### Commit 3: Repositories
```
feat(repositories): add discovery engine repositories

Add DiscoverySearchRepository, DiscoveryRunRepository,
DiscoveryCandidateRepository, DiscoverySourceRepository.
```

**Files:**
- `app/repositories/discovery_search_repository.py`
- `app/repositories/discovery_run_repository.py`
- `app/repositories/discovery_candidate_repository.py`
- `app/repositories/discovery_source_repository.py`
- `app/repositories/__init__.py` (export)

### Commit 4: Pydantic schemas
```
feat(schemas): add discovery engine Pydantic schemas

Add Create/Update/Read/List schemas for DiscoverySearch,
DiscoveryRun, DiscoveryCandidate. Add DiscoverySourceRead,
DiscoverySearchCriteria validation schema.
```

**Files:**
- `app/schemas/discovery.py`
- `app/schemas/__init__.py` (if needed)

### Commit 5: DiscoverySearchService + DiscoveryCandidateService
```
feat(services): add discovery search and candidate services

Add DiscoverySearchService (CRUD for ICP searches).
Add DiscoveryCandidateService (deduplication, accept/reject).
```

**Files:**
- `app/services/discovery_search_service.py`
- `app/services/discovery_candidate_service.py`
- `app/services/__init__.py` (export)

### Commit 6: Unit tests for models, schemas, repositories
```
test: add discovery engine unit tests

Add model tests, schema validation tests,
repository query tests for discovery tables.
```

**Files:**
- `tests/unit/test_discovery_models.py`
- `tests/unit/test_discovery_schemas.py`
- `tests/integration/test_discovery_repositories.py`

### Commit 7: Discovery search CRUD API endpoints
```
feat(api): add discovery search CRUD endpoints

POST /discovery/searches — create ICP search
GET /discovery/searches — list searches
GET /discovery/searches/{id} — get search
PATCH /discovery/searches/{id} — update search
DELETE /discovery/searches/{id} — delete search
```

**Files:**
- `app/api/v1/endpoints/discovery.py`
- `app/api/dependencies.py` (add service providers)
- `app/api/v1/router.py` (register router)

### Commit 8: Integration tests for CRUD API
```
test: add discovery search CRUD API tests

Test create, list, get, update, delete endpoints.
Test tenant isolation. Test criteria validation.
```

**Files:**
- `tests/integration/api/test_discovery_search.py`

### Commit 9: DiscoverySettings config
```
feat(config): add DiscoverySettings to configuration

Add DiscoverySettings dataclass with free provider API keys
and rate limit configuration. Add to Settings composition.
```

**Files:**
- `app/core/config.py`

### Commit 10: DiscoverySourceService
```
feat(services): add discovery source rate limit service

Track daily/monthly API usage per source.
Gate requests against configured limits.
Reset daily counters.
```

**Files:**
- `app/services/discovery_source_service.py`
- `app/services/__init__.py` (export)

### Commit 11: DiscoveryAgent with Google Custom Search
```
feat(agents): add DiscoveryAgent with Google Custom Search

Create DiscoveryAgent extending BaseAgent.
Implement Google Custom Search source (100/day free).
Source methods are independently testable.
```

**Files:**
- `app/agents/discovery/__init__.py`
- `app/agents/discovery/agent.py`
- `app/agents/discovery/sources/__init__.py`
- `app/agents/discovery/sources/google_search.py`

### Commit 12: Google News RSS source
```
feat(agents): add Google News RSS source to DiscoveryAgent

Implement RSS feed parsing for company news discovery.
Uses feedparser library (free, no API key).
Detects funding announcements, hiring posts, product launches.
```

**Files:**
- `app/agents/discovery/sources/google_news_rss.py`
- `pyproject.toml` (add feedparser dependency)

### Commit 13: SEC EDGAR source
```
feat(agents): add SEC EDGAR source to DiscoveryAgent

Implement full-text search against SEC EDGAR filings.
Discovers public companies by industry, keyword, SIC code.
No API key required.
```

**Files:**
- `app/agents/discovery/sources/sec_edgar.py`

### Commit 14: OpenCorporates source
```
feat(agents): add OpenCorporates source to DiscoveryAgent

Implement company search via OpenCorporates free API.
Provides company name, industry, size, jurisdiction.
500 lookups/month free.
```

**Files:**
- `app/agents/discovery/sources/opencorporates.py`

### Commit 15: Agent unit tests
```
test: add DiscoveryAgent unit tests

Test each source method with mocked HTTP responses.
Test rate limit checking. Test deduplication logic.
Test error handling and graceful degradation.
```

**Files:**
- `tests/unit/agents/discovery/__init__.py`
- `tests/unit/agents/discovery/test_agent.py`
- `tests/unit/agents/discovery/test_google_search.py`
- `tests/unit/agents/discovery/test_google_news_rss.py`
- `tests/unit/agents/discovery/test_sec_edgar.py`
- `tests/unit/agents/discovery/test_opencorporates.py`

### Commit 16: DiscoveryRunService
```
feat(services): add discovery run lifecycle service

Track discovery run status, statistics, and timing.
Manage run-to-search relationships.
```

**Files:**
- `app/services/discovery_run_service.py`
- `app/services/__init__.py` (export)

### Commit 17: Deduplication logic
```
feat: add candidate deduplication logic

Match candidates against existing org companies by:
1. Exact domain match
2. Normalized name match (fuzzy)
Mark matched candidates as 'deduplicated' with linked company_id.
```

**Files:**
- `app/services/discovery_candidate_service.py` (extend)

### Commit 18: Discovery pipeline workflow
```
feat(workflows): add discovery_pipeline workflow

Chain: search_criteria → DiscoveryAgent → dedup → candidate creation.
Register in workflow registry.
```

**Files:**
- `app/workflows/discovery_pipeline.py`
- `app/main.py` (register workflow)

### Commit 19: Discovery API endpoints (runs, candidates, accept, reject)
```
feat(api): add discovery runs, candidates, accept/reject endpoints

GET /discovery/runs — list runs
GET /discovery/runs/{id} — get run
GET /discovery/runs/{id}/candidates — list candidates
POST /discovery/candidates/{id}/accept — accept + create company
POST /discovery/candidates/{id}/reject — reject candidate
POST /discovery/searches/{id}/run — trigger discovery run
```

**Files:**
- `app/api/v1/endpoints/discovery.py` (extend)

### Commit 20: Accept flow — create company + trigger enrichment
```
feat: implement candidate accept flow

Accept candidate → create Company record
→ trigger intelligence_pipeline workflow.
Set discovered_via='discovery_pipeline' on new companies.
```

**Files:**
- `app/services/discovery_candidate_service.py` (extend)

### Commit 21: Discovery source management endpoints
```
feat(api): add discovery source management endpoints

GET /discovery/sources — list sources and usage
POST /discovery/sources — configure a source (admin)
```

**Files:**
- `app/api/v1/endpoints/discovery.py` (extend)

### Commit 22: Integration tests for full pipeline
```
test: add full discovery pipeline integration tests

Test: search → discover → dedup → accept → enrich → score.
Test: tenant isolation across discovery flows.
Test: rate limit enforcement.
Test: empty result handling.
```

**Files:**
- `tests/integration/test_discovery_pipeline.py`
- `tests/integration/api/test_discovery_api.py`

### Commit 23: Documentation
```
docs: add discovery engine architecture documentation

Add docs/discovery_engine_architecture.md.
Update docs/api_reference.md with discovery endpoints.
Update docs/project_state.md with new components.
Update docs/project_handoff.md with discovery engine.
```

**Files:**
- `docs/discovery_engine_architecture.md`
- `docs/api_reference.md` (extend)
- `docs/project_state.md` (extend)
- `docs/project_handoff.md` (extend)

### Commit 24: Candidate archival and rate limit reset
```
feat: add candidate archival and rate limit daily reset

Auto-archive rejected candidates after 30 days.
Daily reset of source request counters.
```

**Files:**
- `app/services/discovery_source_service.py` (extend)
- `app/services/discovery_candidate_service.py` (extend)

### Commit 25: Full test suite verification
```
test: verify full test suite passes

Run complete test suite. All existing tests unchanged.
New discovery tests pass. No regressions.
```

**No file changes** — verification only.

---

## Appendix A: File Inventory

### New Files (Estimated: 35)

| Layer | Files |
|-------|-------|
| Migration | 1 |
| Models | 4 |
| Repositories | 4 |
| Schemas | 1 |
| Services | 4 |
| Agent | 5 (init + agent + 3 source modules) |
| Workflow | 1 |
| API endpoints | 1 |
| Config | 0 (extend existing) |
| Tests | 14 |
| Documentation | 1 |

### Modified Files (Estimated: 10)

| File | Change |
|------|--------|
| `app/models/company.py` | Add `discovered_via` column |
| `app/models/__init__.py` | Export new models |
| `app/repositories/__init__.py` | Export new repositories |
| `app/services/__init__.py` | Export new services |
| `app/api/dependencies.py` | Add service providers |
| `app/api/v1/router.py` | Register discovery router |
| `app/main.py` | Register DiscoveryAgent + workflow |
| `app/core/config.py` | Add DiscoverySettings |
| `pyproject.toml` | Add feedparser dependency |
| `app/agents/registry.py` | Auto-register DiscoveryAgent |

## Appendix B: Dependency Additions

| Package | Purpose | Cost |
|---------|---------|------|
| `feedparser` | RSS/Atom feed parsing for Google News | Free, open source |
| `httpx` | Already in project (for async HTTP) | Free |
| `difflib` (stdlib) | Fuzzy name matching for deduplication | Free |

No paid dependencies required.

## Appendix C: API Call Budget

Per discovery run with all sources enabled:

| Source | Calls | Free Limit | Cost |
|--------|-------|-----------|------|
| Google Custom Search | 1-10 | 100/day | $0 |
| Google News RSS | 1-5 | Unlimited | $0 |
| SEC EDGAR | 1-3 | Unlimited | $0 |
| OpenCorporates | 1-5 | 500/month | $0 |
| **Total per run** | **4-23** | | **$0** |

At 10 runs/day: ~230 API calls/day, well within free limits.
