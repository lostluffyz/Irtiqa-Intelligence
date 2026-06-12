from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.dependencies import get_app_settings
from app.core.config import AuthSettings, DatabaseSettings, LoggingSettings, Settings
from app.main import create_app


def test_health_endpoint_returns_service_status() -> None:
    test_settings = _test_settings()
    app = create_app(test_settings, configure_logging_on_startup=False)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "irtiqa-intelligence",
        "database": "sqlite",
    }


def test_health_endpoint_uses_dependency_injected_settings() -> None:
    app = create_app(_test_settings(), configure_logging_on_startup=False)
    external_settings = _test_settings(database_url="postgresql+psycopg://user:pass@localhost/db")
    app.dependency_overrides[get_app_settings] = lambda: external_settings

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["database"] == "external"


def test_app_lifespan_starts_and_exposes_settings() -> None:
    test_settings = _test_settings()
    app = create_app(test_settings, configure_logging_on_startup=False)

    with TestClient(app) as client:
        assert client.app.state.settings == test_settings
        response = client.get("/health")

    assert response.status_code == 200


def _test_settings(database_url: str = "sqlite:///:memory:") -> Settings:
    return Settings(
        database=DatabaseSettings(
            url=database_url,
            echo=False,
            pool_pre_ping=True,
            sqlite_foreign_keys=True,
            sqlite_journal_mode="WAL",
            sqlite_busy_timeout_ms=5000,
        ),
        logging=LoggingSettings(
            level="INFO",
            app_level="INFO",
            database_level="WARNING",
            repository_level="INFO",
            console_enabled=False,
            file_enabled=False,
            file_path=Path("unused.log"),
            file_max_bytes=10_485_760,
            file_backup_count=5,
            format="%(levelname)s:%(name)s:%(message)s",
            date_format="%Y-%m-%dT%H:%M:%S%z",
        ),
        auth=AuthSettings(),
    )
