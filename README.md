# Irtiqa Intelligence

Irtiqa Intelligence is a production-grade lead intelligence platform designed around a FastAPI backend, SQLAlchemy data layer, SQLite-first storage, and a future PostgreSQL migration path.

## Current Scope

The repository currently contains:

- FastAPI application with CRUD API endpoints for all entities.
- SQLAlchemy ORM models with Alembic migrations.
- SQLite database configuration (PostgreSQL verified).
- Service layer with transaction boundaries.
- Repository pattern for data access.
- Pydantic v2 schemas for API boundaries.
- Five production agents (Deep Scraper, Technographic, Intent Signal, Intelligence Scoring, Personalization).
- Background job foundation with in-process scheduling.
- Workflow foundation with `score_refresh` workflow.
- Centralized structured logging and error handling.
- Architecture documentation.

## Architecture

The current implemented schema contains nine core tables:

- `companies`
- `contacts`
- `websites`
- `technologies`
- `intent_signals`
- `intelligence_scores`
- `outreach_messages`
- `agent_runs`
- `jobs`

Documentation lives in:

- `docs/database.md`
- `docs/agents.md`
- `docs/workflows.md`
- `docs/postgresql_compatibility_verification_design.md`

## Setup

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

For PostgreSQL support:

```bash
pip install "psycopg[binary]>=3.2.0"
```

## Configuration

Copy `.env.example` to `.env` and adjust values as needed.

Default SQLite URL:

```text
sqlite:///database/irtiqa.db
```

To use PostgreSQL, set `DATABASE_URL`:

```text
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa
```

## Database Migrations

Run migrations:

```bash
python -m alembic upgrade head
```

Check for schema drift:

```bash
python -m alembic check
```

## Testing

Run the full test suite:

```bash
python -m pytest
```

Run PostgreSQL compatibility tests:

```bash
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/irtiqa_verify python -m pytest tests/integration/test_postgresql_compatibility.py
```

## Repository Boundaries

Repositories encapsulate database reads and writes for ORM entities. They do not own transaction boundaries. Use `session_scope()` or a higher-level service/workflow transaction boundary to commit or roll back work.

## Development Rules

- Do not commit generated SQLite databases.
- Do not commit `__pycache__` directories.
- Do not create mock production data.
- Keep architecture modular and SQLAlchemy models PostgreSQL-compatible.
- Keep agent implementation separate from database and repository layers.
