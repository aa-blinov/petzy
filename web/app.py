"""Flask web application for pet health tracking - Petzy."""

import csv
import io
import logging
import sys
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import quote

import bcrypt
import jwt
from flask import Flask, jsonify, make_response, redirect, render_template, request, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded

from web.db import db
from web.configs import FLASK_CONFIG, RATE_LIMIT_CONFIG, LOGGING_CONFIG
from gridfs import GridFS
from bson import ObjectId
from bson.errors import InvalidId


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

from web.auth import auth_bp  # noqa: E402
from web.pets import pets_bp  # noqa: E402
from web.users import users_bp  # noqa: E402

app.register_blueprint(auth_bp)
app.register_blueprint(pets_bp)
app.register_blueprint(users_bp)


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


from web import security

# Re-export security constants/helpers for backward compatibility (tests & other modules)
JWT_SECRET_KEY = security.JWT_SECRET_KEY
JWT_ALGORITHM = security.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = security.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = security.REFRESH_TOKEN_EXPIRE_DAYS
ADMIN_USERNAME = security.ADMIN_USERNAME
ADMIN_PASSWORD_HASH = security.ADMIN_PASSWORD_HASH

verify_user_credentials = security.verify_user_credentials
create_access_token = security.create_access_token
create_refresh_token = security.create_refresh_token
verify_token = security.verify_token
get_token_from_request = security.get_token_from_request
try_refresh_access_token = security.try_refresh_access_token
get_current_user = security.get_current_user
is_admin = security.is_admin
login_required = security.login_required
admin_required = security.admin_required

# Use a default user_id for web user (can be any number, just for data storage)
DEFAULT_USER_ID = 0


# Helper function for safe error handling
def handle_error(error, context="", status_code=500):
    """Safely handle errors with logging and user-friendly messages."""
    if isinstance(error, ValueError):
        logger.warning(f"Invalid input data: {context}, error={error}")
        return jsonify({"error": "Invalid input data"}), 400
    elif isinstance(error, (KeyError, AttributeError)):
        logger.warning(f"Missing required data: {context}, error={error}")
        return jsonify({"error": "Missing required data"}), 400
    else:
        logger.error(f"Unexpected error: {context}, error={error}", exc_info=True)
        return jsonify({"error": "Internal server error"}), status_code


# Helper function for safe datetime parsing
def parse_datetime(date_str, time_str=None, allow_future=True, max_future_days=1, max_past_years=50):
    """
    Safely parse datetime from date and optional time strings.

    Args:
        date_str: Date string in format "YYYY-MM-DD"
        time_str: Optional time string in format "HH:MM"
        allow_future: Whether to allow future dates (default: True)
        max_future_days: Maximum days in the future allowed (default: 1)
        max_past_years: Maximum years in the past allowed (default: 50)

    Returns:
        datetime object if parsing and validation succeed

    Raises:
        ValueError: If date format is invalid or date is out of allowed range
    """
    if not date_str:
        raise ValueError("Date string is required")

    try:
        if time_str:
            # Parse date and time
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            # Parse date only
            dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        if time_str:
            raise ValueError(f"Invalid date/time format. Expected YYYY-MM-DD HH:MM, got '{date_str} {time_str}'")
        else:
            raise ValueError(f"Invalid date format. Expected YYYY-MM-DD, got '{date_str}'")

    # Validate date range
    now = datetime.now()
    max_future = now + timedelta(days=max_future_days) if allow_future else now
    max_past = now - timedelta(days=max_past_years * 365)

    if dt > max_future:
        raise ValueError(f"Date cannot be more than {max_future_days} day(s) in the future")

    if dt < max_past:
        raise ValueError(f"Date cannot be more than {max_past_years} years in the past")

    return dt


