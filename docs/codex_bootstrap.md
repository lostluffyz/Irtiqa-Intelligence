# Codex Bootstrap

Use this file first when starting a new Codex session on Irtiqa Intelligence.

## Project Mission

Irtiqa Intelligence is a production-grade lead intelligence platform.

The long-term product goal is to enrich companies and contacts, detect technologies, identify intent signals, score opportunities, and generate outreach-ready messages through a modular agent-based architecture.

## AGENTS.md Summary

Repository rules:

- Build a production-grade lead intelligence platform.
- Backend architecture is FastAPI-based.
- Database is SQLite first.
- Future PostgreSQL support is required.
- Architecture must be agent-based and modular.
- Type hints are required.
- Logging is required.
- Error handling is required.
- Never create mock data.
- Never create temporary solutions.
- Maintain clean architecture.
- Follow SOLID principles.

Planned future agents:

1. Deep Scraper Agent
2.  **Intent Signal Agent**: Build upon base agent concepts to extract behavioral signals.
3.  **Intelligence Scoring Agent**: Build on workflow abstractions to continuously score leads.
4. Personalization Agent

Do not implement agents yet.

## Current Architecture

Implemented package structure:

```text
app/
|-- main.py
|-- api/
|   |-- dependencies.py
|   |-- errors.py
|   |-- router.py
|   `-- v1/
|       |-- router.py
|       `-- endpoints/
|           |-- health.py
|           |-- companies.py
|           |-- contacts.py
|           |-- websites.py
|           |-- technologies.py
|           |-- intent_signals.py
|           |-- intelligence_scores.py
|           |-- outreach_messages.py
|           `-- agent_runs.py
|-- core/
|   |-- config.py
|   |-- errors.py
|   `-- logging.py
|-- database/
|   |-- engine.py
|   `-- session.py
|-- models/
|   |-- base.py
|   |-- company.py
|   |-- contact.py
|   |-- website.py
|   |-- technology.py
|   |-- intent_signal.py
|   |-- intelligence_score.py
|   |-- outreach_message.py
|   `-- agent_run.py
|-- repositories/
|   |-- base.py
|   |-- company_repository.py
|   |-- contact_repository.py
|   |-- website_repository.py
|   |-- technology_repository.py
|   |-- intent_signal_repository.py
|   |-- intelligence_score_repository.py
|   |-- outreach_message_repository.py
|   `-- agent_run_repository.py
`-- services/
    |-- base.py
    |-- company_service.py
    |-- contact_service.py
    |-- website_service.py
    |-- technology_service.py
    |-- intent_signal_service.py
    |-- intelligence_score_service.py
    |-- outreach_message_service.py
    `-- agent_run_service.py
`-- agents/
    |-- __init__.py
    |-- base.py
    |-- context.py
    |-- result.py
    |-- registry.py
    `-- errors.py
`-- schemas/
    |-- base.py
    |-- company.py
    |-- contact.py
    |-- website.py
    |-- technology.py
    |-- intent_signal.py
    |-- intelligence_score.py
    |-- outreach_message.py
    `-- agent_run.py
`-- workflows/
    |-- base.py
    |-- context.py
    |-- errors.py
    |-- policies.py
    |-- registry.py
    |-- result.py
    |-- runner.py
    |-- score_refresh.py
    |-- scoring_policy.py
    `-- states.py
```

Implemented database tooling:

```text
alembic.ini
database/migrations/
|-- env.py
|-- script.py.mako
`-- versions/
    |-- 20260531_0001_initial_schema.py
    `-- 20260531_0002_database_hardening.py
```

Implemented tests:

```text
tests/
|-- conftest.py
|-- unit/
|   |-- core/
|   |   |-- test_errors.py
|   |   `-- test_logging.py
|   |-- agents/
|   |   |-- test_context.py
|   |   |-- test_result.py
|   |   |-- test_registry.py
|   |   `-- test_base.py
|   |-- test_models.py
|   `-- test_schemas.py
`-- integration/
    |-- api/
    |   |-- test_app.py
    |   |-- test_crud_phase_1.py
    |   |-- test_crud_phase_2.py
    |   `-- test_crud_phase_3.py
    |-- test_database_hardening.py
    |-- test_migrations.py
    |-- test_repositories.py
    |-- test_services.py
    `-- test_session_scope.py
