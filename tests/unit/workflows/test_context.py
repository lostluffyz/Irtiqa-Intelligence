from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.workflows.context import WorkflowContext


def test_workflow_context_requires_company_or_contact() -> None:
    with pytest.raises(PydanticValidationError):
        WorkflowContext(workflow_name="score_refresh")


def test_workflow_context_rejects_blank_workflow_name() -> None:
    with pytest.raises(PydanticValidationError):
        WorkflowContext(workflow_name="", company_id="00000000-0000-0000-0000-000000000000")


def test_workflow_context_freezes_options_copy() -> None:
    options = {"force": True}
    context = WorkflowContext(
        workflow_name="score_refresh",
        company_id="00000000-0000-0000-0000-000000000000",
        options=options,
    )

    options["force"] = False

    assert context.options["force"] is True
    with pytest.raises(TypeError):
        context.options["force"] = False


def test_workflow_context_rejects_non_mapping_options() -> None:
    with pytest.raises(PydanticValidationError):
        WorkflowContext(
            workflow_name="score_refresh",
            company_id="00000000-0000-0000-0000-000000000000",
            options=["invalid"],
        )
