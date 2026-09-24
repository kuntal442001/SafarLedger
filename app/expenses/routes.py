from flask import render_template, redirect, url_for, flash, Response, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Tour, Expense, Traveler
from app.expenses import expenses
from app.expenses.forms import ExpenseForm

ALLOWED_RECEIPT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_RECEIPT_BYTES = 4 * 1024 * 1024

def _read_receipt(file_storage):
    """Read and validate a receipt image for storage in PostgreSQL."""
    if not file_storage or not file_storage.filename:
        return None

    content_type = (file_storage.mimetype or "").lower()
    if content_type not in ALLOWED_RECEIPT_TYPES:
        raise ValueError("Receipt must be a JPG, PNG, WEBP or GIF image.")

    data = file_storage.read()
    if not data:
        raise ValueError("The selected receipt is empty.")
    if len(data) > MAX_RECEIPT_BYTES:
        raise ValueError("Receipt image must be smaller than 4 MB.")

    safe_name = secure_filename(file_storage.filename) or "receipt"
    return {
        "image": data,
        "filename": safe_name,
        "content_type": content_type,
    }


# ---------------------------------
# Add Expense to a Trip
# ---------------------------------

@expenses.route("/tour/<int:tour_id>/create", methods=["GET", "POST"])
@login_required
def create(tour_id):
    # Make sure the trip belongs to the current user
    tour = Tour.query.filter_by(
        id=tour_id,
        user_id=current_user.id
    ).first_or_404()

    form = ExpenseForm(tour=tour)

    if form.validate_on_submit():
        try:
            receipt = _read_receipt(form.receipt_file.data)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("expenses/create.html", form=form, tour=tour)
        
        selected_participants = (
            Traveler.query
            .filter(
                Traveler.tour_id == tour.id,
                Traveler.id.in_(form.participants.data)
            )
            .all()
            if form.participants.data else []
        )

        expense = Expense(
            Id_Tour=tour.id,
            Id_Cat=form.Id_Cat.data,
            expense_type=form.expense_type.data or None,
            description=form.description.data or None,
            # Persons always reflects who's actually ticked as a
            # participant. Only falls back to the manually entered
            # count when no travelers have been logged for the trip.
            persons=len(selected_participants) if selected_participants else form.persons.data,
            expense_date=form.expense_date.data,
            days=form.days.data,
            amount=form.amount.data,
            receipt_image=receipt["image"] if receipt else None,
            receipt_filename=receipt["filename"] if receipt else None,
            receipt_content_type=receipt["content_type"] if receipt else None,
        )

        if selected_participants:
            expense.participants = selected_participants

        db.session.add(expense)
        db.session.commit()

        flash("Expense added successfully!", "success")
        return redirect(url_for("tours.detail", tour_id=tour.id))

    return render_template(
        "expenses/create.html",
        form=form,
        tour=tour
    )


# ---------------------------------
# Edit Expense
# ---------------------------------

@expenses.route("/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit(expense_id):
    expense = (
        Expense.query
        .join(Tour, Expense.Id_Tour == Tour.id)
        .filter(
            Expense.id_Exp == expense_id,
            Tour.user_id == current_user.id
        )
        .first_or_404()
    )

    form = ExpenseForm(obj=expense, tour=expense.tour)

    if not form.is_submitted():
        form.participants.data = [p.id for p in expense.participants]

    if form.validate_on_submit():
        new_receipt = None
        try:
            if form.receipt_file.data and form.receipt_file.data.filename:
                new_receipt = _read_receipt(form.receipt_file.data)
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("expenses/edit.html", form=form, expense=expense)

        selected_participants = (
            Traveler.query
            .filter(
                Traveler.tour_id == expense.Id_Tour,
                Traveler.id.in_(form.participants.data)
            )
            .all()
            if form.participants.data else []
        )

        expense.Id_Cat = form.Id_Cat.data
        expense.expense_type = form.expense_type.data or None
        expense.description = form.description.data or None
        # Persons always reflects who's actually ticked as a
        # participant. Only falls back to the manually entered
        # count when no travelers are selected for this expense.
        expense.persons = len(selected_participants) if selected_participants else form.persons.data
        expense.expense_date = form.expense_date.data
        expense.days = form.days.data
        expense.amount = form.amount.data
        expense.participants = selected_participants

        if new_receipt:
            expense.receipt_image = new_receipt["image"]
            expense.receipt_filename = new_receipt["filename"]
            expense.receipt_content_type = new_receipt["content_type"]

        db.session.commit()

        flash("Expense updated successfully!", "success")
        return redirect(url_for("tours.detail", tour_id=expense.Id_Tour))

    return render_template(
        "expenses/edit.html",
        form=form,
        expense=expense
    )


# ---------------------------------
# View original receipt
# ---------------------------------

@expenses.route("/<int:expense_id>/receipt", methods=["GET"])
@login_required
def receipt(expense_id):
    expense = (
        Expense.query
        .join(Tour, Expense.Id_Tour == Tour.id)
        .filter(
            Expense.id_Exp == expense_id,
            Tour.user_id == current_user.id
        )
        .first_or_404()
    )

    if not expense.receipt_image:
        abort(404)

    headers = {
        "Content-Type": expense.receipt_content_type or "application/octet-stream",
        "Content-Disposition": f'inline; filename="{expense.receipt_filename or "receipt"}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
    return Response(bytes(expense.receipt_image), headers=headers)


# ---------------------------------
# Delete Expense
# ---------------------------------

@expenses.route("/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete(expense_id):
    expense = (
        Expense.query
        .join(Tour, Expense.Id_Tour == Tour.id)
        .filter(
            Expense.id_Exp == expense_id,
            Tour.user_id == current_user.id
        )
        .first_or_404()
    )

    tour_id = expense.Id_Tour
    db.session.delete(expense)
    db.session.commit()

    flash("Expense deleted successfully!", "success")
    return redirect(url_for("tours.detail", tour_id=tour_id))
