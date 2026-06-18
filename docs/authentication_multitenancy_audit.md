> **Status: IMPLEMENTED**

# Authentication & Multi-Tenancy Design Audit

## Executive Summary

The design document builds a reasonable authentication and multi-tenancy layer but contains **one critical flaw, five high-severity issues, and ten medium-severity issues** that must be addressed before implementation begins. The most severe problems are in tenant isolation enforcement (which is dangerously incomplete), the JWT org-claim trust model (which trusts the client to declare which organization they belong to on every request), and the password reset implementation (which violates its own security premise).

**Verdict: NOT READY FOR IMPLEMENTATION.** The tenant isolation model has a fundamental trust gap that would allow cross-tenant data access in production.

---

## Findings

### Critical

#### F-1: Cross-Tenant Access via JWT Org Claim Is Not Verified

**Severity: Critical**

**Description**: The design stores the organization ID in the JWT `org` claim and says the server "trusts the JWT claim (for read operations)" without verifying membership on every request. The `get_current_organization` dependency shown in the pseudocode accepts `current_org_id` from a cookie or session without any database look-up verifying the user is actually a member of that org.

```python
async def get_current_organization(
    user: User = Depends(get_current_user),
    current_org_id: str | None = None,  # from session or cookie
) -> Organization:
    # 1. Verify user is a member of the current org.  ← THIS IS STUBBED
    # 2. Return organization or raise 403.
```

**Impact**: A malicious user could craft a request with a different `org` in the JWT (by requesting a new token with modified claims) or manipulate the `X-Organization-Id` header. If the membership check is not performed, they would gain access to any organization's data. Since the JWT is signed, the token-level `org` claim is tamper-proof, but the flow for *choosing which org* is not — the user already has tokens, and the org claim on those tokens is set at login. The risk is: if User A is a member of Org A and Org B, and they request a token while "current_org" is Org A, the token has `org: org_a`. They cannot access Org B with that token. But the design says the client sends `X-Organization-Id` separately, which is unsigned and unauthenticated.

**Root Cause**: The design splits org selection from org verification. The JWT encodes one org ID at login time, but the client can switch orgs between requests. The separate `X-Organization-Id` header is not part of the signed JWT, so it can be tampered with.

**Recommendation**: All tenant-scoped requests must have the target organization verified against an explicit membership lookup. The `X-Organization-Id` header must be validated on every request by checking that the authenticated user has a membership in that org. The `get_current_organization` dependency must perform a database membership lookup, not trust a cookie or decoded JWT claim alone.

---

### High

#### F-2: Password Reset Token Returned in API Response Is a Design Flaw, Not a Limitation

**Severity: High**

**Description**: The design admits the reset token is returned in the API response body "because there is no email-sending infrastructure" and calls it a "documented limitation." In practice this means: anyone who can intercept or observe the API response (proxy logs, client-side logs, browser devtools, network monitor) gains the ability to reset any user's password within 15 minutes. The design claims the token is "short-lived (15 minutes) and single-use" as mitigation, but 15 minutes is an eternity for an account-takeover attack.

**Impact**: If the password-reset endpoint is exposed without email delivery, every deployed instance has an unauthenticated account-takeover vulnerability. This is not a "limitation" — it's a vulnerability that would be scored CVSS 9.1 (Critical) if deployed as described.

**Root Cause**: The design prioritizes having a complete API over deferring the password reset flow until email infrastructure exists.

**Recommendation**: Either:
1. Remove the password-reset endpoints entirely from Phase 1. Return a clear error: "Password reset requires email configuration."
2. Or implement the reset token delivery through a configurable callback (e.g., a webhook or log sink) that can be replaced by email later, but **never** return the token in the response body.

---

#### F-3: API Key Authentication Conflicts with JWT Authentication Flow

**Severity: High**

**Description**: The design says API keys use the same `Authorization: Bearer <token>` header as JWT tokens. The authentication dependency tries to decode the token as JWT first, and if it fails, checks if it matches an API key hash. This means a malformed JWT triggers an API key lookup on every request. An expired JWT (which is a routine event — 15-min expiry) also goes through the API key fallback. This conflates two different authentication methods into one code path and creates a timing side-channel — API key lookup takes measurably longer than JWT decoding, allowing an attacker to distinguish between "invalid JWT" and "valid API key, wrong org" responses.

