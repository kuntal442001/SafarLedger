from flask import Flask, redirect, url_for

from app.config import Config
from app.extensions import db, migrate, login_manager, limiter


def create_app():
    app = Flask(__name__)

    @app.route("/")
    def home():
        return redirect(url_for("dashboard.index"))

    # ---------------------------------------------------------
    # Load configuration
    # ---------------------------------------------------------
    app.config.from_object(Config)

    # ---------------------------------------------------------
    # Initialize extensions
    # ---------------------------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)

    # ---------------------------------------------------------
    # Import models
    # ---------------------------------------------------------
    from app.models.user import User
    from app.models.tour import Tour
    from app.models.expense import Expense
    from app.models.traveler import Traveler
    from app.models.traveler_group import TravelerGroup
    from app.models.expense_participant import expense_participants
    from app.models.itinerary_item import ItineraryItem
    from app.models.expense_payment import ExpensePayment

    # ---------------------------------------------------------
    # Flask-Login user loader
    # ---------------------------------------------------------
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ---------------------------------------------------------
    # Register authentication blueprint
    # ---------------------------------------------------------
    from app.auth import auth

    app.register_blueprint(auth)

    # ---------------------------------------------------------
    # Register dashboard blueprint
    # ---------------------------------------------------------
    from app.dashboard import dashboard

    app.register_blueprint(dashboard)

    # ---------------------------------------------------------
    # Register tours blueprint
    # ---------------------------------------------------------
    from app.tours import tours

    app.register_blueprint(tours)

    # ---------------------------------------------------------
    # Register expenses blueprint
    # ---------------------------------------------------------
    from app.expenses import expenses

    app.register_blueprint(expenses)

    # ---------------------------------------------------------
    # Register travelers blueprint
    # ---------------------------------------------------------
    from app.travelers import travelers

    app.register_blueprint(travelers)

    # ---------------------------------------------------------
    # Register traveler groups blueprint
    # ---------------------------------------------------------
    from app.groups import groups

    app.register_blueprint(groups)

    # ---------------------------------------------------------
    # Register itinerary blueprint
    # ---------------------------------------------------------
    from app.itinerary import itinerary

    app.register_blueprint(itinerary)

    # ---------------------------------------------------------
    # Register trip report blueprint
    # ---------------------------------------------------------
    from app.reports import reports

    app.register_blueprint(reports)

    # ---------------------------------------------------------
    # Register traveler settlement blueprint
    # ---------------------------------------------------------
    from app.settlements import settlements

    app.register_blueprint(settlements)

    return app