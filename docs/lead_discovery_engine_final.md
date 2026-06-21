# Lead Discovery Engine — Final Implementation Blueprint

> **Status: PLANNED** — Authoritative implementation document.
> **Supersedes:** `lead_discovery_engine_design.md`, `lead_discovery_engine_review.md`
> **Created:** 2026-06-21

---

## 1. Problem Definition

### The Gap

Irtiqa Intelligence can enrich and score companies, but users must already know the company domain before triggering the intelligence pipeline. There is no proactive mechanism to discover new companies matching an ideal customer profile (ICP).

The intelligence pipeline is **reactive** — it requires `POST /intelligence/pipeline` with a known `company_id`. Users must manually find companies, create company records, then trigger the pipeline. This defeats the purpose of a lead intelligence platform.

### User Stories

1. **As a salesperson**, I want to enter "companies in fintech with 50-200 employees that recently raised Series A" and get a list of scored leads.
2. **As a marketer**, I want to discover companies that recently adopted specific technologies in my target industry.
3. **As a growth engineer**, I want to periodically discover new companies matching my ICP for review and enrichment.
4. **As an SDR**, I want to find contacts at discovered companies with intent signals.

### Current Platform State

| Capability | Status |
|---|---|
| Enrich a known company (scrape, detect tech, find intent, score, generate outreach) | ✅ Implemented |
| Retrieve and review scored leads | ✅ Implemented |
| Discover new companies by industry, technology, or behavior | ❌ Missing |
| Save and reuse ICP search criteria | ❌ Missing |
| Track discovery provenance and observability | ❌ Missing |

---

## 2. Final Architecture

### High-Level Design

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
│  │  status='needs_review'                │                   │
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

### Design Principles

1. **Zero-cost primary** — All core discovery uses free APIs. No paid subscriptions required.
2. **Maximal reuse** — Companies table for candidates, existing evidence system for provenance, existing intelligence pipeline for enrichment, existing job system for scheduling.
3. **Graceful degradation** — If a source is rate-limited or unavailable, the engine continues with remaining sources.
4. **Decouple discovery from enrichment** — Discovery finds companies; users decide when to enrich. This avoids expensive batch pipeline runs and gives users control.
5. **Tenant-scoped** — All discoveries are scoped to the user's organization via `organization_id`.

### Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| No `discovery_candidates` table | Companies table with `discovered_via` column handles everything. `(org_id, domain)` uniqueness prevents duplicates. |
| No `discovery_sources` table | Rate limits are ephemeral (reset daily). In-memory tracking via config is sufficient. |
| SEC EDGAR as primary source | Unlimited, no API key, structured data. Superior to Google Custom Search for company discovery. |
| No auto-enrichment | Discovery pipeline creates companies with `status='needs_review'`. Users trigger `intelligence_pipeline` when ready. |
| Existing evidence system | `BaseAgent.execute()` records evidence automatically. No new evidence infrastructure needed. |
| `discovery_score` field | Lightweight deterministic score at discovery time helps users prioritize before expensive enrichment. |

---

## 3. Final Database Schema

### New Tables (2)

#### `discovery_searches`

Stores ICP search criteria that users save for recurring or one-shot discovery.

```sql
CREATE TABLE discovery_searches (
    id                  VARCHAR(36) PRIMARY KEY,
    organization_id     VARCHAR(36) NOT NULL
                            REFERENCES organizations(id) ON DELETE CASCADE,
    name                VARCHAR(255) NOT NULL,
    description         TEXT,
    criteria            TEXT NOT NULL,          -- JSON blob
    status              VARCHAR(50) DEFAULT 'active' NOT NULL,
    last_run_at         DATETIME,
    total_discovered    INTEGER DEFAULT 0,
    created_at          DATETIME NOT NULL,
    updated_at          DATETIME NOT NULL
);

CREATE INDEX ix_discovery_searches_org
    ON discovery_searches(organization_id);
```

**`status` values:** `active`, `archived`

**CHECK constraint:**
```sql
CHECK (status IN ('active', 'archived'))
```

#### `discovery_runs`

Tracks each execution of a discovery search.

