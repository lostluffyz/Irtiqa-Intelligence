"""create organizations and memberships tables

Revision ID: 20260613_0006
Revises: 20260612_0005
Create Date: 2026-06-13
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260613_0006"
down_revision = "20260612_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organizations ────────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
    op.create_index("ix_organizations_status", "organizations", ["status"])

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_organizations_status"),
            "status IN ('active', 'suspended', 'cancelled')",
        )

    # ── memberships ─────────────────────────────────────────────────────────
    op.create_table(
        "memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(50), nullable=False, server_default=sa.text("'member'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_memberships_user_org",
        "memberships",
        ["user_id", "organization_id"],
        unique=True,
    )
    op.create_index(
        "ix_memberships_organization_id",
        "memberships",
        ["organization_id"],
    )
    op.create_index(
        "ix_memberships_user_id",
        "memberships",
        ["user_id"],
    )

    with op.batch_alter_table("memberships") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_memberships_role"),
            "role IN ('owner', 'admin', 'member', 'viewer')",
        )


def downgrade() -> None:
    with op.batch_alter_table("memberships") as batch_op:
        batch_op.drop_constraint(op.f("ck_memberships_role"), type_="check")

    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_organization_id", table_name="memberships")
    op.drop_index("ix_memberships_user_org", table_name="memberships")
    op.drop_table("memberships")

    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_constraint(op.f("ck_organizations_status"), type_="check")

    op.drop_index("ix_organizations_status", table_name="organizations")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
