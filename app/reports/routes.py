from collections import defaultdict
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from flask import render_template, request, send_file
from flask_login import current_user, login_required
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether,
)

from sqlalchemy.orm import selectinload, joinedload

from app.models import Tour, TravelerGroup, Expense, ItineraryItem
from app.models.expense_payment import ExpensePayment
from app.settlements.routes import calculate_settlement
from app.reports import reports


SECTIONS = [
    ("overview", "Trip Overview", "Dates, destination, budget, spending and trip duration"),
    ("travelers", "Travelers", "Traveler names, ages and traveler type"),
    ("itinerary", "Complete Itinerary", "Dates, times, locations, categories and descriptions"),
    ("expenses", "Expense Summary", "Every recorded expense with date, category and amount"),
    ("categories", "Category-wise Expenses", "Spending grouped by expense category"),
    ("daily", "Daily Spending", "Total spending grouped by expense date"),
    ("traveler_cost", "Per-Traveler Cost", "Expense share assigned to each traveler"),
    ("settlement", "Settlement Summary", "Traveler balances and suggested transfers"),
    ("payments", "Payment Records", "Recorded payments, payer, method and notes"),
]


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def get_tour(tour_id):
    return Tour.query.filter_by(id=tour_id, user_id=current_user.id).first_or_404()


def get_report_tour(tour_id):
    # PDF generation walks nearly every trip relationship. Load those
    # collections in batches so it does not issue one query per
    # expense, participant, payment, or itinerary category.
    return (
        Tour.query
        .options(
            selectinload(Tour.travelers),
            selectinload(Tour.traveler_groups).selectinload(TravelerGroup.travelers),
            selectinload(Tour.expenses).options(
                joinedload(Expense.category),
                selectinload(Expense.participants),
                selectinload(Expense.payments).options(
                    joinedload(ExpensePayment.paid_by),
                    joinedload(ExpensePayment.on_behalf_of),
                    joinedload(ExpensePayment.paid_for_group),
                ),
            ),
            selectinload(Tour.itinerary_items).joinedload(ItineraryItem.category),
        )
        .filter_by(id=tour_id, user_id=current_user.id)
        .first_or_404()
    )


def selected_sections(form):
    selected = {key for key, _, _ in SECTIONS if form.get(key) == "on"}
    return selected


def build_group_report_data(tour, group):
    all_data = build_report_data(tour)
    group_ids = {t.id for t in group.travelers}
    balances = [row for row in all_data["balances"] if row["traveler"].id in group_ids]
    share_by_id = {row["traveler"].id: row["share"] for row in balances}

    # Allocate each expense to the group using the same participant rules as settlement.
    group_expenses = []
    group_category_totals = defaultdict(Decimal)
    group_daily_totals = defaultdict(Decimal)
    group_total = Decimal("0.00")
    for expense in all_data["expenses"]:
        participants = [p for p in expense.participants if p.is_chargeable] if expense.participants else [t for t in tour.travelers if t.is_chargeable]
        if not participants:
            continue
        amount = money(expense.amount)
        count = len(participants)
        base = (amount / count).quantize(Decimal("0.01"))
        remainder = amount - (base * count)
        allocated = Decimal("0.00")
        for index, traveler in enumerate(sorted(participants, key=lambda x: x.id)):
            share = base + (remainder if index == count - 1 else Decimal("0.00"))
            if traveler.id in group_ids:
                allocated += share
        allocated = money(allocated)
        if allocated > 0:
            group_expenses.append((expense, allocated))
            group_category_totals[expense.category.Cat_Desc if expense.category else "Other"] += allocated
            group_daily_totals[expense.expense_date] += allocated
            group_total += allocated

    group_paid = sum((money(row["paid"]) for row in balances), Decimal("0.00"))
    group_balance = money(group_paid - group_total)
    return {
        **all_data,
        "travelers": sorted(group.travelers, key=lambda t: (t.name.lower(), t.id)),
        "expenses": [e for e, _ in group_expenses],
        "group_expenses": group_expenses,
        "total_spent": money(group_total),
        "remaining": money(tour.budget) - money(group_total),
        "category_totals": sorted(group_category_totals.items(), key=lambda x: (-x[1], x[0].lower())),
        "daily_totals": sorted(group_daily_totals.items(), key=lambda x: x[0]),
        "balances": balances,
        "share_by_id": share_by_id,
        "group_paid": group_paid,
        "group_balance": group_balance,
        "transfers": [],
    }


