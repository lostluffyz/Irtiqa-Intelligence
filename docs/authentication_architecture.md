# Authentication Architecture

## Overview

Irtiqa Intelligence implements RS256 JWT-based authentication with bcrypt password hashing, email verification, database-backed rate limiting, and self-service account deletion.

## Authentication Flow

```text
Register → Verify Email → Login → JWT Tokens → API Access
                                                      │
                              Refresh Token ←─────────┘
                              (before access token expires)
```

## Token Architecture

### Access Token
- Algorithm: RS256 (RSA-SHA256)
- Claims: `user_id`, `org` (organization_id), `role`, `exp`, `iat`
- Expiry: configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` (default 15 minutes)

### Refresh Token
- Stored as SHA-256 hash in `refresh_tokens` table
- Expiry: configurable via `REFRESH_TOKEN_EXPIRE_DAYS` (default 7 days)
- Single-use: invalidated after use, new refresh token issued

## Multi-Tenancy Integration

Every authenticated request carries both user identity and organization context:

1. JWT contains `org` claim (organization_id) and `role` claim
2. `get_current_organization` dependency decodes JWT twice:
   - First decode: authenticate user via `AuthService.authenticate_with_token()`
   - Second decode: extract `org` and `role` claims
3. Database membership lookup verifies the user belongs to the claimed organization
4. Returns `TenantContext(organization_id, user_id, role)`

This prevents JWT-only trust — the database is always consulted (F-1 fix).

## Role Hierarchy

| Role | Level | Permissions |
|------|-------|------------|
| `viewer` | 10 | Read-only access |
| `member` | 50 | Create and update most entities |
| `admin` | 80 | Delete most entities |
| `owner` | 100 | Full access, cross-tenant global queries |

## Database Tables

- `users` — user accounts (email, password_hash, display_name, is_active)
- `refresh_tokens` — hashed refresh tokens with expiry
- `email_verification_tokens` — email verification tokens
- `password_reset_tokens` — password reset tokens
- `failed_login_attempts` — rate limiting (email, ip_address, attempted_at)
- `memberships` — user-organization associations with roles
- `organizations` — tenant organizations

## Security Features

- Password hashing: bcrypt (passlib)
- Rate limiting: database-backed `failed_login_attempts` table
- Email verification: required before first login
- Self-service deletion: `DELETE /auth/me` with cascade cleanup
- JWKS endpoint: `GET /.well-known/jwks.json` for public key distribution

## API Endpoints

See `docs/api_reference.md` for the complete endpoint list.

## Key Files

- `app/services/auth_service.py` — Authentication logic
- `app/core/security.py` — JWT encode/decode, password hashing
- `app/core/tenant.py` — TenantContext, require_role()
- `app/api/dependencies.py` — get_current_organization, get_current_user
- `app/api/v1/endpoints/auth.py` — Auth API routes