**Impact**: API key authentication adds latency to every expired-JWT refresh cycle. The JWT → API key fallback path is exercised on every token expiry, meaning ~1 in every ~180 requests per user (for 15-min tokens with continuous use). There is no way to distinguish a JWT from an API key without attempting JWT decode first, which is wasteful.

**Root Cause**: Sharing the `Authorization` header format between JWT and API keys without a discriminator.

**Recommendation**: Use a distinct prefix or header for API keys:
- JWT: `Authorization: Bearer <jwt>`
- API Key: `Authorization: Bearer irt_sk_...` (the prefix `irt_sk_` can be used to discriminate without attempting JWT decode first)
OR
- API Key: `X-API-Key: irt_sk_...` (separate header).

---

#### F-4: Tenant Filtering Relies on Human Discipline, Not Architecture

**Severity: High**

**Description**: The design explicitly states "The tradeoff is that every new query method must remember to include `organization_id`" and relies on "code review" and "integration tests" to catch omissions. For a production SaaS system processing multi-tenant data, a single missed `organization_id` filter in any query method — existing or future — silently leaks data across all tenants.

**Impact**: A new developer adding a `CompanyService.list_by_name(name)` method six months from now who forgets to add the `organization_id` filter would return companies from all tenants. This would not be caught at compile time, would not be caught by existing tests, and would not be visible in logs. It would be discovered only when a customer reports seeing another customer's data.

**Root Cause**: The design adds `organization_id` as a regular column parameter rather than as a required, validated, and inherited tenant context.

**Recommendation**: Implement tenant context at the infrastructure layer, not the application layer:
1. Add `organization_id` as a required filter in `BaseRepository` methods so every inherited query is automatically scoped.
2. Implement a `TenantContext` object that is injected into services and repositories, not passed as an ad-hoc parameter.
3. Add audit logging for any query that runs without an `organization_id` filter (detect the absence in a middleware or repository hook).

---

#### F-5: Domain Entity Tenancy Model Is Incomplete and Inconsistent

**Severity: High**

**Description**: The design proposes two different FK strategies for the same data:
- `companies`: `organization_id` FK with `CASCADE` delete.
- Child entities: `organization_id` FK with `SET NULL` on org delete.

The justification for `SET NULL` on child entities is "tenant-scoped queries without joining through companies." But this creates a dangerous inconsistency: if an organization is deleted, all its child records (contacts, websites, technologies, etc.) lose their `organization_id` but the records themselves are **not deleted**. They become orphaned with NULL tenant IDs. A subsequent query that includes `WHERE organization_id IS NULL` or that accidentally omits the filter would expose these records across tenants.

Furthermore, the design says evidence_records "already provides tenant scoping via company → org" but leaves the column undefined. Evidence_records has a `company_id` column — it does NOT have an `organization_id` column and does NOT have a `companies → organization_id` join available without adding one.

**Impact**: Deleting an organization leaves orphaned, untethered records in the database with NULL tenant IDs. These records are invisible to all tenants (since queries filter by organization_id), creating ghost data. If any query omits the filter, all orphaned records become visible.

**Root Cause**: The FK strategy for child tables prioritizes query convenience over data integrity.

**Recommendation**: Use a single consistent policy:
- All domain entities: `organization_id` FK with `CASCADE` delete (not `SET NULL`).
- Include `organization_id` on `evidence_records` explicitly (the design claims it's "already provided" but it's not).
- Add a composite index `(organization_id, company_id)` on all child tables for query performance.

---

### Medium

#### F-6: HS256 JWT Has No Key Rotation Mechanism

**Severity: Medium**

**Description**: The design uses HS256 (symmetric HMAC) with a single `JWT_SECRET` environment variable. Key rotation requires coordinating a secret change across all running instances simultaneously — any instance still using the old secret would reject tokens signed with the new secret (or vice versa). The design mentions "JWT secret rotation" and "multiple valid secrets" but provides no architecture for it — no `key_id` header in the JWT, no secrets table, no versioned key store.

**Impact**: When the JWT secret needs to be rotated (a standard operational practice for HS256), all users are forced to re-login because existing tokens become invalid. For a SaaS platform with long-lived sessions (7-day refresh tokens), this is a significant disruption.

