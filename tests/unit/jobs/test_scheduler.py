from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.jobs.scheduler import JobScheduler


@pytest.mark.asyncio
async def test_scheduler_run_calls_poll_once() -> None:
    mock_runner = MagicMock()
    mock_runner.start = AsyncMock()
    mock_runner._poll_once = AsyncMock()
    
    scheduler = JobScheduler(mock_runner, poll_interval=0.01)
    
    # Run for a short time
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)
    await scheduler.shutdown()
    await task
    
    # Should have called poll_once multiple times
    assert mock_runner._poll_once.call_count >= 2


@pytest.mark.asyncio
async def test_scheduler_shutdown_stops_loop() -> None:
    mock_runner = MagicMock()
    mock_runner.start = AsyncMock()
    mock_runner._poll_once = AsyncMock()
    
    scheduler = JobScheduler(mock_runner, poll_interval=0.01)
    
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.02)
    
    # Shutdown should stop the loop
    await scheduler.shutdown()
    await task
    
    # No more calls after shutdown
    call_count_at_shutdown = mock_runner._poll_once.call_count
    await asyncio.sleep(0.02)
    assert mock_runner._poll_once.call_count == call_count_at_shutdown


@pytest.mark.asyncio
async def test_scheduler_handles_poll_error() -> None:
    mock_runner = MagicMock()
    mock_runner.start = AsyncMock()
    mock_runner._poll_once = AsyncMock(side_effect=[Exception("poll error"), None, None])
    
    scheduler = JobScheduler(mock_runner, poll_interval=0.01)
    
    task = asyncio.create_task(scheduler.run())
    await asyncio.sleep(0.05)
    await scheduler.shutdown()
    await task
    
    # Should continue after error
    assert mock_runner._poll_once.call_count >= 2