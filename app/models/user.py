from datetime import datetime, timedelta, timezone

from flask import current_app
from flask_login import UserMixin
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = db.Column(db.String(255), nullable=False)

    # ---------------------------------------------------------
    # Account security
    # ---------------------------------------------------------

    # Whether the user has clicked the confirmation link sent at
    # registration. Existing accounts are backfilled to True by the
    # migration that adds this column, so nobody already using the app
    # gets locked out; only new registrations start unverified.
    is_verified = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

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

    # ---------------------------------------------------------
    # Login lockout
    # ---------------------------------------------------------

    @property
    def is_locked(self):
        if not self.locked_until:
            return False

        locked_until = self.locked_until

        # Some DB drivers (e.g. SQLite, used in tests) return naive
        # datetimes even for timezone-aware columns. Treat a naive
        # value as UTC rather than raising a comparison error.
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)

        return locked_until > datetime.now(timezone.utc)

    def register_failed_login(self, max_attempts=5, lockout_minutes=15):
        """Call after a wrong password. Locks the account once the
        failed-attempt threshold is reached."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1

        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=lockout_minutes
            )

    def reset_failed_login(self):
        """Call after a successful login or password reset."""
        self.failed_login_attempts = 0
        self.locked_until = None

    # ---------------------------------------------------------
    # Email confirmation / password reset tokens
    #
    # These are stateless (itsdangerous-signed), so no extra DB columns
    # are needed to store them - they just encode enough to verify
    # themselves and expire on their own.
    # ---------------------------------------------------------

    @staticmethod
    def _serializer():
        return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

    def generate_confirmation_token(self):
        return self._serializer().dumps(self.email, salt="email-confirm")

    @staticmethod
    def verify_confirmation_token(token, max_age=86400):
        """Returns the email encoded in the token, or None if the token
        is invalid/expired (24 hour default lifetime)."""
        try:
            return User._serializer().loads(
                token, salt="email-confirm", max_age=max_age
            )
        except (BadSignature, SignatureExpired):
            return None

    def generate_reset_token(self):
        # Folding a fragment of the current password hash into the
        # payload means the token stops working the moment the password
        # is changed, without needing a dedicated DB column.
        payload = f"{self.id}:{self.password_hash[-12:]}"
        return self._serializer().dumps(payload, salt="password-reset")

    @staticmethod
    def verify_reset_token(token, max_age=3600):
        """Returns the matching User, or None if the token is
        invalid/expired (1 hour default lifetime)."""
        try:
            payload = User._serializer().loads(
                token, salt="password-reset", max_age=max_age
            )
            user_id_str, hash_fragment = payload.split(":", 1)
        except (BadSignature, SignatureExpired, ValueError):
            return None

        user = db.session.get(User, int(user_id_str))

        if not user or user.password_hash[-12:] != hash_fragment:
            return None

        return user

    def __repr__(self):
        return f"<User {self.email}>"
