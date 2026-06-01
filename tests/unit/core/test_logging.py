from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.core.config import LoggingSettings
from app.core.logging import (
    APPLICATION_LOGGER_NAME,
    DATABASE_LOGGER_NAME,
    REPOSITORY_LOGGER_NAME,
    configure_logging,
    get_database_logger,
    get_logger,
    get_repository_logger,
)


@pytest.fixture(autouse=True)
def reset_logging() -> None:
    logging.shutdown()
    yield
    logging.shutdown()


def make_logging_settings(
    log_path: Path,
    *,
    level: str = "INFO",
    app_level: str = "INFO",
    database_level: str = "WARNING",
    repository_level: str = "INFO",
    console_enabled: bool = True,
    file_enabled: bool = True,
) -> LoggingSettings:
    return LoggingSettings(
        level=level,
        app_level=app_level,
        database_level=database_level,
        repository_level=repository_level,
        console_enabled=console_enabled,
        file_enabled=file_enabled,
        file_path=log_path,
        file_max_bytes=1024 * 1024,
        file_backup_count=1,
        format=(
            "timestamp=%(asctime)s level=%(levelname)s logger=%(name)s "
            "message=%(message)s"
        ),
        date_format="%Y-%m-%dT%H:%M:%S%z",
    )


def test_configure_logging_writes_structured_file_log(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "irtiqa.log"
    configure_logging(make_logging_settings(log_path, console_enabled=False))

    logger = get_logger()
    logger.info("platform logging online")

    for handler in logger.handlers:
        handler.flush()

    log_content = log_path.read_text(encoding="utf-8")

    assert "timestamp=" in log_content
    assert "level=INFO" in log_content
    assert f"logger={APPLICATION_LOGGER_NAME}" in log_content
    assert "message=platform logging online" in log_content


def test_configure_logging_writes_console_log(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(make_logging_settings(tmp_path / "ignored.log", file_enabled=False))

    logger = get_logger()
    logger.warning("console logging online")

    captured = capsys.readouterr()

    assert "timestamp=" in captured.err
    assert "level=WARNING" in captured.err
    assert "message=console logging online" in captured.err


def test_configure_logging_sets_application_database_and_repository_levels(
    tmp_path: Path,
) -> None:
    configure_logging(
        make_logging_settings(
            tmp_path / "irtiqa.log",
            level="INFO",
            app_level="DEBUG",
            database_level="ERROR",
            repository_level="WARNING",
            console_enabled=False,
        )
    )

    assert logging.getLogger(APPLICATION_LOGGER_NAME).level == logging.DEBUG
    assert logging.getLogger(DATABASE_LOGGER_NAME).level == logging.ERROR
    assert logging.getLogger(REPOSITORY_LOGGER_NAME).level == logging.WARNING


def test_logger_factories_return_expected_names() -> None:
    assert get_logger().name == APPLICATION_LOGGER_NAME
    assert get_logger("core").name == "irtiqa.core"
    assert get_database_logger().name == DATABASE_LOGGER_NAME
    assert get_database_logger("pool").name == "sqlalchemy.engine.pool"
    assert get_repository_logger().name == REPOSITORY_LOGGER_NAME
    assert get_repository_logger("CompanyRepository").name == "irtiqa.repositories.CompanyRepository"


def test_configure_logging_rejects_invalid_level(tmp_path: Path) -> None:
    settings = make_logging_settings(tmp_path / "irtiqa.log", level="NOPE")

    with pytest.raises(ValueError, match="Unsupported log level"):
        configure_logging(settings)


def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    settings = make_logging_settings(tmp_path / "irtiqa.log", console_enabled=True, file_enabled=True)

    configure_logging(settings)
    configure_logging(settings)

    logger = logging.getLogger(APPLICATION_LOGGER_NAME)

    assert len(logger.handlers) == 2
