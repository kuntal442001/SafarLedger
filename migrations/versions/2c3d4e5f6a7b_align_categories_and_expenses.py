"""Align legacy expense schema and create master categories.

Revision ID: 2c3d4e5f6a7b
Revises: 2ba76b9937bf
"""
from alembic import op
import sqlalchemy as sa

revision = "2c3d4e5f6a7b"
down_revision = "2ba76b9937bf"
branch_labels = None
depends_on = None


def upgrade():
    # The current application uses a master category table. The original
    # migration chain never created it, so create it before any FK references.
    op.create_table(
        "Mast_Categories",
        sa.Column("Id_Cat", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("Cat_Desc", sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint("Id_Cat"),
        sa.UniqueConstraint("Cat_Desc"),
    )

    # Preserve the standard categories used by SafarLedger. The INSERT is
    # intentionally idempotent with respect to this migration (which itself
    # only runs once).
    op.execute(sa.text("""
        INSERT INTO "Mast_Categories" ("Id_Cat", "Cat_Desc") VALUES
            (1, 'Food'),
            (2, 'Transport'),
            (3, 'Accommodation'),
            (4, 'Activities'),
            (5, 'Shopping'),
            (6, 'Other')
    """))

    # Bring the legacy expenses table in line with the current Expense model.
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.alter_column(
            "tour_id",
            new_column_name="Id_Tour",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )
        batch_op.add_column(sa.Column("Id_Cat", sa.Integer(), nullable=True))

    # Convert the legacy text category into the master-category FK. Existing
    # standard values are mapped to the seeded IDs. Unknown legacy category
    # names are inserted into Mast_Categories and then mapped as well.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT DISTINCT category FROM expenses WHERE category IS NOT NULL")).fetchall()
    for (category,) in rows:
        category = str(category).strip()
        if not category:
            category = "Other"
        exists = conn.execute(
            sa.text('SELECT 1 FROM "Mast_Categories" WHERE "Cat_Desc" = :name'),
            {"name": category},
        ).first()
        if not exists:
            conn.execute(
                sa.text('INSERT INTO "Mast_Categories" ("Cat_Desc") VALUES (:name)'),
                {"name": category},
            )

    conn.execute(sa.text("""
        UPDATE expenses e
        SET "Id_Cat" = c."Id_Cat"
        FROM "Mast_Categories" c
        WHERE c."Cat_Desc" = NULLIF(BTRIM(e.category), '')
           OR (NULLIF(BTRIM(e.category), '') IS NULL AND c."Cat_Desc" = 'Other')
    """))

    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.alter_column("Id_Cat", nullable=False)
        batch_op.drop_column("category")
        batch_op.create_index(
            batch_op.f("ix_expenses_Id_Tour"), ["Id_Tour"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_expenses_Id_Cat"), ["Id_Cat"], unique=False
        )
        batch_op.create_foreign_key(
            "fk_expenses_Id_Cat_Mast_Categories",
            "Mast_Categories",
            ["Id_Cat"],
            ["Id_Cat"],
        )


def downgrade():
    # Restore the legacy text category and tour_id naming.
    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category", sa.String(length=50), nullable=True))

    op.execute(sa.text("""
        UPDATE expenses e
        SET category = c."Cat_Desc"
        FROM "Mast_Categories" c
        WHERE c."Id_Cat" = e."Id_Cat"
    """))

    with op.batch_alter_table("expenses", schema=None) as batch_op:
        batch_op.alter_column("category", nullable=False)
        batch_op.drop_constraint("fk_expenses_Id_Cat_Mast_Categories", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_expenses_Id_Cat"))
        batch_op.drop_index(batch_op.f("ix_expenses_Id_Tour"))
        batch_op.drop_column("Id_Cat")
        batch_op.alter_column(
            "Id_Tour",
            new_column_name="tour_id",
            existing_type=sa.Integer(),
            existing_nullable=False,
        )

    op.drop_table("Mast_Categories")
