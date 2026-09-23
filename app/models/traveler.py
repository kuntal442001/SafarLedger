from datetime import datetime, timezone

from app.extensions import db


class Traveler(db.Model):
    __tablename__ = "travelers"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    tour_id = db.Column(
        db.Integer,
        db.ForeignKey("tours.id"),
        nullable=False,
        index=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    age = db.Column(
        db.Integer,
        nullable=False
    )

    group_id = db.Column(
        db.Integer,
        db.ForeignKey("traveler_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # ---------------------------------------------------------
    # Relationship
    # ---------------------------------------------------------

    tour = db.relationship(
        "Tour",
        back_populates="travelers"
    )

    group = db.relationship(
        "TravelerGroup",
        back_populates="travelers"
    )

    # ---------------------------------------------------------
    # Expense classification
    # ---------------------------------------------------------

    @property
    def is_chargeable(self):
        """
        Travelers aged 10 years or older are chargeable.
        Travelers below 10 are not included in the
        chargeable per-person expense calculation.
        """
        return self.age >= 10

    @property
    def traveler_type(self):
        """
        Returns a simple classification for display.
        """
        if self.age < 2:
            return "Baby"
        elif self.age < 10:
            return "Child"
        else:
            return "Adult"

    def __repr__(self):
        return f"<Traveler {self.name}, age={self.age}>"