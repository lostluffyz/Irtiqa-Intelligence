# Lead Retrieval Architecture

## Overview

The Lead Retrieval API provides a tenant-scoped aggregated view of lead intelligence. After the intelligence pipeline completes, this endpoint allows users to retrieve and review all scored leads without querying multiple tables.

## Endpoint

```
GET /api/v1/leads?limit=100&offset=0&minimum_score=50.0
```

## Response Shape

```json
{
  "items": [
    {
      "company_id": "uuid",
      "company_name": "Acme Corp",
      "domain": "acme.com",
      "industry": "software",
      "status": "active",
      "technologies": [{"name": "HubSpot", "category": "crm"}],
      "intent_signals": [{"signal_type": "technology_change", "confidence": 0.88}],
      "latest_intelligence_score": {
        "total_score": 81.4,
        "opportunity_score": 82.0,
        "urgency_score": 76.0
      },
      "outreach_messages": [{"channel": "email", "subject": "Hello", "message_body": "..."}],
      "updated_at": "2026-06-18T12:00:00Z"
    }
  ],
  "total": 42,
  "limit": 100,
  "offset": 0
}
```

## Score Field Mapping

| Response Field | Source Field | Meaning |
|---------------|-------------|---------|
| `total_score` | `IntelligenceScore.total_score` | Overall opportunity score |
| `opportunity_score` | `IntelligenceScore.fit_score` | How well the company fits the ICP |
| `urgency_score` | `IntelligenceScore.intent_score` | Buying signal strength and recency |

## Architecture

```
GET /leads
  │
  ▼
LeadRetrievalService (read-only aggregation)
  │
  ├── CompanyRepository.list(organization_id)  ← paginated
  ├── CompanyRepository.count_by_organization() ← total count
  │
  ├── Batch: technologies WHERE company_id IN (page_ids)
  ├── Batch: intent_signals WHERE company_id IN (page_ids)
  ├── Subquery: latest intelligence_scores per company
  ├── Batch: outreach_messages WHERE company_id IN (page_ids)
  │
  ├── _apply_score_filter() ← if minimum_score set
  ├── _count_filtered()     ← recomputes total when filter active
  │
  ▼
LeadListResponse
```

## Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Results per page (1-500) |
| `offset` | int | 0 | Number of results to skip |
| `minimum_score` | float | null | Only include leads with total_score >= this value |

## Design Decisions

1. **Read-only service** — `LeadRetrievalService` does not extend `BaseService` because it performs cross-table aggregation, not single-entity CRUD.

2. **Batch queries** — Technologies, signals, and messages are fetched with `WHERE company_id IN (...)` (one query per entity type per page, not per company).

3. **Latest score subquery** — Uses `func.max(scored_at)` grouped by company_id, joined back to get the full row.

4. **minimum_score filter** — Applied post-fetch. When active, `total` is recomputed across the full organization to keep pagination correct.

5. **Tenant isolation** — Company list is filtered by `organization_id` via `_apply_tenant_filter()`. Child entity queries are transitively correct through `company_ids`.

## Key Files

- `app/schemas/lead.py` — Pydantic response schemas
- `app/services/lead_retrieval_service.py` — Aggregation service
- `app/api/v1/endpoints/leads.py` — FastAPI endpoint
- `app/repositories/company_repository.py` — count_by_organization()
- `tests/unit/test_lead_schemas.py` — Schema tests
- `tests/integration/test_lead_retrieval_service.py` — Service tests
- `tests/integration/api/test_lead_retrieval_api.py` — API tests