# Helper function for safe date parsing (for birth_date)
def parse_date(date_str, allow_future=False, max_past_years=50):
    """
    Safely parse date string (for birth_date).

    Args:
        date_str: Date string in format "YYYY-MM-DD"
        allow_future: Whether to allow future dates (default: False for birth dates)
        max_past_years: Maximum years in the past allowed (default: 50)

    Returns:
        datetime object if parsing and validation succeed, None if date_str is empty

    Raises:
        ValueError: If date format is invalid or date is out of allowed range
    """
    if not date_str:
        return None

    return parse_datetime(
        date_str, time_str=None, allow_future=allow_future, max_future_days=0, max_past_years=max_past_years
    )


# Helper function to safely parse event datetime with error handling
def parse_event_datetime(date_str, time_str, context=""):
    """
    Safely parse event datetime with proper error handling.

    Args:
        date_str: Date string in format "YYYY-MM-DD"
        time_str: Time string in format "HH:MM"
        context: Context string for error messages

    Returns:
        datetime object if parsing succeeds, None if both date_str and time_str are empty

    Raises:
        ValueError: If date format is invalid or date is out of allowed range
    """
    if date_str and time_str:
        return parse_datetime(date_str, time_str, allow_future=True, max_future_days=1)
    elif date_str or time_str:
        # If only one is provided, it's invalid
        raise ValueError("Both date and time must be provided together")
    else:
        return datetime.now()


# Helper function to get current user with authorization check
def get_current_user():
    """
    Get current authenticated user.

    Returns:
        tuple: (username, error_response) where error_response is None if authorized,
               or (None, (jsonify_response, status_code)) if not authorized
    """
    username = getattr(request, "current_user", None)
    if not username:
        return None, (jsonify({"error": "Unauthorized"}), 401)
    return username, None


# Helper function to validate pet_id and check access
def validate_pet_access(pet_id, username):
    """
    Validate pet_id format and check if user has access to the pet.

    Args:
        pet_id: Pet ID string
        username: Username to check access for

    Returns:
        tuple: (success, error_response) where success is True if access granted,
               or (False, (jsonify_response, status_code)) if validation/access fails
    """
    if not pet_id:
        return False, (jsonify({"error": "pet_id обязателен"}), 400)

    if not validate_pet_id(pet_id):
        return False, (jsonify({"error": "Неверный формат pet_id"}), 400)

    if not check_pet_access(pet_id, username):
        return False, (jsonify({"error": "Нет доступа к этому животному"}), 403)

    return True, None


# Helper function to safely parse event datetime with error handling and logging
def parse_event_datetime_safe(date_str, time_str, context="", pet_id=None, username=None):
    """
    Safely parse event datetime with error handling and logging.

    Args:
        date_str: Date string in format "YYYY-MM-DD"
        time_str: Time string in format "HH:MM"
        context: Context string for error messages (e.g., "asthma attack")
        pet_id: Optional pet_id for logging
        username: Optional username for logging

    Returns:
        tuple: (datetime_object, error_response) where error_response is None if parsing succeeds,
               or (None, (jsonify_response, status_code)) if parsing fails
    """
    if date_str and time_str:
        try:
            event_dt = parse_datetime(date_str, time_str, allow_future=True, max_future_days=1)
            return event_dt, None
        except ValueError as e:
            log_context = f"pet_id={pet_id}, user={username}" if pet_id and username else ""
            logger.warning(f"Invalid datetime format for {context}: {log_context}, error={e}")
            return None, (jsonify({"error": f"Неверный формат даты/времени: {str(e)}"}), 400)
    else:
        return datetime.now(), None


