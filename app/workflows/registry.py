from __future__ import annotations

from app.core.errors import WorkflowError
from app.workflows.base import Workflow


class WorkflowRegistry:
    def __init__(self) -> None:
        self._workflows: dict[str, type[Workflow]] = {}

    def register(self, workflow: type[Workflow]) -> None:
        name = getattr(workflow, "name", None)
        if not name or not isinstance(name, str):
            raise WorkflowError(
                "Workflow class must define a stable name.",
                details={"workflow_class": workflow.__name__},
            )
        if name in self._workflows:
            raise WorkflowError(
                "Workflow is already registered.",
                details={"workflow_name": name},
            )
        self._workflows[name] = workflow

    def get(self, workflow_name: str) -> type[Workflow]:
        workflow = self._workflows.get(workflow_name)
        if workflow is None:
            raise WorkflowError(
                "Workflow is not registered.",
                details={"workflow_name": workflow_name},
            )
        return workflow

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._workflows))
