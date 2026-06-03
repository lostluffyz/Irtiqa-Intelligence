"""add raw_html and extracted_text to websites

Revision ID: 20260603_0003
Revises: 20260531_0002
Create Date: 2026-06-03
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260603_0003"
down_revision = "20260531_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("websites", sa.Column("raw_html", sa.Text(), nullable=True))
    op.add_column("websites", sa.Column("extracted_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("websites", "extracted_text")
    op.drop_column("websites", "raw_html")
