from flask import Blueprint


itinerary = Blueprint(
    "itinerary",
    __name__,
    url_prefix="/itinerary"
)


from app.itinerary import routes
