from flask import render_template, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, current_user

from app.extensions import db, limiter
from app.models.user import User
from app.auth import auth
from app.auth.forms import RegistrationForm, LoginForm


def normalize_phone(phone):
    """Normalize common phone formatting while preserving an optional + prefix."""
    phone = (phone or "").strip()
    if phone.startswith("+"):
        return "+" + "".join(ch for ch in phone[1:] if ch.isdigit())
    return "".join(ch for ch in phone if ch.isdigit())


# ============================================================
# REGISTER
# ============================================================

@auth.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegistrationForm()

    if form.validate_on_submit():
        name = form.name.data.strip()
        phone = normalize_phone(form.phone.data)

        existing_user = User.query.filter_by(phone=phone).first()

        if existing_user:
            flash("An account with this phone number already exists.", "error")
            return redirect(url_for("auth.register"))

        user = User(
            name=name,
            phone=phone,
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        flash("Registration successful. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


# ============================================================
# LOGIN
# ============================================================

@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()

    if form.validate_on_submit():
        phone = normalize_phone(form.phone.data)
        user = User.query.filter_by(phone=phone).first()

        if user and user.is_locked:
            flash(
                "This account is temporarily locked after repeated failed "
                "login attempts. Try again later.",
                "error",
            )
            return render_template("auth/login.html", form=form)

        if user and user.check_password(form.password.data):
            user.reset_failed_login()
            db.session.commit()
            login_user(user)
            flash("Login successful.", "success")
            return redirect(url_for("dashboard.index"))

        if user:
            user.register_failed_login(
                max_attempts=current_app.config.get("LOGIN_MAX_ATTEMPTS", 5),
                lockout_minutes=current_app.config.get("LOGIN_LOCKOUT_MINUTES", 15),
            )
            db.session.commit()

        flash("Invalid phone number or password.", "error")

    return render_template("auth/login.html", form=form)


# ============================================================
# LOGOUT
# ============================================================

@auth.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))
