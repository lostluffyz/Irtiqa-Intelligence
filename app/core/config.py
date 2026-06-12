from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE, override=True)
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "database" / "irtiqa.db"
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "irtiqa.log"


@dataclass(frozen=True)
class DatabaseSettings:
    url: str
    echo: bool
    pool_pre_ping: bool
    sqlite_foreign_keys: bool
    sqlite_journal_mode: str
    sqlite_busy_timeout_ms: int

    @property
    def is_sqlite(self) -> bool:
        return self.url.startswith("sqlite")


@dataclass(frozen=True)
class LoggingSettings:
    level: str
    app_level: str
    database_level: str
    repository_level: str
    console_enabled: bool
    file_enabled: bool
    file_path: Path
    file_max_bytes: int
    file_backup_count: int
    format: str
    date_format: str


@dataclass(frozen=True)
class AuthSettings:
    jwt_private_key: str | None = None
    jwt_algorithm: str = "RS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    password_reset_expire_minutes: int = 15
    max_login_attempts: int = 5
    login_lockout_minutes: int = 15
    dev_mode: bool = False


@dataclass(frozen=True)
class Settings:
    database: DatabaseSettings
    logging: LoggingSettings
    auth: AuthSettings


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}")

    return Settings(
        database=DatabaseSettings(
            url=database_url,
            echo=_env_bool("DATABASE_ECHO", False),
            pool_pre_ping=_env_bool("DATABASE_POOL_PRE_PING", True),
            sqlite_foreign_keys=_env_bool("SQLITE_FOREIGN_KEYS", True),
            sqlite_journal_mode=os.getenv("SQLITE_JOURNAL_MODE", "WAL"),
            sqlite_busy_timeout_ms=_env_int("SQLITE_BUSY_TIMEOUT_MS", 5000),
        ),
        logging=LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"),
            app_level=os.getenv("APP_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")),
            database_level=os.getenv("DATABASE_LOG_LEVEL", "WARNING"),
            repository_level=os.getenv("REPOSITORY_LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO")),
            console_enabled=_env_bool("LOG_CONSOLE_ENABLED", True),
            file_enabled=_env_bool("LOG_FILE_ENABLED", True),
            file_path=Path(os.getenv("LOG_FILE_PATH", DEFAULT_LOG_PATH.as_posix())),
            file_max_bytes=_env_int("LOG_FILE_MAX_BYTES", 10_485_760),
            file_backup_count=_env_int("LOG_FILE_BACKUP_COUNT", 5),
            format=os.getenv(
                "LOG_FORMAT",
                (
                    "timestamp=%(asctime)s level=%(levelname)s "
                    "logger=%(name)s module=%(module)s function=%(funcName)s "
                    "line=%(lineno)d message=%(message)s"
                ),
            ),
            date_format=os.getenv("LOG_DATE_FORMAT", "%Y-%m-%dT%H:%M:%S%z"),
        ),
        auth=AuthSettings(
            jwt_private_key=os.getenv("JWT_PRIVATE_KEY"),
            access_token_expire_minutes=_env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 15),
            refresh_token_expire_days=_env_int("REFRESH_TOKEN_EXPIRE_DAYS", 7),
            password_reset_expire_minutes=_env_int("PASSWORD_RESET_EXPIRE_MINUTES", 15),
            max_login_attempts=_env_int("MAX_LOGIN_ATTEMPTS", 5),
            login_lockout_minutes=_env_int("LOGIN_LOCKOUT_MINUTES", 15),
            dev_mode=_env_bool("DEV_MODE", False),
        ),
    )
