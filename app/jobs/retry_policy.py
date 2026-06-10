from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random


def compute_next_scheduled_at(
    retry_count: int,
    base_delay_seconds: float = 60.0,
) -> datetime:
    """Exponential backoff with jitter.

    Args:
        retry_count: Number of retries already attempted (0 for first retry).
        base_delay_seconds: Base delay in seconds before exponential backoff.

    Returns:
        datetime: Next scheduled execution time in UTC.
    """
    delay = base_delay_seconds * (2 ** retry_count)
    jitter = random.uniform(0, delay * 0.1)
    return datetime.now(timezone.utc) + timedelta(seconds=delay + jitter)