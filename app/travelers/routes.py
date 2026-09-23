from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Tour, Traveler, TravelerGroup
from app.travelers import travelers
from app.travelers.forms import TravelerForm


# ---------------------------------
# List Travelers for a Trip
# ---------------------------------

@travelers.route("/tour/<int:tour_id>")
@login_required
def list_travelers(tour_id):
    # Make sure the trip belongs to the current user
    tour = Tour.query.filter_by(
        id=tour_id,
        user_id=current_user.id
    ).first_or_404()

    travelers_list = (
        Traveler.query
        .filter_by(tour_id=tour.id)
        .order_by(Traveler.name.asc())
        .all()
    )

    return render_template(
        "travelers/list.html",
        tour=tour,
        travelers=travelers_list
    )


# ---------------------------------
# Add Traveler to a Trip
# ---------------------------------

@travelers.route("/tour/<int:tour_id>/create", methods=["GET", "POST"])
@login_required
def create(tour_id):
    tour = Tour.query.filter_by(
        id=tour_id,
        user_id=current_user.id
    ).first_or_404()

    form = TravelerForm()
    form.group_id.choices = [(0, "Unassigned")] + [
        (g.id, g.name) for g in sorted(tour.traveler_groups, key=lambda x: (x.name.lower(), x.id))
    ]

    if form.validate_on_submit():
        group_id = form.group_id.data or None
        group = TravelerGroup.query.filter_by(id=group_id, tour_id=tour.id).first() if group_id else None
        if group_id and not group:
            flash("Invalid group selected.", "danger")
            return render_template("travelers/create.html", form=form, tour=tour)
        traveler = Traveler(
            tour_id=tour.id,
            name=form.name.data.strip(),
            age=form.age.data,
            group_id=group_id,
        )

        db.session.add(traveler)
        db.session.commit()

        flash("Traveler added successfully!", "success")
        return redirect(url_for("travelers.list_travelers", tour_id=tour.id))

    return render_template(
        "travelers/create.html",
        form=form,
        tour=tour
    )


# ---------------------------------
# Edit Traveler
# ---------------------------------

@travelers.route("/<int:traveler_id>/edit", methods=["GET", "POST"])
@login_required
def edit(traveler_id):
    # Get the traveler and ensure their trip belongs to the current user
    traveler = (
        Traveler.query
        .join(Tour, Traveler.tour_id == Tour.id)
        .filter(
            Traveler.id == traveler_id,
            Tour.user_id == current_user.id
        )
        .first_or_404()
    )

    form = TravelerForm(obj=traveler)
    form.group_id.choices = [(0, "Unassigned")] + [
        (g.id, g.name) for g in sorted(traveler.tour.traveler_groups, key=lambda x: (x.name.lower(), x.id))
    ]
    if request.method == "GET":
        form.group_id.data = traveler.group_id or 0

    if form.validate_on_submit():
        group_id = form.group_id.data or None
        group = TravelerGroup.query.filter_by(id=group_id, tour_id=traveler.tour_id).first() if group_id else None
        if group_id and not group:
            flash("Invalid group selected.", "danger")
            return render_template("travelers/edit.html", form=form, traveler=traveler)
        traveler.name = form.name.data.strip()
        traveler.age = form.age.data
        traveler.group_id = group_id

        db.session.commit()

        flash("Traveler updated successfully!", "success")
        return redirect(url_for("travelers.list_travelers", tour_id=traveler.tour_id))

    return render_template(
        "travelers/edit.html",
        form=form,
        traveler=traveler
    )


# ---------------------------------
# Delete Traveler
# ---------------------------------

@travelers.route("/<int:traveler_id>/delete", methods=["POST"])
@login_required
def delete(traveler_id):
    traveler = (
        Traveler.query
        .join(Tour, Traveler.tour_id == Tour.id)
        .filter(
            Traveler.id == traveler_id,
            Tour.user_id == current_user.id
        )
        .first_or_404()
    )

    tour_id = traveler.tour_id

    db.session.delete(traveler)
    db.session.commit()

    flash("Traveler removed successfully! Any expenses they were linked to will be recalculated.", "success")
    return redirect(url_for("travelers.list_travelers", tour_id=tour_id))
