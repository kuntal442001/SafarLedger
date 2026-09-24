"""Add private receipt storage fields to expenses.

Revision ID: 0f1a2b3c4d5e
Revises: f1a2b3c4d5e6, 9a7b6c5d4e3f
"""
from alembic import op
import sqlalchemy as sa

revision = "0f1a2b3c4d5e"
down_revision = ("f1a2b3c4d5e6", "9a7b6c5d4e3f")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("expenses", sa.Column("receipt_path", sa.String(length=500), nullable=True))
    op.add_column("expenses", sa.Column("receipt_filename", sa.String(length=255), nullable=True))
    op.add_column("expenses", sa.Column("receipt_content_type", sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column("expenses", "receipt_content_type")
    op.drop_column("expenses", "receipt_filename")
    op.drop_column("expenses", "receipt_path")
