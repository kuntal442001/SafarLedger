from datetime import date

from flask import render_template
from flask_login import login_required, current_user
from sqlalchemy import func

from app.dashboard import dashboard
from app.extensions import db
from app.models.tour import Tour
from app.models.expense import Expense


@dashboard.route("/")
@login_required
def index():

    # One aggregate query replaces the three separate Tour queries used for
    # total trips, active trips, and total budget.
    today = date.today()
    stats = (
        db.session.query(
            func.count(Tour.id),
            func.count(
                Tour.id
            ).filter(
                Tour.start_date <= today,
                Tour.end_date >= today,
            ),
            func.coalesce(func.sum(Tour.budget), 0),
        )
        .filter(Tour.user_id == current_user.id)
        .one()
    )

    total_trips, active_trips, total_budget = stats

    # ---------------------------------------------------------
    # Total spending
    #
    # Expenses are connected to tours, so we join expenses
    # with tours and only calculate the current user's expenses.
    # ---------------------------------------------------------

    total_spending = (
        db.session.query(
            func.coalesce(func.sum(Expense.amount), 0)
        )
        .join(
            Tour,
            Expense.Id_Tour == Tour.id
        )
        .filter(
            Tour.user_id == current_user.id
        )
        .scalar()
    )

    # ---------------------------------------------------------
    # Remaining budget
    # ---------------------------------------------------------

    remaining_budget = total_budget - total_spending

    # ---------------------------------------------------------
    # Recent trips
    # ---------------------------------------------------------

    recent_trips = (
        Tour.query
        .filter_by(user_id=current_user.id)
        .order_by(Tour.created_at.desc())
        .limit(5)
        .all()
    )

    # ---------------------------------------------------------
    # Render dashboard
    # ---------------------------------------------------------

    return render_template(
        "dashboard/index.html",
        user=current_user,
        total_trips=total_trips,
        active_trips=active_trips,
        total_budget=total_budget,
        total_spending=total_spending,
        remaining_budget=remaining_budget,
        recent_trips=recent_trips
    )