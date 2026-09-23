from datetime import date

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, DecimalField, IntegerField, DateField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from wtforms.widgets import ListWidget, CheckboxInput

from app.models import MastCategory


class ExpenseForm(FlaskForm):

    Id_Cat = SelectField(
        "Category",
        coerce=int,
        validators=[DataRequired(message="Please select a category.")]
    )

    expense_type = StringField(
        "Type",
        validators=[
            Optional(),
            Length(max=100)
        ]
    )

    description = StringField(
        "Description",
        validators=[
            Optional(),
            Length(max=255)
        ]
    )

    persons = IntegerField(
        "No. of Persons",
        validators=[
            DataRequired(),
            NumberRange(min=1, message="No. of persons must be at least 1.")
        ],
        default=1
    )

    expense_date = DateField(
        "Date",
        validators=[DataRequired()],
        default=date.today
    )

    days = IntegerField(
        "Days",
        validators=[
            DataRequired(),
            NumberRange(min=1, message="Days must be at least 1.")
        ],
        default=1
    )

    amount = DecimalField(
        "Amount",
        validators=[
            DataRequired(),
            NumberRange(min=0.01, message="Amount must be greater than 0.")
        ],
        places=2
    )

    # ---------------------------------------------------------
    # Participants
    #
    # Which travelers this expense should be split between.
    # Left empty on trips with no travelers logged yet (falls
    # back to splitting evenly across the whole party).
    # Non-chargeable travelers (age < 10) can still be ticked
    # for record-keeping, but they're never actually billed.
    # ---------------------------------------------------------
    participants = SelectMultipleField(
        "Participants",
        coerce=int,
        validators=[Optional()],
        option_widget=CheckboxInput(),
        widget=ListWidget(prefix_label=False)
    )

    submit = SubmitField("Save Expense")

    def __init__(self, *args, tour=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.Id_Cat.choices = [
            (c.Id_Cat, c.Cat_Desc)
            for c in MastCategory.query.order_by(MastCategory.Cat_Desc).all()
        ]

        if tour is not None:
            self.participants.choices = [
                (
                    t.id,
                    f"{t.name} ({t.age}{'' if t.is_chargeable else ' - Free'})"
                )
                for t in sorted(tour.travelers, key=lambda t: t.name)
            ]
        else:
            self.participants.choices = []
