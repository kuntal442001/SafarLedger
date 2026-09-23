from flask import render_template, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, current_user

from app.extensions import db, limiter
from app.models.user import User
from app.auth import auth
from app.auth.forms import (
    RegistrationForm,
    LoginForm,
    ForgotPasswordForm,
    ResetPasswordForm,
)
from app.auth.email_utils import send_email


# ============================================================
# REGISTER
# ============================================================

@auth.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():

    # Already logged in
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegistrationForm()

    if form.validate_on_submit():

        name = form.name.data.strip()
        email = form.email.data.strip().lower()

        # Check whether email already exists
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash(
                "An account with this email already exists.",
                "error"
            )

            return redirect(url_for("auth.register"))

        # Create user
        user = User(
            name=name,
            email=email
        )

        # Hash password
        user.set_password(form.password.data)

        # Save user
        db.session.add(user)
        db.session.commit()

        # Send confirmation email (falls back to showing the link
        # directly if no mail server is configured yet)
        token = user.generate_confirmation_token()
        confirm_url = url_for("auth.confirm_email", token=token, _external=True)

        emailed = send_email(
            subject="Confirm your SafarLedger account",
            recipients=[user.email],
            body=(
                f"Hi {user.name},\n\n"
                f"Please confirm your account by visiting:\n{confirm_url}\n\n"
                f"This link expires in 24 hours."
            ),
        )

        if emailed:
            flash(
                "Registration successful. Check your email to confirm "
                "your account, then log in.",
                "success"
            )
        else:
            flash(
                f"Registration successful. Confirm your account here: "
                f"{confirm_url}",
                "success"
            )

        return redirect(url_for("auth.login"))

    return render_template(
        "auth/register.html",
        form=form
    )


# ============================================================
# CONFIRM EMAIL
# ============================================================

@auth.route("/confirm/<token>")
def confirm_email(token):

    email = User.verify_confirmation_token(token)

    if not email:
        flash(
            "That confirmation link is invalid or has expired.",
            "error"
        )
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()

    if not user:
        flash("That confirmation link is invalid.", "error")
        return redirect(url_for("auth.login"))

    if user.is_verified:
        flash("Your account is already confirmed. You can log in.", "success")
    else:
        user.is_verified = True
        db.session.commit()
        flash("Your account has been confirmed. You can now log in.", "success")

    return redirect(url_for("auth.login"))


# ============================================================
# LOGIN
# ============================================================

@auth.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():

    # Already logged in
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()

    if form.validate_on_submit():

        email = form.email.data.strip().lower()

        # Find user by email
        user = User.query.filter_by(email=email).first()

        # Locked account - stop before even checking the password
        if user and user.is_locked:
            flash(
                "This account is temporarily locked after repeated "
                "failed login attempts. Try again later, or reset your "
                "password.",
                "error"
            )
            return render_template("auth/login.html", form=form)

        # Check credentials
        if user and user.check_password(form.password.data):

            user.reset_failed_login()
            db.session.commit()

            # Flask-Login creates the session
            login_user(user, remember=form.remember.data)

            if user.is_verified:
                flash("Login successful.", "success")
            else:
                flash(
                    "Login successful. Note: your email is not yet "
                    "confirmed - check your inbox for the confirmation link.",
                    "success"
                )

            return redirect(url_for("dashboard.index"))

        # Wrong password for a real account - count it toward lockout
        if user:
            user.register_failed_login(
                max_attempts=current_app.config.get("LOGIN_MAX_ATTEMPTS", 5),
                lockout_minutes=current_app.config.get("LOGIN_LOCKOUT_MINUTES", 15),
            )
            db.session.commit()

        # Don't reveal whether email exists
        flash(
            "Invalid email or password.",
            "error"
        )

    return render_template(
        "auth/login.html",
        form=form
    )


# ============================================================
# FORGOT PASSWORD
# ============================================================

@auth.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def forgot_password():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = ForgotPasswordForm()

    if form.validate_on_submit():

        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            token = user.generate_reset_token()
            reset_url = url_for("auth.reset_password", token=token, _external=True)

            emailed = send_email(
                subject="Reset your SafarLedger password",
                recipients=[user.email],
                body=(
                    f"Hi {user.name},\n\n"
                    f"Reset your password by visiting:\n{reset_url}\n\n"
                    f"This link expires in 1 hour. If you didn't request "
                    f"this, you can safely ignore this email."
                ),
            )

            if not emailed:
                # No mail server configured - surface the link directly
                # rather than pretending an email went out.
                flash(
                    f"No mail server is configured yet - here is your "
                    f"reset link: {reset_url}",
                    "success"
                )
                return redirect(url_for("auth.login"))

        # Same message whether or not the email is registered, so this
        # never reveals which emails have accounts.
        flash(
            "If that email is registered, a reset link has been sent.",
            "success"
        )
        return redirect(url_for("auth.login"))

    return render_template(
        "auth/forgot_password.html",
        form=form
    )


# ============================================================
# RESET PASSWORD
# ============================================================

@auth.route("/reset-password/<token>", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def reset_password(token):

    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    user = User.verify_reset_token(token)

    if not user:
        flash(
            "That password reset link is invalid or has expired.",
            "error"
        )
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()

    if form.validate_on_submit():

        user.set_password(form.password.data)
        user.reset_failed_login()
        db.session.commit()

        flash("Your password has been reset. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template(
        "auth/reset_password.html",
        form=form
    )


# ============================================================
# LOGOUT
# ============================================================

@auth.route("/logout")
def logout():

    logout_user()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("auth.login"))
