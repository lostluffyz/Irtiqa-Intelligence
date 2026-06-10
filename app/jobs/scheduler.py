from __future__ import annotations

import asyncio
import logging

from app.jobs.runner import JobRunner
from app.core.logging import get_logger


class JobScheduler:
    def __init__(self, runner: JobRunner, *, poll_interval: float = 5.0) -> None:
        self.runner = runner
        self.poll_interval = poll_interval
        self.logger = get_logger("jobs.scheduler")
        self._shutdown_event = asyncio.Event()

    async def run(self) -> None:
        self.logger.info(
            "JobScheduler starting",
            extra={"poll_interval": self.poll_interval},
        )
        await self.runner.start()

        while not self._shutdown_event.is_set():
            try:
                await self.runner._poll_once()
            except Exception as exc:
                self.logger.error(
                    "Error in scheduler polling loop",
                    extra={"error": str(exc)},
                    exc_info=True,
                )

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.poll_interval,
                )
            except asyncio.TimeoutError:
                continue

        self.logger.info("JobScheduler stopped")

    async def shutdown(self) -> None:
        self.logger.info("JobScheduler shutdown requested")
        self._shutdown_event.set()