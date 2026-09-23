from app.extensions import db


# ---------------------------------------------------------
# Expense <-> Traveler participation
#
# Tracks exactly which travelers were part of a given
# expense, so costs can be split only among the people who
# actually took part (and so free travelers, e.g. under 10,
# never get billed).
# ---------------------------------------------------------

expense_participants = db.Table(
    "expense_participants",
    db.Column(
        "expense_id",
        db.Integer,
        db.ForeignKey("expenses.id_Exp"),
        primary_key=True
    ),
    db.Column(
        "traveler_id",
        db.Integer,
        db.ForeignKey("travelers.id"),
        primary_key=True
    )
)
