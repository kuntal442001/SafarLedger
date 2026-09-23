from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from sqlalchemy.orm import selectinload
from app.models import Tour, Traveler, TravelerGroup
from app.groups import groups


def get_tour(tour_id):
    return Tour.query.filter_by(id=tour_id, user_id=current_user.id).first_or_404()


def next_group_name(tour):
    used = set()
    for group in tour.traveler_groups:
        if group.name.lower().startswith("group "):
            suffix = group.name[6:].strip()
            if suffix.isdigit():
                used.add(int(suffix))
    number = 1
    while number in used:
        number += 1
    return f"Group {number}"


@groups.route("/tour/<int:tour_id>")
@login_required
def list_groups(tour_id):
    tour = (
        Tour.query
        .options(
            selectinload(Tour.travelers),
            selectinload(Tour.traveler_groups).selectinload(TravelerGroup.travelers),
        )
        .filter_by(id=tour_id, user_id=current_user.id)
        .first_or_404()
    )
    groups_list = sorted(tour.traveler_groups, key=lambda g: (g.name.lower(), g.id))
    unassigned = [t for t in tour.travelers if t.group_id is None]
    return render_template(
        "groups/list.html",
        tour=tour,
        groups=groups_list,
        unassigned=unassigned,
    )


@groups.route("/tour/<int:tour_id>/create", methods=["GET", "POST"])
@login_required
def create(tour_id):
    tour = get_tour(tour_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Group name is required.", "danger")
        elif len(name) > 100:
            flash("Group name must be 100 characters or fewer.", "danger")
        elif TravelerGroup.query.filter_by(tour_id=tour.id, name=name).first():
            flash("A group with that name already exists in this trip.", "danger")
        else:
            group = TravelerGroup(tour_id=tour.id, name=name)
            db.session.add(group)
            db.session.commit()
            flash(f"{name} created successfully!", "success")
            return redirect(url_for("groups.list_groups", tour_id=tour.id))

    suggested_name = next_group_name(tour)
    return render_template("groups/form.html", tour=tour, group=None, suggested_name=suggested_name)


@groups.route("/<int:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit(group_id):
    group = (
        TravelerGroup.query
        .join(Tour, TravelerGroup.tour_id == Tour.id)
        .filter(TravelerGroup.id == group_id, Tour.user_id == current_user.id)
        .first_or_404()
    )
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        duplicate = TravelerGroup.query.filter(
            TravelerGroup.tour_id == group.tour_id,
            TravelerGroup.name == name,
            TravelerGroup.id != group.id,
        ).first()
        if not name:
            flash("Group name is required.", "danger")
        elif len(name) > 100:
            flash("Group name must be 100 characters or fewer.", "danger")
        elif duplicate:
            flash("A group with that name already exists in this trip.", "danger")
        else:
            group.name = name
            db.session.commit()
            flash("Group updated successfully!", "success")
            return redirect(url_for("groups.list_groups", tour_id=group.tour_id))

    return render_template("groups/form.html", tour=group.tour, group=group, suggested_name=group.name)


@groups.route("/<int:group_id>/delete", methods=["POST"])
@login_required
def delete(group_id):
    group = (
        TravelerGroup.query
        .join(Tour, TravelerGroup.tour_id == Tour.id)
        .filter(TravelerGroup.id == group_id, Tour.user_id == current_user.id)
        .first_or_404()
    )
    tour_id = group.tour_id
    for traveler in group.travelers:
        traveler.group_id = None
    db.session.delete(group)
    db.session.commit()
    flash("Group deleted. Its travelers are now unassigned.", "success")
    return redirect(url_for("groups.list_groups", tour_id=tour_id))


@groups.route("/<int:group_id>/assign", methods=["POST"])
@login_required
def assign(group_id):
    group = (
        TravelerGroup.query
        .join(Tour, TravelerGroup.tour_id == Tour.id)
        .filter(TravelerGroup.id == group_id, Tour.user_id == current_user.id)
        .first_or_404()
    )
    traveler_id = request.form.get("traveler_id", type=int)
    traveler = Traveler.query.filter_by(id=traveler_id, tour_id=group.tour_id).first() if traveler_id else None
    if not traveler:
        flash("Invalid traveler selected.", "danger")
    else:
        traveler.group_id = group.id
        db.session.commit()
        flash(f"{traveler.name} added to {group.name}.", "success")
    return redirect(url_for("groups.list_groups", tour_id=group.tour_id))


@groups.route("/traveler/<int:traveler_id>/remove", methods=["POST"])
@login_required
def remove_traveler(traveler_id):
    traveler = (
        Traveler.query
        .join(Tour, Traveler.tour_id == Tour.id)
        .filter(Traveler.id == traveler_id, Tour.user_id == current_user.id)
        .first_or_404()
    )
    tour_id = traveler.tour_id
    traveler.group_id = None
    db.session.commit()
    flash(f"{traveler.name} is now unassigned.", "success")
    return redirect(url_for("groups.list_groups", tour_id=tour_id))
