"""Add discovery engine tables and company extensions.

Lead Discovery Engine Phase 1: Database foundation for ICP-based
company discovery. Creates discovery_searches and discovery_runs
tables, and extends companies with discovery provenance columns.

Revision ID: 20260618_0008
Revises: 20260616_0007
Create Date: 2026-06-18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260618_0008"
down_revision = "20260616_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── discovery_searches ────────────────────────────────────────────────
    op.create_table(
        "discovery_searches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("criteria", sa.Text, nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column(
            "total_discovered",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_discovery_searches_organization_id",
        "discovery_searches",
        ["organization_id"],
    )

    with op.batch_alter_table("discovery_searches") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_discovery_searches_status"),
            "status IN ('active', 'archived')",
        )

    # ── discovery_runs ────────────────────────────────────────────────────
    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "search_id",
            sa.String(36),
            sa.ForeignKey("discovery_searches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column(
            "sources_queried",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "companies_found",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "companies_created",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "companies_skipped",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_discovery_runs_organization_id",
        "discovery_runs",
        ["organization_id"],
    )
    op.create_index(
        "ix_discovery_runs_search_id",
        "discovery_runs",
        ["search_id"],
    )
    op.create_index(
        "ix_discovery_runs_status",
        "discovery_runs",
        ["status"],
    )

    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_discovery_runs_status"),
            "status IN ('running', 'succeeded', 'failed')",
        )

    # ── companies: add discovery provenance columns ───────────────────────
    with op.batch_alter_table("companies") as batch_op:
        batch_op.add_column(
            sa.Column("discovered_via", sa.String(100))
        )
        batch_op.add_column(
            sa.Column(
                "discovery_search_id",
                sa.String(36),
                sa.ForeignKey("discovery_searches.id", ondelete="SET NULL"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "discovery_score",
                sa.Float,
                nullable=False,
                server_default=sa.text("0.0"),
            )
        )

    with op.batch_alter_table("companies") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_companies_discovery_score"),
            "discovery_score >= 0.0 AND discovery_score <= 1.0",
        )


def downgrade() -> None:
    # ── companies: remove discovery provenance columns ────────────────────
    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_companies_discovery_score"), type_="check"
        )
        batch_op.drop_column("discovery_score")
        batch_op.drop_column("discovery_search_id")
        batch_op.drop_column("discovered_via")

    # ── discovery_runs ────────────────────────────────────────────────────
    with op.batch_alter_table("discovery_runs") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_discovery_runs_status"), type_="check"
        )

    op.drop_index("ix_discovery_runs_status", table_name="discovery_runs")
    op.drop_index("ix_discovery_runs_search_id", table_name="discovery_runs")
    op.drop_index("ix_discovery_runs_organization_id", table_name="discovery_runs")
    op.drop_table("discovery_runs")

    # ── discovery_searches ────────────────────────────────────────────────
    with op.batch_alter_table("discovery_searches") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_discovery_searches_status"), type_="check"
        )

    op.drop_index(
        "ix_discovery_searches_organization_id", table_name="discovery_searches"
    )
    op.drop_table("discovery_searches")