# Helper function to get record and validate access for update/delete operations
def get_record_and_validate_access(record_id, collection_name, username):
    """
    Get record by ID and validate user access.

    Args:
        record_id: Record ID string (ObjectId)
        collection_name: Name of the collection (e.g., "asthma_attacks")
        username: Username to check access for

    Returns:
        tuple: (record, pet_id, error_response) where error_response is None if successful,
               or (None, None, (jsonify_response, status_code)) if validation fails
    """
    try:
        record_id_obj = ObjectId(record_id)
    except (InvalidId, TypeError, ValueError):
        return None, None, (jsonify({"error": "Invalid record_id format"}), 400)

    existing = db[collection_name].find_one({"_id": record_id_obj})
    if not existing:
        return None, None, (jsonify({"error": "Record not found"}), 404)

    pet_id = existing.get("pet_id")
    if not pet_id:
        return None, None, (jsonify({"error": "Invalid record"}), 400)

    # Check pet access
    if not check_pet_access(pet_id, username):
        return None, None, (jsonify({"error": "Нет доступа к этому животному"}), 403)

    return existing, pet_id, None


# Helper function to get pet and validate access
def get_pet_and_validate(pet_id, username, require_owner=False):
    """
    Get pet by ID and validate user access.

    Args:
        pet_id: Pet ID string
        username: Username to check access for
        require_owner: If True, only owner can access (default: False)

    Returns:
        tuple: (pet, error_response) where error_response is None if successful,
               or (None, (jsonify_response, status_code)) if validation fails
    """
    if not validate_pet_id(pet_id):
        return None, (jsonify({"error": "Неверный формат pet_id"}), 400)

    pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
    if not pet:
        return None, (jsonify({"error": "Питомец не найден"}), 404)

    if require_owner:
        if pet.get("owner") != username:
            return None, (jsonify({"error": "Только владелец может выполнить это действие"}), 403)
    else:
        if not check_pet_access(pet_id, username):
            return None, (jsonify({"error": "Нет доступа к этому животному"}), 403)

    return pet, None


def create_access_token(username: str) -> str:
    """Create JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"username": username, "exp": expire, "type": "access"}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(username: str) -> str:
    """Create JWT refresh token and store it in database."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"username": username, "exp": expire, "type": "refresh"}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    # Store refresh token in database
    db["refresh_tokens"].insert_one(
        {"token": token, "username": username, "created_at": datetime.now(timezone.utc), "expires_at": expire}
    )

    return token


def verify_token(token: str, token_type: str = "access") -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != token_type:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_token_from_request():
    """Extract token from Authorization header or cookie."""
    # Try Authorization header first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    # Try cookie
    return request.cookies.get("access_token")


def try_refresh_access_token():
    """Try to refresh access token using refresh token. Returns new access token or None."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return None

    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")
    if not payload:
        return None

    # Check if token exists in database
    token_record = db["refresh_tokens"].find_one({"token": refresh_token})
    if not token_record:
        return None

    username = payload.get("username")
    return create_access_token(username)


def login_required(f):
    """Decorator to require valid JWT access token."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = get_token_from_request()
        payload = None
        new_token = None

        if token:
            payload = verify_token(token, "access")

        if not payload:
            # Token missing or invalid, try to refresh
            new_token = try_refresh_access_token()
            if new_token:
                payload = verify_token(new_token, "access")
                if not payload:
                    new_token = None

        if not payload:
            # No valid token available
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized", "message": "Token required"}), 401
            return redirect(url_for("login"))

        # We have valid token (either original or refreshed)
        request.current_user = payload.get("username")

        # Execute the function
        response = f(*args, **kwargs)

        # If we refreshed the token, set it in the response cookie
        if new_token:
            # Wrap response if needed to set cookie
            if isinstance(response, tuple):
                response_obj, status_code = response[0], response[1] if len(response) > 1 else 200
                response = make_response(response_obj, status_code)
            elif not hasattr(response, "set_cookie"):
                response = make_response(response)

            response.set_cookie(
                "access_token",
                new_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                httponly=True,
                secure=False,
                samesite="Lax",
            )

        return response

    return decorated_function


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

    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    """Logout route - clear tokens and redirect to login."""
    response = make_response(redirect(url_for("login")))
    response.set_cookie("access_token", "", max_age=0)
    response.set_cookie("refresh_token", "", max_age=0)
    return response


