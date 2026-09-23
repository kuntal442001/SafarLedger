"""Add generic traveler groups and group assignment

Revision ID: d4e5f6a7b8c9
Revises: c8d9e0f1a2b3
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "traveler_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tour_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tour_id"], ["tours.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_traveler_groups_tour_id", "traveler_groups", ["tour_id"], unique=False)
    op.add_column("travelers", sa.Column("group_id", sa.Integer(), nullable=True))
    op.create_index("ix_travelers_group_id", "travelers", ["group_id"], unique=False)
    op.create_foreign_key(
        "fk_travelers_group_id_traveler_groups",
        "travelers", "traveler_groups", ["group_id"], ["id"], ondelete="SET NULL"
    )


def downgrade():
    op.drop_constraint("fk_travelers_group_id_traveler_groups", "travelers", type_="foreignkey")
    op.drop_index("ix_travelers_group_id", table_name="travelers")
    op.drop_column("travelers", "group_id")
    op.drop_index("ix_traveler_groups_tour_id", table_name="traveler_groups")
    op.drop_table("traveler_groups")
