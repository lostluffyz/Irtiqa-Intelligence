from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.jobs.retry_policy import compute_next_scheduled_at


def test_compute_next_scheduled_at_first_retry() -> None:
    result = compute_next_scheduled_at(0, base_delay_seconds=60.0)
    now = datetime.now(timezone.utc)
    
    # Should be roughly 60 seconds in the future (with 10% jitter)
    delay = (result - now).total_seconds()
    assert 54 <= delay <= 66


def test_compute_next_scheduled_at_exponential_backoff() -> None:
    result_0 = compute_next_scheduled_at(0, base_delay_seconds=60.0)
    result_1 = compute_next_scheduled_at(1, base_delay_seconds=60.0)
    result_2 = compute_next_scheduled_at(2, base_delay_seconds=60.0)

    # Check that delay increases exponentially (with jitter)
    delay_0 = (result_0 - datetime.now(timezone.utc)).total_seconds()
    delay_1 = (result_1 - datetime.now(timezone.utc)).total_seconds()
    delay_2 = (result_2 - datetime.now(timezone.utc)).total_seconds()

    # With jitter, delays should be roughly 60, 120, 240 seconds
    # Allow some tolerance for jitter
    assert 54 <= delay_0 <= 66
    assert 108 <= delay_1 <= 132
    assert 216 <= delay_2 <= 264


def test_compute_next_scheduled_at_jitter_bounded() -> None:
    """Test that jitter is bounded to 10% of delay."""
    for retry_count in range(5):
        result = compute_next_scheduled_at(retry_count, base_delay_seconds=100.0)
        delay = (result - datetime.now(timezone.utc)).total_seconds()
        expected_base = 100.0 * (2 ** retry_count)
        max_delay = expected_base * 1.1  # 10% jitter max
        assert delay <= max_delay + 1  # +1 for time elapsed during test


def test_compute_next_scheduled_at_deterministic_with_seed() -> None:
    """Test that with fixed seed, results are deterministic."""
    import random
    random.seed(42)
    result_1 = compute_next_scheduled_at(0, base_delay_seconds=60.0)
    
    random.seed(42)
    result_2 = compute_next_scheduled_at(0, base_delay_seconds=60.0)
    
    # Results should be very close (within 1 second due to time passing)
    assert abs((result_1 - result_2).total_seconds()) < 1