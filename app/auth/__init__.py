from flask import Blueprint


auth = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth"
)


# Import routes after creating the Blueprint
from app.auth import routes