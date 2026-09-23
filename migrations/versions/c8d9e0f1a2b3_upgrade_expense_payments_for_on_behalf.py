"""Upgrade expense payments for payer/on-behalf settlement

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
"""
from alembic import op
import sqlalchemy as sa

revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("expense_payments")}

    # The original settlement migration called these traveler_id,
    # payment_method and paid_at. The current model uses clearer names.
    if "traveler_id" in columns and "paid_by_id" not in columns:
        op.alter_column(
            "expense_payments",
            "traveler_id",
            new_column_name="paid_by_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        columns.remove("traveler_id")
        columns.add("paid_by_id")

    if "payment_method" in columns and "method" not in columns:
        op.alter_column(
            "expense_payments",
            "payment_method",
            new_column_name="method",
            existing_type=sa.String(length=30),
            existing_nullable=False,
        )
        columns.remove("payment_method")
        columns.add("method")

    if "paid_at" in columns and "created_at" not in columns:
        op.alter_column(
            "expense_payments",
            "paid_at",
            new_column_name="created_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
        columns.remove("paid_at")
        columns.add("created_at")

    if "on_behalf_of_id" not in columns:
        op.add_column(
            "expense_payments",
            sa.Column("on_behalf_of_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_expense_payments_on_behalf_of_id",
            "expense_payments",
            "travelers",
            ["on_behalf_of_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(
            op.f("ix_expense_payments_on_behalf_of_id"),
            "expense_payments",
            ["on_behalf_of_id"],
            unique=False,
        )

    # Recreate the payer index under the current column name if needed.
    indexes = {idx["name"] for idx in inspector.get_indexes("expense_payments")}
    if "ix_expense_payments_paid_by_id" not in indexes:
        op.create_index(
            op.f("ix_expense_payments_paid_by_id"),
            "expense_payments",
            ["paid_by_id"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("expense_payments")}
    indexes = {idx["name"] for idx in inspector.get_indexes("expense_payments")}

    if "ix_expense_payments_on_behalf_of_id" in indexes:
        op.drop_index(op.f("ix_expense_payments_on_behalf_of_id"), table_name="expense_payments")
    if "on_behalf_of_id" in columns:
        op.drop_constraint(
            "fk_expense_payments_on_behalf_of_id",
            "expense_payments",
            type_="foreignkey",
        )
        op.drop_column("expense_payments", "on_behalf_of_id")

    if "ix_expense_payments_paid_by_id" in indexes:
        op.drop_index(op.f("ix_expense_payments_paid_by_id"), table_name="expense_payments")
    if "paid_by_id" in columns:
        op.alter_column(
            "expense_payments",
            "paid_by_id",
            new_column_name="traveler_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )

    if "method" in columns:
        op.alter_column(
            "expense_payments",
            "method",
            new_column_name="payment_method",
            existing_type=sa.String(length=30),
            existing_nullable=False,
        )
    if "created_at" in columns:
        op.alter_column(
            "expense_payments",
            "created_at",
            new_column_name="paid_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
        )
    op.create_index(
        op.f("ix_expense_payments_traveler_id"),
        "expense_payments",
        ["traveler_id"],
        unique=False,
    )
