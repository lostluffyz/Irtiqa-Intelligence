# Irtiqa Intelligence

Irtiqa Intelligence is a production-grade lead intelligence platform designed around a FastAPI backend, SQLAlchemy data layer, SQLite-first storage, and a future PostgreSQL migration path.

## Current Scope

The repository currently contains:

- SQLAlchemy ORM models.
- Alembic migrations.
- SQLite database configuration.
- Session management.
- Repository pattern.
- Architecture documentation.

Agent, API, scraping, and frontend implementation have not started yet.

## Architecture

The current implemented schema contains eight core tables:

- `companies`
- `contacts`
- `websites`
- `technologies`
- `intent_signals`
- `intelligence_scores`
- `outreach_messages`
- `agent_runs`

Documentation lives in:

- `docs/database.md`
- `docs/agents.md`
- `docs/workflows.md`

## Setup

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

For PostgreSQL support later:

```bash
pip install -e .[postgres]
```

## Configuration

Copy `.env.example` to `.env` and adjust values as needed.

Default SQLite URL:

```text
sqlite:///database/irtiqa.db
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

## Repository Boundaries

Repositories encapsulate database reads and writes for ORM entities. They do not own transaction boundaries. Use `session_scope()` or a higher-level service/workflow transaction boundary to commit or roll back work.

## Development Rules

- Do not commit generated SQLite databases.
- Do not commit `__pycache__` directories.
- Do not create mock production data.
- Keep architecture modular and SQLAlchemy models PostgreSQL-compatible.
- Keep agent implementation separate from database and repository layers.
