"""add user security fields (verification + login lockout)

Revision ID: f1a2b3c4d5e6
Revises: e6f7g8h9i0j1
Create Date: 2026-09-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1a2b3c4d5e6"
down_revision = "e6f7g8h9i0j1"
branch_labels = None
depends_on = None


def upgrade():
    # server_default='true' backfills every existing row as verified so
    # nobody who could already log in gets locked out by this change.
    # New rows go through the model's Python-side default (False) since
    # SQLAlchemy sends an explicit value on INSERT, overriding the
    # server default.
    op.add_column(
        "users",
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    # Drop the server defaults after backfill so future schema changes
    # don't rely on them - the model's Python-side defaults take over.
    op.alter_column("users", "is_verified", server_default=None)
    op.alter_column("users", "failed_login_attempts", server_default=None)


def downgrade():
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_attempts")
    op.drop_column("users", "is_verified")
