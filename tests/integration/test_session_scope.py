from __future__ import annotations

import importlib
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event as sa_event

from app.models.company import Company
from app.models.organization import Organization


def reload_database_modules(monkeypatch: pytest.MonkeyPatch, sqlite_database_url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", sqlite_database_url)

    config_module = importlib.import_module("app.core.config")
    engine_module = importlib.import_module("app.database.engine")
    session_module = importlib.import_module("app.database.session")

    config_module.get_settings.cache_clear()
    importlib.reload(engine_module)
    importlib.reload(session_module)


def create_schema_for_session_scope(sqlite_database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    reload_database_modules(monkeypatch, sqlite_database_url)

    from app.database.engine import engine
    from app.models import Base

    @sa_event.listens_for(engine, "connect")
    def enable_fk(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)


def test_session_scope_commits_on_success(
    sqlite_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_schema_for_session_scope(sqlite_database_url, monkeypatch)

    from app.database.session import SessionLocal, session_scope

    with session_scope() as session:
        org_id = str(uuid4())
        from sqlalchemy import text
        now = datetime.now(timezone.utc)
        session.execute(
            text("INSERT INTO organizations (id, name, slug, status, created_at, updated_at) VALUES (:id, :name, :slug, :status, :created, :updated)"),
            {"id": org_id, "name": "Session Test Org", "slug": "session-test", "status": "active", "created": now, "updated": now},
        )
        session.add(
            Company(
                organization_id=org_id,
                name="Committed Company",
                domain="committed.example",
                status="active",
            )
        )

    verification_session = SessionLocal()
    try:
        assert verification_session.query(Company).filter_by(domain="committed.example").one_or_none()
    finally:
        verification_session.close()


def test_session_scope_rolls_back_on_error(
    sqlite_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_schema_for_session_scope(sqlite_database_url, monkeypatch)

    from app.database.session import SessionLocal, session_scope

    try:
        with session_scope() as session:
            session.add(
                Company(
                    organization_id=str(uuid4()),
                    name="Rollback Company",
                    domain="rollback.example",
                    status="active",
                )
            )
            raise ValueError("Simulated failure")
    except ValueError:
        pass

    verification_session = SessionLocal()
    try:
        assert verification_session.query(Company).filter_by(domain="rollback.example").one_or_none() is None
    finally:
        verification_session.close()