def build_report_data(tour):
    expenses = sorted(tour.expenses, key=lambda e: (e.expense_date, e.id_Exp))
    travelers = sorted(tour.travelers, key=lambda t: (t.name.lower(), t.id))
    itinerary = sorted(tour.itinerary_items, key=lambda i: (i.itinerary_date, i.sort_order, i.time or 0, i.id))
    total_spent = sum((money(e.amount) for e in expenses), Decimal("0.00"))
    remaining = money(tour.budget) - total_spent

    category_totals = defaultdict(Decimal)
    daily_totals = defaultdict(Decimal)
    for expense in expenses:
        category_totals[expense.category.Cat_Desc if expense.category else "Other"] += money(expense.amount)
        daily_totals[expense.expense_date] += money(expense.amount)

    balances, transfers = calculate_settlement(tour)
    share_by_id = {row["traveler"].id: row["share"] for row in balances}

    return {
        "expenses": expenses,
        "travelers": travelers,
        "itinerary": itinerary,
        "total_spent": total_spent,
        "remaining": remaining,
        "category_totals": sorted(category_totals.items(), key=lambda x: (-x[1], x[0].lower())),
        "daily_totals": sorted(daily_totals.items(), key=lambda x: x[0]),
        "balances": balances,
        "transfers": transfers,
        "share_by_id": share_by_id,
    }


