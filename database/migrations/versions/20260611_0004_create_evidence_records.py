"""create evidence_records table

Revision ID: 20260611_0004
Revises: 20260609_0003
Create Date: 2026-06-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260611_0004"
down_revision = "20260609_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evidence_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("source_detail", sa.Text(), nullable=True),
        sa.Column("source_location_type", sa.String(50), nullable=True),
        sa.Column("source_location_value", sa.String(500), nullable=True),
        sa.Column("evidence_type", sa.String(150), nullable=False),
        sa.Column("evidence_value", sa.Text(), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=True),
        sa.Column("relationship_type", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "agent_run_id",
            sa.String(36),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("company_id", sa.String(36), nullable=True),
        sa.Column("contact_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index(
        "ix_evidence_target",
        "evidence_records",
        ["target_type", "target_id"],
    )
    op.create_index(
        "ix_evidence_source",
        "evidence_records",
        ["source_type", "source_id"],
    )
    op.create_index(
        "ix_evidence_type",
        "evidence_records",
        ["evidence_type"],
    )
    op.create_index(
        "ix_evidence_relationship",
        "evidence_records",
        ["relationship_type"],
    )
    op.create_index(
        "ix_evidence_agent_run",
        "evidence_records",
        ["agent_run_id"],
    )
    op.create_index(
        "ix_evidence_company",
        "evidence_records",
        ["company_id"],
    )
    op.create_index(
        "ix_evidence_contact",
        "evidence_records",
        ["contact_id"],
    )
    op.create_index(
        "ix_evidence_hash",
        "evidence_records",
        ["evidence_hash"],
    )
    op.create_index(
        "ix_evidence_target_type",
        "evidence_records",
        ["target_type"],
    )
    op.create_index(
        "ix_evidence_created_at",
        "evidence_records",
        ["created_at"],
    )
    op.create_index(
        "ix_evidence_source_location",
        "evidence_records",
        ["source_location_type", "source_location_value"],
    )

    # Check constraints via batch alter for SQLite compatibility
    with op.batch_alter_table("evidence_records") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_evidence_records_evidence_type"),
            "evidence_type IN ("
            "'html_snippet', 'text_excerpt', 'url_match', "
            "'signature_match', 'computed_metric', 'agent_summary'"
            ")",
        )
        batch_op.create_check_constraint(
            op.f("ck_evidence_records_relationship_type"),
            "relationship_type IN ("
            "'supports', 'contradicts', 'contributes_to', 'generates'"
            ")",
        )
        batch_op.create_check_constraint(
            op.f("ck_evidence_records_confidence"),
            "confidence >= 0.0 AND confidence <= 1.0",
        )


def downgrade() -> None:
    with op.batch_alter_table("evidence_records") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_evidence_records_confidence"), type_="check"
        )
        batch_op.drop_constraint(
            op.f("ck_evidence_records_relationship_type"), type_="check"
        )
        batch_op.drop_constraint(
            op.f("ck_evidence_records_evidence_type"), type_="check"
        )

    op.drop_index("ix_evidence_source_location", table_name="evidence_records")
    op.drop_index("ix_evidence_created_at", table_name="evidence_records")
    op.drop_index("ix_evidence_target_type", table_name="evidence_records")
    op.drop_index("ix_evidence_hash", table_name="evidence_records")
    op.drop_index("ix_evidence_contact", table_name="evidence_records")
    op.drop_index("ix_evidence_company", table_name="evidence_records")
    op.drop_index("ix_evidence_agent_run", table_name="evidence_records")
    op.drop_index("ix_evidence_relationship", table_name="evidence_records")
    op.drop_index("ix_evidence_type", table_name="evidence_records")
    op.drop_index("ix_evidence_source", table_name="evidence_records")
    op.drop_index("ix_evidence_target", table_name="evidence_records")

    op.drop_table("evidence_records")
