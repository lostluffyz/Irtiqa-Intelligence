# Project State

This document is the handoff reference for continuing Irtiqa Intelligence development without prior chat history.

## Current Architecture

Irtiqa Intelligence is a production-grade lead intelligence platform in backend-complete stage.

Current architectural direction:

## Active Components

### Backend
*   **FastAPI**: Configured and running.
*   **Database**: SQLite with SQLAlchemy 2.0 and Alembic.
*   **Models**: `Company`, `Contact`, `Website`, `Technology`, `IntentSignal`, `IntelligenceScore`, `OutreachMessage`, `AgentRun`, `Job`, `User`, `Organization`, `Membership`, `EvidenceRecord`, plus auth models (`EmailVerificationToken`, `PasswordResetToken`, `RefreshToken`, `FailedLoginAttempt`).
*   **Service Layer**: `CompanyService`, `ContactService`, `WebsiteService`, `TechnologyService`, `IntentSignalService`, `IntelligenceScoreService`, `OutreachMessageService`, `AgentRunService`, `JobService`, `EvidenceService`, `AuthService`, `MembershipService`, `OrganizationService`, `LeadRetrievalService` implemented.
*   **Agent Interface Foundation**: Standardized abstractions via `app.agents` (`BaseAgent`, `AgentContext`, `AgentResult`).
*   **Deep Scraper Agent**: Core crawling, parsing, and structured data persistence implemented and tested.
*   **Technographic Agent**: Signature-based technology detection implemented and tested.
*   **Intent Signal Agent**: Rule-based commercial buying signal detection implemented and tested.
*   **Intelligence Scoring Agent**: Aggregation of fit, intent, technographic, and engagement scores utilizing the DeterministicScoreRefreshPolicy.
*   **Personalization Agent**: Generation of tailored, multi-variant outreach copy based on all accumulated intelligence.
*   **Background Job Foundation**: In-process job scheduling, execution, and monitoring for agents and workflows implemented and tested.
*   **Intelligence Pipeline Workflow**: End-to-end orchestration chaining all 5 agents into a single pipeline triggered via `POST /intelligence/pipeline`.
*   **Multi-Tenancy Phase 1**: Organization and Membership foundation with owner-protection, role management, 5-step slug generation, and `create_with_owner()` atomicity.
*   **Authentication System**: RS256 JWT, bcrypt password hashing, email verification, database-backed rate limiting, self-service account deletion, Swagger/OpenAPI bearer auth integration.
*   **Lead Retrieval API**: Tenant-scoped aggregated lead intelligence endpoint at `GET /api/v1/leads`. Returns companies with technologies, intent signals, latest intelligence score, and outreach messages in a single response. Supports `limit`, `offset`, and `minimum_score` query parameters.

### Next Steps

- Technographic Intelligence Agent implemented and tested with 40+ signatures across 8 categories.
- Personalization Agent implemented and tested with deterministic multi-variant template architecture.
- Intelligence Scoring Agent implemented and tested by importing the deterministic workflow scoring policy.
- Intent Signal Agent implemented and tested with deterministic rules across 8 signal families.
- Deep Scraper Agent implemented and tested with robust parsing and persistence.
- FastAPI lifespan startup/shutdown logging implemented.
- SQLAlchemy ORM model layer implemented.
- SQLite-first database setup implemented.
- SQLite WAL mode and busy timeout implemented.
- PostgreSQL compatibility planned through SQLAlchemy and Alembic.
- Repository pattern implemented for database access.
- Service layer implemented above repositories.
- Pydantic v2 schema layer implemented for service and future API boundaries.
- Testing foundation implemented for the current database layer.
- Centralized structured logging implemented.
- Structured error hierarchy implemented.
- SQLite backup strategy documented.
- Agent Interface Foundation implemented with fully asynchronous abstract contracts.
- Frontend exists only as an empty top-level placeholder directory.

Current top-level structure:

