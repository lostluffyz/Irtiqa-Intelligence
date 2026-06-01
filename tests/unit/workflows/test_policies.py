from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.workflows.policies import RetryPolicy


def test_retry_policy_defaults_to_no_retry() -> None:
    policy = RetryPolicy()

    assert policy.max_attempts == 1
    assert not policy.should_retry(attempt=1, error_code="irtiqa.external_integration_error")


def test_retry_policy_validates_delay_bounds() -> None:
    with pytest.raises(PydanticValidationError):
        RetryPolicy(max_attempts=3, initial_delay_seconds=5.0, max_delay_seconds=1.0)


def test_retry_policy_identifies_retryable_errors_and_backoff_delay() -> None:
    policy = RetryPolicy(
        max_attempts=3,
        initial_delay_seconds=2.0,
        backoff_multiplier=2.0,
        max_delay_seconds=5.0,
        retryable_error_codes=frozenset({"irtiqa.external_integration_error"}),
    )

    assert policy.should_retry(attempt=1, error_code="irtiqa.external_integration_error")
    assert not policy.should_retry(attempt=3, error_code="irtiqa.external_integration_error")
    assert not policy.should_retry(attempt=1, error_code="irtiqa.validation_error")
    assert policy.delay_for_attempt(1) == 2.0
    assert policy.delay_for_attempt(2) == 4.0
    assert policy.delay_for_attempt(3) == 5.0
