from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    phone = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(db.String(255), nullable=False)

    failed_login_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    locked_until = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    tours = db.relationship(
        "Tour",
        back_populates="operator",
        cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_locked(self):
        if not self.locked_until:
            return False

        locked_until = self.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        return locked_until > datetime.now(timezone.utc)

    def register_failed_login(self, max_attempts=5, lockout_minutes=15):
        """Count a failed password attempt and temporarily lock the account."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1

        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=lockout_minutes
            )

    def reset_failed_login(self):
        """Clear the failed-login counter after successful authentication."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def __repr__(self):
        return f"<User {self.phone}>"
