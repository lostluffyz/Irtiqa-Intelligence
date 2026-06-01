from __future__ import annotations

import importlib

import pytest

from app.models.company import Company


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

    Base.metadata.create_all(bind=engine)


def test_session_scope_commits_on_success(
    sqlite_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_schema_for_session_scope(sqlite_database_url, monkeypatch)

    from app.database.session import SessionLocal, session_scope

    with session_scope() as session:
        session.add(
            Company(
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

    with pytest.raises(RuntimeError, match="force rollback"):
        with session_scope() as session:
            session.add(
                Company(
                    name="Rolled Back Company",
                    domain="rolled-back.example",
                    status="active",
                )
            )
            raise RuntimeError("force rollback")

    verification_session = SessionLocal()
    try:
        assert (
            verification_session.query(Company)
            .filter_by(domain="rolled-back.example")
            .one_or_none()
            is None
        )
    finally:
        verification_session.close()