**Root Cause**: HS256 is simpler than RS256 or EdDSA but has no built-in key rotation story.

**Recommendation**: Switch to RS256 (RSA) or EdDSA (Ed25519) for JWT signing. This allows:
- Publishing a public key (`/.well-known/jwks.json`) for external verification.
- Rotating keys without invalidating existing tokens (old public key remains valid until tokens expire).
- A `kid` (key ID) header in the JWT for versioned key lookup.

If HS256 is kept for simplicity, implement a versioned secrets table in the database.

---

#### F-7: Registration Flow Is Insecure Without Email Verification

**Severity: Medium**

**Description**: The registration endpoint creates a fully active user + organization in a single step. There is no email verification. `email_verified_at` is set to `None`, but the design says "Accounts with unverified emails can log in." This means anyone can register with any email address without proving ownership.

**Impact**: User enumeration is possible (the 200 vs. 201 status on registration), and organizations can be created with fake email addresses. Resource limits (organizations per email) can be bypassed.

**Recommended fix**: Require email verification before the user can log in. Send a verification email with a time-limited token. The `is_active` flag should be `False` until email is verified. Registration without email infrastructure should return an error explaining the requirement.

---

#### F-8: Rate Limiter Is Stateless and Ineffective for Distributed Deployment

**Severity: Medium**

**Description**: The in-memory rate limiter tracks `(ip_address, email)` tuples in process memory. In a multi-process deployment (multiple uvicorn workers, or multiple servers), each process has its own counter. An attacker can make up to `5 × process_count` attempts before being locked out. Process restart resets all counters.

**Impact**: The rate limiter provides a false sense of security. It stops casual guessing but does not meaningfully prevent brute-force attacks against a production deployment with >1 worker.

**Recommended fix**: Move rate limiting to a shared store (Redis or database) for the initial implementation, or document that the in-memory limiter is a development-only placeholder and deploy a reverse-proxy rate limiter (e.g., nginx, Cloudflare) for production.

---

#### F-9: Role Hierarchy Allows an Admin to Remove the Last Owner

**Severity: Medium**

**Description**: The membership model says "An admin or owner can remove any non-owner member." The ownership transfer says "transfer ownership to another member." But there is no check that prevents the last owner from being removed or from having their role changed. If an org has exactly one owner, and an admin removes that owner, the org is left with no owner. No one can then transfer ownership, manage billing, or delete the org.

**Impact**: Orphaned organization that cannot be administered. Requires manual database intervention to fix.

**Recommended fix**: Enforce at the service layer: an organization must always have at least one member with `role=owner`. Prevent role changes away from `owner` and membership deletions if the target member is the last owner. This check must be in `MembershipService.update_role()` and `MembershipService.remove()`.

---

#### F-10: `accepted_at` Field Exists but Invitation Acceptance Flow Is Not Specified

**Severity: Medium**

**Description**: The `memberships` table has an `accepted_at` field, suggesting that invitations create pending memberships. But the API endpoints include no `POST /organizations/{org_id}/invitations/{token}/accept` path, and the membership creation flow doesn't describe how a user accepts an invitation. The `POST /organizations/{org_id}/members` endpoint creates a membership directly (presumably with `accepted_at=now()`), but the field definition implies a two-step flow.

**Impact**: The `accepted_at` field is dead code if memberships are created directly. If a two-step flow is intended, the API and service layer are incomplete.

**Recommended fix**: Either remove `accepted_at` (simplify to direct membership creation), or implement the full invitation acceptance flow with a unique token.

---

#### F-11: `slug` Uniqueness Has No Collision Resolution

**Severity: Low**

**Description**: The `organizations.slug` column is unique. The design says the slug is "generated" during registration but does not specify how. A naive implementation using `slugify(organization_name)` will collide when two organizations have the same name (e.g., "Acme Corp" and "Acme Corp" from different users).

**Impact**: Registration fails with a database integrity error if the generated slug is not unique.

**Recommended fix**: Append a random suffix (e.g., `acme-corp-a1b2c3`) on collision, or derive the slug from a UUID, or implement a slug generation function that retries with incrementing suffixes.

---

#### F-12: No Account Deletion / GDPR Compliance

**Severity: Low**

