# Project Handoff

This document is the canonical handoff for Irtiqa Intelligence. It is written so a completely new Codex session can continue development without needing prior conversation history.

## 1. Current Repository Architecture

Irtiqa Intelligence is currently in the backend foundation phase. The implemented work includes project metadata, database architecture, SQLAlchemy models, Pydantic schemas, Alembic migrations, SQLite session management, repository classes, service classes, centralized logging, structured errors, database hardening, SQLite backup strategy documentation, a FastAPI application skeleton, a health endpoint, CRUD API Endpoints Phase 1 for companies, contacts, and websites, CRUD API Endpoints Phase 2 for technologies, intent signals, and intelligence scores, CRUD API Endpoints Phase 3 for outreach messages and agent runs, workflow foundation, the concrete `score_refresh` workflow, Agent Interface Foundation, and tests.

The CRUD API milestone is complete for all current persisted entities. Workflow foundation and `score_refresh` exist. Agent Interface Foundation with async `BaseAgent`, `AgentContext`, `AgentResult`, and `AgentRegistry` is complete. Deep Scraper Agent, Technographic Agent, Intent Signal Agent, Intelligence Scoring Agent, and Personalization Agent have been implemented. Jobs, frontend, and external integrations do not exist yet.

Current repository layout:

```text
Irtiqa-Intelligence/
|-- AGENTS.md
|-- README.md
|-- pyproject.toml
|-- alembic.ini
|-- .env.example
|-- .gitignore
|
|-- app/
|   |-- __init__.py
|   |
|   |-- api/
|   |   |-- __init__.py
|   |   |-- dependencies.py
|   |   |-- errors.py
|   |   |-- router.py
|   |   `-- v1/
|   |
|   |-- core/
|   |   |-- __init__.py
|   |   |-- config.py
|   |   |-- errors.py
|   |   `-- logging.py
|   |
|   |-- database/
|   |   |-- __init__.py
|   |   |-- engine.py
|   |   `-- session.py
|   |
|   |-- models/
|   |   |-- __init__.py
|   |   |-- base.py
|   |   |-- company.py
|   |   |-- contact.py
|   |   |-- website.py
|   |   |-- technology.py
|   |   |-- intent_signal.py
|   |   |-- intelligence_score.py
|   |   |-- outreach_message.py
|   |   `-- agent_run.py
|   |
|   `-- repositories/
|       |-- __init__.py
|       |-- base.py
|       |-- company_repository.py
|       |-- contact_repository.py
|       |-- website_repository.py
|       |-- technology_repository.py
|       |-- intent_signal_repository.py
|       |-- intelligence_score_repository.py
|       |-- outreach_message_repository.py
|       `-- agent_run_repository.py
|
|-- app/agents/
|   |-- __init__.py
|   |-- base.py
|   |-- context.py
|   |-- result.py
|   |-- registry.py
|   |-- errors.py
|   |
|   |-- deep_scraper/
|   |-- intelligence_scoring/
|   |-- intent_signal/
|   |-- personalization/
|   `-- technographic/
|
|-- app/services/
|   |-- __init__.py
|   |-- base.py
|   |-- company_service.py
|   |-- contact_service.py
|   |-- website_service.py
|   |-- technology_service.py
|   |-- intent_signal_service.py
|   |-- intelligence_score_service.py
|   |-- outreach_message_service.py
|   `-- agent_run_service.py
|
|-- app/main.py
|
|-- app/schemas/
|   |-- __init__.py
|   |-- base.py
|   |-- company.py
|   |-- contact.py
|   |-- website.py
|   |-- technology.py
|   |-- intent_signal.py
|   |-- intelligence_score.py
|   |-- outreach_message.py
|   `-- agent_run.py
|
|-- app/workflows/
|   |-- __init__.py
|   |-- base.py
|   |-- context.py
|   |-- errors.py
|   |-- policies.py
|   |-- registry.py
|   |-- result.py
|   |-- runner.py
|   |-- score_refresh.py
|   |-- scoring_policy.py
|   `-- states.py
|
|-- database/
|   `-- migrations/
|       |-- env.py
|       |-- script.py.mako
|       `-- versions/
|           `-- 20260531_0001_initial_schema.py
|           `-- 20260531_0002_database_hardening.py
|
|-- docs/
|   |-- agents.md
|   |-- database.md
|   |-- workflows.md
|   |-- project_state.md
|   `-- project_handoff.md
|
|-- tests/
|   |-- __init__.py
|   |-- conftest.py
|   |-- unit/
|   |   |-- __init__.py
|   |   |-- core/
|   |   |-- test_models.py
|   |   `-- test_schemas.py
|   `-- integration/
|       |-- __init__.py
|       |-- api/
|       |-- test_database_hardening.py
|       |-- test_migrations.py
|       |-- test_repositories.py
|       `-- test_session_scope.py
|
|-- agents/
|-- backend/
|-- frontend/
`-- prompts/
```

Top-level placeholder directories currently exist:

- `agents/`
- `backend/`
- `frontend/`
- `prompts/`

These directories are not part of the implemented architecture yet. The implemented Python package currently lives under `app/`.

## 2. Database Schema Summary

The current database is SQLite-first and SQLAlchemy-based, with a future PostgreSQL migration path.

Implemented tables:

1. `companies`
2. `contacts`
3. `websites`
4. `technologies`
5. `intent_signals`
6. `intelligence_scores`
7. `outreach_messages`
8. `agent_runs`

### Schema Relationships

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

intelligence_scores 1--many outreach_messages
```

