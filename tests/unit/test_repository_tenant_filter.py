from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy import select

from app.models.membership import Membership
from app.models.organization import Organization
from app.repositories.base import BaseRepository


def _repo_for_model(model_class: type) -> BaseRepository:
    mock_session = MagicMock()
    repo: BaseRepository = BaseRepository(mock_session)
    repo.model = model_class
    return repo


class TestApplyTenantFilter:
    def test_adds_filter_for_model_with_org_id(self) -> None:
        repo = _repo_for_model(Membership)
        statement = select(Membership)
        filtered = repo._apply_tenant_filter(statement, organization_id="org-123")
        sql = str(filtered)
        # The WHERE clause should contain organization_id = :organization_id
        assert "WHERE" in sql.upper() and "organization_id" in sql[sql.upper().index("WHERE"):]

    def test_skips_filter_when_org_id_is_none(self) -> None:
        repo = _repo_for_model(Membership)
        statement = select(Membership)
        filtered = repo._apply_tenant_filter(statement, organization_id=None)
        sql = str(filtered)
        # The column appears in SELECT; we verify no WHERE clause was added
        assert "WHERE" not in sql.upper()

    def test_skips_filter_for_model_without_org_id(self) -> None:
        repo = _repo_for_model(Organization)
        statement = select(Organization)
        filtered = repo._apply_tenant_filter(statement, organization_id="org-123")
        sql = str(filtered)
        # Organization has no organization_id column
        assert "WHERE" not in sql.upper()


class TestCheckTenantFilter:
    def test_no_warning_when_org_id_provided(self) -> None:
        repo = _repo_for_model(Membership)
        statement = select(Membership)
        repo.logger = MagicMock()
        repo._check_tenant_filter(statement, organization_id="org-123")
        repo.logger.warning.assert_not_called()

    def test_warning_when_org_id_missing_for_scoped_model(self) -> None:
        repo = _repo_for_model(Membership)
        statement = select(Membership)
        repo.logger = MagicMock()
        repo._check_tenant_filter(statement, organization_id=None)
        repo.logger.warning.assert_called_once()
