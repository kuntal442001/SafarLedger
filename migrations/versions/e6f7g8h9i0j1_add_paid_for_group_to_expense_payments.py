"""Allow an expense payment to be explicitly made for a traveler group

Revision ID: e6f7g8h9i0j1
Revises: d4e5f6a7b8c9
"""
from alembic import op
import sqlalchemy as sa

revision = "e6f7g8h9i0j1"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "expense_payments",
        sa.Column("paid_for_group_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_expense_payments_paid_for_group_id",
        "expense_payments",
        ["paid_for_group_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_expense_payments_paid_for_group_id_traveler_groups",
        "expense_payments",
        "traveler_groups",
        ["paid_for_group_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_expense_payments_paid_for_group_id_traveler_groups",
        "expense_payments",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_expense_payments_paid_for_group_id",
        table_name="expense_payments",
    )
    op.drop_column("expense_payments", "paid_for_group_id")