### Table Purpose Summary

`companies`

Stores canonical company accounts. The primary lookup is `domain`.

`contacts`

Stores people associated with companies. Contacts replace the earlier planning term `leads`.

`websites`

Stores company-owned or company-related URLs discovered during enrichment.

`technologies`

Stores company-specific detected technology usage. This is not yet split into a global technology catalog plus company technology join table.

`intent_signals`

Stores buying intent, operational signals, technology change signals, growth signals, and related triggers.

`intelligence_scores`

Stores versioned score records for companies and optional contacts. Scores are intended to be append-only.

`outreach_messages`

Stores outreach message drafts and personalization outputs. This replaces the earlier planning term `personalization_outputs`.

`agent_runs`

Stores execution history for future agents and workflows. Until a dedicated workflow table exists, workflow status should be inferred from relevant agent run records.

### Database Design Decisions

- UUIDs are stored as `String(36)` for SQLite compatibility.
- PostgreSQL may later migrate these to native UUIDs if needed.
- `created_at` and `updated_at` exist on every model through `TimestampMixin`.
- SQLAlchemy `DateTime(timezone=True)` is used, although SQLite does not truly preserve timezone semantics.
- Foreign keys use `CASCADE` where child records are owned by the parent, and `SET NULL` where historical records should survive parent deletion.
- SQLite foreign keys are enabled with `PRAGMA foreign_keys=ON`.
- SQLite WAL mode is enabled with `PRAGMA journal_mode=WAL`.
- SQLite busy timeout defaults to `5000` ms.
- SQLite backup and restore procedures are documented in `docs/database.md`.
- The initial migration revision is `20260531_0001`.
- The database hardening migration revision is `20260531_0002`.
- Alembic is the migration tool.
- `database/irtiqa.db` is a generated artifact and must not be committed.

### Current Database Constraints

Implemented hardening constraints:

- `companies.status` must be `active`, `needs_review`, or `archived`.
- `contacts.status` must be `active`, `unverified`, `qualified`, `disqualified`, or `archived`.
- `agent_runs.status` must be `pending`, `running`, `succeeded`, `failed`, or `cancelled`.
- `outreach_messages.status` must be `draft`, `ready_for_review`, `approved`, `sent`, or `archived`.
- `technologies.confidence` must be between `0.0` and `1.0`.
- `intent_signals.strength` must be between `0.0` and `1.0`.
- `intent_signals.confidence` must be between `0.0` and `1.0`.
- `intelligence_scores.fit_score`, `intent_score`, `technographic_score`, `engagement_score`, and `total_score` must be between `0.0` and `100.0`.
- `intelligence_scores.confidence` must be between `0.0` and `1.0`.
- `outreach_messages.confidence` must be between `0.0` and `1.0`.

## 3. Completed Tasks

Completed architecture and documentation:

- Created architecture documentation.
- Created database documentation.
- Created agent architecture documentation.
- Created workflow architecture documentation.
- Created project state handoff.
- Created this project handoff document.

Completed database foundation:

- Created SQLAlchemy ORM models for all current tables.
- Created shared SQLAlchemy `Base`.
- Created UUID primary key mixin.
- Created timestamp mixin.
- Created Alembic configuration.
- Created initial Alembic migration.
- Verified migrations against SQLite.
- Created SQLite-first database configuration.
- Created SQLAlchemy engine factory.
- Enabled SQLite foreign key enforcement.
- Enabled SQLite WAL mode.
- Enabled SQLite busy timeout.
- Created `SessionLocal`.
- Created `session_scope()` with commit, rollback, and close behavior.
- Added portable database check constraints for status, confidence, strength, and score ranges.

Completed repository foundation:

- Created generic `BaseRepository`.
- Created repository classes for all current models.
- Added entity-specific query methods for current expected access patterns.
- Added generic repository count support for pagination-ready API list responses.
- Kept transaction control outside repository methods.

