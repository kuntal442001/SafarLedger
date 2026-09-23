"""Align expenses primary-key column with the current Expense model.

Revision ID: 3c4d5e6f7a8b
Revises: 2ba76b9937bf
Create Date: 2026-09-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "3c4d5e6f7a8b"
down_revision = "2c3d4e5f6a7b"
branch_labels = None
depends_on = None


def upgrade():
    # The original initial migration created expenses.id, while the
    # current application model and subsequent settlement migrations
    # use expenses.id_Exp. Rename the existing PK instead of creating
    # a second column, preserving all existing expense IDs.
    op.alter_column(
        "expenses",
        "id",
        new_column_name="id_Exp",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "expenses",
        "id_Exp",
        new_column_name="id",
        existing_type=sa.Integer(),
        existing_nullable=False,
    )
