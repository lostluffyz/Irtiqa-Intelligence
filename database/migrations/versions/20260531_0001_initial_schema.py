"""initial schema

Revision ID: 20260531_0001
Revises: None
Create Date: 2026-05-31 12:45:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260531_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("industry", sa.String(length=150), nullable=True),
        sa.Column("company_size", sa.String(length=100), nullable=True),
        sa.Column("headquarters", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_companies")),
    )
    op.create_index("ix_companies_created_at", "companies", ["created_at"], unique=False)
    op.create_index("ix_companies_domain", "companies", ["domain"], unique=True)
    op.create_index("ix_companies_industry", "companies", ["industry"], unique=False)
    op.create_index("ix_companies_name", "companies", ["name"], unique=False)
    op.create_index("ix_companies_status", "companies", ["status"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("first_name", sa.String(length=150), nullable=True),
        sa.Column("last_name", sa.String(length=150), nullable=True),
        sa.Column("full_name", sa.String(length=300), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("seniority", sa.String(length=100), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_contacts_company_id_companies"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"], unique=False)
    op.create_index("ix_contacts_department", "contacts", ["department"], unique=False)
    op.create_index("ix_contacts_email", "contacts", ["email"], unique=True)
    op.create_index("ix_contacts_linkedin_url", "contacts", ["linkedin_url"], unique=False)
    op.create_index("ix_contacts_seniority", "contacts", ["seniority"], unique=False)
    op.create_index("ix_contacts_status", "contacts", ["status"], unique=False)

    op.create_table(
        "websites",
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("normalized_url", sa.String(length=1000), nullable=False),
        sa.Column("page_type", sa.String(length=100), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_websites_company_id_companies"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_websites")),
    )
    op.create_index("ix_websites_company_id", "websites", ["company_id"], unique=False)
    op.create_index("ix_websites_http_status", "websites", ["http_status"], unique=False)
    op.create_index("ix_websites_last_scraped_at", "websites", ["last_scraped_at"], unique=False)
    op.create_index("ix_websites_normalized_url", "websites", ["normalized_url"], unique=True)
    op.create_index("ix_websites_page_type", "websites", ["page_type"], unique=False)

    op.create_table(
        "agent_runs",
        sa.Column("company_id", sa.String(length=36), nullable=True),
        sa.Column("contact_id", sa.String(length=36), nullable=True),
        sa.Column("agent_name", sa.String(length=150), nullable=False),
        sa.Column("workflow_name", sa.String(length=150), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_agent_runs_company_id_companies"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_agent_runs_contact_id_contacts"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index("ix_agent_runs_agent_name", "agent_runs", ["agent_name"], unique=False)
    op.create_index("ix_agent_runs_agent_name_status", "agent_runs", ["agent_name", "status"], unique=False)
    op.create_index("ix_agent_runs_company_id", "agent_runs", ["company_id"], unique=False)
    op.create_index("ix_agent_runs_contact_id", "agent_runs", ["contact_id"], unique=False)
    op.create_index("ix_agent_runs_finished_at", "agent_runs", ["finished_at"], unique=False)
    op.create_index("ix_agent_runs_started_at", "agent_runs", ["started_at"], unique=False)
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)
    op.create_index("ix_agent_runs_workflow_name", "agent_runs", ["workflow_name"], unique=False)
    op.create_index("ix_agent_runs_workflow_name_status", "agent_runs", ["workflow_name", "status"], unique=False)

    op.create_table(
        "technologies",
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("website_id", sa.String(length=36), nullable=True),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=150), nullable=False),
        sa.Column("vendor", sa.String(length=255), nullable=True),
        sa.Column("detection_method", sa.String(length=150), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], name=op.f("fk_technologies_agent_run_id_agent_runs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_technologies_company_id_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], name=op.f("fk_technologies_website_id_websites"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_technologies")),
    )
    op.create_index("ix_technologies_agent_run_id", "technologies", ["agent_run_id"], unique=False)
    op.create_index("ix_technologies_category", "technologies", ["category"], unique=False)
    op.create_index("ix_technologies_company_id", "technologies", ["company_id"], unique=False)
    op.create_index("ix_technologies_confidence", "technologies", ["confidence"], unique=False)
    op.create_index("ix_technologies_last_detected_at", "technologies", ["last_detected_at"], unique=False)
    op.create_index("ix_technologies_name", "technologies", ["name"], unique=False)
    op.create_index("ix_technologies_website_id", "technologies", ["website_id"], unique=False)
    op.create_index("uq_technologies_company_name_category", "technologies", ["company_id", "name", "category"], unique=True)

    op.create_table(
        "intent_signals",
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("contact_id", sa.String(length=36), nullable=True),
        sa.Column("website_id", sa.String(length=36), nullable=True),
        sa.Column("technology_id", sa.String(length=36), nullable=True),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("signal_type", sa.String(length=150), nullable=False),
        sa.Column("signal_name", sa.String(length=255), nullable=False),
        sa.Column("signal_value", sa.Text(), nullable=True),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], name=op.f("fk_intent_signals_agent_run_id_agent_runs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_intent_signals_company_id_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_intent_signals_contact_id_contacts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["technology_id"], ["technologies.id"], name=op.f("fk_intent_signals_technology_id_technologies"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["website_id"], ["websites.id"], name=op.f("fk_intent_signals_website_id_websites"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intent_signals")),
    )
    op.create_index("ix_intent_signals_agent_run_id", "intent_signals", ["agent_run_id"], unique=False)
    op.create_index("ix_intent_signals_company_id", "intent_signals", ["company_id"], unique=False)
    op.create_index("ix_intent_signals_company_type_observed", "intent_signals", ["company_id", "signal_type", "observed_at"], unique=False)
    op.create_index("ix_intent_signals_confidence", "intent_signals", ["confidence"], unique=False)
    op.create_index("ix_intent_signals_contact_id", "intent_signals", ["contact_id"], unique=False)
    op.create_index("ix_intent_signals_observed_at", "intent_signals", ["observed_at"], unique=False)
    op.create_index("ix_intent_signals_signal_type", "intent_signals", ["signal_type"], unique=False)
    op.create_index("ix_intent_signals_strength", "intent_signals", ["strength"], unique=False)
    op.create_index("ix_intent_signals_technology_id", "intent_signals", ["technology_id"], unique=False)
    op.create_index("ix_intent_signals_website_id", "intent_signals", ["website_id"], unique=False)

    op.create_table(
        "intelligence_scores",
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("contact_id", sa.String(length=36), nullable=True),
        sa.Column("technology_id", sa.String(length=36), nullable=True),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("fit_score", sa.Float(), nullable=False),
        sa.Column("intent_score", sa.Float(), nullable=False),
        sa.Column("technographic_score", sa.Float(), nullable=False),
        sa.Column("engagement_score", sa.Float(), nullable=False),
        sa.Column("total_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("score_version", sa.String(length=100), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], name=op.f("fk_intelligence_scores_agent_run_id_agent_runs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_intelligence_scores_company_id_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_intelligence_scores_contact_id_contacts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["technology_id"], ["technologies.id"], name=op.f("fk_intelligence_scores_technology_id_technologies"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intelligence_scores")),
    )
    op.create_index("ix_intelligence_scores_agent_run_id", "intelligence_scores", ["agent_run_id"], unique=False)
    op.create_index("ix_intelligence_scores_company_id", "intelligence_scores", ["company_id"], unique=False)
    op.create_index("ix_intelligence_scores_company_total", "intelligence_scores", ["company_id", "total_score"], unique=False)
    op.create_index("ix_intelligence_scores_confidence", "intelligence_scores", ["confidence"], unique=False)
    op.create_index("ix_intelligence_scores_contact_id", "intelligence_scores", ["contact_id"], unique=False)
    op.create_index("ix_intelligence_scores_contact_total", "intelligence_scores", ["contact_id", "total_score"], unique=False)
    op.create_index("ix_intelligence_scores_scored_at", "intelligence_scores", ["scored_at"], unique=False)
    op.create_index("ix_intelligence_scores_score_version", "intelligence_scores", ["score_version"], unique=False)
    op.create_index("ix_intelligence_scores_technology_id", "intelligence_scores", ["technology_id"], unique=False)
    op.create_index("ix_intelligence_scores_total_score", "intelligence_scores", ["total_score"], unique=False)

    op.create_table(
        "outreach_messages",
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("contact_id", sa.String(length=36), nullable=True),
        sa.Column("intelligence_score_id", sa.String(length=36), nullable=True),
        sa.Column("agent_run_id", sa.String(length=36), nullable=True),
        sa.Column("channel", sa.String(length=100), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column("personalization_angle", sa.Text(), nullable=False),
        sa.Column("call_to_action", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], name=op.f("fk_outreach_messages_agent_run_id_agent_runs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name=op.f("fk_outreach_messages_company_id_companies"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], name=op.f("fk_outreach_messages_contact_id_contacts"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["intelligence_score_id"], ["intelligence_scores.id"], name=op.f("fk_outreach_messages_intelligence_score_id_intelligence_scores"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outreach_messages")),
    )
    op.create_index("ix_outreach_messages_agent_run_id", "outreach_messages", ["agent_run_id"], unique=False)
    op.create_index("ix_outreach_messages_channel", "outreach_messages", ["channel"], unique=False)
    op.create_index("ix_outreach_messages_company_id", "outreach_messages", ["company_id"], unique=False)
    op.create_index("ix_outreach_messages_confidence", "outreach_messages", ["confidence"], unique=False)
    op.create_index("ix_outreach_messages_contact_id", "outreach_messages", ["contact_id"], unique=False)
    op.create_index("ix_outreach_messages_generated_at", "outreach_messages", ["generated_at"], unique=False)
    op.create_index("ix_outreach_messages_intelligence_score_id", "outreach_messages", ["intelligence_score_id"], unique=False)
    op.create_index("ix_outreach_messages_status", "outreach_messages", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_outreach_messages_status", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_intelligence_score_id", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_generated_at", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_contact_id", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_confidence", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_company_id", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_channel", table_name="outreach_messages")
    op.drop_index("ix_outreach_messages_agent_run_id", table_name="outreach_messages")
    op.drop_table("outreach_messages")

    op.drop_index("ix_intelligence_scores_total_score", table_name="intelligence_scores")
    op.drop_index("ix_intelligence_scores_technology_id", table_name="intelligence_scores")
    op.drop_index("ix_intelligence_scores_score_version", table_name="intelligence_scores")
    op.drop_index("ix_intelligence_scores_scored_at", table_name="intelligence_scores")
    op.drop_index("ix_intelligence_scores_contact_total", table_name="intelligence_scores")
    op.drop_index("ix_intelligence_scores_contact_id", table_name="intelligence_scores")
    op.drop_index("ix_intelligence_scores_confidence", table_name="intelligence_scores")
    op.drop_index("ix_intelligence_scores_company_total", table_name="intelligence_scores")
    op.drop_index("ix_intelligence_scores_company_id", table_name="intelligence_scores")
    op.drop_index("ix_intelligence_scores_agent_run_id", table_name="intelligence_scores")
    op.drop_table("intelligence_scores")

    op.drop_index("ix_intent_signals_website_id", table_name="intent_signals")
    op.drop_index("ix_intent_signals_technology_id", table_name="intent_signals")
    op.drop_index("ix_intent_signals_strength", table_name="intent_signals")
    op.drop_index("ix_intent_signals_signal_type", table_name="intent_signals")
    op.drop_index("ix_intent_signals_observed_at", table_name="intent_signals")
    op.drop_index("ix_intent_signals_contact_id", table_name="intent_signals")
    op.drop_index("ix_intent_signals_confidence", table_name="intent_signals")
    op.drop_index("ix_intent_signals_company_type_observed", table_name="intent_signals")
    op.drop_index("ix_intent_signals_company_id", table_name="intent_signals")
    op.drop_index("ix_intent_signals_agent_run_id", table_name="intent_signals")
    op.drop_table("intent_signals")

    op.drop_index("uq_technologies_company_name_category", table_name="technologies")
    op.drop_index("ix_technologies_website_id", table_name="technologies")
    op.drop_index("ix_technologies_name", table_name="technologies")
    op.drop_index("ix_technologies_last_detected_at", table_name="technologies")
    op.drop_index("ix_technologies_confidence", table_name="technologies")
    op.drop_index("ix_technologies_company_id", table_name="technologies")
    op.drop_index("ix_technologies_category", table_name="technologies")
    op.drop_index("ix_technologies_agent_run_id", table_name="technologies")
    op.drop_table("technologies")

    op.drop_index("ix_agent_runs_workflow_name_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_workflow_name", table_name="agent_runs")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_started_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_finished_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_contact_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_company_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_name_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_agent_name", table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index("ix_websites_page_type", table_name="websites")
    op.drop_index("ix_websites_normalized_url", table_name="websites")
    op.drop_index("ix_websites_last_scraped_at", table_name="websites")
    op.drop_index("ix_websites_http_status", table_name="websites")
    op.drop_index("ix_websites_company_id", table_name="websites")
    op.drop_table("websites")

    op.drop_index("ix_contacts_status", table_name="contacts")
    op.drop_index("ix_contacts_seniority", table_name="contacts")
    op.drop_index("ix_contacts_linkedin_url", table_name="contacts")
    op.drop_index("ix_contacts_email", table_name="contacts")
    op.drop_index("ix_contacts_department", table_name="contacts")
    op.drop_index("ix_contacts_company_id", table_name="contacts")
    op.drop_table("contacts")

    op.drop_index("ix_companies_status", table_name="companies")
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_index("ix_companies_industry", table_name="companies")
    op.drop_index("ix_companies_domain", table_name="companies")
    op.drop_index("ix_companies_created_at", table_name="companies")
    op.drop_table("companies")
