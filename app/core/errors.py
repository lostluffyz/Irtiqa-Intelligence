from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Self

from app.core.logging import get_logger


class IrtiqaError(Exception):
    default_code = "irtiqa.error"
    default_message = "An application error occurred."
    default_log_level = logging.ERROR

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.details = dict(details or {})
        self.cause = cause
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "type": self.__class__.__name__,
        }
        if self.details:
            payload["details"] = self.details
        if self.cause is not None:
            payload["cause"] = self.cause.__class__.__name__
        return payload

    def with_details(self, **details: Any) -> Self:
        self.details.update(details)
        return self

    def log(
        self,
        logger: logging.Logger | None = None,
        *,
        level: int | None = None,
        include_traceback: bool = False,
    ) -> None:
        active_logger = logger or get_logger("errors")
        active_logger.log(
            level or self.default_log_level,
            str(self),
            extra={
                "error_code": self.code,
                "error_type": self.__class__.__name__,
                "error_details": self.details,
            },
            exc_info=include_traceback,
        )


class ConfigurationError(IrtiqaError):
    default_code = "irtiqa.configuration_error"
    default_message = "Application configuration is invalid."


class DatabaseError(IrtiqaError):
    default_code = "irtiqa.database_error"
    default_message = "A database operation failed."


class DatabaseConnectionError(DatabaseError):
    default_code = "irtiqa.database_connection_error"
    default_message = "Database connection failed."


class DatabaseMigrationError(DatabaseError):
    default_code = "irtiqa.database_migration_error"
    default_message = "Database migration failed."


class RepositoryError(IrtiqaError):
    default_code = "irtiqa.repository_error"
    default_message = "A repository operation failed."


class EntityNotFoundError(RepositoryError):
    default_code = "irtiqa.entity_not_found"
    default_message = "The requested entity was not found."
    default_log_level = logging.INFO


class EntityConflictError(RepositoryError):
    default_code = "irtiqa.entity_conflict"
    default_message = "The requested entity operation conflicts with existing data."


class ValidationError(IrtiqaError):
    default_code = "irtiqa.validation_error"
    default_message = "Input validation failed."
    default_log_level = logging.WARNING


class ServiceError(IrtiqaError):
    default_code = "irtiqa.service_error"
    default_message = "A service operation failed."


class WorkflowError(IrtiqaError):
    default_code = "irtiqa.workflow_error"
    default_message = "A workflow operation failed."


class WorkflowStateError(WorkflowError):
    default_code = "irtiqa.workflow_state_error"
    default_message = "Workflow state is invalid for the requested operation."


class AgentError(IrtiqaError):
    default_code = "irtiqa.agent_error"
    default_message = "An agent operation failed."


class AgentConfigurationError(AgentError):
    default_code = "irtiqa.agent_configuration_error"
    default_message = "Agent configuration is invalid."


class AgentExecutionError(AgentError):
    default_code = "irtiqa.agent_execution_error"
    default_message = "Agent execution failed."


class AgentValidationError(AgentError):
    default_code = "irtiqa.agent_validation_error"
    default_message = "Agent input validation failed."
    default_log_level = logging.WARNING


class AgentNetworkError(AgentError):
    default_code = "irtiqa.agent_network_error"
    default_message = "An agent network operation failed."


class AgentRateLimitError(AgentNetworkError):
    default_code = "irtiqa.agent_rate_limit_error"
    default_message = "Agent request was rate-limited."
    default_log_level = logging.WARNING


class AgentTimeoutError(AgentNetworkError):
    default_code = "irtiqa.agent_timeout_error"
    default_message = "Agent operation timed out."


class PermissionError(IrtiqaError):
    default_code = "irtiqa.forbidden"
    default_message = "You do not have permission to perform this action."
    default_log_level = logging.WARNING


class ExternalIntegrationError(IrtiqaError):
    default_code = "irtiqa.external_integration_error"
    default_message = "An external integration failed."


__all__ = [
    "AgentConfigurationError",
    "AgentError",
    "AgentExecutionError",
    "AgentNetworkError",
    "AgentRateLimitError",
    "AgentTimeoutError",
    "AgentValidationError",
    "ConfigurationError",
    "DatabaseConnectionError",
    "DatabaseError",
    "DatabaseMigrationError",
    "EntityConflictError",
    "EntityNotFoundError",
    "ExternalIntegrationError",
    "IrtiqaError",
    "PermissionError",
    "RepositoryError",
    "ServiceError",
    "ValidationError",
    "WorkflowError",
    "WorkflowStateError",
]