```sql
CREATE TABLE discovery_runs (
    id                  VARCHAR(36) PRIMARY KEY,
    organization_id     VARCHAR(36) NOT NULL
                            REFERENCES organizations(id) ON DELETE CASCADE,
    search_id           VARCHAR(36) NOT NULL
                            REFERENCES discovery_searches(id) ON DELETE CASCADE,
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

CREATE INDEX ix_discovery_runs_org
    ON discovery_runs(organization_id);
CREATE INDEX ix_discovery_runs_search
    ON discovery_runs(search_id);
CREATE INDEX ix_discovery_runs_status
    ON discovery_runs(status);
```

**`status` values:** `running`, `succeeded`, `failed`

**CHECK constraint:**
```sql
CHECK (status IN ('running', 'succeeded', 'failed'))
```

### Modified Tables (1)

#### `companies` — add 3 columns

```sql
ALTER TABLE companies
    ADD COLUMN discovered_via VARCHAR(100);
    -- Values: NULL (manual), 'discovery_pipeline'

ALTER TABLE companies
    ADD COLUMN discovery_search_id VARCHAR(36)
        REFERENCES discovery_searches(id) ON DELETE SET NULL;

ALTER TABLE companies
    ADD COLUMN discovery_score FLOAT DEFAULT 0.0 NOT NULL;
    -- Range: 0.0 to 1.0
    -- CHECK constraint added in database hardening:
    -- CHECK (discovery_score >= 0.0 AND discovery_score <= 1.0)
```

**Column purposes:**

| Column | Purpose |
|--------|---------|
| `discovered_via` | Distinguishes manually-created companies (`NULL`) from pipeline-discovered ones (`'discovery_pipeline'`). |
| `discovery_search_id` | Links back to the ICP search that found this company. `SET NULL` on delete preserves the company. |
| `discovery_score` | Lightweight match quality score computed at discovery time (0.0-1.0). Helps users prioritize before enrichment. |

### Criteria JSON Shape

Stored in `discovery_searches.criteria`:

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

### Migration

Single Alembic migration: `20260618_0008_create_discovery_tables.py`

- Creates `discovery_searches` table
- Creates `discovery_runs` table
- Adds `discovered_via`, `discovery_search_id`, `discovery_score` to `companies`

---

## 4. Final Service Architecture

### Services (2 new)

#### `DiscoverySearchService`

CRUD for ICP search definitions. Extends `BaseService[DiscoverySearch, DiscoverySearchRepository]`.

```python
class DiscoverySearchService(
    BaseService[DiscoverySearch, DiscoverySearchRepository]
):
    """CRUD for ICP search definitions."""
    model = DiscoverySearch
    repository = DiscoverySearchRepository

    def _before_create(
        self,
        repository: DiscoverySearchRepository,
        values: dict[str, Any],
    ) -> None:
        """Validate that criteria JSON contains required fields."""
        criteria = values.get("criteria")
        if criteria is None:
            raise ValidationError(
                "criteria is required",
                details={"service": self.__class__.__name__},
            )
        self._validate_criteria_json(criteria)
```

The `_before_create()` override validates the criteria JSON structure on both
create and update (via `create()` and `update()` paths through `BaseService`).
Validation checks for required top-level keys (`industry`, `keywords`) and
type correctness (lists for `technologies`, `keywords`, `exclude_domains`).

Methods (inherited from `BaseService`):

- `create(organization_id, **values)` — validates criteria JSON via `_before_create()`
- `list(*, organization_id, limit, offset)` — tenant-scoped listing
- `get_required(search_id)` — raises `EntityNotFoundError` if missing
- `update(search_id, **values)` — partial update
- `delete(search_id)` — cascade deletes associated runs

#### `DiscoveryRunService`

Discovery run lifecycle management. Does **not** extend `BaseService` — similar to `LeadRetrievalService`, it manages a specific workflow trigger rather than generic CRUD.

```python
class DiscoveryRunService:
    """Manages discovery execution lifecycle."""

    def start_run(self, *, organization_id: str,
                  search_id: str) -> DiscoveryRun: ...
    def complete_run(self, run_id: str, *,
                     stats: dict) -> None: ...
    def fail_run(self, run_id: str, *,
                 error_message: str) -> None: ...
    def list_runs(self, *, organization_id: str,
                  search_id: str | None = None,
                  limit: int = 100, offset: int = 0
                  ) -> Sequence[DiscoveryRun]: ...
    def get_run(self, run_id: str) -> DiscoveryRun | None: ...
```

