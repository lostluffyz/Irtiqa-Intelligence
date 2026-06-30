from __future__ import annotations

from uuid import uuid4

import pytest

from app.workflows.context import WorkflowContext


def test_workflow_context_requires_company_or_contact_or_organization() -> None:
    """Verify that WorkflowContext requires at least one target identifier."""
    with pytest.raises(ValueError, match="Workflow context requires organization_id, company_id, or contact_id"):
        WorkflowContext(
            workflow_name="test_workflow",
            company_id=None,
            contact_id=None,
            organization_id=None,
        )


def test_workflow_context_accepts_company_id_only() -> None:
    """Verify that WorkflowContext accepts company_id alone."""
    context = WorkflowContext(
        workflow_name="test_workflow",
        company_id=str(uuid4()),
        contact_id=None,
        organization_id=None,
    )
    assert context.company_id is not None
    assert context.contact_id is None
    assert context.organization_id is None


def test_workflow_context_accepts_contact_id_only() -> None:
    """Verify that WorkflowContext accepts contact_id alone."""
    context = WorkflowContext(
        workflow_name="test_workflow",
        company_id=None,
        contact_id=str(uuid4()),
        organization_id=None,
    )
    assert context.company_id is None
    assert context.contact_id is not None
    assert context.organization_id is None


def test_workflow_context_accepts_organization_id_only() -> None:
    """Verify that WorkflowContext accepts organization_id alone (organization-scoped workflows)."""
    org_id = str(uuid4())
    context = WorkflowContext(
        workflow_name="discovery_pipeline",
        company_id=None,
        contact_id=None,
        organization_id=org_id,
    )
    assert context.company_id is None
    assert context.contact_id is None
    assert context.organization_id == org_id


def test_workflow_context_accepts_all_identifiers() -> None:
    """Verify that WorkflowContext accepts all identifiers simultaneously."""
    company_id = str(uuid4())
    contact_id = str(uuid4())
    org_id = str(uuid4())
    context = WorkflowContext(
        workflow_name="test_workflow",
        company_id=company_id,
        contact_id=contact_id,
        organization_id=org_id,
    )
    assert context.company_id == company_id
    assert context.contact_id == contact_id
    assert context.organization_id == org_id


def test_workflow_context_is_immutable() -> None:
    """Verify that WorkflowContext is frozen."""
    context = WorkflowContext(
        workflow_name="test_workflow",
        company_id=str(uuid4()),
    )
    with pytest.raises(Exception):
        context.workflow_name = "modified"


def test_workflow_context_options_are_immutable() -> None:
    """Verify that WorkflowContext options are frozen."""
    context = WorkflowContext(
        workflow_name="test_workflow",
        company_id=str(uuid4()),
        options={"key": "value"},
    )
    with pytest.raises(TypeError):
        context.options["key"] = "modified"
