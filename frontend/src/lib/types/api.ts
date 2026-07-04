/**
 * Frontend API contracts for authentication.
 *
 * Contracts mirror the verified backend schemas (OpenAPI). They are intentionally
 * narrow and only cover the auth surface area used by Phase 1.1 — additional
 * resources (companies, leads, discovery, etc.) will grow into separate modules.
 *
 * Notes on verified shapes (see docs/frontend_architecture.md Section 18):
 * - POST /auth/login  → LoginResponse (access_token, refresh_token, token_type, user, organization|null)
 * - POST /auth/refresh → RefreshTokenResponse (access_token, refresh_token, token_type) — NO user/org
 * - POST /auth/logout  → 204 No Content; requires refresh_token in body + Authorization header
 * - GET  /auth/me      → UserResponse
 */

export interface UserResponse {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
  role: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserResponse;
  organization: OrganizationSummary | null;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface RefreshTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

/**
 * Optional logout response shape — POST /auth/logout returns 204 No Content and
 * has no JSON body, so this is omitted in practice. Declared for code that
 * wants to type the absence of a payload explicitly.
 */
export type LogoutResponse = void;

/**
 * Typed backend error envelope. Observed on validation failures (422) and other
 * structured errors. Optional `fields` / `details` accommodate error variants.
 */
export interface ApiErrorResponse {
  error?: {
    code?: string;
    message?: string;
    type?: string;
    details?: Record<string, unknown>;
  };
}

/* ── Companies ──────────────────────────────────────────────────────────── */

/**
 * Verified from OpenAPI GET /companies response items and GET /companies/{company_id}.
 * All fields are required (nullable fields use `| null`).
 */
export interface CompanyRead {
  id: string;
  created_at: string;
  updated_at: string;
  name: string;
  domain: string;
  industry: string | null;
  company_size: string | null;
  headquarters: string | null;
  description: string | null;
  linkedin_url: string | null;
  status: 'active' | 'needs_review' | 'archived';
}

/**
 * Verified from OpenAPI GET /companies response.
 * Envelope — all fields required.
 */
export interface CompanyList {
  total: number;
  limit: number;
  offset: number;
  items: CompanyRead[];
}