```text
Irtiqa-Intelligence/
|-- AGENTS.md
|-- README.md
|-- pyproject.toml
|-- alembic.ini
|-- .env.example
|-- .gitignore
|-- app/
|   |-- api/
|   |-- agents/
|   |-- core/
|   |-- database/
|   |-- models/
|   |-- repositories/
|   |-- schemas/
|   |-- services/
|   `-- workflows/
|-- database/
|   `-- migrations/
|-- docs/
|   |-- agents.md
|   |-- database.md
|   |-- workflows.md
|   `-- project_state.md
|-- tests/
|   |-- conftest.py
|   |-- integration/
|   `-- unit/
|-- agents/
|-- backend/
|-- frontend/
`-- prompts/
```

Important rule from `AGENTS.md`: do not create mock data or temporary solutions. Keep the architecture production-ready, modular, typed, logged, and error-aware.

## Current Repository Status

Current status:

- Backend foundation is stable and tested.
- Task 2, Core Logging Setup, is complete.
- Task 3, Structured Error Handling, is complete.
- Task 4, Database Hardening, is complete.
- Task 5, SQLite Backup Strategy Documentation, is complete.
- Task 6, Service Layer, is complete.
- Task 7, Pydantic Schemas, is complete.
- Task 8, FastAPI Skeleton, is complete.
- Task 9, CRUD API Endpoints Phase 1, is complete for companies, contacts, and websites.
- Task 9, CRUD API Endpoints Phase 2, is complete for technologies, intent signals, and intelligence scores.
- Task 9, CRUD API Endpoints Phase 3, is complete for outreach messages and agent runs.
- Task 10, Workflow Foundation Phase 1, is complete.
- Phase 2 `score_refresh` workflow is complete.
- Task 11, Agent Interface Foundation, is complete.
- Deep Scraper Agent is complete.
- Technographic Agent is complete.
- Intent Signal Agent is complete.
- Intelligence Scoring Agent is complete.
- Personalization Agent is complete.
- Task 12, Background Job Foundation, is complete.
- Current full test suite result is `489 passed` (27 skipped PostgreSQL-only).
- Evidence records system implemented with dedicated `evidence_records` table, service, API, and agent integration.
- Intelligence Pipeline workflow implemented: chains all 5 agents (Deep Scraper → Technographic → Intent Signal → Intelligence Scoring → Personalization) into a single orchestrated run triggered via API.
- Alembic schema drift check reports no new upgrade operations after upgrading to head.
- Generated artifacts such as `database/irtiqa.db`, `.pytest_cache/`, and `__pycache__/` should remain uncommitted.
- The full CRUD API milestone is complete. Workflow foundation and `score_refresh` exist. Agent Interface Foundation, Deep Scraper Agent, Technographic Agent, Intent Signal Agent, Intelligence Scoring Agent, and Personalization Agent are complete. Background Job Foundation is complete. Lead Retrieval API is complete. Scraping orchestration, frontend, and external integrations have not been implemented.

## Repository Health Summary

Current health:

- Foundation status: healthy.
- Current test count: `489 passed` (27 skipped PostgreSQL-only).
- Schema drift status: clean after upgrading the local SQLite database to Alembic head.
- Architecture status: API routes, database, repositories, services, schemas, workflows, agent interface, Deep Scraper Agent, Technographic Agent, Intent Signal Agent, Intelligence Scoring Agent, Personalization Agent, Background Job Foundation, Evidence Records System, Intelligence Pipeline Workflow, Multi-Tenancy Phase 1 (Organization & Membership), and Lead Retrieval API are implemented.
- Runtime surface status: health endpoint and CRUD endpoints for all models exist; Lead Retrieval endpoint exists; workflow foundation and `score_refresh` exist; agent foundation exists; Deep Scraper, Technographic Agent, Intent Signal Agent, Intelligence Scoring Agent, and Personalization Agent exist; Background Job Foundation with job scheduling, execution, and monitoring APIs exist.
- Artifact status: generated local artifacts such as `database/irtiqa.db`, `.pytest_cache/`, and `__pycache__/` must remain uncommitted.
- CI status: GitHub Actions workflow configured with ruff, mypy, compileall validation and full test suite (489 passed, 27 skipped PostgreSQL-only) on every push and pull request.
- Next milestone: external integrations and orchestration.

## Database Schema

The implemented schema contains seventeen tables:

- `companies`
- `contacts`
- `websites`
- `technologies`
- `intent_signals`
- `intelligence_scores`
- `outreach_messages`
- `evidence_records`
- `memberships`
- `organizations`
- `agent_runs`
- `jobs`
- `users`
- `refresh_tokens`
- `email_verification_tokens`
- `password_reset_tokens`
- `failed_login_attempts`

Relationship summary:

```text
companies 1--many contacts
companies 1--many websites
companies 1--many technologies
companies 1--many intent_signals
companies 1--many intelligence_scores
companies 1--many outreach_messages
companies 1--many agent_runs

contacts 1--many intent_signals
contacts 1--many intelligence_scores
contacts 1--many outreach_messages
contacts 1--many agent_runs

websites 1--many technologies
websites 1--many intent_signals

technologies 1--many intent_signals
technologies 1--many intelligence_scores

