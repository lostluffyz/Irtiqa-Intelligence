from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.workflows.context import WorkflowContext
from app.workflows.result import WorkflowResult


class Workflow(ABC):
    name: str

    def __init__(self, **services: Any) -> None:
        self.services = dict(services)

    @abstractmethod
    async def execute(self, context: WorkflowContext) -> WorkflowResult:
        raise NotImplementedError
