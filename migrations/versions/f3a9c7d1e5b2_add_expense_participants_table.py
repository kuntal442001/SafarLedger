"""Add expense_participants table

Revision ID: f3a9c7d1e5b2
Revises: 2ba76b9937bf
Create Date: 2026-09-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a9c7d1e5b2'
down_revision = '3c4d5e6f7a8b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'expense_participants',
        sa.Column('expense_id', sa.Integer(), nullable=False),
        sa.Column('traveler_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['expense_id'], ['expenses.id_Exp'], ),
        sa.ForeignKeyConstraint(['traveler_id'], ['travelers.id'], ),
        sa.PrimaryKeyConstraint('expense_id', 'traveler_id')
    )


def downgrade():
    op.drop_table('expense_participants')
