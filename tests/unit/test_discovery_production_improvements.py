from __future__ import annotations

import pytest

from app.services.discovery_run_service import DiscoveryRunService


def test_error_message_truncation() -> None:
    """Verify that error messages are truncated to prevent database overflow."""
    service = DiscoveryRunService()

    # Short message unchanged
    short_msg = "Error occurred"
    assert service._truncate_error_message(short_msg) == short_msg

    # Long message truncated
    long_msg = "X" * 3000
    truncated = service._truncate_error_message(long_msg)
    assert len(truncated) == 2000
    assert truncated.endswith("...")
    assert truncated[:1997] == "X" * 1997


def test_error_message_truncation_custom_length() -> None:
    """Verify error message truncation respects custom max_length."""
    service = DiscoveryRunService()

    message = "Y" * 500
    truncated = service._truncate_error_message(message, max_length=100)
    assert len(truncated) == 100
    assert truncated.endswith("...")
    assert truncated[:97] == "Y" * 97


def test_error_message_truncation_at_boundary() -> None:
    """Verify error message truncation handles exact boundary case."""
    service = DiscoveryRunService()

    # Exactly at max_length
    message = "Z" * 2000
    truncated = service._truncate_error_message(message, max_length=2000)
    assert truncated == message
    assert not truncated.endswith("...")

    # One character over
    message_over = "Z" * 2001
    truncated_over = service._truncate_error_message(message_over, max_length=2000)
    assert len(truncated_over) == 2000
    assert truncated_over.endswith("...")