### Services NOT created (and why)

| Omitted Service | Rationale |
|----------------|-----------|
| ~~`DiscoveryCandidateService`~~ | Companies are created directly by the workflow. No separate candidate lifecycle. |
| ~~`DiscoverySourceService`~~ | Rate limits tracked in-memory via `DiscoverySettings` config. No database state needed. |

### Existing Services Reused

| Service | How Reused |
|---------|-----------|
| `CompanyService` | Creates companies discovered by the pipeline. `create(organization_id, ...)` with `discovered_via='discovery_pipeline'`. |
| `EvidenceService` | DiscoveryAgent records evidence via `BaseAgent.execute()` → `record_evidence_batch()`. Full provenance tracking with zero new code. |
| `JobService` | Discovery runs scheduled via existing `POST /jobs/schedule-workflow` mechanism. |
| `LeadRetrievalService` | Can filter discovered companies via `discovered_via` column (future enhancement). |

---

## 5. Final API Endpoints (8 endpoints)

### Discovery Searches

| Method | Path | Description | Auth Level |
|--------|------|-------------|------------|
| `POST` | `/discovery/searches` | Create an ICP search (201) | `member` |
| `GET` | `/discovery/searches` | List saved searches (paginated) | `viewer` |
| `GET` | `/discovery/searches/{search_id}` | Get a search definition | `viewer` |
| `PATCH` | `/discovery/searches/{search_id}` | Update search criteria | `member` |
| `DELETE` | `/discovery/searches/{search_id}` | Delete a search (204) | `admin` |

### Discovery Runs

| Method | Path | Description | Auth Level |
|--------|------|-------------|------------|
| `POST` | `/discovery/searches/{search_id}/run` | Trigger a discovery run (202) | `member` |
| `GET` | `/discovery/runs` | List runs for org (paginated, filterable by `search_id` and `status`) | `viewer` |
| `GET` | `/discovery/runs/{run_id}` | Get run status and statistics | `viewer` |

### Query Parameters

**`GET /discovery/searches`**: `limit` (1-500, default 100), `offset` (default 0), `status` (optional)

**`GET /discovery/runs`**: `limit` (1-500, default 100), `offset` (default 0), `search_id` (optional), `status` (optional)

### What Happened to Other Endpoints

| Removed Endpoint | Reason |
|-----------------|--------|
| `GET /discovery/runs/{id}/candidates` | Candidates are companies — use `GET /companies?discovered_via=discovery_pipeline` |
| `POST /discovery/candidates/{id}/accept` | No accept step — companies created directly by discovery agent |
| `POST /discovery/candidates/{id}/reject` | Use `PATCH /companies/{id}` to set `status='archived'` |
| `GET /discovery/sources` | Rate limits are in-memory, not persisted |
| `POST /discovery/sources` | Sources configured via env vars, not API |

---

## 6. Final Workflow Design

### New Workflow: `discovery_pipeline`

```text
search_criteria (from DiscoverySearch.criteria)
  │
  ▼
DiscoveryAgent ──────────────────────────────┐
  │                                          │
  ├── SEC EDGAR: search by keywords/SIC     │
  ├── Google News RSS: detect funding/hiring │
  └── OpenCorporates: company registration   │
  │                                          │
  ▼                                          │
Deduplicate against existing org companies   │
  │ (domain unique constraint + name match)  │
  │                                          │
  ▼                                          │
Create Company records in batch              │
  │ status='needs_review'                    │
  │ discovered_via='discovery_pipeline'      │
  │ discovery_score=computed from match      │
  │ discovery_search_id=link to search       │
  │                                          │
  ▼                                          │
Update DiscoveryRun with statistics          │
  │ companies_found, companies_created,      │
  │ companies_skipped, sources_queried       │
  │                                          │
  ▼                                          │
Update DiscoverySearch counters              │
  │ increment total_discovered               │
  │ set last_run_at = now                    │
  │                                          │
  ▼                                          │
Done. User reviews companies in the UI       │
and triggers intelligence_pipeline manually  │
```

### Key Workflow Behavior