Completed service layer:

- Created generic `BaseService`.
- Created `CompanyService`.
- Created `ContactService`.
- Created `WebsiteService`.
- Created `TechnologyService`.
- Created `IntentSignalService`.
- Created `IntelligenceScoreService`.
- Created `OutreachMessageService`.
- Created `AgentRunService`.
- Services use repositories for data access.
- Services own business-use-case transaction boundaries through `session_scope()`.
- Services support generic create, read, update, list, count, and delete operations.
- Services use centralized logging.
- Services use structured errors from `app/core/errors.py`.
- Repositories remain data-access only.

Completed Pydantic schema layer:

- Created shared schema base classes.
- Created `CompanyCreate`, `CompanyUpdate`, `CompanyRead`, and `CompanyList`.
- Created `ContactCreate`, `ContactUpdate`, `ContactRead`, and `ContactList`.
- Created `WebsiteCreate`, `WebsiteUpdate`, `WebsiteRead`, and `WebsiteList`.
- Created `TechnologyCreate`, `TechnologyUpdate`, `TechnologyRead`, and `TechnologyList`.
- Created `IntentSignalCreate`, `IntentSignalUpdate`, `IntentSignalRead`, and `IntentSignalList`.
- Created `IntelligenceScoreCreate`, `IntelligenceScoreUpdate`, `IntelligenceScoreRead`, and `IntelligenceScoreList`.
- Created `OutreachMessageCreate`, `OutreachMessageUpdate`, `OutreachMessageRead`, and `OutreachMessageList`.
- Created `AgentRunCreate`, `AgentRunUpdate`, `AgentRunRead`, and `AgentRunList`.
- Read schemas support ORM-compatible serialization through Pydantic v2 `from_attributes`.
- Update schemas reject empty update payloads.
- Schema validation mirrors current status, confidence, strength, and score constraints.

Completed FastAPI skeleton:

- Created `app/main.py`.
- Created `create_app()` application factory.
- Created module-level ASGI `app` instance.
- Created `app/api/` router package structure.
- Created health endpoint at `/health`.
- Created dependency providers for settings and database sessions.
- Registered structured exception handlers for `IrtiqaError`, request validation errors, and unhandled exceptions.
- Integrated application configuration and runtime logging setup.
- Added FastAPI lifespan startup and shutdown logging.
- Used FastAPI lifespan events instead of deprecated startup/shutdown decorators.

Completed CRUD API Endpoints Phase 1:

- Added service dependency providers for `CompanyService`, `ContactService`, and `WebsiteService`.
- Added `POST`, `GET` list, `GET` by id, `PATCH`, and `DELETE` endpoints for companies.
- Added `POST`, `GET` list, `GET` by id, `PATCH`, and `DELETE` endpoints for contacts.
- Added `POST`, `GET` list, `GET` by id, `PATCH`, and `DELETE` endpoints for websites.
- List endpoints return `items`, `total`, `limit`, and `offset`.
- Routes reuse existing Pydantic create, update, read, and list schemas.
- Routes use service dependencies rather than repositories.
- Structured API errors are returned through the existing exception handlers.
- Delete endpoints return `204 No Content`.

Completed CRUD API Endpoints Phase 2:

- Added service dependency providers for `TechnologyService`, `IntentSignalService`, and `IntelligenceScoreService`.
- Added `POST`, `GET` list, `GET` by id, `PATCH`, and `DELETE` endpoints for technologies.
- Added `POST`, `GET` list, `GET` by id, `PATCH`, and `DELETE` endpoints for intent signals.
- Added `POST`, `GET` list, `GET` by id, `PATCH`, and `DELETE` endpoints for intelligence scores.
- List endpoints return `items`, `total`, `limit`, and `offset`.
- Routes reuse existing Pydantic create, update, read, and list schemas.
- Routes use service dependencies rather than repositories.
- Structured API errors are returned through the existing exception handlers.
- Delete endpoints return `204 No Content`.

Completed CRUD API Endpoints Phase 3:

- Added service dependency providers for `OutreachMessageService` and `AgentRunService`.
- Added `POST`, `GET` list, `GET` by id, `PATCH`, and `DELETE` endpoints for outreach messages.
- Added `POST`, `GET` list, `GET` by id, `PATCH`, and `DELETE` endpoints for agent runs.
- List endpoints return `items`, `total`, `limit`, and `offset`.
- Routes reuse existing Pydantic create, update, read, and list schemas.
- Routes use service dependencies rather than repositories.
- Structured API errors are returned through the existing exception handlers.
- Delete endpoints return `204 No Content`.
- This completes the CRUD API milestone for all current persisted entities.

