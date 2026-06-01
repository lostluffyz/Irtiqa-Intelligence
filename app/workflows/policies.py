from __future__ import annotations

from pydantic import Field, model_validator

from app.schemas.base import IrtiqaSchema


class RetryPolicy(IrtiqaSchema):
    max_attempts: int = Field(default=1, ge=1, le=10)
    initial_delay_seconds: float = Field(default=0.0, ge=0.0, le=300.0)
    backoff_multiplier: float = Field(default=1.0, ge=1.0, le=10.0)
    max_delay_seconds: float = Field(default=0.0, ge=0.0, le=3600.0)
    retryable_error_codes: frozenset[str] = Field(default_factory=frozenset)
    timeout_seconds: float | None = Field(default=None, gt=0.0, le=86400.0)

    @model_validator(mode="after")
    def validate_delay_bounds(self) -> RetryPolicy:
        if self.max_attempts > 1 and self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("max_delay_seconds must be greater than or equal to initial_delay_seconds.")
        return self

    def should_retry(self, *, attempt: int, error_code: str) -> bool:
        return attempt < self.max_attempts and error_code in self.retryable_error_codes

    def delay_for_attempt(self, attempt: int) -> float:
        if attempt <= 1:
            return self.initial_delay_seconds
        delay = self.initial_delay_seconds * (self.backoff_multiplier ** (attempt - 1))
        return min(delay, self.max_delay_seconds)
