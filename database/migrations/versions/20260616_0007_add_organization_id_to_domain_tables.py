"""Add organization_id to all business entity tables.

Phase 3: Tenant isolation for business entities. Every domain table
gains an organization_id FK column for direct tenant scoping.

Revision ID: 20260616_0007
Revises: 20260613_0006
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260616_0007"
down_revision = "20260613_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Company ──────────────────────────────────────────────────────────
    with op.batch_alter_table("companies") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(36), nullable=False))
        batch_op.create_foreign_key("fk_companies_org", "organizations", ["organization_id"], ["id"])
        batch_op.drop_index("ix_companies_domain")
        batch_op.create_index("ix_companies_organization_id", ["organization_id"])
        batch_op.create_index("uq_companies_org_domain", ["organization_id", "domain"], unique=True)

    # ── Contact ──────────────────────────────────────────────────────────
    with op.batch_alter_table("contacts") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(36), nullable=False))
        batch_op.create_foreign_key("fk_contacts_org", "organizations", ["organization_id"], ["id"])
        batch_op.drop_index("ix_contacts_email")
        batch_op.create_index("ix_contacts_organization_id", ["organization_id"])
        batch_op.create_index("uq_contacts_org_email", ["organization_id", "email"], unique=True)

    # ── IntentSignal ─────────────────────────────────────────────────────
    with op.batch_alter_table("intent_signals") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(36), nullable=False))
        batch_op.create_foreign_key("fk_intent_signals_org", "organizations", ["organization_id"], ["id"])
        batch_op.drop_index("ix_intent_signals_company_id")
        batch_op.drop_index("ix_intent_signals_company_type_observed")
        batch_op.create_index("ix_intent_signals_organization_id", ["organization_id"])
        batch_op.create_index(
            "ix_intent_signals_org_company_type_observed",
            ["organization_id", "company_id", "signal_type", "observed_at"],
        )

    # ── OutreachMessage ──────────────────────────────────────────────────
    with op.batch_alter_table("outreach_messages") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(36), nullable=False))
        batch_op.create_foreign_key("fk_outreach_messages_org", "organizations", ["organization_id"], ["id"])
        batch_op.create_index("ix_outreach_messages_organization_id", ["organization_id"])
        batch_op.create_index("ix_outreach_messages_org_company", ["organization_id", "company_id"])

    # ── EvidenceRecord ───────────────────────────────────────────────────
    with op.batch_alter_table("evidence_records") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(36), nullable=False))
        batch_op.create_foreign_key("fk_evidence_records_org", "organizations", ["organization_id"], ["id"])
        batch_op.create_index("ix_evidence_organization_id", ["organization_id"])
        batch_op.create_index("ix_evidence_org_target", ["organization_id", "target_type", "target_id"])
        batch_op.create_index("ix_evidence_org_source", ["organization_id", "source_type", "source_id"])

    # ── AgentRun ─────────────────────────────────────────────────────────
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(36), nullable=False))
        batch_op.create_foreign_key("fk_agent_runs_org", "organizations", ["organization_id"], ["id"])
        batch_op.create_index("ix_agent_runs_organization_id", ["organization_id"])
        batch_op.create_index("ix_agent_runs_org_agent_status", ["organization_id", "agent_name", "status"])

    # ── IntelligenceScore ────────────────────────────────────────────────
    with op.batch_alter_table("intelligence_scores") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(36), nullable=False))
        batch_op.create_foreign_key("fk_intelligence_scores_org", "organizations", ["organization_id"], ["id"])
        batch_op.drop_index("ix_intelligence_scores_company_total")
        batch_op.create_index("ix_intelligence_scores_organization_id", ["organization_id"])
        batch_op.create_index(
            "ix_intelligence_scores_org_company_total",
            ["organization_id", "company_id", "total_score"],
        )

    # ── Job ──────────────────────────────────────────────────────────────
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("organization_id", sa.String(36), nullable=True))
        batch_op.create_foreign_key("fk_jobs_org", "organizations", ["organization_id"], ["id"])
        batch_op.create_index("ix_jobs_organization_id", ["organization_id"])


def downgrade() -> None:
    # Reverse order to avoid FK constraint issues
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_organization_id")
        batch_op.drop_constraint("fk_jobs_org", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("intelligence_scores") as batch_op:
        batch_op.drop_index("ix_intelligence_scores_organization_id")
        batch_op.drop_index("ix_intelligence_scores_org_company_total")
        batch_op.create_index("ix_intelligence_scores_company_total", ["company_id", "total_score"])
        batch_op.drop_constraint("fk_intelligence_scores_org", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_index("ix_agent_runs_organization_id")
        batch_op.drop_index("ix_agent_runs_org_agent_status")
        batch_op.drop_constraint("fk_agent_runs_org", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("evidence_records") as batch_op:
        batch_op.drop_index("ix_evidence_organization_id")
        batch_op.drop_index("ix_evidence_org_target")
        batch_op.drop_index("ix_evidence_org_source")
        batch_op.drop_constraint("fk_evidence_records_org", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("outreach_messages") as batch_op:
        batch_op.drop_index("ix_outreach_messages_organization_id")
        batch_op.drop_index("ix_outreach_messages_org_company")
        batch_op.drop_constraint("fk_outreach_messages_org", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("intent_signals") as batch_op:
        batch_op.drop_index("ix_intent_signals_organization_id")
        batch_op.drop_index("ix_intent_signals_org_company_type_observed")
        batch_op.create_index("ix_intent_signals_company_type_observed", ["company_id", "signal_type", "observed_at"])
        batch_op.create_index("ix_intent_signals_company_id", ["company_id"])
        batch_op.drop_constraint("fk_intent_signals_org", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("contacts") as batch_op:
        batch_op.drop_index("ix_contacts_organization_id")
        batch_op.drop_index("uq_contacts_org_email")
        batch_op.create_index("ix_contacts_email", ["email"], unique=True)
        batch_op.drop_constraint("fk_contacts_org", type_="foreignkey")
        batch_op.drop_column("organization_id")

    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_index("ix_companies_organization_id")
        batch_op.drop_index("uq_companies_org_domain")
        batch_op.create_index("ix_companies_domain", ["domain"], unique=True)
        batch_op.drop_constraint("fk_companies_org", type_="foreignkey")
        batch_op.drop_column("organization_id")