Completed Workflow Foundation and score_refresh:

- Added workflow context, result, state, retry policy, registry, and runner contracts.
- Added deterministic `score_refresh.v1` scoring policy in `app/workflows/scoring_policy.py`.
- Added executable `score_refresh` workflow in `app/workflows/score_refresh.py`.
- `score_refresh` uses only existing persisted companies, contacts, technologies, and intent signals.
- `score_refresh` creates append-only `intelligence_scores` records.
- `score_refresh` records observability through `agent_runs` with `agent_name=score_refresh_policy`.
- `score_refresh` returns created score ids through `WorkflowResult.output_ids["intelligence_scores"]`.
- `score_refresh` raises structured `WorkflowError` failures and marks started agent runs as failed when execution fails.
- No concrete agents, jobs, scraping, or external APIs were introduced.

Completed Agent Interface Foundation:

- Added `app/agents/` package with `base.py`, `context.py`, `result.py`, `registry.py`, and `errors.py`.
- Added async `BaseAgent` abstract class using the Template Method pattern with lifecycle hooks.
- Added `AgentContext` Pydantic model with frozen options, required `company_id`, and optional `contact_id`.
- Added `AgentResult` Pydantic model with structured output IDs, error envelopes, timing, and stats.
- Added `AgentRegistry` for name-based agent class lookup with validation.
- Added `AgentRunOutput` typed dictionary as the return type for `BaseAgent._run()`.
- Extended `app/core/errors.py` with `AgentValidationError`, `AgentNetworkError`, `AgentRateLimitError`, and `AgentTimeoutError`.
- Added `app/agents/errors.py` re-exporting all agent error classes.
- Added agent interface unit tests for context, result, registry, and lifecycle.
- Agents integrate with `AgentRunService` for `agent_runs` observability.
- Agents use structured logging via `irtiqa.agents` namespace.
- 1. **Agent Interface Foundation**: `app.agents` with `BaseAgent`, context models, output mappings.
- 2. **Deep Scraper Agent**: Asynchronous HTML fetcher mapped to `Website` models.
- 3. **Technographic Agent**: Signature-based detector (70/30 weighting model) integrated with `TechnologyService`.
- 4. **Intent Signal Agent**: Deterministic rule engine that converts scraped text and detected technologies into persisted `intent_signals`.
- 5. **Intelligence Scoring Agent**: Aggregation engine that imports the deterministic workflow scoring policy to produce intelligence scores.
- 6. **Database & Migrations**: Schema locked in. Database hardening done.
- 7. **Service Layer**: Business boundaries over repositories with transaction scope support.

## 4. Test Results

Last full test run:

```text
python -m pytest
```

Result:

```text
245 passed
```

Current test coverage verifies:

- Alembic migrations upgrade correctly.
- Alembic revision is recorded.
- Migration-created columns match SQLAlchemy model metadata.
- Migration downgrade removes application tables.
- Model metadata contains the current schema.
- All models include UUID primary keys.
- All models include `created_at` and `updated_at`.
- Company relationships are declared.
- ORM relationships persist and load correctly.
- Repository methods work against SQLite.
- Service create and query operations work against SQLite.
- Service duplicate/not-found/validation errors use structured errors.
- Service transactions roll back on database errors.
- Pydantic schemas validate create and update payloads.
- Pydantic read and list schemas serialize from ORM-compatible attributes.
- Schema validation rejects invalid statuses, invalid numeric ranges, blank strings, and empty update payloads.
- `session_scope()` commits on success.
- `session_scope()` rolls back on exceptions.
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
- Workflow foundation validates context, results, states, policies, registry, and runner behavior.
- `score_refresh.v1` scoring is deterministic, bounded, versioned, and evidence-only.
- `score_refresh` appends intelligence scores, records `agent_runs` observability, returns output ids, and reports structured failures.

Additional migration verification:

```text
python -m alembic upgrade head
python -m alembic check
```

Result:

```text
No new upgrade operations detected.
```

Important test behavior:

- Tests use temporary SQLite databases.
- Tests should not create or depend on `database/irtiqa.db`.
- Running tests may create `__pycache__/` and `.pytest_cache/`; these are ignored by `.gitignore`.

## 5. Repository Health Summary

Current health:

