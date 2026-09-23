from decimal import Decimal
from datetime import time
import json
import os
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen


from flask import render_template, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy.orm import selectinload, joinedload

from app.extensions import db
from app.models import Tour, Expense, ItineraryItem, TravelerGroup
from app.tours import tours
from app.tours.forms import TourForm


# ---------------------------------
# Weather API helper
# ---------------------------------

WEATHER_API_BASE = "https://api.weatherapi.com/v1"


def _fetch_json(url, timeout=10):
    request = Request(
        url,
        headers={"User-Agent": "SafarLedger/1.0"}
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _weather_api_request(endpoint, params):
    """Call WeatherAPI.com from the Flask backend so the API key stays private."""
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("WEATHER_API_KEY is not configured")

    query = dict(params)
    query["key"] = api_key
    url = f"{WEATHER_API_BASE}/{endpoint}?{urlencode(query)}"
    return _fetch_json(url)


def _weather_query(location):
    """Make a place query safer for WeatherAPI without forcing every place into Himachal.

    Itinerary entries may include Chandigarh, Howrah, Manali, etc. Adding
    "Himachal Pradesh" to every item would incorrectly move non-Himachal
    locations. India is enough to disambiguate most short place names while
    preserving an explicitly supplied state/region.

    NOTE: this string is only a *hint*. WeatherAPI's `q` free-text search does
    a fuzzy, worldwide match and does not enforce the appended country -- see
    _resolve_place() / KNOWN_PLACES below for the actual fix to that problem.
    """
    value = (location or "").strip()
    if not value:
        return value

    lowered = value.casefold()
    if "india" in lowered or "himachal" in lowered:
        return value
    return f"{value}, India"


# ---------------------------------
# Reliable place resolution
# ---------------------------------
#
# Why this exists: WeatherAPI's `q=<free text>` search is fuzzy and global.
# Appending ", India" to a query like "Kaza" or "Kunzum Pass" is only a hint
# -- if there's no exact match inside India, WeatherAPI happily returns the
# closest *worldwide* text match instead (e.g. "Kaza" -> Balochistan,
# Pakistan; "Kunzum Pass" -> matches on the word "Pass" -> Tambacounda,
# Senegal; "Pin" -> Pin, Belgium). The country never gets enforced.
#
# The fix has two layers:
#   1. A small hardcoded lat/lon table for the fixed set of Spiti-circuit
#      stops this app actually uses. Coordinate queries ("q=32.22,78.07")
#      are unambiguous, so these can never resolve to the wrong country.
#   2. For anything not in that table, call the search/autocomplete
#      endpoint first, inspect the `country` field of each candidate, and
#      only accept a candidate whose country is in the allowed list. If
#      nothing in the allowed countries matches, the place is reported as
#      unresolved instead of silently showing a wrong-country result.
#
# Coordinates below are approximate (a few hundred metres to a couple of km)
# -- good enough for a weather lookup, but adjust if you have more precise
# values for a given stop.
KNOWN_PLACES = {
    "howrah": (22.5958, 88.2636, "Howrah, West Bengal, India"),
    "chandigarh": (30.7333, 76.7794, "Chandigarh, India"),
    "rampur": (31.4520, 77.6334, "Rampur Bushahr, Himachal Pradesh, India"),
    "nako": (31.8181, 78.6212, "Nako, Himachal Pradesh, India"),
    "tabo": (32.0950, 78.3675, "Tabo, Himachal Pradesh, India"),
    "pin valley": (31.9500, 78.1500, "Pin Valley, Himachal Pradesh, India"),
    "pin": (31.9500, 78.1500, "Pin Valley, Himachal Pradesh, India"),
    "kaza": (32.2246, 78.0723, "Kaza, Himachal Pradesh, India"),
    "kunzum pass": (32.4167, 77.6167, "Kunzum Pass, Himachal Pradesh, India"),
    "chandratal": (32.4818, 77.6142, "Chandratal, Himachal Pradesh, India"),
    "batal": (32.3667, 77.5667, "Batal, Himachal Pradesh, India"),
    "atal tunnel": (32.3701, 77.2467, "Atal Tunnel, Himachal Pradesh, India"),
    "manali": (32.2432, 77.1892, "Manali, Himachal Pradesh, India"),
    "spiti valley": (32.2464, 78.0349, "Spiti Valley, Himachal Pradesh, India"),
}

# When a resolved candidate's country isn't in this list, it's rejected
# rather than silently used. Extend this if the itinerary legitimately
# crosses into other countries.
ALLOWED_WEATHER_COUNTRIES = {"india"}


def _known_place_lookup(name):
    """Look up a normalised place name in KNOWN_PLACES, trying a couple of
    light variants (strip punctuation, drop a trailing 'valley'/'pass' etc.
    is intentionally NOT done here to avoid re-introducing fuzzy matching --
    only exact/near-exact keys are accepted)."""
    key = re.sub(r"\s+", " ", (name or "").strip().casefold())
    key = key.strip(" .,")
    return KNOWN_PLACES.get(key)


def _search_candidates(query):
    """Call WeatherAPI's search/autocomplete endpoint, which returns a list
    of candidate locations each with their own country field -- unlike
    forecast.json/current.json, this lets us actually check the country
    before trusting a match."""
    try:
        results = _weather_api_request("search.json", {"q": query})
    except Exception:
        return []
    return results if isinstance(results, list) else []


def _resolve_place(raw_name, allowed_countries=ALLOWED_WEATHER_COUNTRIES):
    """Resolve a free-text itinerary place name to a trustworthy WeatherAPI
    query string, guaranteeing (as far as possible) it's in an allowed
    country instead of a same-named place elsewhere in the world.

    Returns (query_for_api, display_name) on success, or None if nothing
    could be confidently resolved within the allowed countries.
    """
    name = (raw_name or "").strip()
    if not name:
        return None

    # 1. Known Spiti-circuit stop -> exact coordinates, can't be wrong.
    known = _known_place_lookup(name)
    if known:
        lat, lon, display_name = known
        return f"{lat},{lon}", display_name

    # 2. Otherwise ask the search/autocomplete endpoint for candidates and
    #    keep only ones whose country matches. This is the step the old
    #    code skipped entirely -- it just trusted forecast.json's fuzzy
    #    match, which is how Pin/Kaza/Pass/etc. ended up in the wrong
    #    country.
    for candidate_query in (f"{name}, India", name):
        candidates = _search_candidates(candidate_query)
        for candidate in candidates:
            country = (candidate.get("country") or "").casefold()
            if country in allowed_countries:
                lat = candidate.get("lat")
                lon = candidate.get("lon")
                if lat is None or lon is None:
                    continue
                display_name = candidate.get("name") or name
                region = candidate.get("region")
                if region:
                    display_name = f"{display_name}, {region}, {candidate.get('country')}"
                return f"{lat},{lon}", display_name
        if candidates:
            # We got candidates but none were in an allowed country --
            # no point trying the looser query variant too.
            break

    return None


def _title_weather_places(title):
    """Extract weatherable place names from an itinerary title when location is blank.

    Many existing SafarLedger itinerary rows put the route directly in the
    title (for example, "Nako → Tabo") and leave the separate Location field
    empty. Older data should still drive itinerary-based weather, so route
    arrows are treated as place separators.
    """
    value = (title or "").strip()
    if not value:
        return []

    # Prefer route titles: A → B → C / A -> B -> C.
    if "→" in value or "->" in value:
        parts = re.split(r"\s*(?:→|->)\s*", value)
        places = []
        for part in parts:
            cleaned = re.split(r"\s+[—–-]\s+", part, maxsplit=1)[0].strip()
            cleaned = re.sub(r"^arrive\s+", "", cleaned, flags=re.IGNORECASE).strip()
            if cleaned:
                places.append(cleaned)
        return places

    # Common non-route title patterns used in the existing itinerary.
    cleaned = re.sub(
        r"\s*(?:/\s*)?(?:local\s+)?sightseeing(?:\s+tour)?$|\s*(?:/\s*)?return\s+journey$",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()
    if cleaned and cleaned.casefold() not in {"on the train", "train"}:
        return [cleaned]
    return []


def _condition_icon(condition, is_day=True):
    text = (condition or "").casefold()
    if "thunder" in text:
        return "⛈️"
    if "snow" in text or "sleet" in text or "ice" in text or "blizzard" in text:
        return "❄️"
    if "rain" in text or "drizzle" in text or "shower" in text:
        return "🌧️"
    if "fog" in text or "mist" in text:
        return "🌫️"
    if "cloud" in text or "overcast" in text:
        return "⛅"
    return "☀️" if is_day else "🌙"


def _normalise_weather_place(data, requested_name, itinerary_dates, fallback_from=None,
                              resolved_display_name=None):
    """resolved_display_name, when given, is the name _resolve_place() already
    worked out for this stop (from KNOWN_PLACES or a country-filtered search
    candidate). It takes priority over WeatherAPI's own location.name because
    WeatherAPI reverse-geocodes lat/lon queries to the nearest place *it*
    has in its database -- for remote Himalayan stops that's often a
    different village a few km away (e.g. Howrah -> "Nibria", Nako ->
    "Namgia"), not the place actually requested.
    """
    location = data.get("location") or {}
    current = data.get("current") or {}
    condition = (current.get("condition") or {}).get("text") or "Unknown"

    forecast = []
    forecast_days = (data.get("forecast") or {}).get("forecastday") or []
    for day in forecast_days:
        day_data = day.get("day") or {}
        day_condition = (day_data.get("condition") or {}).get("text") or "Unknown"
        forecast.append({
            "date": day.get("date"),
            "condition": day_condition,
            "code": (day_data.get("condition") or {}).get("code"),
            "icon": _condition_icon(day_condition, True),
            "max": day_data.get("maxtemp_c"),
            "min": day_data.get("mintemp_c"),
            "rain_probability": day_data.get("daily_chance_of_rain"),
            "rain_mm": day_data.get("totalprecip_mm"),
        })

    return {
        "requested_name": requested_name,
        "name": resolved_display_name or location.get("name") or requested_name,
        "admin1": location.get("region"),
        "country": location.get("country"),
        "country_code": None,
        "latitude": location.get("lat"),
        "longitude": location.get("lon"),
        "itinerary_dates": itinerary_dates,
        "fallback_from": fallback_from,
        "current": {
            "temperature": current.get("temp_c"),
            "feels_like": current.get("feelslike_c"),
            "humidity": current.get("humidity"),
            "wind": current.get("wind_kph"),
            "condition": condition,
            "code": (current.get("condition") or {}).get("code"),
            "icon": _condition_icon(condition, current.get("is_day", 1) == 1),
            "last_updated": current.get("last_updated"),
        },
        "forecast": forecast,
    }


@tours.route("/<int:tour_id>/weather")
@login_required
def weather(tour_id):
    """Return WeatherAPI.com weather for itinerary places or Spiti fallback."""
    tour = Tour.query.filter_by(
        id=tour_id,
        user_id=current_user.id
    ).first_or_404()

    try:
        itinerary_items = (
            ItineraryItem.query
            .filter_by(tour_id=tour.id)
            .order_by(
                ItineraryItem.itinerary_date.asc(),
                ItineraryItem.sort_order.asc(),
                ItineraryItem.time.asc().nullslast(),
                ItineraryItem.id.asc()
            )
            .all()
        )

        places = []
        seen = set()

        for item in itinerary_items:
            # Use the dedicated Location field when present. For existing
            # itineraries where Location was left blank, fall back to route
            # names embedded in the title so itinerary weather still works.
            item_locations = []
            location = (item.location or "").strip()
            if location:
                item_locations = [location]
            else:
                item_locations = _title_weather_places(item.title)

            date = item.itinerary_date.isoformat()
            for item_location in item_locations:
                key = item_location.casefold()
                if key not in seen:
                    seen.add(key)
                    places.append({"query": item_location, "dates": [date]})
                else:
                    for place in places:
                        if place["query"].casefold() == key and date not in place["dates"]:
                            place["dates"].append(date)
                            break

        mode = "itinerary"

        # No itinerary locations: use an explicit Spiti Valley location when
        # the destination is Spiti, rather than a generic geocoder search.
        if not places:
            destination = (tour.destination or "").strip()
            if not destination:
                return jsonify({
                    "ok": False,
                    "message": "Add a destination or itinerary location before loading weather."
                }), 400

            if "spiti" in destination.casefold():
                query = "Spiti Valley, Himachal Pradesh, India"
            else:
                query = _weather_query(destination)

            places = [{
                "query": query,
                "dates": [],
                "fallback_from": destination if query.casefold() != destination.casefold() else None,
            }]
            mode = "destination"

        weather_places = []
        unresolved = []

        for requested_place in places:
            # Resolve to a country-verified lat/lon query instead of
            # trusting WeatherAPI's fuzzy free-text search -- see
            # _resolve_place() for why this matters.
            resolved = _resolve_place(requested_place["query"])
            if resolved is None:
                unresolved.append(requested_place["query"])
                continue
            query, resolved_display_name = resolved

            try:
                if mode == "destination":
                    # The no-itinerary fallback is intentionally current-weather
                    # only, as requested.
                    data = _weather_api_request(
                        "current.json",
                        {"q": query, "aqi": "no"},
                    )
                else:
                    # For itinerary locations, also return the short forecast
                    # window available to the account.
                    data = _weather_api_request(
                        "forecast.json",
                        {
                            "q": query,
                            "days": 3,
                            "aqi": "no",
                            "alerts": "no",
                        },
                    )
            except Exception:
                unresolved.append(requested_place["query"])
                continue

            if not data.get("location") or not data.get("current"):
                unresolved.append(requested_place["query"])
                continue

            weather_places.append(
                _normalise_weather_place(
                    data,
                    requested_place["query"],
                    requested_place["dates"],
                    requested_place.get("fallback_from"),
                    resolved_display_name=resolved_display_name,
                )
            )

        if not weather_places:
            message = "Could not find weather for the requested location."
            if unresolved:
                message += " Unresolved: " + ", ".join(unresolved) + "."
            return jsonify({"ok": False, "message": message}), 404

        return jsonify({
            "ok": True,
            "mode": mode,
            "places": weather_places,
            "unresolved": unresolved,
            "trip_dates": {
                "start": tour.start_date.isoformat(),
                "end": tour.end_date.isoformat(),
            },
            "forecast_note": (
                "Live weather is provided by WeatherAPI.com. Weather is fetched "
                "separately for every itinerary location; when no itinerary location "
                "exists, Spiti Valley is used as the default location for Spiti trips. "
                "The forecast shown is the currently available forecast window."
            ),
        })

    except Exception:
        return jsonify({
            "ok": False,
            "message": "Weather service is temporarily unavailable. Please try again."
        }), 502

# ---------------------------------
# View All Tours
# ---------------------------------

@tours.route("/")
@login_required
def list_tours():
    tours_list = (
        Tour.query
        .filter_by(user_id=current_user.id)
        .order_by(Tour.start_date.desc())
        .all()
    )

    # Quick per-person / per-person-per-day estimate (budget-based)
    # for the trip cards.
    per_person_estimates = {}

    for tour in tours_list:
        people = tour.number_of_people or 0
        days = tour.number_of_days or 0
        budget = tour.budget or Decimal("0")

        per_person = (budget / people) if people else Decimal("0")
        per_person_per_day = (
            per_person / days
            if days
            else Decimal("0")
        )

        per_person_estimates[tour.id] = {
            "per_person": per_person,
            "per_person_per_day": per_person_per_day
        }

    return render_template(
        "tours/list.html",
        tours=tours_list,
        per_person_estimates=per_person_estimates
    )


# ---------------------------------
# Create New Tour
# ---------------------------------

@tours.route("/create", methods=["GET", "POST"])
@login_required
def create():
    form = TourForm()

    if form.validate_on_submit():
        number_of_days = (
            form.end_date.data - form.start_date.data
        ).days + 1

        tour = Tour(
            tour_name=form.name.data,
            destination=form.destination.data,
            start_date=form.start_date.data,
            end_date=form.end_date.data,
            number_of_people=form.number_of_people.data,
            number_of_days=number_of_days,
            budget=form.budget.data or 0,
            user_id=current_user.id
        )

        db.session.add(tour)
        db.session.commit()

        flash("Trip created successfully!", "success")
        return redirect(url_for("tours.list_tours"))

    return render_template(
        "tours/create.html",
        form=form
    )


# ---------------------------------
# View Tour Details
# ---------------------------------

@tours.route("/<int:tour_id>")
@login_required
def detail(tour_id):
    # The details page needs several related collections. Load them in
    # batches instead of triggering one query per expense/traveler/item.
    tour = (
        Tour.query
        .options(
            selectinload(Tour.travelers),
            selectinload(Tour.traveler_groups).selectinload(TravelerGroup.travelers),
            selectinload(Tour.expenses).options(
                joinedload(Expense.category),
                selectinload(Expense.participants),
            ),
            selectinload(Tour.itinerary_items).joinedload(ItineraryItem.category),
        )
        .filter_by(id=tour_id, user_id=current_user.id)
        .first_or_404()
    )

    expenses = sorted(
        tour.expenses,
        key=lambda expense: expense.created_at,
        reverse=True,
    )
    itinerary_items = sorted(
        tour.itinerary_items,
        key=lambda item: (
            item.itinerary_date,
            item.sort_order,
            item.time or time.min,
            item.id,
        ),
    )

    itinerary_estimated_total = sum(
        (item.estimated_cost or Decimal("0"))
        for item in itinerary_items
    )

    # Expenses are already loaded for the page, so don't issue a second
    # database query just to calculate the same total.
    total_spent = sum(
        (expense.amount or Decimal("0")) for expense in expenses
    )

    # ---------------------------------
    # Actual number of days with expenses
    #
    # Example:
    # Trip duration = 11 days
    # Expenses entered on 2 different dates
    # Result = 2
    # ---------------------------------

    expense_days = len({
        expense.expense_date
        for expense in expenses
        if expense.expense_date
    })

    # ---------------------------------
    # Remaining budget
    # ---------------------------------

    remaining_budget = (
        tour.budget or Decimal("0")
    ) - total_spent

    # ---------------------------------------------------------
    # Per-person / per-person-per-day cost
    #
    # Use actual spend once expenses have been logged.
    # Fall back to planned budget when there are no expenses.
    # ---------------------------------------------------------

    cost_basis = (
        total_spent
        if total_spent and total_spent > 0
        else (tour.budget or Decimal("0"))
    )

    cost_basis_label = (
        "Actual Spend"
        if total_spent and total_spent > 0
        else "Budget Estimate"
    )

    people = tour.number_of_people or 0
    days = tour.number_of_days or 0

    per_person_cost = (
        cost_basis / people
        if people
        else Decimal("0")
    )

    per_person_per_day_cost = (
        per_person_cost / days
        if days
        else Decimal("0")
    )

    # ---------------------------------------------------------
    # Per-traveler cost breakdown
    #
    # Each expense is split only among chargeable travelers
    # (age >= 10) who are marked as participants.
    #
    # Age < 10:
    #   Always free / never billed.
    #
    # No participants recorded:
    #   Falls back to an even split across chargeable travelers.
    # ---------------------------------------------------------

    traveler_totals = {
        traveler.id: Decimal("0")
        for traveler in tour.travelers
    }

    unallocated_amount = Decimal("0")

    chargeable_travelers = [
        traveler
        for traveler in tour.travelers
        if traveler.is_chargeable
    ]

    for expense in expenses:

        # ---------------------------------
        # Expense has participants
        # ---------------------------------

        if expense.participants:

            chargeable_participants = [
                participant
                for participant in expense.participants
                if participant.is_chargeable
            ]

            if chargeable_participants:
                share = (
                    expense.amount /
                    len(chargeable_participants)
                )

                for participant in chargeable_participants:
                    traveler_totals[participant.id] += share

            else:
                # Everyone tagged on this expense
                # is a free traveler.
                unallocated_amount += expense.amount

        # ---------------------------------
        # No participants recorded
        # ---------------------------------

        elif chargeable_travelers:

            share = (
                expense.amount /
                len(chargeable_travelers)
            )

            for traveler in chargeable_travelers:
                traveler_totals[traveler.id] += share

        else:
            unallocated_amount += expense.amount

    # ---------------------------------
    # Prepare traveler cost table
    # ---------------------------------

    traveler_costs = [
        {
            "traveler": traveler,
            "amount": traveler_totals[traveler.id]
        }
        for traveler in sorted(
            tour.travelers,
            key=lambda traveler: traveler.name.lower()
        )
    ]

    # ---------------------------------
    # Render page
    # ---------------------------------

    return render_template(
        "tours/details.html",
        tour=tour,
        expenses=expenses,
        total_spent=total_spent,

        # IMPORTANT:
        # This is the number of actual dates
        # on which expenses were recorded.
        expense_days=expense_days,

        remaining_budget=remaining_budget,

        per_person_cost=per_person_cost,
        per_person_per_day_cost=per_person_per_day_cost,
        cost_basis_label=cost_basis_label,

        traveler_costs=traveler_costs,
        unallocated_amount=unallocated_amount,
        itinerary_items=itinerary_items,
        itinerary_estimated_total=itinerary_estimated_total
    )


# ---------------------------------
# Edit Tour
# ---------------------------------

@tours.route("/<int:tour_id>/edit", methods=["GET", "POST"])
@login_required
def edit(tour_id):
    # Get the tour and ensure it belongs to the current user
    tour = Tour.query.filter_by(
        id=tour_id,
        user_id=current_user.id
    ).first_or_404()

    form = TourForm(
        obj=tour,
        name=tour.tour_name
    )

    if form.validate_on_submit():
        tour.tour_name = form.name.data
        tour.destination = form.destination.data
        tour.start_date = form.start_date.data
        tour.end_date = form.end_date.data
        tour.number_of_people = form.number_of_people.data

        tour.number_of_days = (
            form.end_date.data - form.start_date.data
        ).days + 1

        tour.budget = form.budget.data or 0

        db.session.commit()

        flash("Trip updated successfully!", "success")
        return redirect(
            url_for(
                "tours.detail",
                tour_id=tour.id
            )
        )

    return render_template(
        "tours/edit.html",
        form=form,
        tour=tour
    )


# ---------------------------------
# Delete Tour
# ---------------------------------

@tours.route("/<int:tour_id>/delete", methods=["POST"])
@login_required
def delete(tour_id):
    # Get the tour and ensure it belongs to the current user
    tour = Tour.query.filter_by(
        id=tour_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(tour)
    db.session.commit()

    flash("Trip deleted successfully!", "success")
    return redirect(
        url_for("tours.list_tours")
    )