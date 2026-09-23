from flask_wtf import FlaskForm
from wtforms import StringField, DateField, IntegerField, DecimalField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class TourForm(FlaskForm):
    name = StringField(
        "Trip Name",
        validators=[
            DataRequired(),
            Length(min=2, max=100)
        ]
    )

    destination = StringField(
        "Destination",
        validators=[
            DataRequired(),
            Length(min=2, max=150)
        ]
    )

    start_date = DateField(
        "Start Date",
        validators=[DataRequired()],
        format="%Y-%m-%d"
    )

    end_date = DateField(
        "End Date",
        validators=[DataRequired()],
        format="%Y-%m-%d"
    )

    number_of_people = IntegerField(
        "Number of People",
        validators=[
            DataRequired(),
            NumberRange(min=1, message="At least one person is required.")
        ]
    )

    budget = DecimalField(
        "Budget",
        validators=[
            Optional(),
            NumberRange(min=0, message="Budget cannot be negative.")
        ],
        places=2,
        default=0
    )

    submit = SubmitField("Save Trip")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        if self.start_date.data and self.end_date.data:
            if self.end_date.data < self.start_date.data:
                self.end_date.errors.append(
                    "End date cannot be before the start date."
                )
                return False

        return True