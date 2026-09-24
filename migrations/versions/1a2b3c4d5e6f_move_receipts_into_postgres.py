"""move receipt storage from blob metadata to PostgreSQL bytea

Revision ID: 1a2b3c4d5e6f
Revises: 0f1a2b3c4d5e
"""
from alembic import op
import sqlalchemy as sa

revision = "1a2b3c4d5e6f"
down_revision = "0f1a2b3c4d5e"
branch_labels = None
depends_on = None


def upgrade():
    # Keep the old receipt_path column temporarily for compatibility with
    # databases that already ran the previous Blob migration. It is no longer
    # used by the application.
    op.add_column("expenses", sa.Column("receipt_image", sa.LargeBinary(), nullable=True))


def downgrade():
    op.drop_column("expenses", "receipt_image")
