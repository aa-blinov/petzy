"""Flask web application for pet health tracking - Petzy."""

import logging
import sys

from flask import Flask, jsonify, make_response, redirect, render_template, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded

from web.db import db
from web.configs import FLASK_CONFIG, RATE_LIMIT_CONFIG, LOGGING_CONFIG
from web import security
from web.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    verify_token,
    get_token_from_request,
    try_refresh_access_token,
)
from gridfs import GridFS


# Configure logging
def setup_logging(app):
    """Configure centralized logging for the application."""
    log_level = LOGGING_CONFIG["level"]

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=LOGGING_CONFIG["format"],
        datefmt=LOGGING_CONFIG["datefmt"],
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Configure Flask app logger
    app.logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Suppress noisy loggers
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    return app.logger


# Initialize GridFS for file storage
fs = GridFS(db)

# Configure Flask app with proper template and static folders
app = Flask(
    __name__,
    template_folder=FLASK_CONFIG["template_folder"],
    static_folder=FLASK_CONFIG["static_folder"],
)
app.secret_key = FLASK_CONFIG["secret_key"]
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = FLASK_CONFIG["jsonify_prettyprint_regular"]
app.config["JSON_AS_ASCII"] = FLASK_CONFIG["json_as_ascii"]

# Setup logging
logger = setup_logging(app)

# Initialize Flask-Limiter for rate limiting
# Use memory storage for tests, MongoDB for production
# No default limits - rate limiting applied only to specific endpoints (login)
# Using empty list [] to disable default limits (recommended in documentation)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=RATE_LIMIT_CONFIG["default_limits"],
    storage_uri=RATE_LIMIT_CONFIG["storage_uri"],
    strategy=RATE_LIMIT_CONFIG["strategy"],
)

from web.auth import auth_bp, page_login_required  # noqa: E402
from web.pets import pets_bp  # noqa: E402
from web.users import users_bp  # noqa: E402
from web.health_records import health_records_bp  # noqa: E402
from web.export import export_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(pets_bp)
app.register_blueprint(users_bp)
app.register_blueprint(health_records_bp)
app.register_blueprint(export_bp)


# Error handler for rate limit exceeded
@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(e):
    """Handle rate limit exceeded errors."""
    # Check if request is JSON (API) or HTML (web page)
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"error": str(e.description)}), 429
    else:
        # For HTML requests, render login page with error
        return render_template("login.html", error=str(e.description)), 429


# Use a default user_id for web user (can be any number, just for data storage)
DEFAULT_USER_ID = 0


@app.route("/")
def index():
    """Redirect to login or dashboard."""
    token = get_token_from_request()
    if token:
        payload = verify_token(token, "access")
        if payload:
            return redirect(url_for("dashboard"))

    # Try to refresh using refresh token
    new_token = try_refresh_access_token()
    if new_token:
        payload = verify_token(new_token, "access")
        if payload:
            response = make_response(redirect(url_for("dashboard")))
            response.set_cookie(
                "access_token",
                new_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                httponly=True,
                secure=False,
                samesite="Lax",
            )
            return response

    return redirect(url_for("auth.login"))


@app.route("/dashboard")
@page_login_required
def dashboard():
    """Main dashboard page."""
    username = getattr(request, "current_user", "admin")
    return render_template("dashboard.html", username=username)


if __name__ == "__main__":
    security.ensure_default_admin()
    app.run(host="0.0.0.0", port=5000, debug=FLASK_CONFIG["debug"])
