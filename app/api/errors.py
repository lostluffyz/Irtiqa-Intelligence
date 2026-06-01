from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import (
    ConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    EntityConflictError,
    EntityNotFoundError,
    IrtiqaError,
    ValidationError,
)
from app.core.logging import get_logger


logger = get_logger("api.errors")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(IrtiqaError, handle_irtiqa_error)
    app.add_exception_handler(RequestValidationError, handle_request_validation_error)
    app.add_exception_handler(Exception, handle_unhandled_error)


async def handle_irtiqa_error(request: Request, exc: IrtiqaError) -> JSONResponse:
    exc.log(logger)
    return JSONResponse(
        status_code=_status_code_for_error(exc),
        content={"error": exc.to_dict()},
    )


async def handle_request_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    error = ValidationError(
        "Request validation failed.",
        code="irtiqa.request_validation_error",
        details={"errors": exc.errors()},
        cause=exc,
    )
    error.log(logger)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": error.to_dict()},
    )


async def handle_unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API exception")
    error = IrtiqaError(
        "An unexpected server error occurred.",
        code="irtiqa.internal_server_error",
        cause=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": error.to_dict()},
    )


def _status_code_for_error(exc: IrtiqaError) -> int:
    if isinstance(exc, EntityNotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(exc, EntityConflictError):
        return status.HTTP_409_CONFLICT
    if isinstance(exc, ValidationError):
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    if isinstance(exc, DatabaseConnectionError):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if isinstance(exc, (ConfigurationError, DatabaseError)):
        return status.HTTP_500_INTERNAL_SERVER_ERROR
    return status.HTTP_500_INTERNAL_SERVER_ERROR


ExceptionHandler = Callable[[Request, Any], Awaitable[JSONResponse]]
