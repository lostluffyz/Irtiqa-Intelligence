from __future__ import annotations

from app.core.errors import IrtiqaError


class JobSchedulingError(IrtiqaError):
    default_code = "irtiqa.job_scheduling_error"
    default_message = "Job scheduling failed."


class JobExecutionError(IrtiqaError):
    default_code = "irtiqa.job_execution_error"
    default_message = "Job execution failed."


class JobCancellationError(IrtiqaError):
    default_code = "irtiqa.job_cancellation_error"
    default_message = "Job cancellation failed."


__all__ = [
    "JobCancellationError",
    "JobExecutionError",
    "JobSchedulingError",
]