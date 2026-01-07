"""Flask web application for pet health tracking - Petzy."""

import logging
import os
import sys

from flask import Flask, make_response, redirect, render_template, request, send_from_directory, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from flask_pydantic_spec import FlaskPydanticSpec
from gridfs import GridFS
from werkzeug.exceptions import HTTPException

from web import security
from web.configs import FLASK_CONFIG, LOGGING_CONFIG, RATE_LIMIT_CONFIG
from web.db import db
from web.errors import error_response
from web.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_token_from_request,
    try_refresh_access_token,
    verify_token,
)


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
CORS(app, supports_credentials=True)
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


@app.errorhandler(422)
def handle_unprocessable_entity(err):
    """Handle Pydantic validation errors and return a consistent format."""
    # Try to get the original data from the exception
    data = getattr(err, "data", None)
    if data and "messages" in data:
        # flask-pydantic-spec puts errors in 'messages'
        messages = data["messages"]
        logger.warning(f"Validation error (422): {messages}")
        if isinstance(messages, list) and len(messages) > 0:
            # Format the first error nicely
            # Each message is usually like {'loc': ['body', 'date'], 'msg': '...', 'type': '...'}
            error = messages[0]
            if isinstance(error, dict) and "msg" in error:
                msg = error["msg"]
                # Pydantic errors often look like "Value error, ..."
                if msg.startswith("Value error, "):
                    msg = msg[len("Value error, ") :]
                return error_response("validation_error", msg)
            return error_response("validation_error", str(error))

    # Fallback for other 422 errors
    return error_response("validation_error")


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    """Global error handler for unexpected exceptions."""
    # If it's a standard HTTP exception (like 404, 405)
    if isinstance(e, HTTPException):
        # For API requests, convert to unified error format
        if request.path.startswith("/api/") or request.is_json:
            status_code = e.code
            if status_code == 404:
                return error_response("not_found")
            elif status_code == 405:
                return error_response("method_not_allowed")
            else:
                # For other HTTP exceptions, use generic error with appropriate status
                # This shouldn't happen often, but we handle it gracefully
                return error_response("internal_error")
        # For HTML requests, let Flask handle it normally
        return e

    # For actual code exceptions, log the full traceback
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)

    # Return JSON error if it's an API request or expects JSON
    if request.path.startswith("/api/") or request.is_json:
        return error_response("internal_error")

    # Otherwise return the exception which Flask will convert to a 500 page
    return e


from web.auth import auth_bp, page_login_required  # noqa: E402
from web.pets import pets_bp  # noqa: E402
from web.users import users_bp  # noqa: E402
from web.health_records import health_records_bp  # noqa: E402
from web.medications import medications_bp  # noqa: E402
from web.export import export_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(pets_bp)
app.register_blueprint(users_bp)
app.register_blueprint(health_records_bp)
app.register_blueprint(medications_bp)
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
        return error_response("rate_limit_exceeded")
    else:
        # For HTML requests, render login page with error
        return render_template("login.html", error=str(e.description)), 429


@app.route("/favicon.ico")
def favicon():
    """Serve favicon.ico to prevent 404 errors."""
    # Return optimized SVG version of icon-192.svg as favicon
    # Get the absolute path to static folder
    static_folder = app.static_folder
    if static_folder and not os.path.isabs(static_folder):
        # If relative path, make it absolute relative to app root
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        static_folder = os.path.join(app_root, "web", static_folder)
    elif not static_folder:
        # Fallback to config
        app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        static_folder = os.path.join(app_root, "web", FLASK_CONFIG["static_folder"])
    
    # Try to serve optimized favicon.svg, fallback to icon-192.svg
    favicon_path = os.path.join(static_folder, "favicon.svg")
    if os.path.exists(favicon_path):
        return send_from_directory(
            static_folder, "favicon.svg", mimetype="image/svg+xml"
        )
    else:
        # Fallback to icon-192.svg if favicon.svg doesn't exist
        return send_from_directory(
            static_folder, "icon-192.svg", mimetype="image/svg+xml"
        )


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
