from __future__ import annotations

from sqlalchemy import Engine, create_engine, event

from app.core.config import DatabaseSettings, get_settings


def create_database_engine(settings: DatabaseSettings | None = None) -> Engine:
    database_settings = settings or get_settings().database
    connect_args: dict[str, object] = {}

    if database_settings.is_sqlite:
        connect_args["check_same_thread"] = False

    created_engine = create_engine(
        database_settings.url,
        echo=database_settings.echo,
        pool_pre_ping=database_settings.pool_pre_ping,
        connect_args=connect_args,
        future=True,
    )

    if database_settings.is_sqlite:
        _configure_sqlite(created_engine, database_settings)

    return created_engine


def _configure_sqlite(created_engine: Engine, settings: DatabaseSettings) -> None:
    @event.listens_for(created_engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        if settings.sqlite_foreign_keys:
            cursor.execute("PRAGMA foreign_keys=ON")
        if settings.sqlite_busy_timeout_ms > 0:
            cursor.execute(f"PRAGMA busy_timeout={settings.sqlite_busy_timeout_ms}")
        if settings.sqlite_journal_mode:
            cursor.execute(f"PRAGMA journal_mode={settings.sqlite_journal_mode}")
        cursor.close()


engine = create_database_engine()
