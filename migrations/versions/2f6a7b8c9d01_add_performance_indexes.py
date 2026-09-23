"""Add indexes for common SafarLedger list and detail queries.

Revision ID: 2f6a7b8c9d01
Revises: f1a2b3c4d5e6
"""
from alembic import op
import sqlalchemy as sa


revision = "2f6a7b8c9d01"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    # Dashboard: recent tours and active-tour filtering are both scoped by user.
    op.create_index(
        "ix_tours_user_created_at",
        "tours",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_tours_user_dates",
        "tours",
        ["user_id", "start_date", "end_date"],
        unique=False,
    )

    # Tour details/settlements repeatedly fetch a tour's expenses ordered by
    # creation date or grouped by expense date.
    op.create_index(
        "ix_expenses_tour_created_at",
        "expenses",
        ["Id_Tour", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_expenses_tour_expense_date",
        "expenses",
        ["Id_Tour", "expense_date"],
        unique=False,
    )

    # Itinerary pages filter by tour and then sort by the displayed itinerary
    # order. The existing single-column indexes remain useful for simpler
    # queries, so they are intentionally left untouched.
    op.create_index(
        "ix_itinerary_tour_schedule",
        "itinerary_items",
        ["tour_id", "itinerary_date", "sort_order", "time", "id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_itinerary_tour_schedule", table_name="itinerary_items")
    op.drop_index("ix_expenses_tour_expense_date", table_name="expenses")
    op.drop_index("ix_expenses_tour_created_at", table_name="expenses")
    op.drop_index("ix_tours_user_dates", table_name="tours")
    op.drop_index("ix_tours_user_created_at", table_name="tours")
