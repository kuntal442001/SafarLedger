"""Switch user authentication from email to phone number.

Revision ID: 9a7b6c5d4e3f
Revises: 2f6a7b8c9d01
"""
from alembic import op
import sqlalchemy as sa


revision = "9a7b6c5d4e3f"
down_revision = "2f6a7b8c9d01"
branch_labels = None
depends_on = None


def upgrade():
    # Keep existing values intact while changing the application-facing
    # credential field from email to phone. Existing email values cannot be
    # safely converted into phone numbers automatically, so they remain as
    # legacy values until the account owner supplies a real phone number.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_email")
        batch_op.alter_column(
            "email",
            new_column_name="phone",
            existing_type=sa.String(length=255),
            existing_nullable=False,
        )
        # Keep enough storage for legacy rows. New application input is
        # restricted to 7-15 digits (+ optional prefix) by the WTForms layer.
        batch_op.create_index("ix_users_phone", ["phone"], unique=True)


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index("ix_users_phone")
        batch_op.alter_column(
            "phone",
            new_column_name="email",
            existing_type=sa.String(length=255),
            existing_nullable=False,
        )
        batch_op.create_index("ix_users_email", ["email"], unique=True)