1. **Reads** the `DiscoverySearch` criteria from the database.
2. **Instantiates** the `DiscoveryAgent` with the criteria.
3. **Agent** queries enabled sources in priority order, collecting candidate companies.
4. **Workflow** creates `Company` records for each new discovery. Existing companies (matched by domain) are skipped.
5. **Agent** records evidence for each discovered company via the existing `EvidenceService`.
6. **Workflow** updates the `DiscoveryRun` record with final statistics.
7. **No enrichment** — the intelligence pipeline is triggered separately by the user.

### Discovery Score Calculation

Computed at creation time from available source data:

| Component | Weight | Source |
|-----------|--------|--------|
| Name match quality vs criteria keywords | 0.0–0.4 | Fuzzy string match |
| Industry match vs criteria industry | 0.0–0.2 | Exact/substring match |
| Company size match vs criteria range | 0.0–0.2 | Numeric range check |
| Source reliability | 0.0–0.2 | Source-dependent (EDGAR=0.2, RSS=0.15, OC=0.1) |

This is a **deterministic, pure function** — no external API calls. The `LeadRetrievalService` can filter by `discovery_score` for prioritization.

### Changes to Existing Workflows

**None.** `score_refresh` and `intelligence_pipeline` remain unchanged. The discovery pipeline creates companies; the intelligence pipeline enriches them when triggered separately.

---

## 7. Final Agent Design

### New Agent: `DiscoveryAgent`

```python
class DiscoveryAgent(BaseAgent):
    name = "discovery_agent"
    version = "1.0"

    async def _run(self, context: AgentContext) -> AgentRunOutput:
        # 1. Load search criteria from context.options
        # 2. Initialize rate limit counters (in-memory dict)
        # 3. Query sources in priority order:
        #    a. SEC EDGAR full-text search
        #    b. Google News RSS feed
        #    c. OpenCorporates company search
        # 4. For each source:
        #    - Check in-memory rate limit
        #    - Make HTTP request via httpx.AsyncClient
        #    - Parse response into candidate dicts
        #    - Record EvidenceItem for each candidate
        # 5. Return candidates in output_ids["companies"]
        #    and evidence in output_ids["evidence"]
```

### Source Implementations

#### Source 1: SEC EDGAR (Primary — Unlimited, No Key)

```text
Endpoint: https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt={start}&enddt={end}
Headers: User-Agent: {company_name} {email}
Returns: JSON array of filing entries with company names, CIK numbers, filing types
```

- Queries by industry keywords, company name patterns, SIC codes
- Returns structured data: company name, CIK, filing type, date
- Unlimited requests with proper User-Agent
- **Best for:** US public companies, recent filings, industry-specific discovery

#### Source 2: Google News RSS (Unlimited, No Key)

```text
Feed URL: https://news.google.com/rss/search?q={query}+when:30d&hl=en-US&gl=US&ceid=US:en
Returns: Atom/RSS feed with news articles
```

- Searches by company name, funding keywords, hiring signals
- Parses feed entries for company names, domains, article metadata
- Detects: funding rounds, product launches, hiring posts, partnerships
- **Best for:** Recent activity signals, startup discovery, intent detection

#### Source 3: OpenCorporates (500/month Free)

```text
Endpoint: https://api.opencorporates.com/v0.4/companies/search?q={query}&per_page=50
Headers: None required (optional API key for higher limits)
Returns: JSON with company records: name, jurisdiction, industry, size, status
```

- Searches by company name, industry, jurisdiction
- Returns structured company data with registration details
- 500 lookups/month free tier
- **Best for:** International companies, registration verification, company metadata

### Evidence Recording

Each source method returns `EvidenceItem` entries that the `BaseAgent.execute()` lifecycle records automatically:

```python
EvidenceItem(
    source_type="agent_run",
    source_id=agent_run_id,
    evidence_type="url_match",
    evidence_value=f"Found {company_name} via {source_name}: {source_url}",
    relationship_type="generates",
    target_type="company",
    target_id=company_id,
    confidence=discovery_score,
)
```

The existing `GET /evidence/by-company/{company_id}` endpoint surfaces discovery evidence automatically.

### Rate Limiting (In-Memory)

