"""database hardening constraints

Revision ID: 20260531_0002
Revises: 20260531_0001
Create Date: 2026-05-31 20:45:00.000000
"""

from __future__ import annotations

from alembic import op

revision = "20260531_0002"
down_revision = "20260531_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("companies", recreate="auto") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_companies_status_allowed"),
            "status IN ('active', 'needs_review', 'archived')",
        )

    with op.batch_alter_table("contacts", recreate="auto") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_contacts_status_allowed"),
            "status IN ('active', 'unverified', 'qualified', 'disqualified', 'archived')",
        )

    with op.batch_alter_table("agent_runs", recreate="auto") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_agent_runs_status_allowed"),
            "status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled')",
        )

    with op.batch_alter_table("technologies", recreate="auto") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_technologies_confidence_range"),
            "confidence >= 0.0 AND confidence <= 1.0",
        )

    with op.batch_alter_table("intent_signals", recreate="auto") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_intent_signals_strength_range"),
            "strength >= 0.0 AND strength <= 1.0",
        )
        batch_op.create_check_constraint(
            op.f("ck_intent_signals_confidence_range"),
            "confidence >= 0.0 AND confidence <= 1.0",
        )

    with op.batch_alter_table("intelligence_scores", recreate="auto") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_intelligence_scores_fit_score_range"),
            "fit_score >= 0.0 AND fit_score <= 100.0",
        )
        batch_op.create_check_constraint(
            op.f("ck_intelligence_scores_intent_score_range"),
            "intent_score >= 0.0 AND intent_score <= 100.0",
        )
        batch_op.create_check_constraint(
            op.f("ck_intelligence_scores_technographic_score_range"),
            "technographic_score >= 0.0 AND technographic_score <= 100.0",
        )
        batch_op.create_check_constraint(
            op.f("ck_intelligence_scores_engagement_score_range"),
            "engagement_score >= 0.0 AND engagement_score <= 100.0",
        )
        batch_op.create_check_constraint(
            op.f("ck_intelligence_scores_total_score_range"),
            "total_score >= 0.0 AND total_score <= 100.0",
        )
        batch_op.create_check_constraint(
            op.f("ck_intelligence_scores_confidence_range"),
            "confidence >= 0.0 AND confidence <= 1.0",
        )

    with op.batch_alter_table("outreach_messages", recreate="auto") as batch_op:
        batch_op.create_check_constraint(
            op.f("ck_outreach_messages_status_allowed"),
            "status IN ('draft', 'ready_for_review', 'approved', 'sent', 'archived')",
        )
        batch_op.create_check_constraint(
            op.f("ck_outreach_messages_confidence_range"),
            "confidence >= 0.0 AND confidence <= 1.0",
        )


def downgrade() -> None:
    with op.batch_alter_table("outreach_messages", recreate="auto") as batch_op:
        batch_op.drop_constraint(op.f("ck_outreach_messages_confidence_range"), type_="check")
        batch_op.drop_constraint(op.f("ck_outreach_messages_status_allowed"), type_="check")

    with op.batch_alter_table("intelligence_scores", recreate="auto") as batch_op:
        batch_op.drop_constraint(op.f("ck_intelligence_scores_confidence_range"), type_="check")
        batch_op.drop_constraint(op.f("ck_intelligence_scores_total_score_range"), type_="check")
        batch_op.drop_constraint(op.f("ck_intelligence_scores_engagement_score_range"), type_="check")
        batch_op.drop_constraint(op.f("ck_intelligence_scores_technographic_score_range"), type_="check")
        batch_op.drop_constraint(op.f("ck_intelligence_scores_intent_score_range"), type_="check")
        batch_op.drop_constraint(op.f("ck_intelligence_scores_fit_score_range"), type_="check")

    with op.batch_alter_table("intent_signals", recreate="auto") as batch_op:
        batch_op.drop_constraint(op.f("ck_intent_signals_confidence_range"), type_="check")
        batch_op.drop_constraint(op.f("ck_intent_signals_strength_range"), type_="check")

    with op.batch_alter_table("technologies", recreate="auto") as batch_op:
        batch_op.drop_constraint(op.f("ck_technologies_confidence_range"), type_="check")

    with op.batch_alter_table("agent_runs", recreate="auto") as batch_op:
        batch_op.drop_constraint(op.f("ck_agent_runs_status_allowed"), type_="check")

    with op.batch_alter_table("contacts", recreate="auto") as batch_op:
        batch_op.drop_constraint(op.f("ck_contacts_status_allowed"), type_="check")

    with op.batch_alter_table("companies", recreate="auto") as batch_op:
        batch_op.drop_constraint(op.f("ck_companies_status_allowed"), type_="check")
