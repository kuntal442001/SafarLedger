# SafarLedger

A Flask web app for tour operators to track trips and their expenses against a budget.

## Features

- User registration and login (Flask-Login + hashed passwords)
- Dashboard with total trips, active trips, total budget, total spending, and recent trips
- Create, view, edit, and delete trips (with destination, dates, headcount, and budget)
- Add, edit, and delete expenses against a trip (date, category, type, description, no. of persons, days, amount)
- Trip itinerary with activities grouped automatically by each trip day
- Itinerary activities use categories directly from the existing `Mast_Categories` table
- Trip weather with destination geocoding, current conditions, 7-day forecast, rain probability, and wind/humidity details
- Itinerary activity time, location, notes, and estimated cost tracking
- Automatic budget vs. spending calculation per trip and across all trips
- Each user only ever sees their own trips and expenses

## Tech Stack

- Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF
- PostgreSQL
- Bootstrap 5 (via CDN) for the trip/expense pages

## Setup

1. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # macOS/Linux
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a PostgreSQL database named `safarledger` (or update `DATABASE_URL` below).

4. Copy `.env.example` to `.env` and fill in real values:
   ```
   SECRET_KEY=some-random-secret-key
   DATABASE_URL=postgresql://username:password@localhost:5432/safarledger
   ```

5. Apply database migrations:
   ```
   flask --app run db upgrade
   ```

6. Run the app:
   ```
   python run.py
   ```

7. Open http://127.0.0.1:5000/auth/register to create an account.

## Project Structure

```
app/
  auth/        - registration, login, logout
  dashboard/   - overview page with summary stats
  tours/       - trip CRUD
  expenses/    - expense CRUD (scoped to a trip)
  itinerary/   - trip itinerary and activity CRUD
  models/      - User, Tour, Expense, Traveler, MastCategory, ItineraryItem
  templates/   - Jinja templates per blueprint
  static/      - CSS/JS assets
migrations/    - Alembic migration scripts
tests/         - pytest test scaffolding
```

## Traveler Settlement

The app includes a per-trip settlement page at `/settlement/tour/<tour_id>`.
Payments record the traveler who actually paid and can optionally record who the
payment was made **on behalf of**. This keeps cases such as “Shantanu paid ₹500
for Madhushree” explicit while settlement still calculates the final net amount
from each traveler's share versus money actually paid.

Run the latest migration with:

```bash
flask --app run db upgrade
```


## Traveler Groups

SafarLedger now supports generic traveler groups per trip. Groups are not tied to families; they can represent any logical set of travelers (Group 1, Group 2, Friends, Office, etc.).

### What is included
- Create, rename, and delete groups.
- Assign or unassign travelers from the Travelers form or Groups page.
- Unassigned travelers remain valid trip travelers.
- Trip Details shows a Traveler Groups section.
- Group Reports can be generated from the existing Report Builder.
- Group expense amounts are allocated using the same participant and under-10 billing rules used by settlement.
- Existing expense and settlement behavior is preserved.

### Database update
After replacing your project with this version, run:

```bash
flask db upgrade
```

This applies migration `d4e5f6a7b8c9_add_traveler_groups.py`.

## Trip Weather

Trip Details includes a **Show Weather** section. It loads weather through the Flask backend using Open-Meteo geocoding and forecast APIs. No weather API key or database migration is required.

The weather section shows:
- Current temperature and condition
- Feels-like temperature and humidity
- Wind speed
- 7-day forecast
- Daily high/low temperature
- Rain probability
- Forecast guidance for the trip dates

The external weather service is called by the Flask server rather than directly by the browser.


## Authentication

SafarLedger uses a simple phone-number authentication flow:

- Registration: name, phone number, password, and confirm password.
- Login: phone number and password.
- No email verification, OTP, or email password-reset flow is required.
- Passwords are stored as secure hashes, never as plain text.