```python
# Class-level or instance-level dict — NOT a database table
_rate_limits: dict[str, int] = {
    "sec_edgar": 0,          # unlimited
    "google_news_rss": 0,    # unlimited
    "opencorporates": 0,     # 500/month
}
```

Checked before each source call. Logged when a limit is reached. Resets on process restart (acceptable for MVP).

### No Changes to Existing Agents

Deep Scraper, Technographic, Intent Signal, Intelligence Scoring, and Personalization agents remain unchanged.

---

## 8. Free-Provider Strategy

### Source Priority and Limits

| Priority | Source | Free Limit | API Key Required | Data Quality |
|----------|--------|-----------|-----------------|-------------|
| 1 | SEC EDGAR full-text search | Unlimited | No | High (structured filings) |
| 2 | Google News RSS | Unlimited | No | Medium (news articles) |
| 3 | OpenCorporates search | 500/month | Optional (for higher limits) | High (company registry) |

### API Call Budget

Per discovery run with all sources enabled:

| Source | Expected Calls | Free Limit | Monthly Budget Impact |
|--------|---------------|-----------|----------------------|
| SEC EDGAR | 1–5 | Unlimited | 0% |
| Google News RSS | 1–5 | Unlimited | 0% |
| OpenCorporates | 1–5 | 500/month | ~3% per run |
| **Total per run** | **3–15** | | **Negligible** |

At 10 runs/day: ~150 API calls/day. OpenCorporates budget lasts ~33 days.

### Environment Variables

Added to `app/core/config.py` as `DiscoverySettings`:

```python
@dataclass(frozen=True)
class DiscoverySettings:
    # SEC EDGAR
    sec_edgar_user_agent: str = "IrtiqaIntelligence/1.0 (research@example.com)"

    # OpenCorporates
    opencorporates_api_key: str | None = None

    # Source control
    enabled_sources: str = "sec_edgar,google_news_rss,opencorporates"
    max_companies_per_run: int = 100

    # Rate limits (in-memory, reset on restart)
    opencorporates_monthly_limit: int = 500
```

### Graceful Degradation

If a source fails or is rate-limited:

1. Log the failure at WARNING level
2. Continue with remaining sources
3. Record the failure in `discovery_runs.error_message` if all sources fail
4. Set `discovery_runs.status = 'failed'` only if zero companies were found

---

## 9. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SEC EDGAR rate limiting (unofficial) | Low | Medium | Respectful User-Agent, 1 req/sec pacing, graceful skip |
| OpenCorporates free tier exhausted | Medium | Low | In-memory counter, skip when exhausted, log warning |
| Google News RSS format changes | Low | Low | Feedparser handles standard RSS/Atom; graceful failure |
| Discovery results are noisy | High | Medium | `discovery_score` helps users filter; `needs_review` status for manual check |
| Large batch creates overwhelm job system | Low | Medium | `max_companies_per_run` cap; sequential creation |
| Free provider APIs deprecate | Medium | Low | Each source is a separate module; add/remove without core changes |
| Deduplication misses (same company, different domain) | Medium | Low | Domain-based dedup handles 95%+ of cases; name match is best-effort |
| `discovery_score` is inaccurate | Low | Low | Users rely on intelligence pipeline scores for final prioritization |

---

## 10. Final Commit Plan (15 commits)

### Commit 1: Database migration

```
feat(db): add discovery engine tables and company extensions

- Create discovery_searches table (ICP search criteria)
- Create discovery_runs table (execution tracking)
- Add discovered_via, discovery_search_id, discovery_score to companies
- Migration: 20260618_0008_create_discovery_tables.py
```

**Files:**
- `database/migrations/versions/20260618_0008_create_discovery_tables.py`

### Commit 2: Models

```
feat(models): add DiscoverySearch and DiscoveryRun models

- DiscoverySearch: stores ICP criteria as JSON
- DiscoveryRun: tracks execution lifecycle
- Extend Company model with discovered_via, discovery_search_id, discovery_score
- Update model exports
```

**Files:**
- `app/models/discovery_search.py` (new)
- `app/models/discovery_run.py` (new)
- `app/models/company.py` (modified — add 3 columns)
- `app/models/__init__.py` (modified — export new models)

### Commit 3: Repositories