**Description**: The design includes a `DELETE /organizations/{org_id}` endpoint but no user account deletion endpoint. The `users` table has no `deleted_at` or `anonymized_at` field. For a production SaaS platform handling personal data (email, name), GDPR requires the ability to delete personal data.

**Impact**: Non-compliance with privacy regulations. Users cannot request account deletion through the API.

**Recommended fix**: Add `deleted_at` timestamp to `users` and `organizations`. Implement `DELETE /auth/me` for user self-deletion (anonymize or cascade delete personal data).

---

#### F-13: Agent and Workflow Context Does Not Include Organization ID

**Severity: Medium**

**Description**: The design claims "Agents receive context including the current organization" and "Workflows operate on organization-scoped data." Neither `AgentContext` nor `WorkflowContext` has an `organization_id` field in the current codebase. The design assumes these will be added but doesn't specify the required changes to `app/agents/context.py` and `app/workflows/context.py`. Without explicit `organization_id` in both context objects, agents and workflows have no way to know which organization they're operating on.

**Impact**: Agents and workflows will create data without an `organization_id`, breaking tenant isolation for all agent-created and workflow-created records.

**Root Cause**: The design lists agent/workflow compatibility as "no conflict" but does not specify the changes needed.

**Recommended fix**: Add `organization_id` as a required field to both `AgentContext` and `WorkflowContext`. Update all agent and workflow call sites to pass `organization_id`. This affects:
- `app/agents/context.py` — add field
- `app/workflows/context.py` — add field
- `app/jobs/runner.py` — read from job payload, pass to context
- `app/workflows/runner.py` — read from context, pass to workflow

---

#### F-14: Migration 2 Has No Rollback Strategy for Existing Data

**Severity: Medium**

**Description**: Migration 2 adds `organization_id` to 10 existing tables as nullable columns. The design says "no backfill needed" for child tables, leaving NULL values in production databases. A subsequent migration to make these columns `NOT NULL` requires a backfill that the design doesn't specify. For tables with millions of rows (e.g., `intent_signals`, `agent_runs`), this is a multi-step, potentially hours-long migration.

**Impact**: NULL values in tenant-ID columns create a data integrity gap. Making them NOT NULL later requires a time-consuming, lock-risk migration on production data.

**Recommended fix**: Specify the backfill strategy:
1. Migration 2a: Add `organization_id` as nullable.
2. Data migration script: Backfill `organization_id` on all tables via company → org join (run as a background job or offline maintenance).
3. Migration 2b: Set `organization_id` as `NOT NULL` on all tables after backfill is verified.
4. Include a verification query that detects rows with NULL `organization_id` after backfill.

---

#### F-15: API Key Permission Model Is Overly Permissive

**Severity: Medium**

**Description**: All API keys inherit the `admin` role. This means a read-only integration (e.g., a dashboard that only displays data) would have full admin access including the ability to create API keys, manage members, and update organizations. The design does not support scoped API keys with limited permissions.

**Impact**: API keys are a common attack vector. An overprivileged API key that is leaked exposes more of the system than necessary. The principle of least privilege is violated.

**Recommended fix**: Allow API keys to be created with an optional `role` field (defaulting to `admin` for backward compatibility). A key created with `role=viewer` should only be able to perform read operations.

---

## Risks Table

| Risk | Severity | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| Cross-tenant data breach via unverified org claim | **Critical** | High | Complete data exposure | F-1 fix: verify membership on every request |
| Account takeover via reset-token-in-response | **High** | Medium | Single-account compromise | F-2 fix: remove or secure reset flow |
| Cross-tenant leak via missing `organization_id` filter | **High** | Medium (inevitable over time) | Data exposure across orgs | F-4 fix: base repository enforcement |
| Orphaned records on org deletion | **High** | Low | Ghost data, invisible to all tenants | F-5 fix: CASCADE policy |
| API key privilege escalation | **Medium** | Low | Unauthorized write access | F-15 fix: scoped API key roles |
| Brute-force bypass via multiple workers | **Medium** | Medium | Account compromise | F-8 fix: shared rate limiter |
| Orphaned org on last owner removal | **Medium** | Low | Unadministerable org | F-9 fix: last-owner check |
| Registration abuse without email verification | **Medium** | Medium | Fake accounts, resource exhaustion | F-7 fix: email verification gate |
| JWT secret rotation disruption | **Medium** | Medium | Mass logout on key rotation | F-6 fix: RS256 or versioned secrets |
| Agent/workflow data without tenant context | **Medium** | High (will happen on first agent run) | Missing org_id on agent-created data | F-13 fix: add org_id to contexts |