def P(text, style):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def build_pdf(tour, selected, group=None):
    data = build_group_report_data(tour, group) if group else build_report_data(tour)
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=f"{tour.tour_name} - SafarLedger Trip Report",
        author="SafarLedger",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=23, leading=28, alignment=TA_CENTER, spaceAfter=5*mm)
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=11, textColor=colors.HexColor("#666666"), alignment=TA_CENTER, spaceAfter=8*mm)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, leading=20, textColor=colors.HexColor("#0d2f6b"), spaceBefore=4*mm, spaceAfter=3*mm)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#0d2f6b"), spaceBefore=3*mm, spaceAfter=2*mm)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("Small", parent=body, fontSize=8, textColor=colors.HexColor("#666666"))
    table_head = ParagraphStyle("TableHead", parent=body, fontName="Helvetica-Bold", textColor=colors.white)

    story = [P("SafarLedger", title), P("Trip Report" if not group else "Group Report", subtitle), P(tour.tour_name, h1)]
    story.append(P(tour.destination if not group else f"{tour.destination} • {group.name}", subtitle))

    if "overview" in selected:
        story += [P("Trip Overview", h1)]
        overview = [
            [P("Destination", body), P(tour.destination, body)],
            [P("Dates", body), P(f"{tour.start_date.strftime('%d %b %Y')} – {tour.end_date.strftime('%d %b %Y')}", body)],
            [P("Trip Days", body), P(tour.number_of_days, body)],
            [P("Planned Travelers", body), P(tour.number_of_people, body)],
            [P("Budget", body), P(f"₹{money(tour.budget):,.2f}", body)],
            [P("Total Spent", body), P(f"₹{data['total_spent']:,.2f}", body)],
            [P("Group Spend" if group else "Remaining", body), P(f"₹{data['total_spent']:,.2f}" if group else f"₹{data['remaining']:,.2f}", body)],
            [P("Expense Days", body), P(len(data['daily_totals']), body)],
            *([[P("Group Paid", body), P(f"₹{data['group_paid']:,.2f}", body)], [P("Group Balance", body), P(f"₹{data['group_balance']:,.2f}", body)]] if group else []),
        ]
        t = Table(overview, colWidths=[45*mm, 125*mm])
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#f7f9fc")), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#d9dee7")), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("BOTTOMPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 6)]))
        story.append(t)
        story.append(Spacer(1, 3*mm))

    if "travelers" in selected:
        story += [P("Travelers", h1)]
        rows = [[P("Name", table_head), P("Age", table_head), P("Type", table_head)]]
        for tr in data["travelers"]:
            rows.append([P(tr.name, body), P(tr.age, body), P(tr.traveler_type, body)])
        t = Table(rows, colWidths=[95*mm, 25*mm, 50*mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0d2f6b")), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#d9dee7")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7f9fc")]), ("VALIGN", (0,0), (-1,-1), "MIDDLE")]))
        story.append(t)

    if "itinerary" in selected:
        story += [P("Trip Itinerary", h1)]
        if not data["itinerary"]:
            story.append(P("No itinerary items have been added.", small))
        else:
            for item in data["itinerary"]:
                time_text = item.time.strftime("%I:%M %p") if item.time else "Any time"
                heading = f"{item.itinerary_date.strftime('%d %b %Y')} • {time_text} • {item.title}"
                story.append(P(heading, h2))
                details = []
                if item.location: details.append(f"Location: {item.location}")
                if item.category: details.append(f"Category: {item.category.Cat_Desc}")
                if item.estimated_cost is not None: details.append(f"Estimated cost: ₹{money(item.estimated_cost):,.2f}")
                if item.description: details.append(item.description)
                if details: story.append(P(" • ".join(details), body))

    if "expenses" in selected:
        story.append(PageBreak())
        story += [P("Expense Summary", h1)]
        rows = [[P("Date", table_head), P("Category", table_head), P("Description", table_head), P("Amount", table_head)]]
        expense_rows = data.get("group_expenses", [(e, money(e.amount)) for e in data["expenses"]])
        for e, allocated in expense_rows:
            rows.append([P(e.expense_date.strftime("%d %b %Y"), body), P(e.category.Cat_Desc if e.category else "Other", body), P(e.description or e.expense_type or "—", body), P(f"₹{allocated:,.2f}", body)])
        if len(rows) == 1: rows.append([P("No expenses recorded.", body), "", "", ""])
        t = Table(rows, colWidths=[29*mm, 35*mm, 75*mm, 31*mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0d2f6b")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#d9dee7")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7f9fc")]), ("ALIGN", (-1,1), (-1,-1), "RIGHT")]))
        story.append(t)

    if "categories" in selected:
        story += [P("Category-wise Expenses", h1)]
        rows = [[P("Category", table_head), P("Total", table_head)]] + [[P(k, body), P(f"₹{v:,.2f}", body)] for k,v in data["category_totals"]]
        t = Table(rows, colWidths=[120*mm, 50*mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0d2f6b")), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#d9dee7")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7f9fc")]), ("ALIGN", (1,1), (1,-1), "RIGHT")]))
        story.append(t)

    if "daily" in selected:
        story += [P("Daily Spending", h1)]
        rows = [[P("Date", table_head), P("Total", table_head)]] + [[P(d.strftime("%d %b %Y"), body), P(f"₹{v:,.2f}", body)] for d,v in data["daily_totals"]]
        t = Table(rows, colWidths=[120*mm, 50*mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0d2f6b")), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#d9dee7")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7f9fc")]), ("ALIGN", (1,1), (1,-1), "RIGHT")]))
        story.append(t)

    if "traveler_cost" in selected:
        story += [P("Per-Traveler Cost", h1)]
        rows = [[P("Traveler", table_head), P("Age", table_head), P("Type", table_head), P("Amount Owed", table_head)]]
        for tr in data["travelers"]:
            if tr.is_chargeable:
                amount = data["share_by_id"].get(tr.id, Decimal("0.00"))
                amount_text = f"₹{amount:,.2f}"
            else:
                amount_text = "Free"
            rows.append([P(tr.name, body), P(tr.age, body), P(tr.traveler_type, body), P(amount_text, body)])
        t = Table(rows, colWidths=[75*mm, 25*mm, 35*mm, 35*mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0d2f6b")), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#d9dee7")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7f9fc")]), ("ALIGN", (-1,1), (-1,-1), "RIGHT")]))
        story.append(t)

    if "settlement" in selected:
        story += [P("Settlement Summary", h1)]
        rows = [[P("Traveler", table_head), P("Share", table_head), P("Paid", table_head), P("Balance", table_head)]]
        for row in data["balances"]:
            rows.append([P(row["traveler"].name, body), P(f"₹{row['share']:,.2f}", body), P(f"₹{row['paid']:,.2f}", body), P(f"₹{row['balance']:,.2f}", body)])
        t = Table(rows, colWidths=[75*mm, 32*mm, 32*mm, 31*mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0d2f6b")), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#d9dee7")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7f9fc")]), ("ALIGN", (1,1), (-1,-1), "RIGHT")]))
        story.append(t)
        if data["transfers"]:
            story.append(P("Suggested Transfers", h2))
            for tr in data["transfers"]:
                story.append(P(f"{tr['from'].name} → {tr['to'].name}: ₹{tr['amount']:,.2f}", body))
        else:
            story.append(P("No outstanding transfers are currently calculated.", small))

    if "payments" in selected:
        story += [P("Payment Records", h1)]
        rows = [[P("Date", table_head), P("Expense", table_head), P("Paid by", table_head), P("On behalf of", table_head), P("Method", table_head), P("Amount", table_head)]]
        for e in data["expenses"]:
            for payment in e.payments:
                created = payment.created_at.strftime("%d %b %Y") if payment.created_at else "—"
                beneficiary = (f"Entire {payment.paid_for_group.name}" if payment.paid_for_group else (payment.on_behalf_of.name if payment.on_behalf_of else "—"))
                rows.append([P(created, body), P(e.description or e.expense_type or "Expense", body), P(payment.paid_by.name, body), P(beneficiary, body), P(payment.method, body), P(f"₹{money(payment.amount):,.2f}", body)])
        if len(rows) == 1: rows.append([P("No payment records.", body), "", "", "", "", ""])
        t = Table(rows, colWidths=[23*mm, 39*mm, 32*mm, 32*mm, 27*mm, 27*mm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0d2f6b")), ("GRID", (0,0), (-1,-1), .3, colors.HexColor("#d9dee7")), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f7f9fc")]), ("ALIGN", (-1,1), (-1,-1), "RIGHT")]))
        story.append(t)

    story.append(Spacer(1, 8*mm))
    story.append(P("Generated by SafarLedger", small))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawCentredString(A4[0]/2, 8*mm, f"SafarLedger • {tour.tour_name} • Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    buf.seek(0)
    return buf


@reports.route("/tour/<int:tour_id>")
@login_required
def builder(tour_id):
    tour = get_tour(tour_id)
    group_id = request.args.get("group_id", type=int)
    group = next((g for g in tour.traveler_groups if g.id == group_id), None) if group_id else None
    if group_id and not group:
        return "Group not found", 404
    return render_template("reports/builder.html", tour=tour, sections=SECTIONS, groups=sorted(tour.traveler_groups, key=lambda g: (g.name.lower(), g.id)), selected_group=group)


@reports.route("/tour/<int:tour_id>/generate", methods=["POST"])
@login_required
def generate(tour_id):
    tour = get_report_tour(tour_id)
    selected = selected_sections(request.form)
    group_id = request.form.get("group_id", type=int)
    group = next((g for g in tour.traveler_groups if g.id == group_id), None) if group_id else None
    if group_id and not group:
        return "Group not found", 404
    if not selected:
        return render_template("reports/builder.html", tour=tour, sections=SECTIONS, groups=sorted(tour.traveler_groups, key=lambda g: (g.name.lower(), g.id)), selected_group=group, error="Select at least one section before generating the report."), 400
    pdf = build_pdf(tour, selected, group=group)
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in tour.tour_name).strip() or "Trip"
    if group:
        group_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in group.name).strip() or "Group"
        filename = f"{safe_name}_{group_name}_Report.pdf"
    else:
        filename = f"{safe_name}_Trip_Report.pdf"
    return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=filename)
