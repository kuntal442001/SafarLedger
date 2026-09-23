from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange


class TravelerForm(FlaskForm):

    name = StringField(
        "Name",
        validators=[
            DataRequired(),
            Length(min=1, max=150)
        ]
    )

    age = IntegerField(
        "Age",
        validators=[
            DataRequired(),
            NumberRange(min=0, max=120, message="Enter a valid age.")
        ]
    )

    group_id = SelectField(
        "Group",
        coerce=int,
        choices=[(0, "Unassigned")],
    )

    submit = SubmitField("Save Traveler")