```

## Current Status

The project is in backend foundation stage.

Completed:

- Task 1: Testing Foundation.
- Task 2: Core Logging Setup.
- Task 3: Structured Error Handling.
- Task 4: Database Hardening.
- Task 5: SQLite Backup Strategy Documentation.
- Task 6: Service Layer.
- Task 7: Pydantic Schemas.
- Task 8: FastAPI Skeleton.
- Task 9: CRUD API Endpoints Phase 1 for companies, contacts, and websites.
- Task 9: CRUD API Endpoints Phase 2 for technologies, intent signals, and intelligence scores.
- Task 9: CRUD API Endpoints Phase 3 for outreach messages and agent runs.
- Task 9: Full CRUD API milestone for all current persisted entities.
- Task 10: Workflow Foundation Phase 1.
- Phase 2: `score_refresh` workflow.
- Task 11: Agent Interface Foundation.

Implemented:

- SQLAlchemy ORM models.
- Alembic migration setup.
- Initial schema migration.
- Database hardening migration.
- SQLite engine and session management.
- SQLite foreign keys, WAL mode, and busy timeout.
- Repository pattern.
- Service layer.
- Pydantic v2 schema layer.
- FastAPI application factory.
- FastAPI health endpoint.
- FastAPI API router structure.
- FastAPI dependency providers.
- FastAPI service dependency providers for companies, contacts, websites, technologies, intent signals, intelligence scores, outreach messages, and agent runs.
- FastAPI structured exception handlers.
- FastAPI lifespan startup and shutdown logging.
- CRUD API endpoints for companies, contacts, and websites.
- CRUD API endpoints for technologies, intent signals, and intelligence scores.
- CRUD API endpoints for outreach messages and agent runs.
- Pagination-ready list responses for companies, contacts, websites, technologies, intent signals, intelligence scores, outreach messages, and agent runs.
- Centralized structured logging.
- Structured error hierarchy.
- Workflow foundation.
- Deterministic `score_refresh.v1` scoring policy.
- Executable `score_refresh` workflow using existing persisted data.
- Agent Interface Foundation with async `BaseAgent`, `AgentContext`, `AgentResult`, `AgentRegistry`.
- Structured agent error hierarchy with `AgentValidationError`, `AgentNetworkError`, `AgentRateLimitError`, `AgentTimeoutError`.
- Deep Scraper Agent with async fetching, `robots.txt` enforcement, and DOM parsing.
- Project metadata.
- Documentation.
- Pytest foundation.

Not implemented:

- Jobs.
- Concrete agents (except Deep Scraper).
- Frontend.
- CI.

Latest known full test result:

```text
python -m pytest
192 passed
```

Latest known migration verification:

```text
python -m alembic upgrade head
python -m alembic check
No new upgrade operations detected.
```

## Repository Health Summary

Current health:

- Foundation status: healthy.
- Current test count: `192 passed`.
- Schema drift status: clean after upgrading the local SQLite database to Alembic head.
- Architecture status: FastAPI skeleton, CRUD API Endpoints, database, repositories, services, schemas, workflow foundation, `score_refresh`, Agent Interface Foundation, Deep Scraper Agent, logging, errors, and backup documentation are implemented.
- Runtime surface status: health endpoint and CRUD endpoints exist; workflow foundation exists;
1.  **Agent Interface Foundation**: Standardized interfaces in `app.agents` with `BaseAgent`, context, and result structures.
2.  **Deep Scraper Agent**: Asynchronous, robot-compliant HTTP client storing HTML in `websites` table.
3.  **Technographic Agent**: Signature-matching technology extraction logic utilizing a 70/30 weighting logic and persisting to `technologies` table via the `TechnologyService`.
4.  **Database & Migrations**: Schema locked in. Hardening is in place.
5.  **Service Layer**: Business boundaries over repositories with robust transaction scope support.
- Artifact status: generated local artifacts such as `database/irtiqa.db`, `.pytest_cache/`, and `__pycache__/` must remain uncommitted.
- Next milestone: Technographic Agent Implementation.

## Current Database Schema

Implemented tables:

- `companies`
- `contacts`
- `websites` (updated with `raw_html` and `extracted_text`)
- `technologies`
- `intent_signals`
- `intelligence_scores`
- `outreach_messages`
- `agent_runs`

Canonical names:

- Use `contacts`, not `leads`.
- Use `outreach_messages`, not `personalization_outputs`.
- Use `agent_runs`; there is no `agent_run_events` table yet.
- There is no `source_observations` table yet.

## Database Hardening Decisions

SQLite behavior:

- `PRAGMA foreign_keys=ON`
- `PRAGMA journal_mode=WAL`
- `PRAGMA busy_timeout=5000`

Configured through:

- `SQLITE_FOREIGN_KEYS`
- `SQLITE_JOURNAL_MODE`
- `SQLITE_BUSY_TIMEOUT_MS`

Integrity constraints:

- `companies.status`: `active`, `needs_review`, `archived`
- `contacts.status`: `active`, `unverified`, `qualified`, `disqualified`, `archived`
- `agent_runs.status`: `pending`, `running`, `succeeded`, `failed`, `cancelled`
- `outreach_messages.status`: `draft`, `ready_for_review`, `approved`, `sent`, `archived`
- confidence fields: `0.0` to `1.0`
- `intent_signals.strength`: `0.0` to `1.0`
- intelligence score fields: `0.0` to `100.0`

## Logging Architecture

Implemented in `app/core/logging.py`.

Logger namespaces:

- application: `irtiqa`
- database: `sqlalchemy.engine`
- repositories: `irtiqa.repositories`

Features:

- configurable root, application, database, and repository log levels
- console logging
- rotating file logging
- timestamped key-value format
- log file directory creation
- idempotent configuration

## Error Hierarchy

Implemented in `app/core/errors.py`.

Base:

- `IrtiqaError`

Categories:

- configuration errors
- database errors
- repository errors
- validation errors
- service errors
- workflow errors
- future agent errors
- external integration errors

Features:

- stable error codes
- human-readable messages
- structured details
- optional wrapped cause metadata
- `to_dict()` serialization
- integrated structured logging

## FastAPI Skeleton

Implemented in `app/main.py` and `app/api/`.

Features:

- `create_app()` app factory
- module-level ASGI `app`
- health endpoint at `/health`
- settings dependency provider
- SQLAlchemy session dependency provider
- service dependency providers for companies, contacts, websites, technologies, intent signals, intelligence scores, outreach messages, and agent runs
- structured handlers for `IrtiqaError`, request validation errors, and unhandled exceptions
- lifespan startup and shutdown logging using FastAPI lifespan events

Implemented CRUD API Phase 1:

- `POST`, list `GET`, id `GET`, `PATCH`, and `DELETE` for `/companies`
- `POST`, list `GET`, id `GET`, `PATCH`, and `DELETE` for `/contacts`
- `POST`, list `GET`, id `GET`, `PATCH`, and `DELETE` for `/websites`
- list responses include `items`, `total`, `limit`, and `offset`
- routes use services rather than repositories directly
- structured errors use the existing API error envelope

Implemented CRUD API Phase 2:

- `POST`, list `GET`, id `GET`, `PATCH`, and `DELETE` for `/technologies`
- `POST`, list `GET`, id `GET`, `PATCH`, and `DELETE` for `/intent-signals`
- `POST`, list `GET`, id `GET`, `PATCH`, and `DELETE` for `/intelligence-scores`
- list responses include `items`, `total`, `limit`, and `offset`
- routes use services rather than repositories directly
- structured errors use the existing API error envelope

Implemented CRUD API Phase 3:

- `POST`, list `GET`, id `GET`, `PATCH`, and `DELETE` for `/outreach-messages`
- `POST`, list `GET`, id `GET`, `PATCH`, and `DELETE` for `/agent-runs`
- list responses include `items`, `total`, `limit`, and `offset`
- routes use services rather than repositories directly
- structured errors use the existing API error envelope
- this completes the CRUD API milestone for all current persisted entities

## Transaction Ownership

Current decision:

- Services own transaction boundaries.
- Repositories receive SQLAlchemy sessions but never commit, roll back, or create sessions.
- `session_scope()` is the canonical unit-of-work boundary for current service methods.
- FastAPI routes should call services, not repositories directly.
- FastAPI routes should not open API-level commit/rollback transactions around service calls.
- `get_db_session()` exists as low-level infrastructure, but it is not the default CRUD transaction boundary while services own transactions.
- If future workflows need multiple service operations in one atomic transaction, introduce an explicit unit-of-work abstraction rather than mixing API-level and service-level transactions.

## Implemented Workflow: score_refresh

Implemented in:

- `app/workflows/score_refresh.py`
- `app/workflows/scoring_policy.py`

Behavior:

- Uses only persisted `companies`, `contacts`, `technologies`, and `intent_signals`.
- Creates append-only `intelligence_scores` records.
- Records observability through `agent_runs` with `agent_name=score_refresh_policy`.
- Returns created score ids through `WorkflowResult.output_ids["intelligence_scores"]`.
- Uses deterministic `score_refresh.v1` scoring.
- Does not implement agents, jobs, scraping, or external APIs.

## Development Rules

Always:

- Read `AGENTS.md`.
- Read `docs/project_state.md`.
- Read `docs/project_handoff.md`.
- Keep changes scoped to the requested task.
- Add or update tests for implemented behavior.
- Update handoff docs after foundational tasks.
- Use SQLite-compatible and PostgreSQL-conscious SQLAlchemy patterns.
- Keep repositories free of transaction ownership.
- Keep generated artifacts out of the repo.

Do not:

- Add mock data.
- Add seed data unless explicitly requested as production reference data.
- Add temporary hacks.
- Skip tests for foundation changes.
- Implement agents before the platform foundation is ready.
- Let docs drift from the implemented schema.
- Commit `database/irtiqa.db`, `__pycache__/`, or `.pytest_cache/`.

## What Should Be Built Next

Next recommended task:

```text
Technographic Agent Implementation
```

Recommended scope:

- Implement the Technographic Intelligence Agent by subclassing `BaseAgent`.
- Leverage the raw HTML collected by the Deep Scraper to extract technologies.
- Add focused agent tests with appropriate DOM mocks.
- Update `docs/project_state.md`.
- Update `docs/project_handoff.md`.

## Reference Documents

Use these for deeper context:

- `AGENTS.md`
- `README.md`
- `docs/project_state.md`
- `docs/project_handoff.md`
- `docs/database.md`
- `docs/agents.md`
- `docs/workflows.md`