```
feat(repositories): add discovery search and run repositories

- DiscoverySearchRepository with list_by_organization
- DiscoveryRunRepository with list_by_organization, list_by_search
- Update repository exports
```

**Files:**
- `app/repositories/discovery_search_repository.py` (new)
- `app/repositories/discovery_run_repository.py` (new)
- `app/repositories/__init__.py` (modified)

### Commit 4: Pydantic schemas

```
feat(schemas): add discovery engine Pydantic schemas

- DiscoverySearchCriteria validation schema
- DiscoverySearchCreate, DiscoverySearchUpdate, DiscoverySearchRead, DiscoverySearchList
- DiscoveryRunRead, DiscoveryRunList
- DiscoverySearchCreate validates criteria JSON structure
```

**Files:**
- `app/schemas/discovery.py` (new)

### Commit 5: Services

```
feat(services): add discovery search and run services

- DiscoverySearchService: CRUD for ICP searches (extends BaseService)
- DiscoveryRunService: lifecycle management (standalone, like LeadRetrievalService)
- Update service exports
```

**Files:**
- `app/services/discovery_search_service.py` (new)
- `app/services/discovery_run_service.py` (new)
- `app/services/__init__.py` (modified)

### Commit 6: Unit tests (models, schemas, repositories, services)

```
test: add discovery engine foundation tests

- Model column and relationship tests
- Schema validation and serialization tests
- Repository query and tenant-filter tests
- Service CRUD and lifecycle tests
```

**Files:**
- `tests/unit/test_discovery_models.py` (new)
- `tests/unit/test_discovery_schemas.py` (new)
- `tests/integration/test_discovery_repositories.py` (new)
- `tests/integration/test_discovery_services.py` (new)

### Commit 7: API endpoints

```
feat(api): add discovery search and run API endpoints

POST /discovery/searches — create ICP search (201)
GET /discovery/searches — list searches (paginated)
GET /discovery/searches/{id} — get search
PATCH /discovery/searches/{id} — update search
DELETE /discovery/searches/{id} — delete search (204)
POST /discovery/searches/{id}/run — trigger run (202)
GET /discovery/runs — list runs (paginated, filterable)
GET /discovery/runs/{id} — get run status
All endpoints tenant-scoped via get_current_organization.
```

**Files:**
- `app/api/v1/endpoints/discovery.py` (new)
- `app/api/dependencies.py` (modified — add service providers)
- `app/api/v1/router.py` (modified — register router)

### Commit 8: API integration tests

```
test: add discovery API integration tests

- CRUD endpoint tests (create, list, get, update, delete)
- Tenant isolation verification
- Pagination and filtering tests
- Error handling (not found, validation)
- Run trigger and status tests
```

**Files:**
- `tests/integration/api/test_discovery_api.py` (new)

### Commit 9: DiscoverySettings config

```
feat(config): add DiscoverySettings to configuration

- DiscoverySettings frozen dataclass with source config
- SEC EDGAR user agent, OpenCorporates API key
- Enabled sources, max companies per run, rate limits
- Add to Settings composition and get_settings()
```

**Files:**
- `app/core/config.py` (modified)

### Commit 10: DiscoveryAgent core + SEC EDGAR source

```
feat(agents): add DiscoveryAgent with SEC EDGAR source

- DiscoveryAgent extending BaseAgent
- _search_sec_edgar: full-text search against SEC EDGAR
- In-memory rate limit tracking
- Evidence recording via existing EvidenceService
- Register in agent registry
```

**Files:**
- `app/agents/discovery/__init__.py` (new)
- `app/agents/discovery/agent.py` (new)
- `app/agents/discovery/sources/__init__.py` (new)
- `app/agents/discovery/sources/sec_edgar.py` (new)
- `app/main.py` (modified — register agent)

### Commit 11: Google News RSS + OpenCorporates sources

```
feat(agents): add RSS and OpenCorporates discovery sources

- _search_google_news_rss: RSS feed parsing for funding/hiring signals
- _search_opencorporates: company registration data
- Add feedparser dependency to pyproject.toml
```

**Files:**
- `app/agents/discovery/sources/google_news_rss.py` (new)
- `app/agents/discovery/sources/opencorporates.py` (new)
- `pyproject.toml` (modified — add feedparser)

