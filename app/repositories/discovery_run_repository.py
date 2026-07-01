from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select

from app.models.discovery_run import DiscoveryRun
from app.repositories.base import BaseRepository


class DiscoveryRunRepository(BaseRepository[DiscoveryRun]):
    model = DiscoveryRun

    def list_by_organization(
        self,
        organization_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DiscoveryRun]:
        self.logger.debug(
            "Listing discovery runs by organization",
            extra={
                "model": self.model.__name__,
                "organization_id": organization_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(DiscoveryRun)
            .where(DiscoveryRun.organization_id == organization_id)
            .order_by(DiscoveryRun.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return self.scalars(statement)

    def list_by_search(
        self,
        search_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DiscoveryRun]:
        self.logger.debug(
            "Listing discovery runs by search",
            extra={
                "model": self.model.__name__,
                "search_id": search_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(DiscoveryRun)
            .where(DiscoveryRun.search_id == search_id)
            .order_by(DiscoveryRun.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return self.scalars(statement)

    def list_recent_runs(
        self,
        organization_id: str,
        *,
        limit: int = 10,
    ) -> Sequence[DiscoveryRun]:
        self.logger.debug(
            "Listing recent discovery runs",
            extra={
                "model": self.model.__name__,
                "organization_id": organization_id,
                "limit": limit,
            },
        )
        statement = (
            select(DiscoveryRun)
            .where(DiscoveryRun.organization_id == organization_id)
            .order_by(DiscoveryRun.started_at.desc())
            .limit(limit)
        )
        return self.scalars(statement)

    def list_by_status(
        self,
        status: str,
        organization_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DiscoveryRun]:
        self.logger.debug(
            "Listing discovery runs by status",
            extra={
                "model": self.model.__name__,
                "status": status,
                "organization_id": organization_id,
                "limit": limit,
                "offset": offset,
            },
        )
        statement = (
            select(DiscoveryRun)
            .where(
                DiscoveryRun.organization_id == organization_id,
                DiscoveryRun.status == status,
            )
            .order_by(DiscoveryRun.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return self.scalars(statement)

    def update_statistics(
        self,
        run_id: str,
        *,
        sources_queried: int | None = None,
        companies_found: int | None = None,
        companies_created: int | None = None,
        companies_skipped: int | None = None,
    ) -> None:
        self.logger.debug(
            "Updating discovery run statistics",
            extra={
                "model": self.model.__name__,
                "run_id": run_id,
            },
        )
        run = self.get(run_id)
        if run is None:
            return

        if sources_queried is not None:
            run.sources_queried = sources_queried
        if companies_found is not None:
            run.companies_found = companies_found
        if companies_created is not None:
            run.companies_created = companies_created
        if companies_skipped is not None:
            run.companies_skipped = companies_skipped

    def complete_run(
        self,
        run_id: str,
        *,
        companies_found: int | None = None,
        companies_created: int | None = None,
        companies_skipped: int | None = None,
    ) -> None:
        self.logger.debug(
            "Completing discovery run",
            extra={
                "model": self.model.__name__,
                "run_id": run_id,
            },
        )
        run = self.get(run_id)
        if run is None:
            return

        run.status = "succeeded"
        run.finished_at = datetime.now(timezone.utc)
        if companies_found is not None:
            run.companies_found = companies_found
        if companies_created is not None:
            run.companies_created = companies_created
        if companies_skipped is not None:
            run.companies_skipped = companies_skipped

    def fail_run(self, run_id: str, *, error_message: str) -> None:
        self.logger.debug(
            "Failing discovery run",
            extra={
                "model": self.model.__name__,
                "run_id": run_id,
            },
        )
        run = self.get(run_id)
        if run is None:
            return

        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = error_message
