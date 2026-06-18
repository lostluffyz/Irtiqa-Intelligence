# Architecture Overview

High-level map of how all components in Irtiqa Intelligence connect.

## System Layers

```text
┌─────────────────────────────────────────────────────┐
│                    API Layer                         │
│  FastAPI routes → dependency injection → services   │
├─────────────────────────────────────────────────────┤
│                   Service Layer                     │
│  Business logic → transaction boundaries via        │
│  session_scope() → repository calls                 │
├─────────────────────────────────────────────────────┤
│                  Repository Layer                   │
│  SQLAlchemy queries → ORM entities                  │
│  Tenant filtering via _apply_tenant_filter()        │
├─────────────────────────────────────────────────────┤
│                   ORM Layer                         │
│  SQLAlchemy 2.0 models → mapped_column              │
│  17 tables, UUID primary keys, timestamps           │
├─────────────────────────────────────────────────────┤
│                  Database Layer                     │
│  SQLite (primary) / PostgreSQL (future)             │
│  Alembic migrations (8 revisions)                   │
└─────────────────────────────────────────────────────┘
```

## Cross-Cutting Concerns

```text
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Multi-Tenancy│  │ Authentication│  │  Background   │
│ organization_│  │ JWT (RS256)  │  │  Jobs         │
│ id on domain │  │ bcrypt       │  │  scheduler +  │
│ tables       │  │ email verify │  │  runner       │
└──────────────┘  └──────────────┘  └──────────────┘
```

## Intelligence Pipeline Flow

```text
POST /intelligence/pipeline
  │
  ▼
JobScheduler → JobRunner → IntelligencePipelineWorkflow
  │
  ├── Step 1: Deep Scraper Agent → websites
  ├── Step 2: Technographic Agent → technologies
  ├── Step 3: Intent Signal Agent → intent_signals
  ├── Step 4: Intelligence Scoring Agent → intelligence_scores
  └── Step 5: Personalization Agent → outreach_messages
```

Each step creates an `agent_runs` record for observability.

## Lead Retrieval Flow

```text
GET /api/v1/leads
  │
  ▼
LeadRetrievalService
  │
  ├── CompanyRepository.list(organization_id)
  ├── Batch: technologies WHERE company_id IN (...)
  ├── Batch: intent_signals WHERE company_id IN (...)
  ├── Subquery: latest intelligence_scores per company
  ├── Batch: outreach_messages WHERE company_id IN (...)
  │
  ▼
LeadListResponse (aggregated)
```

## Transaction Ownership

- Services own transaction boundaries via `session_scope()`
- Repositories accept sessions but never commit
- API routes call services, not repositories
- `LeadRetrievalService` is an exception: read-only aggregation service

## Key Patterns

| Pattern | Implementation |
|---------|---------------|
| Multi-tenancy | `organization_id` column on all domain tables, filtered via `_apply_tenant_filter()` |
| Pagination | `items`, `total`, `limit`, `offset` on all list responses |
| Error handling | Structured `IrtiqaError` hierarchy with stable error codes |
| Logging | Centralized via `irtiqa.*` logger namespaces |
| Testing | pytest with temporary SQLite databases per test |
| CI | GitHub Actions: ruff, mypy, compileall, SQLite + PostgreSQL test suite |
