from datetime import datetime, timezone

from app.extensions import db


class ExpensePayment(db.Model):
    __tablename__ = "expense_payments"

    id = db.Column(db.Integer, primary_key=True)
    expense_id = db.Column(
        db.Integer,
        db.ForeignKey("expenses.id_Exp"),
        nullable=False,
        index=True,
    )
    paid_by_id = db.Column(
        db.Integer,
        db.ForeignKey("travelers.id"),
        nullable=False,
        index=True,
    )
    on_behalf_of_id = db.Column(
        db.Integer,
        db.ForeignKey("travelers.id"),
        nullable=True,
        index=True,
    )
    paid_for_group_id = db.Column(
        db.Integer,
        db.ForeignKey("traveler_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    method = db.Column(db.String(30), nullable=False, default="UPI")
    note = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    expense = db.relationship(
        "Expense",
        back_populates="payments",
    )
    paid_by = db.relationship(
        "Traveler",
        foreign_keys=[paid_by_id],
        backref=db.backref("payments_made", lazy="dynamic"),
    )
    on_behalf_of = db.relationship(
        "Traveler",
        foreign_keys=[on_behalf_of_id],
        backref=db.backref("payments_for", lazy="dynamic"),
    )
    paid_for_group = db.relationship(
        "TravelerGroup",
        foreign_keys=[paid_for_group_id],
        backref=db.backref("payments_for_group", lazy="dynamic"),
    )

    def __repr__(self):
        return f"<ExpensePayment {self.amount} for expense {self.expense_id}>"
