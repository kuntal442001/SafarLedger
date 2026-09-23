"""Add expense payments for traveler settlement

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "expense_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("traveler_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(length=30), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id_Exp"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["traveler_id"], ["travelers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_expense_payments_expense_id"), "expense_payments", ["expense_id"], unique=False)
    op.create_index(op.f("ix_expense_payments_traveler_id"), "expense_payments", ["traveler_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_expense_payments_traveler_id"), table_name="expense_payments")
    op.drop_index(op.f("ix_expense_payments_expense_id"), table_name="expense_payments")
    op.drop_table("expense_payments")