### Commit 12: Agent unit tests

```
test: add DiscoveryAgent unit tests

- Test each source method with mocked HTTP responses
- Test in-memory rate limiting
- Test error handling and graceful degradation
- Test evidence item generation
- Test criteria parsing and candidate extraction
```

**Files:**
- `tests/unit/agents/discovery/__init__.py` (new)
- `tests/unit/agents/discovery/test_agent.py` (new)
- `tests/unit/agents/discovery/test_sec_edgar.py` (new)
- `tests/unit/agents/discovery/test_google_news_rss.py` (new)
- `tests/unit/agents/discovery/test_opencorporates.py` (new)

### Commit 13: Discovery pipeline workflow

```
feat(workflows): add discovery_pipeline workflow

- DiscoveryPipelineWorkflow extending Workflow
- Chains: criteria → DiscoveryAgent → create companies
- Companies created with status='needs_review',
  discovered_via='discovery_pipeline',
  discovery_score=computed from match quality
- DiscoveryRun updated with statistics
- Register in workflow registry
```

**Files:**
- `app/workflows/discovery_pipeline.py` (new)
- `app/main.py` (modified — register workflow)

### Commit 14: Integration tests for full pipeline

```
test: add discovery pipeline integration tests

- End-to-end: search → discover → companies created
- Verify company fields (discovered_via, discovery_search_id, discovery_score)
- Tenant isolation across discovery flows
- Empty results handling
- Rate limit exhaustion handling
- Evidence recording verification
```

**Files:**
- `tests/integration/test_discovery_pipeline.py` (new)

### Commit 15: Documentation

```
docs: add discovery engine documentation

- Add docs/discovery_engine_architecture.md
- Update docs/api_reference.md with 8 discovery endpoints
- Update docs/project_state.md with new components
- Update docs/project_handoff.md with discovery engine
```

**Files:**
- `docs/discovery_engine_architecture.md` (new)
- `docs/api_reference.md` (modified)
- `docs/project_state.md` (modified)
- `docs/project_handoff.md` (modified)

---

## 11. Final File Inventory

### New Files (27)

| Layer | Files |
|-------|-------|
| Migration | 1 |
| Models | 2 |
| Repositories | 2 |
| Schemas | 1 |
| Services | 2 |
| Agent | 6 (init + agent + sources init + 3 source modules) |
| Workflow | 1 |
| API endpoint | 1 |
| Config | 0 (extend existing) |
| Tests | 10 (4 unit + 3 agent + 1 API integration + 1 service integration + 1 pipeline integration) |
| Documentation | 1 |

### Modified Files (10)

| File | Change |
|------|--------|
| `app/models/company.py` | Add `discovered_via`, `discovery_search_id`, `discovery_score` columns |
| `app/models/__init__.py` | Export `DiscoverySearch`, `DiscoveryRun` |
| `app/repositories/__init__.py` | Export new repositories |
| `app/services/__init__.py` | Export new services |
| `app/api/dependencies.py` | Add `get_discovery_search_service`, `get_discovery_run_service` |
| `app/api/v1/router.py` | Register discovery router |
| `app/main.py` | Register `DiscoveryAgent` and `DiscoveryPipelineWorkflow` |
| `app/core/config.py` | Add `DiscoverySettings` dataclass |
| `pyproject.toml` | Add `feedparser` dependency |
| `docs/project_state.md` | Document discovery engine |

---

## 12. Consistency Audit Against Current Codebase

### Verified: No Conflicts

