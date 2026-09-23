"""Add itinerary items table

Revision ID: a1b2c3d4e5f6
Revises: f3a9c7d1e5b2
Create Date: 2026-09-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f3a9c7d1e5b2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "itinerary_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tour_id", sa.Integer(), nullable=False),
        sa.Column("itinerary_date", sa.Date(), nullable=False),
        sa.Column("time", sa.Time(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("Id_Cat", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["Id_Cat"], ["Mast_Categories.Id_Cat"]),
        sa.ForeignKeyConstraint(["tour_id"], ["tours.id"]),
        sa.PrimaryKeyConstraint("id")
    )

    op.create_index(
        op.f("ix_itinerary_items_tour_id"),
        "itinerary_items",
        ["tour_id"],
        unique=False
    )

    op.create_index(
        op.f("ix_itinerary_items_itinerary_date"),
        "itinerary_items",
        ["itinerary_date"],
        unique=False
    )

    op.create_index(
        op.f("ix_itinerary_items_Id_Cat"),
        "itinerary_items",
        ["Id_Cat"],
        unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_itinerary_items_Id_Cat"), table_name="itinerary_items")
    op.drop_index(op.f("ix_itinerary_items_itinerary_date"), table_name="itinerary_items")
    op.drop_index(op.f("ix_itinerary_items_tour_id"), table_name="itinerary_items")
    op.drop_table("itinerary_items")
