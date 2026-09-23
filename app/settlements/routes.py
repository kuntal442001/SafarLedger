from decimal import Decimal, ROUND_HALF_UP

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from sqlalchemy.orm import selectinload, joinedload
from app.models import Expense, ExpensePayment, Tour, Traveler, TravelerGroup
from app.settlements import settlements


ZERO = Decimal("0.00")
CENT = Decimal("0.01")
METHODS = ["UPI", "Cash", "Card", "Bank Transfer", "Other"]


def money(value):
    if value is None:
        return ZERO
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def get_tour(tour_id):
    return Tour.query.filter_by(id=tour_id, user_id=current_user.id).first_or_404()


def get_settlement_tour(tour_id):
    # The settlement detail page repeatedly walks travelers, groups, expenses,
    # participants, and payments. Load each collection in batches to avoid
    # an N+1 query for every expense/payment.
    return (
        Tour.query
        .options(
            selectinload(Tour.travelers),
            selectinload(Tour.traveler_groups).selectinload(TravelerGroup.travelers),
            selectinload(Tour.expenses).options(
                selectinload(Expense.participants),
                selectinload(Expense.payments).options(
                    joinedload(ExpensePayment.paid_by),
                    joinedload(ExpensePayment.on_behalf_of),
                    joinedload(ExpensePayment.paid_for_group),
                ),
            ),
        )
        .filter_by(id=tour_id, user_id=current_user.id)
        .first_or_404()
    )


def expense_shares(tour):
    """Return per-traveler shares using the same rules as the expense UI."""
    all_travelers = list(tour.travelers)
    chargeable_travelers = [t for t in all_travelers if t.is_chargeable]
    shares = {t.id: ZERO for t in all_travelers}

    for expense in tour.expenses:
        if expense.participants:
            participants = [p for p in expense.participants if p.is_chargeable]
        else:
            participants = chargeable_travelers

        if not participants:
            continue

        amount = money(expense.amount)
        count = len(participants)
        base = (amount / count).quantize(CENT, rounding=ROUND_HALF_UP)
        remainder = amount - (base * count)

        # Distribute any paise rounding remainder deterministically.
        for index, traveler in enumerate(sorted(participants, key=lambda x: x.id)):
            share = base
            if index == count - 1:
                share += remainder
            shares[traveler.id] += share

    return shares