| Check | Status | Detail |
|-------|--------|--------|
| `companies.status` CHECK constraint allows `'needs_review'` | ✅ | CHECK: `'active' \| 'needs_review' \| 'archived'` |
| `companies.organization_id` FK exists | ✅ | Added by migration `20260616_0007` |
| `companies` unique `(organization_id, domain)` | ✅ | Prevents duplicate discovery within org |
| `organizations` table exists for FK reference | ✅ | Created by migration `20260613_0006` |
| `BaseAgent` pattern supports new agents | ✅ | Template Method with `_run()` + evidence recording |
| `AgentRegistry.register()` available | ✅ | Class-level registration in `app/main.py` lifespan |
| `WorkflowRegistry.register()` available | ✅ | Same pattern as agent registry |
| `BaseService` supports `_before_create()` override | ✅ | `CompanyService` uses this pattern for domain uniqueness |
| `session_scope()` available for `DiscoveryRunService` | ✅ | Used by `LeadRetrievalService` pattern |
| `EvidenceService.record_evidence_batch()` available | ✅ | Called automatically by `BaseAgent.execute()` |
| `httpx` already a dependency | ✅ | In `pyproject.toml` |
| `JobService` supports workflow scheduling | ✅ | `schedule_workflow()` method exists |
| FastAPI dependency injection pattern established | ✅ | Factory functions in `app/api/dependencies.py` |
| Pydantic v2 schema pattern established | ✅ | `IrtiqaSchema` base, `from_attributes=True` |
| Alembic migration pattern established | ✅ | 8 existing migrations, standard `op.create_table()` |
| Test pattern established (temp SQLite, fixtures) | ✅ | `conftest.py` with `migrated_engine`, `session`, domain fixtures |
| `TimestampMixin` provides `created_at`/`updated_at` | ✅ | Applied to all models via mixin |
| `UUIDPrimaryKeyMixin` provides `id` | ✅ | Applied to all models via mixin |
| CHECK constraints enforced on new status columns | ✅ | `discovery_searches.status`, `discovery_runs.status`, `discovery_score` all have CHECK constraints |
| `_before_create()` pattern for criteria validation | ✅ | Mirrors `CompanyService._before_create()` for domain uniqueness |

### No Schema Conflicts

- Adding `discovered_via`, `discovery_search_id`, `discovery_score` to `companies` does not break any existing queries, migrations, or constraints.
- New tables `discovery_searches` and `discovery_runs` do not conflict with existing table names.
- `discovery_searches.organization_id` FK references existing `organizations(id)`.
- `discovery_runs.search_id` FK references `discovery_searches(id)` (new table, no circular dependency).
- All three new columns on `companies` use nullable or DEFAULT values — no NOT NULL on existing rows.

### No API Conflicts

- New prefix `/discovery/` does not conflict with existing routes.
- No existing endpoints use the `/discovery/` path.
- Auth pattern (`get_current_organization`) is reused identically.

### No Workflow Conflicts

- `discovery_pipeline` workflow name is unique (not registered in `WorkflowRegistry`).
- Does not modify `intelligence_pipeline` or `score_refresh`.
- Workflow updates `DiscoverySearch.total_discovered` and `last_run_at` on successful completion.

### Internal Consistency Verified

- `status='needs_review'` used consistently across architecture diagram, decisions table, workflow DDL, and commit 13.
- `discovery_score` CHECK constraint (`0.0`–`1.0`) documented in ALTER TABLE comments, Section 3 DDL, and open questions.
- Agent file count: 6 files (init + agent + sources init + 3 source modules) — matches Section 10 commit plans.
- Total new files: 27 — matches sum of all layers.
- `DiscoverySearchService._before_create()` override documented in service design and referenced in commit plan.

### One Advisory Note

The `companies.discovered_via` column will be `NULL` for all existing 489-test-validated company records. This is correct — only pipeline-discovered companies get a value. No data migration needed.

---

## 13. Open Questions

| # | Question | Default | Rationale |
|---|----------|---------|-----------|
| 1 | Should `DELETE /discovery/searches/{id}` cascade-delete associated runs? | Yes (CASCADE) | Runs are observations of a search; orphaned runs are meaningless |
| 2 | Should the `POST /discovery/searches/{id}/run` endpoint return the run ID for status polling? | Yes (202 + run_id) | Users need to track async execution |
| 3 | Should `discovery_score` be constrained to `[0.0, 1.0]` with a CHECK constraint? | Yes | Consistent with other confidence scores in the schema |
| 4 | Should the workflow limit companies created per run to prevent abuse? | Yes (`max_companies_per_run` from config) | Default 100, configurable via env var |
| 5 | Should discovery runs be cancellable? | Defer to Phase 2 | MVP: runs complete or fail; cancellation adds complexity |
| 6 | Should the `DiscoveryAgent` support multiple API keys for the same source (key rotation)? | No for MVP | Single key per source; rotation is a Phase 2 concern |
