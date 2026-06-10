from __future__ import annotations

from app.jobs.errors import JobCancellationError, JobExecutionError, JobSchedulingError


def test_job_scheduling_error_serialization() -> None:
    error = JobSchedulingError(
        "Cannot schedule job",
        details={"job_id": "test-123", "target_name": "test_agent"},
    )
    
    assert error.code == "irtiqa.job_scheduling_error"
    assert error.message == "Cannot schedule job"
    assert error.details["job_id"] == "test-123"
    assert error.details["target_name"] == "test_agent"
    
    error_dict = error.to_dict()
    assert error_dict["code"] == "irtiqa.job_scheduling_error"
    assert error_dict["message"] == "Cannot schedule job"
    assert error_dict["details"]["job_id"] == "test-123"


def test_job_execution_error_serialization() -> None:
    error = JobExecutionError(
        "Job execution failed",
        details={"job_id": "test-123", "retry_count": 1},
    )
    
    assert error.code == "irtiqa.job_execution_error"
    assert error.message == "Job execution failed"
    assert error.details["job_id"] == "test-123"
    assert error.details["retry_count"] == 1


def test_job_cancellation_error_serialization() -> None:
    error = JobCancellationError(
        "Cannot cancel job",
        details={"job_id": "test-123", "current_status": "running"},
    )
    
    assert error.code == "irtiqa.job_cancellation_error"
    assert error.message == "Cannot cancel job"
    assert error.details["job_id"] == "test-123"
    assert error.details["current_status"] == "running"


def test_job_errors_inherit_from_irtiqa_error() -> None:
    from app.core.errors import IrtiqaError
    
    for error_cls in [JobSchedulingError, JobExecutionError, JobCancellationError]:
        error = error_cls("test")
        assert isinstance(error, IrtiqaError)