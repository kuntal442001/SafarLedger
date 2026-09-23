from flask import Blueprint


expenses = Blueprint(
    "expenses",
    __name__,
    url_prefix="/expenses"
)


from app.expenses import routes
