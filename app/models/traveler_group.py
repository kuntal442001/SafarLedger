from datetime import datetime, timezone

from app.extensions import db


class TravelerGroup(db.Model):
    __tablename__ = "traveler_groups"

    id = db.Column(db.Integer, primary_key=True)
    tour_id = db.Column(
        db.Integer,
        db.ForeignKey("tours.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tour = db.relationship("Tour", back_populates="traveler_groups")
    travelers = db.relationship("Traveler", back_populates="group")

    def __repr__(self):
        return f"<TravelerGroup {self.name}>"
