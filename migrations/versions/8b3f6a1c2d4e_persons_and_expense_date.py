"""Replace quantity with persons and add expense_date

Revision ID: 8b3f6a1c2d4e
Revises: cf4d2189872e
Create Date: 2026-08-29 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b3f6a1c2d4e'
down_revision = 'cf4d2189872e'
branch_labels = None
depends_on = None


def upgrade():
    # Add the new columns, nullable at first so existing rows aren't rejected
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('persons', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('expense_date', sa.Date(), nullable=True))

    # Backfill: persons from the old quantity value (rounded to a whole number,
    # minimum of 1), expense_date from when the expense was created
    op.execute(
        "UPDATE expenses "
        "SET persons = GREATEST(ROUND(quantity)::integer, 1), "
        "expense_date = created_at::date"
    )

    # Now that every row has a value, enforce NOT NULL and drop the old column
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.alter_column('persons', nullable=False)
        batch_op.alter_column('expense_date', nullable=False)
        batch_op.drop_column('quantity')


def downgrade():
    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quantity', sa.Numeric(precision=10, scale=2), nullable=True))

    op.execute("UPDATE expenses SET quantity = persons")

    with op.batch_alter_table('expenses', schema=None) as batch_op:
        batch_op.alter_column('quantity', nullable=False)
        batch_op.drop_column('expense_date')
        batch_op.drop_column('persons')
