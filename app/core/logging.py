from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any

from app.core.config import LoggingSettings, get_settings


APPLICATION_LOGGER_NAME = "irtiqa"
DATABASE_LOGGER_NAME = "sqlalchemy.engine"
REPOSITORY_LOGGER_NAME = "irtiqa.repositories"


def configure_logging(settings: LoggingSettings | None = None) -> None:
    logging_settings = settings or get_settings().logging
    handlers = _build_handlers(logging_settings)

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "structured": {
                    "format": logging_settings.format,
                    "datefmt": logging_settings.date_format,
                }
            },
            "handlers": handlers,
            "root": {
                "level": _normalize_level(logging_settings.level),
                "handlers": list(handlers.keys()),
            },
            "loggers": {
                APPLICATION_LOGGER_NAME: {
                    "level": _normalize_level(logging_settings.app_level),
                    "handlers": list(handlers.keys()),
                    "propagate": False,
                },
                DATABASE_LOGGER_NAME: {
                    "level": _normalize_level(logging_settings.database_level),
                    "handlers": list(handlers.keys()),
                    "propagate": False,
                },
                REPOSITORY_LOGGER_NAME: {
                    "level": _normalize_level(logging_settings.repository_level),
                    "handlers": list(handlers.keys()),
                    "propagate": False,
                },
            },
        }
    )


def get_logger(name: str | None = None) -> logging.Logger:
    if name is None:
        return logging.getLogger(APPLICATION_LOGGER_NAME)
    if name.startswith(APPLICATION_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{APPLICATION_LOGGER_NAME}.{name}")


def get_database_logger(name: str | None = None) -> logging.Logger:
    if name is None:
        return logging.getLogger(DATABASE_LOGGER_NAME)
    return logging.getLogger(f"{DATABASE_LOGGER_NAME}.{name}")


def get_repository_logger(name: str | None = None) -> logging.Logger:
    if name is None:
        return logging.getLogger(REPOSITORY_LOGGER_NAME)
    return logging.getLogger(f"{REPOSITORY_LOGGER_NAME}.{name}")


def _build_handlers(settings: LoggingSettings) -> dict[str, dict[str, Any]]:
    handlers: dict[str, dict[str, Any]] = {}

    if settings.console_enabled:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            "level": _normalize_level(settings.level),
            "formatter": "structured",
        }

    if settings.file_enabled:
        log_path = _resolve_log_path(settings.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": _normalize_level(settings.level),
            "formatter": "structured",
            "filename": str(log_path),
            "maxBytes": settings.file_max_bytes,
            "backupCount": settings.file_backup_count,
            "encoding": "utf-8",
        }

    if not handlers:
        handlers["null"] = {
            "class": "logging.NullHandler",
            "level": _normalize_level(settings.level),
        }

    return handlers


def _resolve_log_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _normalize_level(level: str) -> str:
    normalized_level = level.strip().upper()
    if normalized_level not in logging._nameToLevel:
        raise ValueError(f"Unsupported log level: {level}")
    return normalized_level
