from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import EntityConflictError, EntityNotFoundError, IrtiqaError, ServiceError, ValidationError
from app.core.logging import get_logger
from app.database import session as database_session
from app.models.base import Base
from app.repositories.base import BaseRepository


ModelT = TypeVar("ModelT", bound=Base)
RepositoryT = TypeVar("RepositoryT", bound=BaseRepository[Any])
ResultT = TypeVar("ResultT")


class BaseService(Generic[ModelT, RepositoryT]):
    model: type[ModelT]
    repository: type[RepositoryT]

    def __init__(self) -> None:
        self.logger = get_logger(f"services.{self.__class__.__name__}")

    def create(self, organization_id: str, **values: Any) -> ModelT:
        self._validate_create_values(values)

        def operation(session: Session) -> ModelT:
            repository = self._repository(session)
            values_with_org = {"organization_id": organization_id, **values}
            self._before_create(repository, values_with_org)
            entity = self.model(**values_with_org)
            repository.add(entity)
            session.flush()
            return entity

        return self._run_in_transaction("create", operation)

    def get(self, entity_id: str) -> ModelT | None:
        self._validate_identifier(entity_id, field_name="entity_id")

        def operation(session: Session) -> ModelT | None:
            return self._repository(session).get(entity_id)

        return self._run_in_transaction("get", operation)

    def get_required(self, entity_id: str) -> ModelT:
        entity = self.get(entity_id)
        if entity is None:
            error = EntityNotFoundError(
                details={
                    "service": self.__class__.__name__,
                    "model": self.model.__name__,
                    "entity_id": entity_id,
                }
            )
            error.log(self.logger)
            raise error
        return entity

    def list(self, *, organization_id: str | None = None, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        self._validate_limit(limit)
        self._validate_offset(offset)

        def operation(session: Session) -> Sequence[ModelT]:
            return self._repository(session).list(organization_id=organization_id, limit=limit, offset=offset)

        return self._run_in_transaction("list", operation)

    def count(self) -> int:
        def operation(session: Session) -> int:
            return self._repository(session).count()

        return self._run_in_transaction("count", operation)

    def update(self, entity_id: str, **values: Any) -> ModelT:
        self._validate_identifier(entity_id, field_name="entity_id")
        self._validate_update_values(values)

        def operation(session: Session) -> ModelT:
            repository = self._repository(session)
            entity = repository.get(entity_id)
            if entity is None:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": entity_id,
                    }
                )
            for field, value in values.items():
                setattr(entity, field, value)
            session.flush()
            return entity

        return self._run_in_transaction("update", operation)

    def delete(self, entity_id: str) -> None:
        self._validate_identifier(entity_id, field_name="entity_id")

        def operation(session: Session) -> None:
            repository = self._repository(session)
            entity = repository.get(entity_id)
            if entity is None:
                raise EntityNotFoundError(
                    details={
                        "service": self.__class__.__name__,
                        "model": self.model.__name__,
                        "entity_id": entity_id,
                    }
                )
            repository.delete(entity)
            session.flush()

        self._run_in_transaction("delete", operation)

    def _repository(self, session: Session) -> RepositoryT:
        return self.repository(session)

    def _before_create(self, repository: RepositoryT, values: dict[str, Any]) -> None:
        return None

    def _run_in_transaction(
        self,
        operation_name: str,
        operation: Callable[[Session], ResultT],
    ) -> ResultT:
        try:
            with database_session.session_scope() as session:
                self.logger.debug(
                    "Starting service operation",
                    extra={"service": self.__class__.__name__, "operation": operation_name},
                )
                result = operation(session)
                self.logger.debug(
                    "Completed service operation",
                    extra={"service": self.__class__.__name__, "operation": operation_name},
                )
                return result
        except IrtiqaError:
            raise
        except IntegrityError as exc:
            error = EntityConflictError(
                "Database integrity constraint failed during service operation.",
                details={"service": self.__class__.__name__, "operation": operation_name},
                cause=exc,
            )
            error.log(self.logger, include_traceback=True)
            raise error from exc
        except SQLAlchemyError as exc:
            error = ServiceError(
                "Database operation failed during service execution.",
                details={"service": self.__class__.__name__, "operation": operation_name},
                cause=exc,
            )
            error.log(self.logger, include_traceback=True)
            raise error from exc
        except Exception as exc:
            error = ServiceError(
                "Unexpected service operation failure.",
                details={"service": self.__class__.__name__, "operation": operation_name},
                cause=exc,
            )
            error.log(self.logger, include_traceback=True)
            raise error from exc

    def _validate_create_values(self, values: dict[str, Any]) -> None:
        if not values:
            raise ValidationError(
                "Create operations require at least one field.",
                details={"service": self.__class__.__name__, "model": self.model.__name__},
            )

    def _validate_update_values(self, values: dict[str, Any]) -> None:
        if not values:
            raise ValidationError(
                "Update operations require at least one field.",
                details={"service": self.__class__.__name__, "model": self.model.__name__},
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
