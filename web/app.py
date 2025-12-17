"""Flask web application for pet health tracking - Petzy."""

import logging
import sys

from flask import Flask, jsonify, make_response, redirect, render_template, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded
from flask_pydantic_spec import FlaskPydanticSpec

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

# Initialize FlaskPydanticSpec for OpenAPI documentation and Pydantic validation
api = FlaskPydanticSpec(
    "flask",
    title="Pet Health Control API",
    version="1.0.0",
    path="apidoc",
)


from werkzeug.exceptions import HTTPException


@app.errorhandler(422)
def handle_unprocessable_entity(err):
    """Handle Pydantic validation errors and return a consistent format."""
    # Try to get the original data from the exception
    data = getattr(err, "data", None)
    if data and "messages" in data:
        # flask-pydantic-spec puts errors in 'messages'
        messages = data["messages"]
        if isinstance(messages, list) and len(messages) > 0:
            # Format the first error nicely
            error = messages[0]
            if isinstance(error, dict):
                loc = ".".join(str(x) for x in error.get("loc", []))
                msg = error.get("msg", "Validation error")
                return jsonify({"error": f"{loc}: {msg}"}), 422

    # Fallback for other 422 errors
    return jsonify({"error": "Неверные данные"}), 422


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """Global error handler for unexpected exceptions."""
    # If it's a standard HTTP exception (like 404, 405), let Flask handle it
    if isinstance(e, HTTPException):
        return e

    # For actual code exceptions, log the full traceback
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)

    # Return JSON error if it's an API request or expects JSON
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({"error": "Internal server error"}), 500

    # Otherwise return the exception which Flask will convert to a 500 page
    return e


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

# Register API spec after all blueprints are registered
api.register(app)

# Configure Swagger security
if "components" not in api.spec:
    api.spec["components"] = {}
api.spec["components"]["securitySchemes"] = {
    "bearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }
}
api.spec["security"] = [{"bearerAuth": []}]


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
