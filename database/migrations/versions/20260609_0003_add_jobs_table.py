"""add jobs table

Revision ID: 20260609_0003
Revises: 20260603_0003
Create Date: 2026-06-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260609_0003"
down_revision = "20260603_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_type", sa.String(16), nullable=False),
        sa.Column("target_name", sa.String(128), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("max_retries", sa.Integer(), nullable=False, default=3),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "agent_run_id",
            sa.String(36),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index(
        "ix_jobs_status_scheduled_at",
        "jobs",
        ["status", "scheduled_at"],
    )
    op.create_index(
        "ix_jobs_target_name",
        "jobs",
        ["target_name"],
    )
    op.create_index(
        "ix_jobs_agent_run_id",
        "jobs",
        ["agent_run_id"],
    )

    # Check constraints need batch mode for SQLite
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.create_check_constraint(
            "ck_jobs_status",
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
        )
        batch_op.create_check_constraint(
            "ck_jobs_job_type",
            "job_type IN ('agent', 'workflow')",
        )
        batch_op.create_check_constraint(
            "ck_jobs_retry_count",
            "retry_count <= max_retries",
        )
        batch_op.create_check_constraint(
            "ck_jobs_max_retries",
            "max_retries >= 0",
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("ck_jobs_max_retries", type_="check")
        batch_op.drop_constraint("ck_jobs_retry_count", type_="check")
        batch_op.drop_constraint("ck_jobs_job_type", type_="check")
        batch_op.drop_constraint("ck_jobs_status", type_="check")

    op.drop_index("ix_jobs_agent_run_id", table_name="jobs")
    op.drop_index("ix_jobs_target_name", table_name="jobs")
    op.drop_index("ix_jobs_status_scheduled_at", table_name="jobs")

    op.drop_table("jobs")