---

## Recommended Corrections

### Must Fix Before Implementation

| Priority | Issue | Fix |
|---|---|---|
| 1 | F-1: Cross-tenant access via unverified org claim | Every tenant-scoped request must verify membership via database lookup. The `get_current_organization` dependency must execute a membership query. |
| 2 | F-2: Password reset token in response | Remove password-reset endpoints from Phase 1. Return an explanatory error until email infrastructure exists. |
| 3 | F-4: Tenant filtering relies on human discipline | Implement `organization_id` filtering in `BaseRepository` so every inherited query is automatically scoped. |
| 4 | F-5: Domain entity tenancy is inconsistent | Switch child-table FK strategy to `CASCADE` (not `SET NULL`). Add explicit `organization_id` to `evidence_records`. |

### Should Fix Before Production

| Priority | Issue | Fix |
|---|---|---|
| 5 | F-3: API key / JWT auth path collision | Use `X-API-Key` header or discriminate by `irt_sk_` prefix without attempting JWT decode first. |
| 6 | F-6: JWT secret rotation | Use RS256 or EdDSA, or implement versioned secrets table. |
| 7 | F-7: Registration without email verification | Gate login on email verification. Explain requirement when email infra is absent. |
| 8 | F-8: In-memory rate limiter | Move to shared store (DB or Redis), or document as dev-only and mandate reverse-proxy rate limiting. |
| 9 | F-9: Last owner removal protection | Add service-layer check preventing removal of the last owner. |
| 10 | F-13: Agent/workflow org context | Add `organization_id` to `AgentContext` and `WorkflowContext` as required fields. |
| 11 | F-14: Migration backfill strategy | Define multi-step migration with backfill script for all 10 affected tables. |
| 12 | F-15: API key scoping | Add optional `role` field to API key creation. |

### Fix During Implementation

| Priority | Issue | Fix |
|---|---|---|
| 13 | F-10: `accepted_at` / invitation flow | Either remove the field or implement the full acceptance flow. |
| 14 | F-11: Slug collision resolution | Implement slug generation with collision retry. |
| 15 | F-12: GDPR / account deletion | Add `deleted_at` and `DELETE /auth/me` endpoint. |

---

## Implementation Readiness Verdict

**NOT READY FOR IMPLEMENTATION.**

### The Critical Blocker

**F-1** (cross-tenant access via unverified org claim) is a critical architectural flaw. The current design trusts the client to declare which organization it's acting on and relies on a JWT claim that is set at login time and cannot be changed without re-authentication. The `X-Organization-Id` header is not part of the signed JWT. This means:

1. A user who is a member of Org A and Org B receives a JWT with `org: org_a`.
2. If they send a request with `X-Organization-Id: org_b` (or manipulate a client-side cookie), the system has no way to verify they belong to Org B without a database lookup.
3. The design explicitly says the server "trusts the JWT claim (for read operations)" — meaning it intentionally skips the membership check.

This must be resolved before any code is written, because the entire tenant isolation model depends on it.

### The High-Severity Issues

**F-2** (password reset token in response) is not a "limitation" — it's a vulnerability. If this code is deployed, any network observer can take over any account. The password-reset endpoints must be removed from Phase 1 entirely.

**F-4** (tenant filtering by discipline) will fail under the pressure of a real development cycle. The first time a developer adds a new query method and forgets `organization_id`, customer data will leak. The repository layer must enforce tenant scoping architecturally, not through code review.

**F-5** (inconsistent FK strategy) will create orphaned records and ghost data that is invisible to all tenants. The `SET NULL` approach on child tables should be replaced with `CASCADE` for data integrity, and the missing `evidence_records.organization_id` must be added explicitly.

### Path to Ready

1. Redesign the tenant isolation model to verify org membership on every request via database lookup (not JWT claims alone).
2. Add `organization_id` enforcement at the `BaseRepository` level.
3. Fix the FK strategy to use `CASCADE` consistently across all domain tables.
4. Remove password-reset endpoints from Phase 1.
5. Fix API key authentication to use a separate header or prefix discriminator.
6. Re-audit the revised design.
