from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.models import Base


EXPECTED_TABLES = {
    "agent_runs",
    "companies",
    "contacts",
    "intelligence_scores",
    "intent_signals",
    "jobs",
    "outreach_messages",
    "technologies",
    "websites",
}


def test_migration_upgrade_creates_expected_tables(migrated_engine) -> None:
    inspector = inspect(migrated_engine)

    assert set(inspector.get_table_names()) >= EXPECTED_TABLES | {"alembic_version"}


def test_migration_records_current_revision(alembic_config: Config, sqlite_database_url: str) -> None:
    command.upgrade(alembic_config, "head")
    database_path = sqlite_database_url.removeprefix("sqlite:///")

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("select version_num from alembic_version").fetchone()[0]

    assert revision == "20260609_0003"


def test_migration_schema_matches_model_metadata(migrated_engine) -> None:
    inspector = inspect(migrated_engine)

    for table_name in EXPECTED_TABLES:
        database_columns = {column["name"] for column in inspector.get_columns(table_name)}
        model_columns = set(Base.metadata.tables[table_name].columns.keys())
        assert database_columns == model_columns


def test_migration_downgrade_removes_application_tables(
    alembic_config: Config,
    sqlite_database_url: str,
) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    database_path = Path(sqlite_database_url.removeprefix("sqlite:///"))
    with sqlite3.connect(database_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type='table' order by name"
            )
        }

    assert table_names.isdisjoint(EXPECTED_TABLES)
