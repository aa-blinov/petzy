"""Security and authentication helpers shared across blueprints.

This module is intentionally independent from `web.app` to avoid circular imports.
It exposes JWT helpers, auth helpers and access decorators which are re-exported
from `web.app` and imported directly from blueprints.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps
import logging
from uuid import uuid4

import bcrypt
import jwt
from flask import make_response, request, Response

from web.configs import FLASK_CONFIG, JWT_CONFIG, ADMIN_CONFIG
from web.db import db
from web.errors import error_response


logger = logging.getLogger(__name__)

# JWT configuration
JWT_SECRET_KEY = JWT_CONFIG["secret_key"]
JWT_ALGORITHM = JWT_CONFIG["algorithm"]
ACCESS_TOKEN_EXPIRE_MINUTES = JWT_CONFIG["access_token_expire_minutes"]
REFRESH_TOKEN_EXPIRE_DAYS = JWT_CONFIG["refresh_token_expire_days"]

# Cookie defaults (env-driven via FLASK_CONFIG; see web/configs.py)
COOKIE_SECURE: bool = FLASK_CONFIG["cookie_secure"]
COOKIE_SAMESITE: str = FLASK_CONFIG["cookie_samesite"]

# Authentication credentials - REQUIRED from environment
ADMIN_USERNAME = ADMIN_CONFIG["username"]
ADMIN_PASSWORD_HASH = ADMIN_CONFIG["password_hash"]


def set_auth_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    """Attach an auth cookie to ``response`` using configured defaults.

    Centralising this avoids the silent ``secure=False`` footgun that the
    project shipped with for months — flip ``COOKIE_SECURE=true`` in
    production and HTTPS-only cookies are enforced everywhere at once.
    """
    response.set_cookie(
        key,
        value,
        max_age=max_age,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )

# Validate required environment variables
if not ADMIN_PASSWORD_HASH:
    raise RuntimeError(
        "ADMIN_PASSWORD_HASH environment variable is required! "
        'To generate hash: python -c "import bcrypt; '
        "print(bcrypt.hashpw('your_password'.encode(), bcrypt.gensalt()).decode())\""
    )


def verify_user_credentials(username, password):
    """Verify user credentials from database or fallback to admin."""
    # First, try to find user in database
    user = db["users"].find_one({"username": username, "is_active": True})
    if user:
        try:
            return bcrypt.checkpw(password.encode(), user["password_hash"].encode())
        except (ValueError, TypeError, KeyError):
            return False

    # Fallback to admin credentials for backward compatibility
    try:
        return username == ADMIN_USERNAME and bcrypt.checkpw(password.encode(), ADMIN_PASSWORD_HASH.encode())
    except (ValueError, TypeError):
        return False


def ensure_default_admin():
    """Ensure default admin user exists in database."""
    admin_user = db["users"].find_one({"username": ADMIN_USERNAME})
    if not admin_user:
        db["users"].insert_one(
            {
                "username": ADMIN_USERNAME,
                "password_hash": ADMIN_PASSWORD_HASH,
                "full_name": "Administrator",
                "email": "",
                "created_at": datetime.now(timezone.utc),
                "created_by": "system",
                "is_active": True,
                "is_admin": True,
            }
        )
    elif not admin_user.get("is_admin"):
        # Ensure existing admin also has the flag
        db["users"].update_one({"username": ADMIN_USERNAME}, {"$set": {"is_admin": True}})


def create_access_token(username):
    """Create JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"username": username, "exp": expire, "type": "access"}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(username):
    """Create JWT refresh token and store it in database.

    Each refresh token carries a fresh `jti` (JWT ID, RFC 7519 §4.1.7)
    so that two logins in the same wall-clock second produce distinct
    tokens and don't trip the unique index on `refresh_tokens.jti`.
    Keeping `token` in the document too so existing `find_one({"token":
    ...})` lookups in `verify_refresh_token` keep working.
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = uuid4().hex
    payload = {"username": username, "exp": expire, "type": "refresh", "jti": jti}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    db["refresh_tokens"].insert_one(
        {
            "jti": jti,
            "token": token,
            "username": username,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expire,
        }
    )

    return token


def verify_token(token, token_type="access"):
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


def validate_refresh_token(refresh_token: str):
    """Verify a refresh token end-to-end.

    Returns ``(username, token_record)`` if the token is valid for use,
    or ``None`` if it should be rejected. Side effect: drops the row
    from ``refresh_tokens`` if its stored ``expires_at`` is in the past
    (the JWT signature may still verify under clock skew, so this
    defensive check guards the gap until MongoDB's TTL monitor sweeps).

    Used by both the silent ``try_refresh_access_token`` helper
    (request flow on access-token expiry) and the explicit
    ``/api/auth/refresh`` endpoint, so the invariants are the same.
    """
    if not refresh_token:
        return None

    payload = verify_token(refresh_token, "refresh")
    if not payload:
        return None

    token_record = db["refresh_tokens"].find_one({"token": refresh_token})
    if not token_record:
        return None

    # Defensive cleanup against expired-but-not-yet-TTL-swept rows.
    # PyMongo returns BSON Date as naive UTC datetimes, so we compare
    # in naive UTC to avoid TypeError on tz mismatch.
    expires_at = token_record.get("expires_at")
    if expires_at is not None:
        now_naive_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_naive = (
            expires_at.replace(tzinfo=None)
            if expires_at.tzinfo is not None
            else expires_at
        )
        if expires_naive < now_naive_utc:
            db["refresh_tokens"].delete_one({"_id": token_record["_id"]})
            return None

    username = payload.get("username") or ""
    return username, token_record


def try_refresh_access_token():
    """Try to refresh access token using refresh token. Returns new access token or None."""
    refresh_token = request.cookies.get("refresh_token")
    result = validate_refresh_token(refresh_token)
    if result is None:
        return None
    username, _token_record = result

    # Create new access token
    access_token = create_access_token(username)

    # Update token in database (optional, for tracking)
    db["refresh_tokens"].update_one(
        {"token": refresh_token},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )

    return access_token


def get_current_user():
    """
    Get current authenticated user.

    Returns:
        tuple: (username, error_response) where error_response is None if authorized,
               or (None, (jsonify_response, status_code)) if not authorized
    """
    username = getattr(request, "current_user", None)
    if not username:
        return None, error_response("unauthorized")
    return username, None


def is_admin(username):
    """Check if user is admin."""
    return username == ADMIN_USERNAME


def login_required(f):
    """Decorator to require valid JWT access token."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import g  # imported lazily to avoid hard dependency at import time

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
            return error_response("unauthorized")

        # Store username in request context
        username = payload.get("username")
        setattr(request, "current_user", username)
        g.current_user = username  # optional, for Flask context

        response = f(*args, **kwargs)

        # If the token was refreshed mid-request, hand the new access
        # token back as a cookie.
        #
        # Views return a mix of bare ``Response`` objects and
        # ``(body, status)`` tuples. Today every route puts
        # ``@api.validate`` outside this decorator, and it normalises
        # the tuples before we see them — so the previous
        # ``hasattr(response, "set_cookie")`` guard happened to always
        # hold. It was one decorator-order change away from silently
        # dropping the renewed cookie, though, which would leave the
        # session limping along on refresh_token alone for every
        # request. make_response accepts either shape, so the renewal
        # no longer depends on where the decorator sits. The HTML twin
        # of this decorator (page_login_required) already normalises
        # this way.
        if new_token:
            response = make_response(response)
            set_auth_cookie(
                response,
                "access_token",
                new_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )

        return response

    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        username = getattr(request, "current_user", None)
        if not username or not is_admin(username or ""):
            return error_response("forbidden_admin_only")
        return f(*args, **kwargs)

    return decorated_function
