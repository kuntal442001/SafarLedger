from flask import Blueprint


tours = Blueprint(
    "tours",
    __name__,
    url_prefix="/tours"
)


from app.tours import routes