- Foundation status: healthy.
- Stage: Backend Intelligence Agents
- Test Count: `245 passed`
- Remaining work: Background job orchestration, remaining agents (Personalization), PostgreSQL scaling, deployment.
- Architecture status: FastAPI skeleton, CRUD API Endpoints Phase 1, Phase 2, and Phase 3, SQLAlchemy models, Alembic migrations, SQLite session management, repositories, services, Pydantic schemas, workflow foundation, `score_refresh`, Agent Interface Foundation, structured logging, structured errors, database hardening, and SQLite backup documentation are implemented.
- Runtime surface status: health endpoint and CRUD endpoints for companies, contacts, websites, technologies, intent signals, intelligence scores, outreach messages, and agent runs exist; workflow foundation and `score_refresh` exist; Agent Interface Foundation exists; Deep Scraper, Technographic Agent, Intent Signal Agent, and Intelligence Scoring Agent are implemented; jobs, frontend, and remaining concrete agents are intentionally not implemented yet.
- Documentation status: `docs/project_state.md`, `docs/project_handoff.md`, `docs/codex_bootstrap.md`, `docs/workflows.md`, and `docs/agent_interface_design.md` reflect CRUD API completion, workflow foundation, `score_refresh`, and Agent Interface Foundation.
- Artifact status: generated local artifacts such as `database/irtiqa.db`, `.pytest_cache/`, and `__pycache__/` must remain uncommitted.
- Next milestone: concrete agent implementation or background job foundation.

## 6. Repository Conventions

### Transaction Boundaries

Repositories do not commit transactions.

Correct convention:

```text
Service layer owns transaction boundaries for current CRUD use cases.
Repositories only perform database operations using an injected Session.
```

Use `session_scope()` for explicit unit-of-work boundaries in services. FastAPI routes should call services and should not open their own commit/rollback transaction around service calls.

Current transaction ownership decision:

- The service layer owns transaction boundaries.
- `BaseService._run_in_transaction()` opens `session_scope()`, runs repository operations, commits on success, and rolls back on failure.
- FastAPI CRUD routes should use service dependencies, for example `get_company_service()`, and should not inject repositories directly.
- `app/api/dependencies.py` may expose `get_db_session()` for low-level infrastructure or future specialized use, but this dependency is not the default route boundary while services own transactions.
- API-level transaction ownership was evaluated and rejected for the current phase because it would require refactoring services to accept an injected session or unit-of-work, and mixing both models would risk duplicate or conflicting transaction scopes.
- If future workflows need multiple service operations in one atomic unit, introduce an explicit unit-of-work abstraction rather than quietly moving transaction control into API routes.

### Database Access

All database reads and writes should go through repositories once the service layer is added.

Current repository pattern:

- Accept `Session` in constructor.
- Return ORM entities.
- Do not commit.
- Do not create sessions internally.
- Do not import API, service, workflow, job, scraping, or agent layers.

### Generated Artifacts

Do not commit:

