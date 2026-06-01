from __future__ import annotations

import logging

from app.core.errors import (
    AgentConfigurationError,
    AgentError,
    AgentExecutionError,
    ConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    DatabaseMigrationError,
    EntityConflictError,
    EntityNotFoundError,
    ExternalIntegrationError,
    IrtiqaError,
    RepositoryError,
    ServiceError,
    ValidationError,
    WorkflowError,
    WorkflowStateError,
)


def test_base_error_has_stable_code_message_details_and_string() -> None:
    error = IrtiqaError(
        "Something failed.",
        code="irtiqa.test_error",
        details={"entity": "company"},
    )

    assert error.code == "irtiqa.test_error"
    assert error.message == "Something failed."
    assert error.details == {"entity": "company"}
    assert str(error) == "irtiqa.test_error: Something failed."


def test_error_to_dict_includes_optional_details_and_cause() -> None:
    cause = ValueError("bad value")
    error = DatabaseError("Insert failed.", details={"table": "companies"}, cause=cause)

    assert error.to_dict() == {
        "code": "irtiqa.database_error",
        "message": "Insert failed.",
        "type": "DatabaseError",
        "details": {"table": "companies"},
        "cause": "ValueError",
    }


def test_error_with_details_updates_context_and_returns_self() -> None:
    error = ValidationError().with_details(field="domain", reason="required")

    assert error.details == {"field": "domain", "reason": "required"}


def test_exception_hierarchy_covers_required_categories() -> None:
    assert issubclass(DatabaseError, IrtiqaError)
    assert issubclass(DatabaseConnectionError, DatabaseError)
    assert issubclass(DatabaseMigrationError, DatabaseError)
    assert issubclass(RepositoryError, IrtiqaError)
    assert issubclass(EntityNotFoundError, RepositoryError)
    assert issubclass(EntityConflictError, RepositoryError)
    assert issubclass(ValidationError, IrtiqaError)
    assert issubclass(ServiceError, IrtiqaError)
    assert issubclass(WorkflowError, IrtiqaError)
    assert issubclass(WorkflowStateError, WorkflowError)
    assert issubclass(AgentError, IrtiqaError)
    assert issubclass(AgentConfigurationError, AgentError)
    assert issubclass(AgentExecutionError, AgentError)
    assert issubclass(ExternalIntegrationError, IrtiqaError)
    assert issubclass(ConfigurationError, IrtiqaError)


def test_default_error_codes_are_specific() -> None:
    errors = [
        ConfigurationError(),
        DatabaseError(),
        DatabaseConnectionError(),
        DatabaseMigrationError(),
        RepositoryError(),
        EntityNotFoundError(),
        EntityConflictError(),
        ValidationError(),
        ServiceError(),
        WorkflowError(),
        WorkflowStateError(),
        AgentError(),
        AgentConfigurationError(),
        AgentExecutionError(),
        ExternalIntegrationError(),
    ]

    assert len({error.code for error in errors}) == len(errors)
    assert all(error.code.startswith("irtiqa.") for error in errors)


def test_error_log_uses_structured_extra_fields(caplog) -> None:
    error = RepositoryError("Lookup failed.", details={"model": "Company"})

    with caplog.at_level(logging.ERROR, logger="irtiqa.errors"):
        error.log()

    record = caplog.records[0]

    assert record.message == "irtiqa.repository_error: Lookup failed."
    assert record.error_code == "irtiqa.repository_error"
    assert record.error_type == "RepositoryError"
    assert record.error_details == {"model": "Company"}


def test_not_found_and_validation_errors_use_lower_default_log_levels() -> None:
    assert EntityNotFoundError.default_log_level == logging.INFO
    assert ValidationError.default_log_level == logging.WARNING