def calculate_settlement(tour, traveler_filter=None):
    """Calculate traveler balances and the transfers that are actually needed.

    Payment meanings:

    * Normal payment: the payer gets credit for the amount.  If ``on_behalf_of``
      is set, the beneficiary naturally remains responsible for their share,
      so the resulting transfer points back to the payer.
    * ``paid_for_group_id`` payment: the payment is treated as a group-level
      payment.  When the payer belongs to that same group, the payment settles
      the group's internal obligation and must NOT create artificial
      member-to-member transfers.  The group view therefore shows the members
      as settled when the group's share is fully covered.

    The transfer list is kept separate from the display balances so that the
    "Who owes what?" table can show group settlement status without leaking
    internal group transfers into "Suggested Transfers".
    """
    all_travelers = list(tour.travelers)
    traveler_by_id = {t.id: t for t in all_travelers}
    group_members = {}
    for traveler in all_travelers:
        if traveler.group_id is not None:
            group_members.setdefault(traveler.group_id, []).append(traveler)

    shares = expense_shares(tour)
    paid = {t.id: ZERO for t in all_travelers}

    # Payments that belong to a group are kept separately because a group
    # payment has different settlement semantics from an individual payment.
    group_payment_totals = {}
    for expense in tour.expenses:
        for payment in expense.payments:
            amount = money(payment.amount)
            if payment.paid_for_group_id:
                group_payment_totals[payment.paid_for_group_id] = (
                    group_payment_totals.get(payment.paid_for_group_id, ZERO) + amount
                )
            else:
                paid[payment.paid_by_id] = paid.get(payment.paid_by_id, ZERO) + amount

    # Group payments are credited to their group's members for the purpose of
    # the group-scoped "Who owes what?" display. This makes a full group
    # payment produce zero balances for every member.
    for group_id, amount in group_payment_totals.items():
        members = sorted(group_members.get(group_id, ()), key=lambda t: t.id)
        if not members:
            continue
        total_share = sum((shares.get(t.id, ZERO) for t in members), ZERO)
        if total_share <= ZERO:
            paid[members[-1].id] += amount
            continue

        remaining = amount
        for index, traveler in enumerate(members):
            member_share = shares.get(traveler.id, ZERO)
            if index == len(members) - 1:
                allocation = remaining
            else:
                allocation = (amount * member_share / total_share).quantize(
                    CENT, rounding=ROUND_HALF_UP
                )
                allocation = min(allocation, remaining)
            paid[traveler.id] += allocation
            remaining -= allocation

    travelers = all_travelers
    if traveler_filter is not None:
        allowed_ids = {t.id for t in traveler_filter}
        travelers = [t for t in travelers if t.id in allowed_ids]

    balances = []
    for traveler in travelers:
        share = shares.get(traveler.id, ZERO)
        paid_amount = paid.get(traveler.id, ZERO)
        net = (paid_amount - share).quantize(CENT, rounding=ROUND_HALF_UP)
        balances.append({
            "traveler": traveler,
            "share": share,
            "paid": paid_amount,
            "balance": net,
        })

    # Build transfer balances independently. Normal payments use the same
    # traveler balances as above. Group payments made by a member of that same
    # group are deliberately excluded from member-to-member transfers: the
    # group payment is already an explicit declaration that the payer covered
    # the group as one unit. If somebody outside a group pays for that group,
    # the external payer becomes a creditor and the group's members are the
    # debtors.
    transfer_balances = {t.id: (ZERO - shares.get(t.id, ZERO)) for t in all_travelers}
    for expense in tour.expenses:
        for payment in expense.payments:
            amount = money(payment.amount)
            if payment.paid_for_group_id:
                members = group_members.get(payment.paid_for_group_id, ())
                if not members:
                    transfer_balances[payment.paid_by_id] += amount
                    continue

                payer = traveler_by_id.get(payment.paid_by_id)
                # Same-group group payment: no internal transfer is required.
                # The payment is consumed by the group's own obligation.
                if payer is not None and payer.group_id == payment.paid_for_group_id:
                    # Remove the members' obligation covered by this payment
                    # proportionally. This is only used for transfer generation.
                    total_share = sum((shares.get(t.id, ZERO) for t in members), ZERO)
                    if total_share > ZERO:
                        remaining = amount
                        for index, member in enumerate(sorted(members, key=lambda x: x.id)):
                            member_share = shares.get(member.id, ZERO)
                            if index == len(members) - 1:
                                allocation = remaining
                            else:
                                allocation = (amount * member_share / total_share).quantize(
                                    CENT, rounding=ROUND_HALF_UP
                                )
                                allocation = min(allocation, remaining)
                            transfer_balances[member.id] += allocation
                            remaining -= allocation
                    continue

                # External person paid for the group: the group owes the payer.
                # Allocate the group's payment against members' shares so the
                # suggested transfers point to the real payer.
                total_share = sum((shares.get(t.id, ZERO) for t in members), ZERO)
                if total_share <= ZERO:
                    transfer_balances[payment.paid_by_id] += amount
                    continue
                transfer_balances[payment.paid_by_id] += amount
                remaining = amount
                for index, member in enumerate(sorted(members, key=lambda x: x.id)):
                    member_share = shares.get(member.id, ZERO)
                    if index == len(members) - 1:
                        allocation = remaining
                    else:
                        allocation = (amount * member_share / total_share).quantize(
                            CENT, rounding=ROUND_HALF_UP
                        )
                        allocation = min(allocation, remaining)
                    transfer_balances[member.id] += allocation
                    remaining -= allocation
            else:
                transfer_balances[payment.paid_by_id] += amount

    # Generate transfers from negative balances (owes) to positive balances
    # (gets). Zero/near-zero values are ignored.
    creditors = [
        {"traveler": t, "amount": amount}
        for t in all_travelers
        for amount in [transfer_balances[t.id].quantize(CENT, rounding=ROUND_HALF_UP)]
        if amount > ZERO
    ]
    debtors = [
        {"traveler": t, "amount": -amount}
        for t in all_travelers
        for amount in [transfer_balances[t.id].quantize(CENT, rounding=ROUND_HALF_UP)]
        if amount < ZERO
    ]

    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i]["amount"], creditors[j]["amount"])
        if amount > ZERO:
            transfers.append({
                "from": debtors[i]["traveler"],
                "to": creditors[j]["traveler"],
                "amount": amount.quantize(CENT, rounding=ROUND_HALF_UP),
            })
        debtors[i]["amount"] -= amount
        creditors[j]["amount"] -= amount
        if debtors[i]["amount"] <= ZERO:
            i += 1
        if creditors[j]["amount"] <= ZERO:
            j += 1

    return balances, transfers