@app.route("/api/auth/check-admin", methods=["GET"])
@login_required
def check_admin():
    """Check if current user is admin (returns 200 with isAdmin flag, no 403)."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]
        
        # Check if user is admin
        user = db["users"].find_one({"username": username})
        is_admin = user and user.get("is_admin", False)
        
        return jsonify({"isAdmin": is_admin}), 200
    except Exception as e:
        logger.error(f"Error checking admin status: user={getattr(request, 'current_user', None)}, error={e}", exc_info=True)
        return jsonify({"isAdmin": False}), 200  # Return false instead of error


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("50 per 5 minutes", error_message="Слишком много попыток. Попробуйте позже.")
def login():
    """Login page."""
    # Check if already logged in
    token = get_token_from_request()
    if token:
        payload = verify_token(token, "access")
        if payload:
            return redirect(url_for("dashboard"))

    # If no access token, try to refresh using refresh token
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

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        client_ip = request.remote_addr

        if not username or not password:
            return render_template("login.html", error="Введите логин и пароль")

        # Verify username and password
        if verify_user_credentials(username, password):
            # Create tokens
            access_token = create_access_token(username)
            refresh_token = create_refresh_token(username)

            logger.info(f"Successful login: user={username}, ip={client_ip}")

            # Create response with redirect
            response = make_response(redirect(url_for("dashboard")))

            # Set tokens in httpOnly cookies
            response.set_cookie(
                "access_token",
                access_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="Lax",
            )
            response.set_cookie(
                "refresh_token",
                refresh_token,
                max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
                httponly=True,
                secure=False,  # Set to True in production with HTTPS
                samesite="Lax",
            )

            return response

        # Failed login
        logger.warning(f"Failed login attempt: user={username}, ip={client_ip}")
        return render_template("login.html", error="Неверный логин или пароль")

    return render_template("login.html")


# Helper function to check if user is admin
def is_admin(username: str) -> bool:
    """Check if user is admin."""
    return username == ADMIN_USERNAME


# Decorator for admin-only endpoints
def admin_required(f):
    """Decorator to require admin privileges."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        username = getattr(request, "current_user", None)
        if not username or not is_admin(username):
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)

    return decorated_function


@app.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard page."""
    username = getattr(request, "current_user", "admin")
    return render_template("dashboard.html", username=username)


# Helper function to validate pet_id format
def validate_pet_id(pet_id):
    """Validate that pet_id is a valid ObjectId string."""
    if not pet_id or not isinstance(pet_id, str):
        return False
    try:
        ObjectId(pet_id)
        return True
    except (InvalidId, TypeError, ValueError):
        return False


# Helper function to check pet access
def check_pet_access(pet_id, username):
    """Check if user has access to pet."""
    if not validate_pet_id(pet_id):
        return False
    try:
        pet = db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return False
        # User is owner or in shared_with
        return pet.get("owner") == username or username in pet.get("shared_with", [])
    except Exception:
        return False








@app.route("/api/asthma", methods=["POST"])
@login_required
def add_asthma_attack():
    """Add asthma attack event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Validate pet_id and check access
        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "asthma attack", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        attack_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "duration": data.get("duration", ""),
            "reason": data.get("reason", ""),
            "inhalation": data.get("inhalation", False),
            "comment": data.get("comment", ""),
            "username": username,
        }

        db["asthma_attacks"].insert_one(attack_data)
        logger.info(f"Asthma attack recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Приступ астмы записан"}), 201

    except ValueError as e:
        logger.warning(f"Invalid input data for asthma attack: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error adding asthma attack: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/defecation", methods=["POST"])
