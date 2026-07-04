from __future__ import annotations

from typing import Any

from app.core.errors import IrtiqaError, WorkflowError
from app.core.logging import get_logger
from app.workflows.context import WorkflowContext
from app.workflows.registry import WorkflowRegistry
from app.workflows.result import WorkflowResult
from app.workflows.states import WorkflowStatus


class WorkflowRunner:
    def __init__(self, registry: WorkflowRegistry, **services: Any) -> None:
        self.registry = registry
        self.services = dict(services)
        self.logger = get_logger("workflows.runner")

    async def run(self, context: WorkflowContext) -> WorkflowResult:
        self.logger.info(
            "Starting workflow",
            extra={
                "workflow_name": context.workflow_name,
                "company_id": context.company_id,
                "contact_id": context.contact_id,
                "correlation_id": context.correlation_id,
            },
        )
        result = WorkflowResult(
            workflow_name=context.workflow_name,
            status=WorkflowStatus.RUNNING,
            company_id=context.company_id,
            contact_id=context.contact_id,
        )
        try:
            workflow_type = self.registry.get(context.workflow_name)
            workflow = workflow_type(**self.services)
            completed = await workflow.execute(context)
            self.logger.info(
                "Completed workflow",
                extra={
                    "workflow_name": context.workflow_name,
                    "workflow_status": completed.status.value,
                },
            )
            return completed
        except IrtiqaError as exc:
            exc.log(self.logger)
            return result.finish(WorkflowStatus.FAILED, error=exc.to_dict())
        except Exception as exc:
            error = WorkflowError(
                "Unexpected workflow execution failure.",
                details={"workflow_name": context.workflow_name},
                cause=exc,
            )
            error.log(self.logger, include_traceback=True)
            return result.finish(WorkflowStatus.FAILED, error=error.to_dict())
