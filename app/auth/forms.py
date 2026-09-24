from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Length, Regexp


PHONE_VALIDATOR = Regexp(
    r"^\+?[0-9]{7,15}$",
    message="Enter a valid phone number (7-15 digits, with an optional + prefix)."
)


class RegistrationForm(FlaskForm):

    name = StringField(
        "Name",
        validators=[
            DataRequired(),
            Length(min=2, max=100)
        ]
    )

    phone = StringField(
        "Phone Number",
        validators=[
            DataRequired(),
            Length(min=7, max=16),
            PHONE_VALIDATOR
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

    phone = StringField(
        "Phone Number",
        validators=[
            DataRequired(),
            Length(min=7, max=16),
            PHONE_VALIDATOR
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired()
        ]
    )

    submit = SubmitField("Login")
