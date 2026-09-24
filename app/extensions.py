from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

# Rate limiter for authentication endpoints.
# Storage backend is set via RATELIMIT_STORAGE_URI in config.py.
limiter = Limiter(key_func=get_remote_address)

login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."