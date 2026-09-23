from flask_wtf import FlaskForm
from wtforms import BooleanField, StringField, PasswordField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length
)


class RegistrationForm(FlaskForm):

    name = StringField(
        "Name",
        validators=[
            DataRequired(),
            Length(min=2, max=100)
        ]
    )

    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(),
            Length(max=255)
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, max=128)
        ]
    )

    confirm_password = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            EqualTo(
                "password",
                message="Passwords must match."
            )
        ]
    )

    submit = SubmitField("Create Account")


class LoginForm(FlaskForm):

    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(),
            Length(max=255)
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired()
        ]
    )

    remember = BooleanField(
        "Remember me",
        default=False
    )

    submit = SubmitField("Login")


class ForgotPasswordForm(FlaskForm):

    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(),
            Length(max=255)
        ]
    )

    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):

    password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=8, max=128)
        ]
    )

    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo(
                "password",
                message="Passwords must match."
            )
        ]
    )

    submit = SubmitField("Reset Password")
