from flask import Blueprint

settlements = Blueprint(
    "settlements",
    __name__,
    url_prefix="/settlement",
)

from app.settlements import routes