@login_required
def add_defecation():
    """Add defecation event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Validate pet_id and check access
        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "defecation", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        defecation_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "stool_type": data.get("stool_type", ""),
            "color": data.get("color", "Коричневый"),
            "food": data.get("food", ""),
            "comment": data.get("comment", ""),
            "username": username,
        }

        db["defecations"].insert_one(defecation_data)
        logger.info(f"Defecation recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дефекация записана"}), 201

    except ValueError as e:
        logger.warning(f"Invalid input data for defecation: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error adding defecation: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/litter", methods=["POST"])
@login_required
def add_litter():
    """Add litter change event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Validate pet_id and check access
        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "litter change", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        litter_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "comment": data.get("comment", ""),
            "username": username,
        }

        db["litter_changes"].insert_one(litter_data)
        logger.info(f"Litter change recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Смена лотка записана"}), 201

    except ValueError as e:
        logger.warning(f"Invalid input data for litter change: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error adding litter change: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/weight", methods=["POST"])
@login_required
def add_weight():
    """Add weight measurement."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Validate pet_id and check access
        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "weight", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        weight_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "weight": data.get("weight", ""),
            "food": data.get("food", ""),
            "comment": data.get("comment", ""),
            "username": username,
        }

        db["weights"].insert_one(weight_data)
        logger.info(f"Weight recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Вес записан"}), 201

    except ValueError as e:
        logger.warning(f"Invalid input data for weight: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error adding weight: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/asthma", methods=["GET"])
@login_required
def get_asthma_attacks():
    """Get asthma attacks for current pet."""
    pet_id = request.args.get("pet_id")

    # Get current user
    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    # Validate pet_id and check access
    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    attacks = list(db["asthma_attacks"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for attack in attacks:
        attack["_id"] = str(attack["_id"])
        if isinstance(attack.get("date_time"), datetime):
            attack["date_time"] = attack["date_time"].strftime("%Y-%m-%d %H:%M")
        if attack.get("inhalation") is True:
            attack["inhalation"] = "Да"
        elif attack.get("inhalation") is False:
            attack["inhalation"] = "Нет"

    return jsonify({"attacks": attacks})


@app.route("/api/defecation", methods=["GET"])
@login_required
def get_defecations():
    """Get defecations for current pet."""
    pet_id = request.args.get("pet_id")

    # Get current user
    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    # Validate pet_id and check access
    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    defecations = list(db["defecations"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for defecation in defecations:
        defecation["_id"] = str(defecation["_id"])
        if isinstance(defecation.get("date_time"), datetime):
            defecation["date_time"] = defecation["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"defecations": defecations})


@app.route("/api/litter", methods=["GET"])
@login_required
def get_litter_changes():
    """Get litter changes for current pet."""
    pet_id = request.args.get("pet_id")

    # Get current user
    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    # Validate pet_id and check access
    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    litter_changes = list(db["litter_changes"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for change in litter_changes:
        change["_id"] = str(change["_id"])
        if isinstance(change.get("date_time"), datetime):
            change["date_time"] = change["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"litter_changes": litter_changes})


@app.route("/api/weight", methods=["GET"])
@login_required
def get_weights():
    """Get weight measurements for current pet."""
    pet_id = request.args.get("pet_id")

    # Get current user
    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    # Validate pet_id and check access
    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    weights = list(db["weights"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for weight in weights:
        weight["_id"] = str(weight["_id"])
        if isinstance(weight.get("date_time"), datetime):
            weight["date_time"] = weight["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"weights": weights})


@app.route("/api/asthma/<record_id>", methods=["PUT"])
@login_required
def update_asthma_attack(record_id):
    """Update asthma attack event."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "asthma_attacks", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(
            date_str, time_str, "asthma attack update", pet_id, username
        )
        if error_response:
            return error_response[0], error_response[1]

        attack_data = {
            "date_time": event_dt,
            "duration": data.get("duration", ""),
            "reason": data.get("reason", ""),
            "inhalation": data.get("inhalation", False),
            "comment": data.get("comment", ""),
        }

        result = db["asthma_attacks"].update_one({"_id": ObjectId(record_id)}, {"$set": attack_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Asthma attack updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Приступ астмы обновлен"}), 200

    except ValueError as e:
        logger.warning(
            f"Invalid input data for asthma attack update: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error updating asthma attack: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/asthma/<record_id>", methods=["DELETE"])
@login_required
def delete_asthma_attack(record_id):
    """Delete asthma attack event."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "asthma_attacks", username)
        if error_response:
            return error_response[0], error_response[1]

        result = db["asthma_attacks"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Asthma attack deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Приступ астмы удален"}), 200

    except ValueError as e:
        logger.warning(
            f"Invalid record_id for asthma attack deletion: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        logger.error(f"Error deleting asthma attack: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/defecation/<record_id>", methods=["PUT"])
@login_required
def update_defecation(record_id):
    """Update defecation event."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "defecations", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "defecation update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        defecation_data = {
            "date_time": event_dt,
            "stool_type": data.get("stool_type", ""),
            "color": data.get("color", "Коричневый"),
            "food": data.get("food", ""),
            "comment": data.get("comment", ""),
        }

        result = db["defecations"].update_one({"_id": ObjectId(record_id)}, {"$set": defecation_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Defecation updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дефекация обновлена"}), 200

    except ValueError as e:
        logger.warning(f"Invalid input data for defecation update: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error updating defecation: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/defecation/<record_id>", methods=["DELETE"])
@login_required
def delete_defecation(record_id):
    """Delete defecation event."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "defecations", username)
        if error_response:
            return error_response[0], error_response[1]

        result = db["defecations"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Defecation deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дефекация удалена"}), 200

    except ValueError as e:
        logger.warning(f"Invalid record_id for defecation deletion: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        logger.error(f"Error deleting defecation: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/litter/<record_id>", methods=["PUT"])
@login_required
def update_litter(record_id):
    """Update litter change event."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "litter_changes", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(
            date_str, time_str, "litter change update", pet_id, username
        )
        if error_response:
            return error_response[0], error_response[1]

        litter_data = {"date_time": event_dt, "comment": data.get("comment", "")}

        result = db["litter_changes"].update_one({"_id": ObjectId(record_id)}, {"$set": litter_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Litter change updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Смена лотка обновлена"}), 200

    except ValueError as e:
        logger.warning(
            f"Invalid input data for litter change update: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error updating litter change: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/litter/<record_id>", methods=["DELETE"])
@login_required
def delete_litter(record_id):
    """Delete litter change event."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "litter_changes", username)
        if error_response:
            return error_response[0], error_response[1]

        result = db["litter_changes"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Litter change deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Смена лотка удалена"}), 200

    except ValueError as e:
        logger.warning(
            f"Invalid record_id for litter change deletion: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        logger.error(f"Error deleting litter change: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/weight/<record_id>", methods=["PUT"])
@login_required
def update_weight(record_id):
    """Update weight measurement."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "weights", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "weight update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        weight_data = {
            "date_time": event_dt,
            "weight": data.get("weight", ""),
            "food": data.get("food", ""),
            "comment": data.get("comment", ""),
        }

        result = db["weights"].update_one({"_id": ObjectId(record_id)}, {"$set": weight_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Weight updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Вес обновлен"}), 200

    except ValueError as e:
        logger.warning(f"Invalid input data for weight update: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error updating weight: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/weight/<record_id>", methods=["DELETE"])
@login_required
def delete_weight(record_id):
    """Delete weight measurement."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "weights", username)
        if error_response:
            return error_response[0], error_response[1]

        result = db["weights"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Weight deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Вес удален"}), 200

    except ValueError as e:
        logger.warning(f"Invalid record_id for weight deletion: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        logger.error(f"Error deleting weight: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/feeding", methods=["POST"])
@login_required
def add_feeding():
    """Add feeding event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Validate pet_id and check access
        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "feeding", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        feeding_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "food_weight": data.get("food_weight", ""),
            "comment": data.get("comment", ""),
            "username": username,
        }

        db["feedings"].insert_one(feeding_data)
        logger.info(f"Feeding recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дневная порция записана"}), 201

    except ValueError as e:
        logger.warning(f"Invalid input data for feeding: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error adding feeding: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/feeding", methods=["GET"])
@login_required
def get_feedings():
    """Get feedings for current pet."""
    pet_id = request.args.get("pet_id")

    # Get current user
    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    # Validate pet_id and check access
    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    feedings = list(db["feedings"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for feeding in feedings:
        feeding["_id"] = str(feeding["_id"])
        if isinstance(feeding.get("date_time"), datetime):
            feeding["date_time"] = feeding["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"feedings": feedings})


@app.route("/api/feeding/<record_id>", methods=["PUT"])
@login_required
def update_feeding(record_id):
    """Update feeding event."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "feedings", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        # Parse datetime
        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "feeding update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        feeding_data = {
            "date_time": event_dt,
            "food_weight": data.get("food_weight", ""),
            "comment": data.get("comment", ""),
        }

        result = db["feedings"].update_one({"_id": ObjectId(record_id)}, {"$set": feeding_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Feeding updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дневная порция обновлена"}), 200

    except ValueError as e:
        logger.warning(f"Invalid input data for feeding update: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error updating feeding: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/feeding/<record_id>", methods=["DELETE"])
@login_required
def delete_feeding(record_id):
    """Delete feeding event."""
    try:
        # Get current user
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Get record and validate access
        existing, pet_id, error_response = get_record_and_validate_access(record_id, "feedings", username)
        if error_response:
            return error_response[0], error_response[1]

        result = db["feedings"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        logger.info(f"Feeding deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дневная порция удалена"}), 200

    except ValueError as e:
        logger.warning(f"Invalid record_id for feeding deletion: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        logger.error(f"Error deleting feeding: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/export/<export_type>/<format_type>", methods=["GET"])
@login_required
def export_data(export_type, format_type):
    """Export data in various formats."""
    try:
        pet_id = request.args.get("pet_id")

        if not pet_id:
            return jsonify({"error": "pet_id обязателен"}), 400

        if not validate_pet_id(pet_id):
            return jsonify({"error": "Неверный формат pet_id"}), 400

        username = getattr(request, "current_user", None)
        if not username:
            return jsonify({"error": "Unauthorized"}), 401

        # Check pet access
        if not check_pet_access(pet_id, username):
            return jsonify({"error": "Нет доступа к этому животному"}), 403

        if export_type == "feeding":
            collection = db["feedings"]
            title = "Дневные порции корма"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("food_weight", "Вес корма (г)"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "asthma":
            collection = db["asthma_attacks"]
            title = "Приступы астмы"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("duration", "Длительность"),
                ("reason", "Причина"),
                ("inhalation", "Ингаляция"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "defecation":
            collection = db["defecations"]
            title = "Дефекации"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("stool_type", "Тип стула"),
                ("color", "Цвет стула"),
                ("food", "Корм"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "litter":
            collection = db["litter_changes"]
            title = "Смена лотка"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("comment", "Комментарий"),
            ]
        elif export_type == "weight":
            collection = db["weights"]
            title = "Вес"
            fields = [
                ("date_time", "Дата и время"),
                ("username", "Пользователь"),
                ("weight", "Вес (кг)"),
                ("food", "Корм"),
                ("comment", "Комментарий"),
            ]
        else:
            return jsonify({"error": "Invalid export type"}), 400

        records = list(collection.find({"pet_id": pet_id}).sort([("date_time", -1)]))

        if not records:
            return jsonify({"error": "Нет данных для выгрузки"}), 404

        # Prepare records
        for r in records:
            if isinstance(r.get("date_time"), datetime):
                r["date_time"] = r["date_time"].strftime("%d.%m.%Y %H:%M")
            else:
                r["date_time"] = str(r.get("date_time", ""))

            # Handle missing username for old records
            if not r.get("username"):
                r["username"] = "-"

            if r.get("comment", "").strip() in ("", "Пропустить"):
                r["comment"] = "-"

            if r.get("food", "").strip() in ("", "Пропустить"):
                r["food"] = "-"

            if export_type == "asthma":
                inh = r.get("inhalation")
                if inh is True:
                    r["inhalation"] = "Да"
                elif inh is False:
                    r["inhalation"] = "Нет"
                else:
                    r["inhalation"] = "-"

        # Generate file based on format
        filename_base = f"{title.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}"

        if format_type == "csv":
            output = io.StringIO()
            fieldnames = [ru for _, ru in fields]
            writer = csv.writer(output)
            writer.writerow(fieldnames)
            for r in records:
                writer.writerow([str(r.get(en, "") or "") for en, _ in fields])
            content = output.getvalue().encode("utf-8-sig")  # BOM for Excel
            mimetype = "text/csv"
            filename = f"{filename_base}.csv"

        elif format_type == "tsv":
            output = io.StringIO()
            fieldnames = [ru for _, ru in fields]
            writer = csv.writer(output, delimiter="\t")
            writer.writerow(fieldnames)
            for r in records:
                writer.writerow([str(r.get(en, "") or "") for en, _ in fields])
            content = output.getvalue().encode("utf-8")
            mimetype = "text/tab-separated-values"
            filename = f"{filename_base}.tsv"

        elif format_type == "html":
            html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #000; color: #fff; }}
        table {{ width: 100%; border-collapse: collapse; background: #1c1c1e; border-radius: 10px; overflow: hidden; }}
        th {{ background: #2c2c2e; padding: 12px; text-align: left; font-weight: 600; border-bottom: 1px solid #38383a; }}
        td {{ padding: 12px; border-bottom: 1px solid #38383a; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover {{ background: #2c2c2e; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <table>
        <thead>
            <tr>
"""
            for _, ru in fields:
                html += f"                <th>{ru}</th>\n"
            html += """            </tr>
        </thead>
        <tbody>
"""
            for r in records:
                html += "            <tr>\n"
                for en, _ in fields:
                    value = str(r.get(en, "") or "").replace("<", "&lt;").replace(">", "&gt;")
                    html += f"                <td>{value}</td>\n"
                html += "            </tr>\n"
            html += """        </tbody>
    </table>
</body>
</html>"""
            content = html.encode("utf-8")
            mimetype = "text/html"
            filename = f"{filename_base}.html"

        elif format_type == "md":
            md = f"# {title}\n\n"
            md += "| " + " | ".join(ru for _, ru in fields) + " |\n"
            md += "|" + "---|" * len(fields) + "\n"
            for r in records:
                md += "| " + " | ".join(str(r.get(en, "") or "").replace("|", "\\|") for en, _ in fields) + " |\n"
            content = md.encode("utf-8")
            mimetype = "text/markdown"
            filename = f"{filename_base}.md"

        else:
            return jsonify({"error": "Invalid format type"}), 400

        # Encode filename for HTTP header (RFC 5987)
        encoded_filename = quote(filename)

        response = make_response(content)
        response.headers["Content-Type"] = mimetype
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        logger.info(f"Data exported: type={export_type}, format={format_type}, pet_id={pet_id}, user={username}")
        return response

    except ValueError as e:
        logger.warning(
            f"Invalid input data for export: type={export_type}, format={format_type}, pet_id={pet_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(
            f"Error exporting data: type={export_type}, format={format_type}, pet_id={pet_id}, user={username}, error={e}",
            exc_info=True,
        )
        return jsonify({"error": "Internal server error"}), 500




if __name__ == "__main__":
    security.ensure_default_admin()
    app.run(host="0.0.0.0", port=5000, debug=FLASK_CONFIG["debug"])
