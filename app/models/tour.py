from datetime import datetime, timezone

from app.extensions import db


class Tour(db.Model):

    __tablename__ = "tours"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    tour_name = db.Column(
        db.String(150),
        nullable=False
    )

    destination = db.Column(
        db.String(150),
        nullable=False
    )

    start_date = db.Column(
        db.Date,
        nullable=False
    )

    end_date = db.Column(
        db.Date,
        nullable=False
    )

    number_of_people = db.Column(
        db.Integer,
        nullable=False
    )

    number_of_days = db.Column(
        db.Integer,
        nullable=False
    )

    # ---------------------------------------------------------
    # Trip Budget
    # ---------------------------------------------------------

    budget = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # ---------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------

    operator = db.relationship(
        "User",
        back_populates="tours"
    )

    expenses = db.relationship(
        "Expense",
        back_populates="tour",
        cascade="all, delete-orphan"
    )

    travelers = db.relationship(
        "Traveler",
        back_populates="tour",
        cascade="all, delete-orphan",
        lazy=True
    )

    traveler_groups = db.relationship(
        "TravelerGroup",
        back_populates="tour",
        cascade="all, delete-orphan",
        lazy=True
    )

    itinerary_items = db.relationship(
        "ItineraryItem",
        back_populates="tour",
        cascade="all, delete-orphan",
        lazy=True
    )

    def __repr__(self):
        return f"<Tour {self.tour_name}>"