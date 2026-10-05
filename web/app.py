"""Flask web application for pet health tracking - Petzy."""

import logging
import sys

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.errors import RateLimitExceeded
from flask_limiter.util import get_remote_address
from flask_pydantic_spec import FlaskPydanticSpec
from gridfs import GridFS
from werkzeug.exceptions import HTTPException

from web import security
from web.observability import init_sentry
from web.configs import CORS_CONFIG, FLASK_CONFIG, LOGGING_CONFIG, RATE_LIMIT_CONFIG
from web.db import db, ensure_indexes
from web.errors import error_response


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


# Reporting first, so an error while the app is being built reaches it too.
init_sentry("web")

# Initialize GridFS for file storage
fs = GridFS(db)

# JSON API only — the UI is the React app, served by nginx. No static
# folder, so Flask doesn't register a /static route of its own.
app = Flask(__name__, static_folder=None)
# The React app is served from the same origin (nginx), so it needs no
# CORS at all. Only an explicit CORS_ALLOWED_ORIGINS list opens the API to
# other origins; with none, flask-cors used to echo back any Origin with
# credentials allowed, so SameSite=Lax was all that kept other sites out.
cors_origins = CORS_CONFIG["allowed_origins"]
if cors_origins:  # pragma: no cover
    # Only taken when CORS_ALLOWED_ORIGINS is set in the environment;
    # this module (and its module-level branch) is evaluated exactly
    # once at import time, before any test can set that env var, so
    # exercising this branch would require reloading web.app itself —
    # which would re-register every blueprint a second time.
    CORS(app, supports_credentials=True, origins=cors_origins)

# gunicorn sits behind one proxy (the host nginx, see nginx.conf.server),
# which appends the client's address to X-Forwarded-For. Without this every
# request came from 127.0.0.1, so the per-IP login limit was one limit
# shared by everybody: five bad logins a minute locked out the world.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)  # type: ignore[method-assign]
app.secret_key = FLASK_CONFIG["secret_key"]
app.config["JSONIFY_PRETTYPRINT_REGULAR"] = FLASK_CONFIG["jsonify_prettyprint_regular"]
app.config["JSON_AS_ASCII"] = FLASK_CONFIG["json_as_ascii"]
# Uploads (documents: 10 MB, pet photos: already cropped client-side) are
# the only large bodies. Without a cap Flask read any size into memory
# before the view's own check ran; nginx's 20m let everything up to that
# through. The host proxy caps bodies at 10 MB anyway; 16 MB here only
# bounds what reaches the app if that ever changes.
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# Setup logging
logger = setup_logging(app)


@app.after_request
def _security_headers(response):
    """Headers for everything the API sends.

    A file answered from our own origin (a pet photo, a small document)
    must never run as a page: nosniff stops the browser guessing a type,
    and the sandbox CSP gives an HTML file that slipped through no
    scripts, no origin and no framing. A PDF is left without the CSP:
    the browser's PDF viewer refuses to open inside a sandbox, and its
    type is checked against the file's first bytes on upload.
    HSTS keeps browsers on HTTPS after the first visit. Sent always:
    browsers ignore it on a plain-HTTP answer, and the live proxy doesn't
    reliably tell us the scheme.
    """
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    # /apidoc (Swagger UI, local only: nginx forwards just /api/) loads its own scripts.
    if response.mimetype != "application/pdf" and not request.path.startswith("/apidoc"):
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; sandbox")
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


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
from web.validation import before_request_validation  # noqa: E402

api = FlaskPydanticSpec(
    "flask",
    title="Pet Health Control API",
    version="1.0.0",
    path="apidoc",
    # A request that fails validation answers in the usual error shape, in
    # Russian (web/validation.py), not with pydantic's raw English list.
    before=before_request_validation,
)


from web.pydantic_helpers import keep_form_text_as_text  # noqa: E402

keep_form_text_as_text()


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
            elif status_code == 413:
                return error_response("request_too_large")
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


from web.auth import auth_bp  # noqa: E402
from web.pets import pets_bp  # noqa: E402
from web.users import users_bp  # noqa: E402
from web.account import account_bp  # noqa: E402
from web.legal import legal_bp  # noqa: E402
from web.openapi_doc import docs_bp, finish_spec  # noqa: E402
from web.events import events_bp  # noqa: E402
from web.medications import medications_bp  # noqa: E402
from web.documents import documents_bp  # noqa: E402
from web.push import push_bp  # noqa: E402
from web.export import export_bp  # noqa: E402
from web.medical_card import medical_card_bp  # noqa: E402
from web.medical_share import medical_share_bp  # noqa: E402
from web.vaccines import vaccines_bp  # noqa: E402
from web.medical_records import medical_records_bp  # noqa: E402
from web.builtin_event_types import backfill_litter_type, reorder_default_tiles, seed_builtin_event_types  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(pets_bp)
app.register_blueprint(users_bp)
app.register_blueprint(account_bp)
app.register_blueprint(legal_bp)
app.register_blueprint(events_bp)
app.register_blueprint(medications_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(push_bp)
app.register_blueprint(export_bp)
app.register_blueprint(medical_card_bp)
app.register_blueprint(medical_share_bp)
app.register_blueprint(vaccines_bp)
app.register_blueprint(medical_records_bp)

# Build the indexes the application relies on. MongoDB makes
# create_index a no-op when an identical index already exists, so
# running this at every startup is safe and free.
ensure_indexes()

# Scans are uploaded from the browser straight to the bucket, which needs
# CORS rules for the app's origins. Idempotent, best effort: without them
# only scan uploads fail, and the warning in the log says why.
from web import storage as _storage  # noqa: E402

if _storage.storage_configured():
    _storage.ensure_bucket_cors(logger)
    # gunicorn preloads the app and forks: each worker opens its own
    # connections rather than sharing this process's pool.
    _storage.reset_client()

# Seed the builtin event types (idempotent — skips any key that already
# exists, so a user's edits to a builtin type's label/icon/color survive
# restarts).
seed_builtin_event_types(db)
# Tray changes from before the filling was asked for take the first of its options.
backfill_litter_type(db)
# The admin's own row: every request checks the account is active, and a
# sign-up must find the admin's login taken.
security.ensure_default_admin()
# Pets still on the old alphabetical «+» order get the frequency one.
reorder_default_tiles(db)

# Register API spec after all blueprints are registered
api.register(app)

# What the generated spec can't know: sign-in for a native app, errors,
# time conventions, uploads, files, public endpoints (web/openapi_doc.py).
finish_spec(api.spec)
app.register_blueprint(docs_bp)


# Error handler for rate limit exceeded
@app.errorhandler(RateLimitExceeded)
def handle_rate_limit_exceeded(e):
    """Handle rate limit exceeded errors: say how long to wait, in a header and in words."""
    try:
        window = int(e.limit.limit.get_expiry())
    except Exception:  # an unusual limit object: the generic answer is still an answer
        window = 0
    response, status = error_response("rate_limit_exceeded")
    if window:
        minutes = max(1, round(window / 60))
        if minutes == 1:
            wait = "через минуту"
        elif minutes < 60:
            wait = f"через {minutes} мин"
        else:
            wait = "через час" if minutes == 60 else f"через {round(minutes / 60)} ч"
        body = response.get_json()
        body["error"] = f"Слишком много попыток с этого адреса. Попробуйте {wait}"
        body["retry_after"] = window
        response = jsonify(body)
        response.headers["Retry-After"] = str(window)
    return response, status


if __name__ == "__main__":  # pragma: no cover
    security.ensure_default_admin()
    app.run(host="0.0.0.0", port=5000, debug=FLASK_CONFIG["debug"])
