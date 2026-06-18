# API Reference

Complete endpoint inventory for Irtiqa Intelligence.

Base URL: `/api/v1`

Authentication: Bearer token in `Authorization` header.

## Health

- `GET /health` — Service health check

## Authentication

- `POST /auth/register` — Register new user (201)
- `POST /auth/verify-email` — Verify email address
- `POST /auth/login` — Login (returns JWT tokens)
- `POST /auth/logout` — Logout (204)
- `POST /auth/refresh` — Refresh access token
- `GET /auth/me` — Get current user profile
- `PATCH /auth/me` — Update current user profile
- `DELETE /auth/me` — Delete account (204)
- `GET /.well-known/jwks.json` — JWKS public key endpoint

## Organizations

- `POST /organizations` — Create organization (201)
- `GET /organizations/{organization_id}` — Get organization
- `PATCH /organizations/{organization_id}` — Update organization
- `GET /organizations/{organization_id}/members` — List members
- `POST /organizations/{organization_id}/members` — Add member (201)
- `POST /organizations/{organization_id}/transfer` — Transfer ownership
- `PATCH /organizations/memberships/{membership_id}/role` — Change member role
- `DELETE /organizations/memberships/{membership_id}` — Remove member (204)

## Companies

- `POST /companies` — Create company (201)
- `GET /companies` — List companies (paginated)
- `GET /companies/{company_id}` — Get company
- `PATCH /companies/{company_id}` — Update company
- `DELETE /companies/{company_id}` — Delete company (204)

## Contacts

- `POST /contacts` — Create contact (201)
- `GET /contacts` — List contacts (paginated)
- `GET /contacts/{contact_id}` — Get contact
- `PATCH /contacts/{contact_id}` — Update contact
- `DELETE /contacts/{contact_id}` — Delete contact (204)

## Websites

- `POST /websites` — Create website (201)
- `GET /websites` — List websites (paginated)
- `GET /websites/{website_id}` — Get website
- `PATCH /websites/{website_id}` — Update website
- `DELETE /websites/{website_id}` — Delete website (204)

## Technologies

- `POST /technologies` — Create technology (201)
- `GET /technologies` — List technologies (paginated)
- `GET /technologies/{technology_id}` — Get technology
- `PATCH /technologies/{technology_id}` — Update technology
- `DELETE /technologies/{technology_id}` — Delete technology (204)

## Intent Signals

- `POST /intent-signals` — Create intent signal (201)
- `GET /intent-signals` — List intent signals (paginated)
- `GET /intent-signals/{intent_signal_id}` — Get intent signal
- `PATCH /intent-signals/{intent_signal_id}` — Update intent signal
- `DELETE /intent-signals/{intent_signal_id}` — Delete intent signal (204)

## Intelligence Scores

- `POST /intelligence-scores` — Create intelligence score (201)
- `GET /intelligence-scores` — List intelligence scores (paginated)
- `GET /intelligence-scores/top` — List top scores (supports `?global=true` for cross-tenant)
- `GET /intelligence-scores/{intelligence_score_id}` — Get intelligence score
- `PATCH /intelligence-scores/{intelligence_score_id}` — Update intelligence score
- `DELETE /intelligence-scores/{intelligence_score_id}` — Delete intelligence score (204)

## Outreach Messages

- `POST /outreach-messages` — Create outreach message (201)
- `GET /outreach-messages` — List outreach messages (paginated)
- `GET /outreach-messages/{outreach_message_id}` — Get outreach message
- `PATCH /outreach-messages/{outreach_message_id}` — Update outreach message
- `DELETE /outreach-messages/{outreach_message_id}` — Delete outreach message (204)

## Agent Runs

- `POST /agent-runs` — Create agent run (201)
- `GET /agent-runs` — List agent runs (paginated)
- `GET /agent-runs/{agent_run_id}` — Get agent run
- `PATCH /agent-runs/{agent_run_id}` — Update agent run
- `DELETE /agent-runs/{agent_run_id}` — Delete agent run (204)

## Jobs

- `POST /jobs/schedule-agent` — Schedule agent job (201)
- `POST /jobs/schedule-workflow` — Schedule workflow job (201)
- `GET /jobs` — List jobs (paginated)
- `GET /jobs/{job_id}` — Get job
- `POST /jobs/{job_id}/cancel` — Cancel job
- `POST /jobs/{job_id}/retry` — Retry job

## Intelligence Pipeline

- `POST /intelligence/pipeline` — Trigger intelligence pipeline (202 Accepted)
- `GET /intelligence/pipeline/{job_id}` — Get pipeline job status

## Evidence

- `GET /evidence/by-target/{target_type}/{target_id}` — List evidence by target
- `GET /evidence/by-source/{source_type}/{source_id}` — List evidence by source
- `GET /evidence/by-company/{company_id}` — List evidence by company
- `GET /evidence/by-agent-run/{agent_run_id}` — List evidence by agent run
- `GET /evidence/summary/{target_type}/{target_id}` — Get evidence summary
- `GET /evidence/{evidence_id}` — Get evidence detail

## Leads

- `GET /leads` — Aggregated lead intelligence (query params: `limit`, `offset`, `minimum_score`)

## Pagination

List endpoints return:

```json
{
  "items": [...],
  "total": 42,
  "limit": 100,
  "offset": 0
}
```

## Error Responses

All errors follow the structured envelope:

```json
{
  "error": {
    "code": "irtiqa.entity_not_found",
    "message": "...",
    "details": {}
  }
}
```

## Role Requirements

- `viewer` (10) — Read-only access
- `member` (50) — Create and update most entities
- `admin` (80) — Delete most entities
- `owner` (100) — Full access, cross-tenant global queries
