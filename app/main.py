from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import AsyncContextManager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger


APP_NAME = "Irtiqa Intelligence"
APP_VERSION = "0.1.0"


def create_app(
    settings: Settings | None = None,
    *,
    configure_logging_on_startup: bool = True,
) -> FastAPI:
    app_settings = settings or get_settings()

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        lifespan=_build_lifespan(
            app_settings,
            configure_logging_on_startup=configure_logging_on_startup,
        ),
    )
    app.state.settings = app_settings

    register_exception_handlers(app)
    app.include_router(api_router)

    return app


def _build_lifespan(
    settings: Settings,
    *,
    configure_logging_on_startup: bool,
) -> Callable[[FastAPI], AsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if configure_logging_on_startup:
            configure_logging(settings.logging)
        logger = get_logger("api.lifecycle")
        logger.info(
            "Application startup complete",
            extra={
                "database_url": settings.database.url,
                "database_is_sqlite": settings.database.is_sqlite,
            },
        )
        try:
            yield
        finally:
            logger.info("Application shutdown complete")

    return lifespan


app = create_app()
