from datetime import date

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    SelectField,
    TextAreaField,
    DecimalField,
    DateField,
    TimeField,
    SubmitField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models import MastCategory


class ItineraryItemForm(FlaskForm):

    itinerary_date = DateField(
        "Date",
        validators=[DataRequired()],
        format="%Y-%m-%d"
    )

    time = TimeField(
        "Time",
        validators=[Optional()],
        format="%H:%M"
    )

    title = StringField(
        "Activity",
        validators=[
            DataRequired(message="Please enter an activity."),
            Length(min=2, max=200)
        ]
    )

    location = StringField(
        "Location",
        validators=[
            Optional(),
            Length(max=255)
        ]
    )

    Id_Cat = SelectField(
        "Category",
        coerce=int,
        validators=[DataRequired(message="Please select a category.")]
    )

    description = TextAreaField(
        "Notes",
        validators=[Optional()]
    )

    estimated_cost = DecimalField(
        "Estimated Cost",
        validators=[
            Optional(),
            NumberRange(min=0, message="Estimated cost cannot be negative.")
        ],
        places=2,
        default=0
    )

    submit = SubmitField("Save Activity")

    def __init__(self, *args, tour=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.Id_Cat.choices = [
            (category.Id_Cat, category.Cat_Desc)
            for category in MastCategory.query.order_by(MastCategory.Cat_Desc).all()
        ]

        if not self.is_submitted() and self.itinerary_date.data is None and tour is not None:
            self.itinerary_date.data = tour.start_date
