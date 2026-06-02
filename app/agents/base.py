from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, TypedDict, TypeVar, cast
import time

from app.agents.context import AgentContext
from app.agents.result import AGENT_STATUS_FAILED, AGENT_STATUS_SUCCEEDED, AgentResult
from app.core.errors import (
    AgentConfigurationError,
    AgentError,
    AgentExecutionError,
    AgentValidationError,
    IrtiqaError,
)
from app.core.logging import get_logger
from app.services import AgentRunService


ServiceT = TypeVar("ServiceT")


class AgentRunOutput(TypedDict):
    """Return type for ``BaseAgent._run()``.

    Concrete agents return this structure so they do not need to
    construct the full ``AgentResult`` object themselves.
    """

    output_ids: dict[str, list[str]]
    summary: str
    stats: dict[str, Any]


class BaseAgent(ABC):
    """Abstract base class for all Irtiqa agents.

    Uses the Template Method pattern: the public ``execute()`` method
    handles lifecycle concerns (validation, audit trail, error
    translation) while concrete subclasses implement the abstract
    ``_run()`` method with agent-specific intelligence logic.

    Agents are fully asynchronous.  They receive service dependencies
    through ``**services`` following the same pattern used by
    ``Workflow.__init__``.
    """

    name: str
    version: str

    def __init__(self, **services: Any) -> None:
        self.services: dict[str, Any] = dict(services)
        self.logger = get_logger(f"agents.{self.name}")

    async def execute(self, context: AgentContext) -> AgentResult:
        """Public entrypoint for agent execution.

        Orchestrates context validation, audit-record creation, core
        execution via ``_run()``, and structured result assembly.
        Failures at any stage produce a failed ``AgentResult`` rather
        than propagating raw exceptions.
        """
        start_time = time.perf_counter()
        agent_run_id: str | None = None

        try:
            await self._validate_context(context)

            agent_run_service = self._service("agent_run_service", AgentRunService)
            agent_run = agent_run_service.start_workflow_run(
                agent_name=self.name,
                workflow_name=context.workflow_name or "",
                company_id=context.company_id,
                contact_id=context.contact_id,
                input_summary=self._build_input_summary(context),
            )
            agent_run_id = agent_run.id

            self.logger.info(
                "Agent execution started",
                extra={
                    "agent_name": self.name,
                    "agent_version": self.version,
                    "agent_run_id": agent_run_id,
                    "company_id": context.company_id,
                    "contact_id": context.contact_id,
                    "workflow_name": context.workflow_name,
                    "correlation_id": context.correlation_id,
                },
            )

            run_output = await self._run(context)
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            agent_run_service.mark_succeeded(
                agent_run_id,
                output_summary=run_output["summary"],
            )

            self.logger.info(
                "Agent execution succeeded",
                extra={
                    "agent_name": self.name,
                    "agent_run_id": agent_run_id,
                    "duration_ms": round(duration_ms, 2),
                },
            )

            return AgentResult(
                agent_name=self.name,
                agent_run_id=agent_run_id,
                status=AGENT_STATUS_SUCCEEDED,
                output_ids=run_output["output_ids"],
                summary=run_output["summary"],
                duration_ms=duration_ms,
                stats=run_output["stats"],
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            structured_error = self._translate_exception(exc)
            structured_error.log(self.logger, include_traceback=True)

            if agent_run_id is not None:
                try:
                    agent_run_service = self._service("agent_run_service", AgentRunService)
                    agent_run_service.mark_failed(
                        agent_run_id,
                        error_message=str(structured_error),
                    )
                except Exception:
                    self.logger.warning(
                        "Failed to mark agent run as failed",
                        extra={"agent_run_id": agent_run_id},
                        exc_info=True,
                    )

            self.logger.error(
                "Agent execution failed",
                extra={
                    "agent_name": self.name,
                    "agent_run_id": agent_run_id,
                    "duration_ms": round(duration_ms, 2),
                    "error_code": structured_error.code,
                },
            )

            return AgentResult(
                agent_name=self.name,
                agent_run_id=agent_run_id,
                status=AGENT_STATUS_FAILED,
                summary=f"Failed: {structured_error.message}",
                error=structured_error.to_dict(),
                duration_ms=duration_ms,
            )

    @abstractmethod
    async def _run(self, context: AgentContext) -> AgentRunOutput:
        """Implement agent-specific intelligence logic.

        Concrete subclasses must return an ``AgentRunOutput`` containing
        ``output_ids`` (a mapping of entity table names to created or
        updated record IDs), a human-readable ``summary``, and execution
        ``stats``.
        """
        raise NotImplementedError

    async def _validate_context(self, context: AgentContext) -> None:
        """Validate agent context before execution.

        The base implementation verifies that ``context.agent_name``
        matches the agent's declared ``name``.  Subclasses may override
        to add agent-specific validation (e.g. required option keys).
        """
        if context.agent_name != self.name:
            raise AgentValidationError(
                "Agent context agent_name does not match agent name.",
                details={
                    "expected_agent_name": self.name,
                    "received_agent_name": context.agent_name,
                },
            )

    def _translate_exception(self, exc: Exception) -> AgentError:
        """Convert arbitrary exceptions to structured ``AgentError`` instances."""
        if isinstance(exc, AgentError):
            return exc
        if isinstance(exc, IrtiqaError):
            return AgentExecutionError(
                exc.message,
                details=exc.details,
                cause=exc,
            )
        return AgentExecutionError(
            "Unexpected agent execution failure.",
            details={"exception_type": type(exc).__name__},
            cause=exc,
        )

    def _service(self, key: str, service_type: type[ServiceT]) -> ServiceT:
        """Retrieve a typed service dependency.

        Raises ``AgentConfigurationError`` if the service is missing.
        """
        service = self.services.get(key)
        if service is None:
            raise AgentConfigurationError(
                "Agent service dependency is missing.",
                details={
                    "agent_name": self.name,
                    "service": key,
                    "expected_type": service_type.__name__,
                },
            )
        return cast(ServiceT, service)

    def _build_input_summary(self, context: AgentContext) -> str:
        """Build a human-readable summary of agent input for ``agent_runs.input_summary``."""
        parts = [
            f"agent={self.name}",
            f"version={self.version}",
            f"company_id={context.company_id}",
        ]
        if context.contact_id is not None:
            parts.append(f"contact_id={context.contact_id}")
        if context.workflow_name is not None:
            parts.append(f"workflow_name={context.workflow_name}")
        if context.correlation_id is not None:
            parts.append(f"correlation_id={context.correlation_id}")
        if context.options:
            parts.append(f"options={dict(context.options)}")
        return ", ".join(parts)