agent_runs 1--many technologies
agent_runs 1--many intent_signals
agent_runs 1--many intelligence_scores
agent_runs 1--many outreach_messages
agent_runs 1--many evidence_records
agent_runs 1--many jobs

intelligence_scores 1--many outreach_messages

organizations 1--many memberships (owner, admin, member, viewer)
jobs 1--many agent_runs (optional, nullable)
```

Schema design choices:

- UUIDs are stored as `String(36)` for SQLite compatibility.
- Timestamps use SQLAlchemy `DateTime(timezone=True)`.
- `created_at` and `updated_at` are shared through a timestamp mixin.
- Foreign keys are configured with `CASCADE` or `SET NULL` depending on data ownership.
- Indexes are defined on primary query fields and composite lookup paths.
- Alembic migration revision `20260531_0001` creates the initial schema.
- Alembic migration revision `20260531_0002` adds database hardening constraints.
- Alembic migration revision `20260616_0007` adds `organization_id` to all domain tables for multi-tenancy.
- SQLite connections enable foreign keys, WAL mode, and busy timeout through isolated engine configuration.
- SQLite backup and restore procedures are documented in `docs/database.md`.
- Confidence values are constrained from `0.0` to `1.0`.
- Intent signal strength is constrained from `0.0` to `1.0`.
- Intelligence score values are constrained from `0.0` to `100.0`.
- Stable status values are constrained on `companies`, `contacts`, `agent_runs`, and `outreach_messages`.

Reference docs:

- `docs/database.md`
- `database/migrations/versions/20260531_0001_initial_schema.py`
- `database/migrations/versions/20260531_0002_database_hardening.py`

## Implemented Components

### Project Metadata

Implemented:

- `pyproject.toml`
- `.gitignore`
- `.env.example`
- `README.md`

Declared core dependencies:

- `sqlalchemy`
- `alembic`
- `fastapi`
- `uvicorn[standard]`
- `pydantic-settings`
- `python-dotenv`

Optional dependency groups:

- `dev`
- `postgres`

### Models

Implemented SQLAlchemy models in `app/models/`:

- `base.py`
- `company.py`
- `contact.py`
- `website.py`
- `technology.py`
- `intent_signal.py`
- `intelligence_score.py`
- `outreach_message.py`
- `agent_run.py`
- `job.py`
- `user.py`
- `organization.py`
- `membership.py`
- `evidence_record.py`
- `email_verification_token.py`
- `password_reset_token.py`
- `refresh_token.py`
- `failed_login_attempt.py`

`app/models/__init__.py` exports all model classes and metadata.

### Database Setup

Implemented in `app/database/`:

- `engine.py`
- `session.py`
- `__init__.py`

Features:

- SQLAlchemy engine factory.
- SQLite `check_same_thread=False`.
- SQLite foreign key PRAGMA enabled.
- SQLite WAL mode PRAGMA configured.
- SQLite busy timeout PRAGMA configured.
- `SessionLocal`.
- `session_scope()` context manager with commit, rollback, and close behavior.

### Configuration

Implemented in `app/core/config.py`.

Supported environment variables:

- `DATABASE_URL`
- `DATABASE_ECHO`
- `DATABASE_POOL_PRE_PING`
- `SQLITE_FOREIGN_KEYS`
- `SQLITE_JOURNAL_MODE`
- `SQLITE_BUSY_TIMEOUT_MS`
- `LOG_LEVEL`
- `APP_LOG_LEVEL`
- `DATABASE_LOG_LEVEL`
- `REPOSITORY_LOG_LEVEL`
- `LOG_CONSOLE_ENABLED`
- `LOG_FILE_ENABLED`
- `LOG_FILE_PATH`
- `LOG_FILE_MAX_BYTES`
- `LOG_FILE_BACKUP_COUNT`
- `LOG_DATE_FORMAT`

Default database URL:

```text
sqlite:///database/irtiqa.db
```

### Logging

Implemented in `app/core/logging.py`.

Features:

- Centralized structured log configuration.
- Application logger namespace: `irtiqa`.
- Database logger namespace: `sqlalchemy.engine`.
- Repository logger namespace: `irtiqa.repositories`.
- Configurable application, database, repository, and root log levels.
- Console logging.
- Rotating file logging.
- Timestamped key-value log format.
- File log directory creation.
- Idempotent reconfiguration through `logging.config.dictConfig`.

### Errors

Implemented in `app/core/errors.py`.

Features:

- Shared base `IrtiqaError`.
- Stable error codes.
- Human-readable messages.
- Optional structured details.
- Optional wrapped cause metadata.
- Serializable `to_dict()` output.
- Integrated error logging through centralized logging.
- Database, repository, validation, service, workflow, future agent, configuration, and external integration exception categories.

### API Skeleton

Implemented in `app/main.py` and `app/api/`.

Features:

- FastAPI app factory through `create_app()`.
- Module-level ASGI application instance for server startup.
- Health endpoint at `/health`.
- API router package structure under `app/api/`.
- Dependency providers for application settings and SQLAlchemy sessions.
- Service dependency providers for companies, contacts, websites, technologies, intent signals, intelligence scores, outreach messages, and agent runs.
- Exception handlers for `IrtiqaError`, FastAPI request validation errors, and unhandled exceptions.
- Lifespan startup and shutdown logging using FastAPI lifespan events.
- Runtime logging configuration during lifespan startup.

### API Endpoints

Implemented Phase 1, Phase 2, and Phase 3 CRUD routes and Lead Retrieval API:

- `POST /companies`
- `GET /companies`
- `GET /companies/{company_id}`
- `PATCH /companies/{company_id}`
- `DELETE /companies/{company_id}`
- `POST /contacts`
- `GET /contacts`
- `GET /contacts/{contact_id}`
- `PATCH /contacts/{contact_id}`
- `DELETE /contacts/{contact_id}`
- `POST /websites`
- `GET /websites`
- `GET /websites/{website_id}`
- `PATCH /websites/{website_id}`
- `DELETE /websites/{website_id}`
- `POST /technologies`
- `GET /technologies`
- `GET /technologies/{technology_id}`
- `PATCH /technologies/{technology_id}`
- `DELETE /technologies/{technology_id}`
- `POST /intent-signals`
- `GET /intent-signals`
- `GET /intent-signals/{intent_signal_id}`
- `PATCH /intent-signals/{intent_signal_id}`
- `DELETE /intent-signals/{intent_signal_id}`
- `POST /intelligence-scores`
- `GET /intelligence-scores`
- `GET /intelligence-scores/{intelligence_score_id}`
- `PATCH /intelligence-scores/{intelligence_score_id}`
- `DELETE /intelligence-scores/{intelligence_score_id}`
- `POST /outreach-messages`
- `GET /outreach-messages`
- `GET /outreach-messages/{outreach_message_id}`
- `PATCH /outreach-messages/{outreach_message_id}`
- `DELETE /outreach-messages/{outreach_message_id}`
- `POST /agent-runs`
- `GET /agent-runs`
- `GET /agent-runs/{agent_run_id}`
- `PATCH /agent-runs/{agent_run_id}`
- `DELETE /agent-runs/{agent_run_id}`

Implemented Lead Retrieval API:

- `GET /leads` — Aggregated lead intelligence with tenant isolation.

Query parameters:

- `limit` (1-500, default 100)
- `offset` (default 0)
- `minimum_score` (0.0-100.0, optional)

Response shape:

- `company_id`, `company_name`, `domain`, `industry`, `status`
- `technologies[]` — `name`, `category`
- `intent_signals[]` — `signal_type`, `confidence`
- `latest_intelligence_score` — `total_score`, `opportunity_score` (fit_score), `urgency_score` (intent_score)
- `outreach_messages[]` — `channel`, `subject`, `message_body`
- `updated_at`

Route conventions:

- Routes depend on services, not repositories.
- Routes reuse existing Pydantic schemas for request and response boundaries.
- List endpoints return `items`, `total`, `limit`, and `offset`.
- Structured API errors are returned through the existing FastAPI exception handlers.
- Delete endpoints return `204 No Content`.

### Workflow Foundation

Implemented in `app/workflows/`:

- `context.py`
- `result.py`
- `states.py`
- `errors.py`
- `policies.py`
- `base.py`
- `registry.py`
- `runner.py`
- `score_refresh.py`
- `scoring_policy.py`

Features:

- Typed workflow context objects.
- Structured workflow and workflow-step result objects.
- Workflow status enum and transition validation.
- Retry policy validation helpers.
- Abstract workflow contract.
- Workflow registry for stable workflow-name lookup.
- Workflow runner with centralized logging and structured error conversion.
- Deterministic `score_refresh.v1` workflow using persisted company, contact, technology, and intent signal records.
- Append-only intelligence score creation with `agent_runs` observability.
- Re-export of existing `WorkflowError` and `WorkflowStateError`.
- `intelligence_pipeline.py`: End-to-end orchestration workflow chaining Deep Scraper → Technographic → Intent Signal → Intelligence Scoring → Personalization agents.
- `intelligence_pipeline` executes all 5 agents sequentially with error propagation and `agent_runs` observability at each step.

Current boundaries:

- Workflows are designed to call services, never repositories.
- Services remain transaction owners.
- `score_refresh` and `intelligence_pipeline` are concrete workflows.
- Background Job Foundation integrates with workflows for scheduling and execution.

### Transaction Ownership Strategy

Current decision:

- Services own transaction boundaries.
- API routes should call services, not repositories directly.
- Repositories remain data-access only and never commit.
- `session_scope()` is the canonical unit-of-work boundary for current service methods.
- FastAPI route handlers should stay thin: validate request payloads with schemas, call services, and serialize responses.
- The FastAPI `get_db_session()` dependency is available as low-level infrastructure, but it is not the default transaction boundary for CRUD routes while services own transactions.

Evaluation:

- Service-owned transactions match the current implementation of `BaseService`, which wraps each use-case operation in `session_scope()`.
- Service-owned transactions keep API, future workflow, and future job callers consistent because all callers receive the same service behavior.
- Service-owned transactions preserve repository isolation because repositories accept sessions but do not create, commit, or roll back sessions.
- API-level transactions would require refactoring services to accept an injected session or unit-of-work. Introducing that now would duplicate transaction ownership and risk nested or conflicting session behavior.

Guidance for Task 9:

- Add FastAPI dependencies for service instances, such as `get_company_service()`, instead of injecting repositories into routes.
- Do not wrap service calls in an API-level commit/rollback dependency.
- Do not pass `get_db_session()` sessions into current services unless the service layer is intentionally refactored to support external unit-of-work ownership.
- If a future workflow needs multiple service operations in one atomic transaction, introduce an explicit unit-of-work abstraction rather than quietly mixing API-level and service-level transactions.

### Repositories

Implemented in `app/repositories/`:

- `base.py`
- `company_repository.py`
- `contact_repository.py`
- `website_repository.py`
- `technology_repository.py`
- `intent_signal_repository.py`
- `intelligence_score_repository.py`
- `outreach_message_repository.py`
- `agent_run_repository.py`
- `job_repository.py`
- `evidence_repository.py`
- `membership_repository.py`
- `organization_repository.py`
- `user_repository.py`

Repository convention:

- Repositories receive a SQLAlchemy `Session`.
- Repositories do not commit transactions.
- Transaction boundaries are currently controlled by services through `session_scope()`.

### Services

Implemented in `app/services/`:

- `base.py`
- `company_service.py`
- `contact_service.py`
- `website_service.py`
- `technology_service.py`
- `intent_signal_service.py`
- `intelligence_score_service.py`
- `outreach_message_service.py`
- `agent_run_service.py`
- `auth_service.py`
- `evidence_service.py`
- `job_service.py`
- `membership_service.py`
- `organization_service.py`
- `lead_retrieval_service.py`

Service convention:

- Services use repositories for data access.
- Services own business-use-case boundaries above repositories.
- Services use `session_scope()` for transaction safety.
- Services are the default dependency boundary for future FastAPI CRUD routes.
- Services support generic create, read, update, list, count, and delete operations.
- Services use centralized logging through the `irtiqa.services` logger namespace.
- Services use structured errors from `app/core/errors.py`.
- Repositories remain data-access only and do not commit transactions.

### Schemas

Implemented Pydantic v2 schemas in `app/schemas/`:

- `base.py`
- `company.py`
- `contact.py`
- `website.py`
- `technology.py`
- `intent_signal.py`
- `intelligence_score.py`
- `outreach_message.py`
- `agent_run.py`
- `auth.py`
- `evidence.py`
- `job.py`
- `membership.py`
- `organization.py`
- `lead.py`

Schema convention:

- Each current entity has `Create`, `Update`, `Read`, and `List` schemas.
- Read schemas use `from_attributes=True` for ORM and future FastAPI response compatibility.
- Create schemas validate required persistence fields before service calls.
- Update schemas validate partial update payloads and reject empty update bodies.
- List schemas include `items`, `total`, `limit`, and `offset`.
- Status values and numeric ranges mirror current database constraints.

### Migrations

Implemented Alembic setup:

- `alembic.ini`
- `database/migrations/env.py`
- `database/migrations/script.py.mako`
- `database/migrations/versions/20260531_0001_initial_schema.py`
- `database/migrations/versions/20260531_0002_database_hardening.py`
- `database/migrations/versions/20260603_0003_add_website_content_columns.py`
- `database/migrations/versions/20260609_0003_add_jobs_table.py`
- `database/migrations/versions/20260611_0004_create_evidence_records.py`
- `database/migrations/versions/20260612_0005_create_auth_tables.py`
- `database/migrations/versions/20260613_0006_create_organizations_memberships.py`

### Tests

Implemented pytest foundation in `tests/`:

- `tests/conftest.py`
- `tests/integration/test_database_hardening.py`
- `tests/integration/api/test_app.py`
- `tests/integration/api/test_crud_phase_1.py`
- `tests/integration/api/test_crud_phase_2.py`
- `tests/integration/api/test_crud_phase_3.py`
- `tests/integration/jobs/test_job_api.py`
- `tests/integration/jobs/test_job_lifecycle.py`
- `tests/unit/workflows/test_context.py`
- `tests/unit/workflows/test_result.py`
- `tests/unit/workflows/test_states.py`
- `tests/unit/workflows/test_policies.py`
- `tests/unit/workflows/test_registry.py`
- `tests/unit/workflows/test_runner.py`
- `tests/unit/workflows/test_score_refresh.py`
- `tests/unit/workflows/test_scoring_policy.py`
- `tests/unit/core/test_errors.py`
- `tests/unit/core/test_logging.py`
- `tests/unit/test_models.py`
- `tests/unit/test_schemas.py`
- `tests/integration/test_migrations.py`
- `tests/integration/test_repositories.py`
- `tests/integration/test_score_refresh_workflow.py`
- `tests/integration/test_services.py`
- `tests/integration/test_session_scope.py`
- `tests/unit/jobs/test_errors.py`
- `tests/unit/jobs/test_retry_policy.py`
- `tests/unit/jobs/test_runner.py`
- `tests/unit/jobs/test_scheduler.py`

Coverage currently verifies:

- Alembic migrations upgrade correctly.
- Alembic migration version is recorded.
- Migration-created columns match SQLAlchemy model metadata.
- Migration downgrade removes application tables.
- Model metadata contains the current schema.
- Models include UUID primary keys and timestamps.
- ORM relationships persist and load correctly.
- All repository query methods work against SQLite.
- Service create and query operations work against SQLite.
- Service error handling returns structured errors.
- Service transaction rollback works on database errors.
- Pydantic schemas validate create and update payloads.
- Pydantic read and list schemas serialize from ORM-compatible attributes.
- Schema validation rejects invalid statuses, invalid numeric ranges, blank strings, and empty update payloads.
- `session_scope()` commits on success.
- `session_scope()` rolls back on exception.
- Structured file logging works.
- Console logging works.
- Application, database, and repository log levels are configurable.
- Logger factory names are stable.
- Invalid log levels fail explicitly.
- Logging configuration is idempotent.
- Structured errors expose stable code, message, details, and string output.
- Structured errors serialize to dictionaries.
- Structured errors support contextual detail updates.
- Required exception categories are represented in the hierarchy.
- Error logging emits structured extra fields.
- SQLite foreign keys, WAL mode, and busy timeout are configured.
- Check constraints exist for status, confidence, strength, and score fields.
- Status constraints are enforced.
- Confidence and strength constraints are enforced.
- Intelligence score range constraints are enforced.
- FastAPI health endpoint returns service status.
- FastAPI dependency overrides are supported.
- FastAPI lifespan startup executes through `TestClient`.
- FastAPI CRUD endpoints for companies, contacts, and websites support create, read, update, delete, and pagination-ready list responses.
- FastAPI CRUD endpoints for technologies, intent signals, and intelligence scores support create, read, update, delete, and pagination-ready list responses.
- FastAPI CRUD endpoints for outreach messages and agent runs support create, read, update, delete, and pagination-ready list responses.
- FastAPI CRUD error responses use the structured error envelope for conflict, not found, and validation failures.
- Workflow context validation rejects invalid workflow targets and options.
- Workflow result objects serialize stable status, output, step, and error payloads.
- Workflow state transition validation rejects invalid transitions with structured errors.
- Workflow retry policies validate retry and backoff bounds.
- Workflow registry registers, resolves, lists, and rejects invalid workflow definitions.
- Workflow runner logs execution and returns structured results for success, structured errors, and unexpected failures.
- `score_refresh.v1` scoring is deterministic, bounded, versioned, and evidence-only.
- `score_refresh` appends intelligence scores, records agent run observability, and returns output ids.

Last verified command:

```text
python -m pytest
```

Result:

```text
489 passed, 27 skipped
```

PostgreSQL verification tests:

```text
python -m pytest tests/integration/test_postgresql_compatibility.py
24 passed
```

Full suite against PostgreSQL:

```text
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa_verify python -m pytest
307 passed, 1 expected failure (health endpoint asserts "sqlite")
```

Additional migration verification:

```text
python -m alembic upgrade head
python -m alembic check
```

Result:

```text
No new upgrade operations detected.
```

Note: tests use isolated temporary SQLite databases. `database/irtiqa.db` remains a generated artifact and is ignored by `.gitignore`.

## Completed Tasks

Completed:

- Designed architecture documentation.
- Designed SQLite-first, PostgreSQL-compatible database schema.
- Generated SQLAlchemy models for all current tables.
- Generated Alembic initial migration.
- Verified migration ran correctly against SQLite.
- Implemented database engine and session management.
- Implemented repository pattern.
- Created project metadata and dependency manifest.
- Created `.gitignore`.
- Created `.env.example`.
- Created `README.md`.
- Updated stale documentation to match current schema.
- Removed generated artifacts from the repository.
- Added pytest setup and database test fixtures.
- Added model tests.
- Added migration tests.
- Added repository tests.
- Added `session_scope()` commit and rollback tests.
- Added centralized structured logging.
- Added logging configuration settings.
- Added repository debug logging hooks.
- Added logging tests.
- Added production-ready structured error hierarchy.
- Added structured error logging integration.
- Added structured error tests.
- Added SQLite WAL mode configuration.
- Added SQLite busy timeout configuration.
- Added portable database check constraints.
- Added Alembic database hardening migration.
- Added database hardening tests.
- Documented local SQLite backup strategy.
- Documented automated backup recommendations.
- Documented SQLite restore procedure.
- Documented WAL-specific backup considerations.
- Documented backup order around migrations.
- Documented SQLite-to-PostgreSQL migration backup considerations.
- Added service layer above repositories.
- Added service classes for all current entities.
- Added service transaction boundaries through `session_scope()`.
- Added service structured error handling and centralized logging.
- Added service layer integration tests.
- Added Pydantic v2 schema layer.
- Added create, update, read, and list schemas for all current entities.
- Added schema validation tests.
- Added schema serialization tests.
- Added FastAPI application factory.
- Added API router structure.
- Added health endpoint.
- Added FastAPI dependency providers for settings and database sessions.
- Added FastAPI exception handlers integrated with structured errors.
- Added FastAPI lifespan startup and shutdown logging.
- Added FastAPI health and startup tests.
- Documented service-owned transaction strategy for future CRUD APIs.
- Added service update and count support for CRUD API route behavior.
- Added repository count support for pagination-ready list responses.
- Added FastAPI service dependencies for companies, contacts, and websites.
- Added CRUD API endpoints for companies, contacts, and websites.
- Added FastAPI CRUD integration and error handling tests for companies, contacts, and websites.
- Documented CRUD API Endpoints Phase 1 completion.
- Added FastAPI service dependencies for technologies, intent signals, and intelligence scores.
- Added CRUD API endpoints for technologies, intent signals, and intelligence scores.
- Added FastAPI CRUD integration and error handling tests for technologies, intent signals, and intelligence scores.
- Documented CRUD API Endpoints Phase 2 completion.
- Added FastAPI service dependencies for outreach messages and agent runs.
- Added CRUD API endpoints for outreach messages and agent runs.
- Added FastAPI CRUD integration and error handling tests for outreach messages and agent runs.
- Documented CRUD API Endpoints Phase 3 completion.
- Completed the CRUD API milestone for all current persisted entities.
- Added workflow foundation package.
- Added workflow context, result, state, error, policy, registry, and runner contracts.
- Added workflow foundation unit tests.
- Documented Workflow Foundation Phase 1 completion.
- Added deterministic `score_refresh.v1` scoring policy.
- Added executable `score_refresh` workflow.
- Added append-only score creation and `agent_runs` observability for `score_refresh`.
- Added unit and integration tests for `score_refresh`.
- Added Agent Interface Foundation package.
- Added async `BaseAgent` abstract class with lifecycle management.
- Added `AgentContext` Pydantic model for agent input.
- Added `AgentResult` Pydantic model for agent output.
- Added `AgentRegistry` for name-based agent class lookup.
- Added `AgentRunOutput` typed dictionary for `_run()` return values.
- Added `AgentValidationError`, `AgentNetworkError`, `AgentRateLimitError`, and `AgentTimeoutError` to the structured error hierarchy.
- Added agent error re-exports in `app/agents/errors.py`.
- Added agent interface unit tests for context, result, registry, and lifecycle.
- Documented Agent Interface Foundation completion.
- Implemented Deep Scraper Agent logic mapping normalized URLs and storing `raw_html`.
- Implemented Technographic Agent to detect tools from `raw_html` via signature matching.
- Developed scoring algorithms and tested confidence logic (70/30 weighting).
- Implemented Intent Signal Agent to detect commercial buying signals from `extracted_text` and detected technologies.
- Added deterministic intent rule registry covering hiring, growth, expansion, funding, product launch, partnership, enterprise readiness, and digital transformation signals.
- Added intent signal normalization, confidence scoring, strength scoring, in-run deduplication, cross-run duplicate suppression through `IntentSignalService`, and unit tests.
- Implemented Intelligence Scoring Agent utilizing `DeterministicScoreRefreshPolicy` to compute `IntelligenceScore`s transparently.
- Added Background Job Foundation: `jobs` table with Alembic migration, SQLAlchemy `Job` model, `JobRepository` with status transition helpers, `JobService` with scheduling/retry/cancellation logic, `JobRunner` for agent/workflow execution, `JobScheduler` for polling loop, `JobScheduleAgentRequest`/`JobScheduleWorkflowRequest` schemas, and REST endpoints for schedule/get/list/cancel/retry operations.
- Added FastAPI lifespan integration for `JobScheduler` startup and graceful shutdown.
- Added unit tests for retry policy, scheduler, runner, and errors; integration tests for job lifecycle and API endpoints.
- Completed PostgreSQL Compatibility Verification: verified engine configs, Alembic migrations, constraints, CRUD, datetime, UUID, cascading, and job lifecycle against PostgreSQL 18.x.
- Fixed migration `20260531_0002`: `recreate="always"` -> `recreate="auto"` for PostgreSQL compatibility.
- Fixed migration `20260609_0003`: added `op.f()` wrapper to constraint names for PostgreSQL compatibility.
- Added 24 PostgreSQL verification tests in `tests/integration/test_postgresql_compatibility.py`.
- Implemented Lead Retrieval API: tenant-scoped aggregated lead intelligence at `GET /api/v1/leads`.
- Added `LeadRetrievalService` with batch aggregation queries to avoid N+1 patterns.
- Added `app/schemas/lead.py` with `LeadResponse`, `LeadListResponse`, and nested response schemas.
- Added `count_by_organization` method to `CompanyRepository` for tenant-scoped total count.
- Added `get_lead_retrieval_service` dependency provider in `app/api/dependencies.py`.
- Added `GET /api/v1/leads` endpoint with `limit`, `offset`, and `minimum_score` query parameters.
- Added unit tests for lead response schemas (`tests/unit/test_lead_schemas.py`).
- Added service integration tests for lead retrieval aggregation, tenant isolation, score filtering, and pagination (`tests/integration/test_lead_retrieval_service.py`).
- Added API integration tests for lead retrieval endpoint (`tests/integration/api/test_lead_retrieval_api.py`).

Documentation currently aligned with implemented schema:

- `docs/database.md`
- `docs/agents.md`
- `docs/workflows.md`
- `docs/agent_interface_design.md`
- `docs/project_state.md`
- `docs/project_handoff.md`
- `docs/codex_bootstrap.md`

## Open Issues

Known issues or gaps:

- No Docker or deployment configuration exists yet.
- No repository methods enforce domain-level validation.
- `technology_catalog` is not implemented; `technologies` currently stores company-specific detections directly.
- There is no dedicated `workflow_runs` table; workflow state is expected to be inferred from `agent_runs` for now.
- Multi-Tenancy Phase 2 (JWT org claims, TenantContext, auth integration) is complete.
- Multi-Tenancy Phase 3 (organization_id on domain tables, tenant-scoped queries) is complete (migration 20260616_0007).
- Invitations and API Keys are planned for future phases.

## CI/CD Pipeline

CI is configured with GitHub Actions. Every push and pull request runs:

- **validate** job: ruff linting (advisory), mypy type checking (advisory), compileall syntax verification (blocking).
- **test** job: SQLite migration application, alembic schema drift check, SQLite full test suite (blocking), PostgreSQL 18 service container with migration application and 24 compatibility tests (blocking).

Ruff and mypy are in advisory mode during the current phase to allow incremental debt reduction. They report violations as warnings in the check output but do not block the pipeline. Test execution is the primary merge gate. A future milestone will remove `continue-on-error` after pre-existing code quality issues are resolved.

The full pipeline runs on `ubuntu-latest` with Python 3.11 and completes within 7 minutes.
