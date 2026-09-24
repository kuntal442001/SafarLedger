import os

from dotenv import load_dotenv


# Load environment variables from .env
load_dotenv()


class Config:

    # ---------------------------------------------------------
    # Flask
    # ---------------------------------------------------------

    SECRET_KEY = os.getenv("SECRET_KEY")

    if not SECRET_KEY:
        raise RuntimeError(
            "SECRET_KEY is not set in the environment."
        )

    # ---------------------------------------------------------
    # PostgreSQL / SQLAlchemy
    # ---------------------------------------------------------

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")

    if not SQLALCHEMY_DATABASE_URI:
        raise RuntimeError(
            "DATABASE_URL is not set in the environment."
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Vercel creates short-lived Python instances. Keep the SQLAlchemy pool
    # deliberately small and let Neon's pooled endpoint handle connection
    # multiplexing. These settings avoid stale connections without opening
    # a large pool per serverless instance.
    if SQLALCHEMY_DATABASE_URI.startswith(("postgresql://", "postgres://")):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_size": 2,
            "max_overflow": 0,
            "pool_use_lifo": True,
        }

    # WeatherAPI.com
    WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

    # ---------------------------------------------------------
    # Session Security
    # ---------------------------------------------------------

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Reads SESSION_COOKIE_SECURE=true from the environment once the app
    # is deployed behind HTTPS. Defaults to False so local http:// dev
    # is unaffected.
    SESSION_COOKIE_SECURE = os.getenv(
        "SESSION_COOKIE_SECURE", "false"
    ).lower() == "true"

    # ---------------------------------------------------------
    # Login rate limiting / account lockout
    # ---------------------------------------------------------

    # Storage for Flask-Limiter counters. "memory://" is fine for a
    # single-process dev/staging setup; point this at Redis
    # (e.g. redis://localhost:6379) for a multi-process production deploy.
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")

    LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", 5))
    LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", 15))