@settlements.route("/tour/<int:tour_id>")
@login_required
def detail(tour_id):
    tour = get_settlement_tour(tour_id)
    groups = sorted(tour.traveler_groups, key=lambda g: (g.name.lower(), g.id))
    group_filter = request.args.get("group_id")
    selected_group = None
    selected_unassigned = group_filter == "unassigned"

    if group_filter and group_filter != "unassigned":
        try:
            group_id = int(group_filter)
        except ValueError:
            flash("Invalid group selected.", "danger")
            return redirect(url_for("settlements.detail", tour_id=tour.id))
        selected_group = next((g for g in groups if g.id == group_id), None)
        if selected_group is None:
            flash("Invalid group selected.", "danger")
            return redirect(url_for("settlements.detail", tour_id=tour.id))
        selected_travelers = list(selected_group.travelers)
    elif selected_unassigned:
        selected_travelers = [t for t in tour.travelers if t.group_id is None]
    else:
        selected_travelers = list(tour.travelers)

    # calculate_settlement() always computes trip-level transfers; the
    # traveler filter only affects the displayed balances. Calculate it once
    # and filter the already-computed rows instead of recalculating every
    # expense/payment for each view.
    all_travelers = list(tour.travelers)
    all_balances, all_transfers = calculate_settlement(tour)
    allowed_ids = {t.id for t in selected_travelers}
    balances = [row for row in all_balances if row["traveler"].id in allowed_ids]
    transfers = all_transfers

    # A selected group is settled as a single accounting unit. This is
    # important when one member pays for the other members: the individual
    # rows may show who paid, but the group itself is settled once its total
    # share has been covered by payments made by its members.
    selected_group_share = sum((row["share"] for row in balances), ZERO)
    selected_group_paid = sum((row["paid"] for row in balances), ZERO)
    selected_group_balance = (selected_group_paid - selected_group_share).quantize(CENT, rounding=ROUND_HALF_UP)
    selected_group_settled = bool(
        (selected_group is not None or selected_unassigned)
        and selected_group_balance == ZERO
    )
    expenses = sorted(tour.expenses, key=lambda e: (e.expense_date, e.id_Exp))

    expense_remaining = {}
    for expense in expenses:
        paid_total = sum((money(p.amount) for p in expense.payments), ZERO)
        expense_remaining[expense.id_Exp] = max(ZERO, money(expense.amount) - paid_total)

    allowed_ids = {t.id for t in selected_travelers}
    payment_records = []
    for expense in expenses:
        for payment in expense.payments:
            if payment.paid_by_id in allowed_ids:
                payment_records.append((expense, payment))

    balances_by_id = {row["traveler"].id: row for row in all_balances}
    group_summaries = []
    for group in groups:
        members = list(group.travelers)
        member_rows = [balances_by_id[t.id] for t in members]
        group_summaries.append({
            "group": group,
            "members": members,
            "share": sum((row["share"] for row in member_rows), ZERO),
            "paid": sum((row["paid"] for row in member_rows), ZERO),
            "balance": sum((row["balance"] for row in member_rows), ZERO),
        })

    unassigned = [t for t in tour.travelers if t.group_id is None]
    if unassigned:
        member_rows = [balances_by_id[t.id] for t in unassigned]
        group_summaries.append({
            "group": None,
            "members": unassigned,
            "share": sum((row["share"] for row in member_rows), ZERO),
            "paid": sum((row["paid"] for row in member_rows), ZERO),
            "balance": sum((row["balance"] for row in member_rows), ZERO),
        })

    return render_template(
        "settlements/detail.html",
        tour=tour,
        travelers=list(tour.travelers),
        selected_travelers=selected_travelers,
        groups=groups,
        selected_group=selected_group,
        selected_unassigned=selected_unassigned,
        group_summaries=group_summaries,
        expenses=expenses,
        balances=balances,
        transfers=transfers,
        all_transfers=all_transfers,
        payment_records=payment_records,
        methods=METHODS,
        expense_remaining=expense_remaining,
        selected_group_share=selected_group_share,
        selected_group_paid=selected_group_paid,
        selected_group_balance=selected_group_balance,
        selected_group_settled=selected_group_settled,
    )


