from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal

from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from sqlalchemy.orm import joinedload
from app.models import Tour, ItineraryItem
from app.itinerary import itinerary
from app.itinerary.forms import ItineraryItemForm


def get_user_tour(tour_id):
    return Tour.query.filter_by(
        id=tour_id,
        user_id=current_user.id
    ).first_or_404()


def get_user_item(item_id):
    return (
        ItineraryItem.query
        .join(Tour, ItineraryItem.tour_id == Tour.id)
        .filter(
            ItineraryItem.id == item_id,
            Tour.user_id == current_user.id
        )
        .first_or_404()
    )


def validate_item_date(form, tour):
    if form.itinerary_date.data < tour.start_date or form.itinerary_date.data > tour.end_date:
        form.itinerary_date.errors.append(
            "Itinerary date must be within the trip start and end dates."
        )
        return False
    return True


def get_next_sort_order(tour_id, itinerary_date, exclude_id=None):
    query = ItineraryItem.query.filter_by(
        tour_id=tour_id,
        itinerary_date=itinerary_date
    )

    if exclude_id is not None:
        query = query.filter(ItineraryItem.id != exclude_id)

    last_item = query.order_by(ItineraryItem.sort_order.desc()).first()
    return (last_item.sort_order + 1) if last_item else 0


# ---------------------------------
# View Trip Itinerary
# ---------------------------------

@itinerary.route("/tour/<int:tour_id>")
@login_required
def list_itinerary(tour_id):
    tour = get_user_tour(tour_id)

    items = (
        ItineraryItem.query
        .options(joinedload(ItineraryItem.category))
        .filter_by(tour_id=tour.id)
        .order_by(
            ItineraryItem.itinerary_date.asc(),
            ItineraryItem.sort_order.asc(),
            ItineraryItem.time.asc().nullslast(),
            ItineraryItem.id.asc()
        )
        .all()
    )

    # Build every day of the trip, including days with no activities yet.
    days = OrderedDict()
    current_date = tour.start_date

    while current_date <= tour.end_date:
        days[current_date] = []
        current_date += timedelta(days=1)

    for item in items:
        days.setdefault(item.itinerary_date, []).append(item)

    estimated_total = sum(
        (item.estimated_cost or Decimal("0"))
        for item in items
    )

    return render_template(
        "itinerary/list.html",
        tour=tour,
        days=days,
        itinerary_items=items,
        estimated_total=estimated_total
    )


# ---------------------------------
# Add Activity
# ---------------------------------

@itinerary.route("/tour/<int:tour_id>/create", methods=["GET", "POST"])
@login_required
def create(tour_id):
    tour = get_user_tour(tour_id)
    form = ItineraryItemForm(tour=tour)

    if form.validate_on_submit() and validate_item_date(form, tour):
        item = ItineraryItem(
            tour_id=tour.id,
            itinerary_date=form.itinerary_date.data,
            time=form.time.data,
            title=form.title.data.strip(),
            location=form.location.data.strip() if form.location.data else None,
            Id_Cat=form.Id_Cat.data,
            description=form.description.data.strip() if form.description.data else None,
            estimated_cost=form.estimated_cost.data or 0,
            sort_order=get_next_sort_order(
                tour.id,
                form.itinerary_date.data
            )
        )

        db.session.add(item)
        db.session.commit()

        flash("Itinerary activity added successfully!", "success")
        return redirect(url_for("itinerary.list_itinerary", tour_id=tour.id))

    return render_template(
        "itinerary/create.html",
        form=form,
        tour=tour
    )


# ---------------------------------
# Edit Activity
# ---------------------------------

@itinerary.route("/item/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit(item_id):
    item = get_user_item(item_id)
    tour = item.tour
    form = ItineraryItemForm(obj=item, tour=tour)

    if form.validate_on_submit() and validate_item_date(form, tour):
        date_changed = form.itinerary_date.data != item.itinerary_date

        item.itinerary_date = form.itinerary_date.data
        item.time = form.time.data
        item.title = form.title.data.strip()
        item.location = form.location.data.strip() if form.location.data else None
        item.Id_Cat = form.Id_Cat.data
        item.description = form.description.data.strip() if form.description.data else None
        item.estimated_cost = form.estimated_cost.data or 0

        if date_changed:
            item.sort_order = get_next_sort_order(
                tour.id,
                item.itinerary_date,
                exclude_id=item.id
            )

        db.session.commit()

        flash("Itinerary activity updated successfully!", "success")
        return redirect(url_for("itinerary.list_itinerary", tour_id=tour.id))

    return render_template(
        "itinerary/edit.html",
        form=form,
        tour=tour,
        item=item
    )


# ---------------------------------
# Delete Activity
# ---------------------------------

@itinerary.route("/item/<int:item_id>/delete", methods=["POST"])
@login_required
def delete(item_id):
    item = get_user_item(item_id)
    tour_id = item.tour_id

    db.session.delete(item)
    db.session.commit()

    flash("Itinerary activity deleted successfully!", "success")
    return redirect(url_for("itinerary.list_itinerary", tour_id=tour_id))
