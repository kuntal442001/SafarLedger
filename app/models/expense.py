from datetime import date, datetime, timezone

from app.extensions import db
from app.models.expense_participant import expense_participants


class Expense(db.Model):
    __tablename__ = "expenses"

    id_Exp = db.Column(db.Integer, primary_key=True)

    Id_Tour = db.Column(
        db.Integer,
        db.ForeignKey("tours.id"),
        nullable=False,
        index=True
    )

    Id_Cat = db.Column(
        db.Integer,
        db.ForeignKey("Mast_Categories.Id_Cat"),
        nullable=False,
        index=True
    )

    expense_type = db.Column(
        db.String(100),
        nullable=True
    )

    description = db.Column(
        db.String(255),
        nullable=True
    )

    persons = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )

    expense_date = db.Column(
        db.Date,
        nullable=False,
        default=date.today
    )

    days = db.Column(
        db.Integer,
        nullable=False,
        default=1
    )

    amount = db.Column(
        db.Numeric(12, 2),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    tour = db.relationship(
        "Tour",
        back_populates="expenses"
    )

    category = db.relationship(
        "MastCategory"
    )

    payments = db.relationship(
        "ExpensePayment",
        back_populates="expense",
        cascade="all, delete-orphan",
        lazy=True,
    )

    # ---------------------------------------------------------
    # Travelers who actually took part in this expense. Only
    # chargeable travelers (age >= 10) among these are billed;
    # anyone left out (e.g. skipped the activity) pays nothing
    # for it.
    # ---------------------------------------------------------
    participants = db.relationship(
        "Traveler",
        secondary=expense_participants,
        backref=db.backref("expenses", lazy="dynamic")
    )

    def __repr__(self):
        return f"<Expense {self.Id_Cat}: {self.amount}>"