@settlements.route("/tour/<int:tour_id>/payment", methods=["POST"])
@login_required
def add_payment(tour_id):
    tour = get_tour(tour_id)

    try:
        expense_id = int(request.form.get("expense_id", ""))
        paid_by_id = int(request.form.get("paid_by_id", ""))
        on_behalf_raw = request.form.get("on_behalf_of_id", "")
        on_behalf_of_id = int(on_behalf_raw) if on_behalf_raw else None
        paid_for_group_raw = request.form.get("paid_for_group_id", "")
        paid_for_group_id = int(paid_for_group_raw) if paid_for_group_raw else None
        amount = money(request.form.get("amount", "0"))
    except (TypeError, ValueError):
        flash("Please enter valid payment details.", "danger")
        return redirect(url_for("settlements.detail", tour_id=tour.id))

    expense = Expense.query.filter_by(id_Exp=expense_id, Id_Tour=tour.id).first_or_404()
    traveler_ids = {t.id for t in tour.travelers}
    group_filter = request.form.get("group_id")
    selected_group = None
    if group_filter and group_filter != "unassigned":
        try:
            selected_group_id = int(group_filter)
        except ValueError:
            flash("Invalid group selected.", "danger")
            return redirect(url_for("settlements.detail", tour_id=tour.id))
        selected_group = TravelerGroup.query.filter_by(id=selected_group_id, tour_id=tour.id).first()
        if not selected_group:
            flash("Invalid group selected.", "danger")
            return redirect(url_for("settlements.detail", tour_id=tour.id))

    if paid_by_id not in traveler_ids:
        flash("Invalid payer selected.", "danger")
        return redirect(url_for("settlements.detail", tour_id=tour.id))

    payer = db.session.get(Traveler, paid_by_id)
    if selected_group is not None and payer.group_id != selected_group.id:
        flash("The selected payer does not belong to the selected group.", "danger")
        return redirect(url_for("settlements.detail", tour_id=tour.id, group_id=selected_group.id))
    if group_filter == "unassigned" and payer.group_id is not None:
        flash("The selected payer does not belong to the unassigned group.", "danger")
        return redirect(url_for("settlements.detail", tour_id=tour.id, group_id="unassigned"))

    if on_behalf_of_id is not None and on_behalf_of_id not in traveler_ids:
        flash("Invalid 'on behalf of' traveler selected.", "danger")
        return redirect(url_for("settlements.detail", tour_id=tour.id))

    if paid_for_group_id is not None:
        paid_group = TravelerGroup.query.filter_by(id=paid_for_group_id, tour_id=tour.id).first()
        if not paid_group:
            flash("Invalid payment group selected.", "danger")
            return redirect(url_for("settlements.detail", tour_id=tour.id))
        # When a payment is explicitly for a group, it is valid for any actual
        # payer; this supports one person paying for an entire group.

    if amount <= ZERO:
        flash("Payment amount must be greater than ₹0.", "danger")
        return redirect(url_for("settlements.detail", tour_id=tour.id))

    already_paid = sum((money(p.amount) for p in expense.payments), ZERO)
    remaining = money(expense.amount) - already_paid
    if amount > remaining:
        flash(
            f"Payment exceeds this expense. Remaining payable: ₹{remaining:,.2f}.",
            "danger",
        )
        return redirect(url_for("settlements.detail", tour_id=tour.id))

    method = (request.form.get("method") or "UPI").strip()
    if method not in METHODS:
        method = "Other"

    note = (request.form.get("note") or "").strip() or None

    payment = ExpensePayment(
        expense=expense,
        paid_by_id=paid_by_id,
        on_behalf_of_id=on_behalf_of_id,
        paid_for_group_id=paid_for_group_id,
        amount=amount,
        method=method,
        note=note,
    )
    db.session.add(payment)
    db.session.commit()

    payer = db.session.get(Traveler, paid_by_id)
    beneficiary = db.session.get(Traveler, on_behalf_of_id) if on_behalf_of_id else None
    if paid_for_group_id:
        paid_group = db.session.get(TravelerGroup, paid_for_group_id)
        message = f"Payment added: {payer.name} paid ₹{amount:,.2f} for {paid_group.name}."
    elif beneficiary and beneficiary.id != payer.id:
        message = f"Payment added: {payer.name} paid ₹{amount:,.2f} on behalf of {beneficiary.name}."
    else:
        message = f"Payment added: {payer.name} paid ₹{amount:,.2f}."
    flash(message, "success")
    return redirect(url_for("settlements.detail", tour_id=tour.id))


@settlements.route("/payment/<int:payment_id>/delete", methods=["POST"])
@login_required
def delete_payment(payment_id):
    payment = (
        ExpensePayment.query
        .join(Expense, ExpensePayment.expense_id == Expense.id_Exp)
        .join(Tour, Expense.Id_Tour == Tour.id)
        .filter(ExpensePayment.id == payment_id, Tour.user_id == current_user.id)
        .first_or_404()
    )
    tour_id = payment.expense.Id_Tour
    db.session.delete(payment)
    db.session.commit()
    flash("Payment deleted.", "success")
    return redirect(url_for("settlements.detail", tour_id=tour_id))
