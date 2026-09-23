from flask import Blueprint


travelers = Blueprint(
    "travelers",
    __name__,
    url_prefix="/travelers"
)


from app.travelers import routes
