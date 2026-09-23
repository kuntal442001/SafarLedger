from datetime import datetime, timezone

from app.extensions import db


class ItineraryItem(db.Model):
    __tablename__ = "itinerary_items"

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

    itinerary_date = db.Column(
        db.Date,
        nullable=False,
        index=True
    )

    time = db.Column(
        db.Time,
        nullable=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    location = db.Column(
        db.String(255),
        nullable=True
    )

    Id_Cat = db.Column(
        db.Integer,
        db.ForeignKey("Mast_Categories.Id_Cat"),
        nullable=False,
        index=True
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    estimated_cost = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    sort_order = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    tour = db.relationship(
        "Tour",
        back_populates="itinerary_items"
    )

    category = db.relationship(
        "MastCategory"
    )

    def __repr__(self):
        return f"<ItineraryItem {self.title}>"