- `database/irtiqa.db`
- `*.db`
- `*.sqlite`
- `*.sqlite3`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.env`

### Naming

Current canonical entity names:

- Use `contacts`, not `leads`, in implemented code.
- Use `outreach_messages`, not `personalization_outputs`, in implemented code.
- Use `agent_runs`, not `agent_run_events`, unless an event table is intentionally introduced later.
- Do not reference `source_observations` unless that table is intentionally designed and migrated later.

### Documentation

When schema, relationships, or architecture change, update:

- `docs/database.md`
- `docs/agents.md`
- `docs/workflows.md`
- `docs/project_state.md`
- `docs/project_handoff.md`

## 7. Coding Standards

The project must follow the rules in `AGENTS.md`:

- Production-ready only.
- Never create mock data.
- Never create temporary solutions.
- Maintain clean architecture.
- Follow SOLID principles.
- Type hints required.
- Logging required for future runtime modules.
- Error handling required for future runtime modules.

Current code standards:

- Python 3.11+ target in `pyproject.toml`.
- SQLAlchemy 2-style typed ORM mappings.
- Use `Mapped[...]` and `mapped_column`.
- Use explicit relationships.
- Use explicit indexes for common access patterns.
- Keep ORM models in `app/models/`.
- Keep database setup in `app/database/`.
- Keep configuration in `app/core/config.py`.
- Keep repository classes in `app/repositories/`.
- Keep tests under `tests/unit/` and `tests/integration/`.

Style and quality tools declared:

- `ruff`
- `mypy`
- `pytest`

No CI pipeline exists yet.

## 8. Architectural Decisions

### Decision: SQLite First

SQLite is the first database target because the project is early-stage and local-first. PostgreSQL compatibility is preserved through SQLAlchemy and Alembic.

Implications:

- Use SQLAlchemy portable types.
- Avoid SQLite-only SQL in repositories.
- Keep dialect-specific behavior isolated.
- Test migrations with SQLite now.
- Add PostgreSQL verification later.

### Decision: SQLAlchemy ORM

The project uses SQLAlchemy ORM rather than raw SQL for application persistence.

Implications:

- Models are the source of application-level schema metadata.
- Alembic manages migration history.
- Repositories operate on ORM entities.

### Decision: Repository Pattern

Repositories isolate query logic from future services, APIs, workflows, and agents.

Implications:

- Services should depend on repositories.
- API routes should depend on services, not repositories directly.
- Agents should not own database session lifecycle.

### Decision: Contacts, Not Leads

The implemented schema uses `contacts`. Earlier planning docs referred to leads, but docs have been updated.

Implications:

- New code should use `Contact`, `contacts`, and `contact_id`.
- Avoid introducing a parallel `Lead` model unless the schema is intentionally redesigned.

### Decision: Outreach Messages, Not Personalization Outputs

The implemented schema uses `outreach_messages`.

Implications:

- The future Personalization Agent should produce `outreach_messages`.
- Avoid creating `personalization_outputs` unless a migration intentionally adds it.

### Decision: Agent Runs Before Agents

`agent_runs` exists before agent implementation.

Implications:

- Future agents should create and update `agent_runs`.
- `agent_runs` is the initial observability mechanism.
- A later `agent_run_events` table may be useful, but it is not currently implemented.

### Decision: No Evidence Table Yet

There is no `source_observations` table.

Implications:

- Current evidence references live in fields such as `websites.url`, `intent_signals.source_url`, and run summaries.
- A dedicated evidence table can be added later if agents need richer provenance.

## 9. Current Roadmap

Priority order from the current state:

1. Add agent interfaces only.
2. Add background job foundation.
3. Add PostgreSQL compatibility verification.
4. Add CI and quality gates.
5. Implement actual agents.

Completed roadmap item:

- Testing foundation.
- Logging foundation.
- Structured error foundation.
- Database hardening.
- SQLite backup strategy documentation.
- Service layer.
- Pydantic schema layer.
- FastAPI skeleton.
- CRUD API Endpoints Phase 1 for companies, contacts, and websites.
- CRUD API Endpoints Phase 2 for technologies, intent signals, and intelligence scores.
- CRUD API Endpoints Phase 3 for outreach messages and agent runs.
- Full CRUD API milestone for all current persisted entities.
- Workflow foundation.
- `score_refresh` workflow.
- Agent Interface Foundation.

## 10. Next Recommended Task

The next recommended task is:

```text
Concrete Agent Implementation
```

Recommended scope:

- Implement the Personalization Agent by subclassing `BaseAgent`.
- Define personalization templates and placeholders.

Alternative next task:

```text
Background Job Foundation
```

Recommended scope:

- Add a job scheduling layer for long-running agent execution.
- Integrate with existing workflow and agent foundations.
- Do not add scraping, frontend, or external API calls yet.

Why concrete agents or job foundation are next:

- The full CRUD API milestone is implemented and tested.
- Workflow foundation and `score_refresh` are implemented and tested.
- Agent Interface Foundation is implemented and tested.
- Deep Scraper, Technographic, Intent Signal, and Intelligence Scoring Agents are completed.
- Concrete agents or job scheduling are the next boundaries.

## 11. Open Issues

Current known gaps:

- CRUD API routes currently exist for all current persisted entities: companies, contacts, websites, technologies, intent signals, intelligence scores, outreach messages, and agent runs.
- Workflow foundation, workflow runner, and `score_refresh` exist.
- **1. Background Orchestration**
- The foundation is built. We need a celery/arq equivalent or a cron system to orchestrate workflows and agents.
- Agents (Deep Scraper, Technographic) are synchronous to the runner for now but designed for asynchronous invocation.
- No frontend implementation exists yet.
- No CI configuration exists yet.
- No Docker or deployment configuration exists yet.
- No PostgreSQL runtime verification has been performed.
- No repository methods enforce domain-level validation.
- `technology_catalog` is not implemented.
- `technologies` currently stores company-specific detections directly.
- No dedicated `workflow_runs` table exists.
- No dedicated `source_observations` or evidence table exists.
- No dedicated `agent_run_events` table exists.
- `database/irtiqa.db` should remain uncommitted and generated locally only.

## 12. Future Agent Implementation Plan

Do not implement agents until the following are complete:

1. Logging foundation.
2. Structured errors.
3. Database hardening.
4. Service layer.
5. Pydantic schemas.
6. Workflow layer.
7. Agent base interfaces.
8. Tests for services, workflows, and agent interfaces.

Future agent sequence:

### Phase 1: Agent Interfaces Only (COMPLETED)

Implemented files:

```text
app/agents/__init__.py
app/agents/base.py
app/agents/context.py
app/agents/result.py
app/agents/registry.py
app/agents/errors.py
tests/unit/agents/__init__.py
tests/unit/agents/test_context.py
tests/unit/agents/test_result.py
tests/unit/agents/test_registry.py
tests/unit/agents/test_base.py
```

Completed:

- Defined async `BaseAgent` abstract class with Template Method lifecycle.
- Defined `AgentContext` and `AgentResult` Pydantic models.
- Defined `AgentRegistry` for name-based lookup.
- Extended error hierarchy with `AgentValidationError`, `AgentNetworkError`, `AgentRateLimitError`, `AgentTimeoutError`.
- Added agent error re-exports.
- Added unit tests for context, result, registry, and lifecycle.

### Phase 2: Completed Agents

1. Deep Scraper Agent (Completed)
2. Technographic Intelligence Agent (Completed)
3. Intent Signal Agent (Completed)
4. Intelligence Scoring Agent (Completed)

These initial agents established the standard execution pattern for scraping websites, analyzing tools, and extracting evidence-backed commercial intent signals.

### Phase 3: Pending Agents

Recommended order:

1. Personalization Agent.

Reason:

- The platform now has scraped text, detected technologies, and persisted intent signals.
- The remaining agents will score that intelligence and generate outreach-ready messages.

Future agent output mapping:

```text
Deep Scraper Agent -> websites, agent_runs
Technographic Intelligence Agent -> technologies, agent_runs
Intent Signal Agent -> intent_signals, agent_runs
Intelligence Scoring Agent -> intelligence_scores, agent_runs
Personalization Agent -> outreach_messages, agent_runs
```

Future agent guardrails:

- No mock data.
- No unsupported claims.
- Explicit confidence values.
- Explicit run status.
- Explicit error handling.
- No hidden external calls.
- No direct API coupling.
- No direct frontend coupling.

## 13. Antigravity Integration Plan

Antigravity integration should be treated as a development-environment and operator-experience layer, not as a replacement for the project architecture.

Important assumption:

- Antigravity should orchestrate or assist development workflows around this repository.
- It should not bypass repository conventions, tests, migrations, or documentation.

### Phase 1: Repository Awareness

Goal:

- Ensure Antigravity can understand the repo from documentation alone.

Required docs:

- `README.md`
- `docs/project_state.md`
- `docs/project_handoff.md`
- `docs/database.md`
- `docs/agents.md`
- `docs/workflows.md`

Expected Antigravity behavior:

- Read `docs/project_handoff.md` first.
- Respect `AGENTS.md`.
- Avoid implementing agents before prerequisites are complete.
- Run tests after foundation changes.

### Phase 2: Development Task Execution

Goal:

- Use Antigravity to execute bounded engineering tasks in the exact roadmap order.

Allowed early tasks:

- Logging foundation.
- Structured errors.
- Database hardening.
- Service layer.
- Schemas.
- API skeleton.

Disallowed early tasks:

- Scraping.
- Agent implementation.
- Frontend implementation.
- Background job complexity before workflows exist.

### Phase 3: Test and Verification Workflow

Goal:

- Antigravity should verify each change with the narrowest meaningful test set first, then the full suite.

Expected commands:

```text
python -m pytest
python -m alembic check
python -m compileall app database tests
```

When API exists, add:

```text
FastAPI integration tests
OpenAPI schema checks
```

When PostgreSQL support is added, add:

```text
PostgreSQL migration verification
PostgreSQL repository integration tests
```

### Phase 4: Agent-Aware Development

Goal:

- After the base platform exists, Antigravity can assist with agent development one agent at a time.

Required before this phase:

- Agent base contracts.
- Workflow layer.
- Service layer.
- Logging.
- Errors.
- Tests.
- Documentation updates.

Agent task constraints:

- Implement one agent per task.
- Add tests for each agent.
- Update docs after each agent.
- Avoid broad rewrites.
- Do not add external providers without explicit configuration and tests.

### Phase 5: Operational Runbooks

Goal:

- Antigravity should help maintain operational docs once runtime components exist.

Future docs:

- `docs/runbooks/database.md`
- `docs/runbooks/migrations.md`
- `docs/runbooks/agents.md`
- `docs/runbooks/workflows.md`
- `docs/runbooks/deployment.md`

## 14. Exact Development Order

Follow this exact order unless the user explicitly changes priority.

### 1. Logging Foundation

Objective:

- Add centralized logging configuration.

Status:

- Completed.

Dependencies:

- Existing `app/core/config.py`.

Files likely affected:

```text
app/core/logging.py
app/core/config.py
tests/unit/core/
docs/project_state.md
docs/project_handoff.md
```

Do not add:

- API.
- Services.
- Agents.

### 2. Structured Errors

Objective:

- Add shared exception hierarchy.

Status:

- Completed.

Dependencies:

- Logging foundation.

Files likely affected:

```text
app/core/errors.py
tests/unit/core/
docs/project_state.md
docs/project_handoff.md
```

### 3. Database Hardening

Objective:

- Improve SQLite production behavior and add portable constraints.

Status:

- Completed.

Dependencies:

- Existing tests.
- Structured errors preferred.

Files likely affected:

```text
app/database/engine.py
app/models/
database/migrations/versions/
tests/integration/
docs/database.md
docs/project_state.md
docs/project_handoff.md
```

Include:

- SQLite WAL mode.
- SQLite busy timeout.
- confidence constraints.
- score constraints.

### 4. SQLite Backup Strategy

Objective:

- Document SQLite backup, restore, WAL, migration, and PostgreSQL transition practices.

Status:

- Completed.

Dependencies:

- Database hardening.

Files affected:

```text
docs/database.md
docs/project_state.md
docs/project_handoff.md
```

Did not add:

- Application code.
- Services.
- API.
- Workflows.
- Agents.

### 5. Service Layer

Objective:

- Add business-use-case layer over repositories.

Status:

- Completed.

Dependencies:

- Repositories.
- Logging.
- Errors.
- Database tests.

Files likely affected:

```text
app/services/
tests/unit/services/
tests/integration/services/
docs/workflows.md
docs/project_state.md
docs/project_handoff.md
```

### 6. Pydantic Schemas

Objective:

- Add input/output schemas for service and future API boundaries.

Status:

- Completed.

Dependencies:

- Service layer direction.

Files likely affected:

```text
app/schemas/
tests/unit/schemas/
docs/database.md
docs/project_state.md
docs/project_handoff.md
```

### 7. FastAPI Skeleton

Objective:

- Add app creation, health route, dependency wiring, and error handlers.

Status:

- Completed.

Dependencies:

- Logging.
- Errors.
- Database session management.
- Schemas.

Files likely affected:

```text
app/main.py
app/api/
tests/integration/api/
README.md
docs/project_state.md
docs/project_handoff.md
```

### 8. CRUD API Endpoints

Objective:

- Expose current entities through API routes.

Status:

- Completed for all current persisted entities.

Dependencies:

- FastAPI skeleton.
- Services.
- Schemas.

Files likely affected:

```text
app/api/v1/endpoints/
tests/integration/api/
docs/api.md
docs/project_state.md
docs/project_handoff.md
```

### 9. Workflow Layer

Objective:

- Add workflow orchestration without agent implementation.

Status:

- Workflow foundation completed.
- `score_refresh` completed as the first concrete executable workflow.

Dependencies:

- Services.
- Logging.
- Errors.

Files likely affected:

```text
app/workflows/
tests/unit/workflows/
tests/integration/test_score_refresh_workflow.py
docs/workflows.md
docs/project_state.md
docs/project_handoff.md
```

### 10. Agent Base Interfaces

Objective:

- Add abstract contracts for future agents.

Dependencies:

- Workflow layer.
- Logging.
- Errors.

Files likely affected:

```text
app/agents/base/
tests/unit/agents/base/
docs/agents.md
docs/project_state.md
docs/project_handoff.md
```

Concrete agents have begun implementation.

### 11. Background Job Foundation

Objective:

- Prepare long-running execution.

Dependencies:

- Workflow layer.
- Agent interfaces.

Files likely affected:

```text
app/jobs/
tests/unit/jobs/
docs/workflows.md
docs/project_state.md
docs/project_handoff.md
```

### 12. PostgreSQL Compatibility Verification

Objective:

- Verify migrations and repositories against PostgreSQL.

Dependencies:

- Stable database schema.
- Test foundation.

Files likely affected:

```text
pyproject.toml
tests/integration/database/
docs/database.md
README.md
docs/project_state.md
docs/project_handoff.md
```

### 13. CI and Quality Gates

Objective:

- Add automated checks.

Dependencies:

- Tests.
- Linting.
- Typing configuration.

Files likely affected:

```text
.github/workflows/
pyproject.toml
README.md
docs/project_state.md
docs/project_handoff.md
```

### 14. Concrete Agent Implementation

Objective:

- Implement real intelligence agents.

Dependencies:

- All prior foundation layers.

Files likely affected:

```text
app/agents/deep_scraper/
app/agents/technographic_intelligence/
app/agents/intent_signal/
app/agents/intelligence_scoring/
app/agents/personalization/
tests/unit/agents/
tests/integration/workflows/
docs/agents.md
docs/workflows.md
docs/project_state.md
docs/project_handoff.md
```

Concrete agent order:

1. Deep Scraper Agent (Completed).
2. Technographic Intelligence Agent (Completed).
3. Intent Signal Agent (Completed).
4. Intelligence Scoring Agent (Completed).
5. Personalization Agent.
