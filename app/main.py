from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import AsyncContextManager
import asyncio

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.agents import (
    DeepScraperAgent,
    IntelligenceScoringAgent,
    IntentSignalAgent,
    PersonalizationAgent,
    TechnographicAgent,
)
from app.agents.registry import AgentRegistry
from app.jobs import JobRunner, JobScheduler
from app.services import JobService
from app.workflows.registry import WorkflowRegistry
from app.workflows.intelligence_pipeline import IntelligencePipelineWorkflow
from app.workflows.score_refresh import ScoreRefreshWorkflow


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

        job_service = JobService()

        agent_registry = AgentRegistry()
        agent_registry.register(DeepScraperAgent)
        agent_registry.register(TechnographicAgent)
        agent_registry.register(IntentSignalAgent)
        agent_registry.register(IntelligenceScoringAgent)
        agent_registry.register(PersonalizationAgent)

        workflow_registry = WorkflowRegistry()
        workflow_registry.register(ScoreRefreshWorkflow)
        workflow_registry.register(IntelligencePipelineWorkflow)

        job_runner = JobRunner(
            job_service=job_service,
            agent_registry=agent_registry,
            workflow_registry=workflow_registry,
            poll_interval=5.0,
        )
        scheduler = JobScheduler(job_runner, poll_interval=5.0)
        scheduler_task = asyncio.create_task(scheduler.run())

        try:
            yield
        finally:
            await scheduler.shutdown()
            await scheduler_task
            logger.info("Application shutdown complete")

    return lifespan


app = create_app()
