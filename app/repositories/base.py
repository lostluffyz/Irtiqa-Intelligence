from __future__ import annotations

from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.logging import get_repository_logger
from app.models.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session
        self.logger = get_repository_logger(self.__class__.__name__)

    def add(self, entity: ModelT) -> ModelT:
        self.logger.debug("Adding entity", extra={"model": self.model.__name__})
        self.session.add(entity)
        return entity

    def get(self, entity_id: str) -> ModelT | None:
        self.logger.debug(
            "Fetching entity by id",
            extra={"model": self.model.__name__, "entity_id": entity_id},
        )
        return self.session.get(self.model, entity_id)

    def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        self.logger.debug(
            "Listing entities",
            extra={"model": self.model.__name__, "limit": limit, "offset": offset},
        )
        statement = select(self.model).offset(offset).limit(limit)
        return self.session.scalars(statement).all()

    def count(self) -> int:
        self.logger.debug("Counting entities", extra={"model": self.model.__name__})
        statement = select(func.count()).select_from(self.model)
        return self.session.scalar(statement) or 0

    def delete(self, entity: ModelT) -> None:
        self.logger.debug("Deleting entity", extra={"model": self.model.__name__})
        self.session.delete(entity)

    def exists(self, entity_id: str) -> bool:
        return self.get(entity_id) is not None

    def scalar_one_or_none(self, statement: Select[tuple[ModelT]]) -> ModelT | None:
        return self.session.scalars(statement).one_or_none()

    def scalars(self, statement: Select[tuple[ModelT]]) -> Sequence[ModelT]:
        return self.session.scalars(statement).all()
