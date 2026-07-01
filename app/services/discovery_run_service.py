from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any, TypeVar

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import EntityConflictError, EntityNotFoundError, IrtiqaError, ServiceError, ValidationError
from app.core.logging import get_logger
from app.database import session as database_session
from app.models.discovery_run import DiscoveryRun
from app.models.discovery_search import DiscoverySearch
from app.repositories.discovery_run_repository import DiscoveryRunRepository
from app.repositories.discovery_search_repository import DiscoverySearchRepository


DISCOVERY_RUN_STATUSES = {"running", "succeeded", "failed"}
ResultT = TypeVar("ResultT")


class DiscoveryRunService:
    """Manages discovery run lifecycle and statistics."""

    def __init__(self) -> None:
        self.logger = get_logger(f"services.{self.__class__.__name__}")

    def start_run(self, *, organization_id: str, search_id: str) -> DiscoveryRun:
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_identifier(search_id, field_name="search_id")

        def operation(session: Session) -> DiscoveryRun:
            search = self._get_search_for_organization(session, search_id, organization_id)
            if search.status != "active":
                raise ValidationError(
                    "Archived discovery searches cannot be run.",
                    details={
                        "service": self.__class__.__name__,
                        "search_id": search_id,
                        "status": search.status,
                    },
                )
            repository = DiscoveryRunRepository(session)
            run = DiscoveryRun(
                organization_id=organization_id,
                search_id=search_id,
                status="running",
                sources_queried=0,
                companies_found=0,
                companies_created=0,
                companies_skipped=0,
                started_at=datetime.now(timezone.utc),
            )
            repository.add(run)
            session.flush()
            return run

        return self._run_in_transaction("start_run", operation)

    def update_statistics(
        self,
        run_id: str,
        *,
        organization_id: str,
        sources_queried: int | None = None,
        companies_found: int | None = None,
        companies_created: int | None = None,
        companies_skipped: int | None = None,
    ) -> DiscoveryRun:
        self._validate_identifier(run_id, field_name="run_id")
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_optional_counter(sources_queried, field_name="sources_queried")
        self._validate_optional_counter(companies_found, field_name="companies_found")
        self._validate_optional_counter(companies_created, field_name="companies_created")
        self._validate_optional_counter(companies_skipped, field_name="companies_skipped")

        def operation(session: Session) -> DiscoveryRun:
            run = self._get_run_for_organization(session, run_id, organization_id)
            if run.status != "running":
                raise ValidationError(
                    "Discovery run statistics can only be updated while running.",
                    details={
                        "service": self.__class__.__name__,
                        "run_id": run_id,
                        "status": run.status,
                    },
                )
            self._apply_statistics(
                run,
                sources_queried=sources_queried,
                companies_found=companies_found,
                companies_created=companies_created,
                companies_skipped=companies_skipped,
            )
            self._validate_statistics_consistency(run)
            session.flush()
            return run

        return self._run_in_transaction("update_statistics", operation)

    def complete_run(
        self,
        run_id: str,
        *,
        organization_id: str,
        sources_queried: int | None = None,
        companies_found: int | None = None,
        companies_created: int | None = None,
        companies_skipped: int | None = None,
    ) -> DiscoveryRun:
        self._validate_identifier(run_id, field_name="run_id")
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_optional_counter(sources_queried, field_name="sources_queried")
        self._validate_optional_counter(companies_found, field_name="companies_found")
        self._validate_optional_counter(companies_created, field_name="companies_created")
        self._validate_optional_counter(companies_skipped, field_name="companies_skipped")

        def operation(session: Session) -> DiscoveryRun:
            run = self._get_run_for_organization(session, run_id, organization_id)
            self._require_running(run, operation_name="complete_run")
            self._apply_statistics(
                run,
                sources_queried=sources_queried,
                companies_found=companies_found,
                companies_created=companies_created,
                companies_skipped=companies_skipped,
            )
            self._validate_statistics_consistency(run)
            run.status = "succeeded"
            run.finished_at = datetime.now(timezone.utc)
            run.error_message = None
            session.flush()
            return run

        return self._run_in_transaction("complete_run", operation)

    def fail_run(self, run_id: str, *, organization_id: str, error_message: str) -> DiscoveryRun:
        self._validate_identifier(run_id, field_name="run_id")
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_identifier(error_message, field_name="error_message")

        # Truncate error message to prevent database column overflow
        truncated_error = self._truncate_error_message(error_message)

        def operation(session: Session) -> DiscoveryRun:
            run = self._get_run_for_organization(session, run_id, organization_id)
            self._require_running(run, operation_name="fail_run")
            run.status = "failed"
            run.finished_at = datetime.now(timezone.utc)
            run.error_message = truncated_error
            session.flush()
            return run

        return self._run_in_transaction("fail_run", operation)

    def get_run(self, run_id: str, *, organization_id: str) -> DiscoveryRun:
        self._validate_identifier(run_id, field_name="run_id")
        self._validate_identifier(organization_id, field_name="organization_id")

        def operation(session: Session) -> DiscoveryRun:
            return self._get_run_for_organization(session, run_id, organization_id)

        return self._run_in_transaction("get_run", operation)

    def list_by_search(
        self,
        search_id: str,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DiscoveryRun]:
        self._validate_identifier(search_id, field_name="search_id")
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[DiscoveryRun]:
            self._get_search_for_organization(session, search_id, organization_id)
            runs = DiscoveryRunRepository(session).list_by_search(
                search_id,
                limit=limit,
                offset=offset,
            )
            return [run for run in runs if run.organization_id == organization_id]

        return self._run_in_transaction("list_by_search", operation)

    def list_recent_runs(
        self,
        *,
        organization_id: str,
        limit: int = 10,
    ) -> Sequence[DiscoveryRun]:
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_limit(limit)

        def operation(session: Session) -> Sequence[DiscoveryRun]:
            return DiscoveryRunRepository(session).list_recent_runs(
                organization_id,
                limit=limit,
            )

        return self._run_in_transaction("list_recent_runs", operation)

    def list_by_status(
        self,
        status: str,
        *,
        organization_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[DiscoveryRun]:
        self._validate_identifier(organization_id, field_name="organization_id")
        self._validate_status(status)
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[DiscoveryRun]:
            return DiscoveryRunRepository(session).list_by_status(
                status,
                organization_id,
                limit=limit,
                offset=offset,
            )

        return self._run_in_transaction("list_by_status", operation)

    def _run_in_transaction(
        self,
        operation_name: str,
        operation: Callable[[Session], ResultT],
    ) -> ResultT:
        try:
            with database_session.session_scope() as session:
                self.logger.debug(
                    "Starting discovery run service operation",
                    extra={"service": self.__class__.__name__, "operation": operation_name},
                )
                result = operation(session)
                self.logger.debug(
                    "Completed discovery run service operation",
                    extra={"service": self.__class__.__name__, "operation": operation_name},
                )
                return result
        except IrtiqaError:
            raise
        except IntegrityError as exc:
            error = EntityConflictError(
                "Database integrity constraint failed during discovery run service operation.",
                details={"service": self.__class__.__name__, "operation": operation_name},
                cause=exc,
            )
            error.log(self.logger, include_traceback=True)
            raise error from exc
        except SQLAlchemyError as exc:
            error = ServiceError(
                "Database operation failed during discovery run service execution.",
                details={"service": self.__class__.__name__, "operation": operation_name},
                cause=exc,
            )
            error.log(self.logger, include_traceback=True)
            raise error from exc
        except Exception as exc:
            error = ServiceError(
                "Unexpected discovery run service operation failure.",
                details={"service": self.__class__.__name__, "operation": operation_name},
                cause=exc,
            )
            error.log(self.logger, include_traceback=True)
            raise error from exc

    def _get_search_for_organization(
        self,
        session: Session,
        search_id: str,
        organization_id: str,
    ) -> DiscoverySearch:
        search = DiscoverySearchRepository(session).get(search_id)
        if search is None or search.organization_id != organization_id:
            raise EntityNotFoundError(
                details={
                    "service": self.__class__.__name__,
                    "model": DiscoverySearch.__name__,
                    "entity_id": search_id,
                }
            )
        return search

    def _get_run_for_organization(
        self,
        session: Session,
        run_id: str,
        organization_id: str,
    ) -> DiscoveryRun:
        run = DiscoveryRunRepository(session).get(run_id)
        if run is None or run.organization_id != organization_id:
            raise EntityNotFoundError(
                details={
                    "service": self.__class__.__name__,
                    "model": DiscoveryRun.__name__,
                    "entity_id": run_id,
                }
            )
        return run

    def _apply_statistics(
        self,
        run: DiscoveryRun,
        *,
        sources_queried: int | None,
        companies_found: int | None,
        companies_created: int | None,
        companies_skipped: int | None,
    ) -> None:
        if sources_queried is not None:
            run.sources_queried = sources_queried
        if companies_found is not None:
            run.companies_found = companies_found
        if companies_created is not None:
            run.companies_created = companies_created
        if companies_skipped is not None:
            run.companies_skipped = companies_skipped

    def _validate_statistics_consistency(self, run: DiscoveryRun) -> None:
        if run.companies_created + run.companies_skipped > run.companies_found:
            raise ValidationError(
                "Created and skipped companies cannot exceed companies found.",
                details={
                    "service": self.__class__.__name__,
                    "run_id": run.id,
                    "companies_found": run.companies_found,
                    "companies_created": run.companies_created,
                    "companies_skipped": run.companies_skipped,
                },
            )

    def _require_running(self, run: DiscoveryRun, *, operation_name: str) -> None:
        if run.status != "running":
            raise ValidationError(
                "Discovery run lifecycle operation requires a running run.",
                details={
                    "service": self.__class__.__name__,
                    "operation": operation_name,
                    "run_id": run.id,
                    "status": run.status,
                },
            )

    def _validate_identifier(self, value: str, *, field_name: str) -> None:
        if not value or not value.strip():
            raise ValidationError(
                f"{field_name} is required.",
                details={"service": self.__class__.__name__, "field": field_name},
            )

    def _validate_limit(self, limit: int) -> None:
        if limit < 1 or limit > 500:
            raise ValidationError(
                "Limit must be between 1 and 500.",
                details={"service": self.__class__.__name__, "limit": limit},
            )

    def _validate_offset(self, offset: int) -> None:
        if offset < 0:
            raise ValidationError(
                "Offset must be greater than or equal to 0.",
                details={"service": self.__class__.__name__, "offset": offset},
            )

    def _validate_optional_counter(self, value: int | None, *, field_name: str) -> None:
        if value is not None and value < 0:
            raise ValidationError(
                f"{field_name} must be greater than or equal to 0.",
                details={
                    "service": self.__class__.__name__,
                    "field": field_name,
                    "value": value,
                },
            )

    def _validate_status(self, status: Any) -> None:
        if status not in DISCOVERY_RUN_STATUSES:
            raise ValidationError(
                "Discovery run status must be running, succeeded, or failed.",
                details={
                    "service": self.__class__.__name__,
                    "field": "status",
                    "status": status,
                },
            )

    @staticmethod
    def _truncate_error_message(error_message: str, max_length: int = 2000) -> str:
        """Truncate error message to prevent database column overflow."""
        if len(error_message) <= max_length:
            return error_message
        return error_message[: max_length - 3] + "..."
