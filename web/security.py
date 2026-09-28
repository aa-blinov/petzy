"""Security and authentication helpers shared across blueprints.

This module is intentionally independent from `web.app` to avoid circular imports.
It exposes JWT helpers, auth helpers and access decorators which are re-exported
from `web.app` and imported directly from blueprints.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps
import logging
import time
from uuid import uuid4

import bcrypt
import jwt
from flask import make_response, request, Response

from web.configs import FLASK_CONFIG, JWT_CONFIG, ADMIN_CONFIG
from web.db import db
from web.errors import error_response
from web.observability import set_user as set_sentry_user


logger = logging.getLogger(__name__)

# JWT configuration
JWT_SECRET_KEY = JWT_CONFIG["secret_key"]

# Keys anyone can read in this public repository: signing with one of them
# lets anybody mint a session for any login, the admin's included. The
# fallback in configs.py only exists so a missing key fails loudly here.
_PUBLIC_KEYS = {
    "",
    "dev-secret-key-change-in-production",
    "your-secret-key-for-sessions-change-in-production",
    "your-jwt-secret-key",
}
if JWT_SECRET_KEY in _PUBLIC_KEYS:
    raise RuntimeError("JWT_SECRET_KEY (or FLASK_SECRET_KEY) must be set to a private random value")
JWT_ALGORITHM = JWT_CONFIG["algorithm"]
ACCESS_TOKEN_EXPIRE_MINUTES = JWT_CONFIG["access_token_expire_minutes"]
REFRESH_TOKEN_EXPIRE_DAYS = JWT_CONFIG["refresh_token_expire_days"]
# How long a spent refresh token still answers (with its successor): two
# tabs refreshing at once, or a retry after the answer was lost.
REFRESH_REUSE_GRACE_SECONDS = 30

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


# Checked against when the login doesn't exist, so an unknown name takes
# as long to refuse as a wrong password: the answer's timing shouldn't
# tell anyone which logins are real.
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt()).decode()


def verify_user_credentials(username, password):
    """Verify user credentials from database or fallback to admin."""
    # First, try to find user in database
    user = db["users"].find_one({"username": username, "is_active": True})
    if user:
        try:
            return bcrypt.checkpw(password.encode(), user["password_hash"].encode())
        except (ValueError, TypeError, KeyError):
            return False
    if username != ADMIN_USERNAME:
        bcrypt.checkpw(password.encode(), _DUMMY_HASH.encode())
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
    payload = {"username": username, "exp": expire, "type": "access", "iat": int(time.time())}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(username, family=None):
    """Create JWT refresh token and store it in database.

    ``family`` ties the tokens one sign-in rotates through (see
    ``rotate_refresh_token``); a new sign-in starts a family of its own.

    Each refresh token carries a fresh `jti` (JWT ID, RFC 7519 §4.1.7)
    so that two logins in the same wall-clock second produce distinct
    tokens and don't trip the unique index on `refresh_tokens.jti`.
    Keeping `token` in the document too so existing `find_one({"token":
    ...})` lookups in `verify_refresh_token` keep working.
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = uuid4().hex
    payload = {"username": username, "exp": expire, "type": "refresh", "jti": jti, "iat": int(time.time())}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    db["refresh_tokens"].insert_one(
        {
            "jti": jti,
            "family": family or jti,
            "token": token,
            "username": username,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expire,
        }
    )

    return token


def is_active_user(username, issued_at=None) -> bool:
    """The account exists, isn't disabled, and the token was issued after
    its sessions were last ended. Checked on every request, so disabling
    someone or a new password takes effect at once, not when the access
    token (15 minutes) or the refresh token (7 days) runs out."""
    if not username:
        return False
    user = db["users"].find_one({"username": username, "is_active": {"$ne": False}}, {"sessions_valid_after": 1})
    if user is None:
        return False
    valid_after = user.get("sessions_valid_after")
    return not (valid_after and issued_at is not None and issued_at < valid_after)


def revoke_user_sessions(username) -> None:
    """End every session of a user: after a password change or disabling.
    Tokens issued before this second stop working; a session carried on
    right after (fresh cookies from the same request) is issued after it."""
    db["refresh_tokens"].delete_many({"username": username})
    db["users"].update_one({"username": username}, {"$set": {"sessions_valid_after": int(time.time())}})


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
        expires_naive = expires_at.replace(tzinfo=None) if expires_at.tzinfo is not None else expires_at
        if expires_naive < now_naive_utc:
            db["refresh_tokens"].delete_one({"_id": token_record["_id"]})
            return None

    username = payload.get("username") or ""
    if not is_active_user(username, payload.get("iat")):
        return None
    return username, token_record


def _aware(moment: datetime) -> datetime:
    """PyMongo hands BSON dates back naive (UTC)."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def rotate_refresh_token(refresh_token):
    """Spend a refresh token: ``(username, next refresh token)``, or None.

    Every use hands out a successor, and the spent token stays on record
    (until its own expiry) as the evidence of reuse. Presented again:

    - within REFRESH_REUSE_GRACE_SECONDS, it answers with the same
      successor: two tabs, or a retry after a dropped answer, refresh at
      the same moment and both carry on;
    - later, somebody kept a copy: the whole family (every token of that
      sign-in) is revoked, and the device has to sign in again. A stolen
      refresh token is good until its owner's next refresh, not 7 days.
    """
    result = validate_refresh_token(refresh_token)
    if result is None:
        return None
    username, record = result
    family = record.get("family") or record.get("jti")
    now = datetime.now(timezone.utc)

    if not record.get("rotated_at"):
        successor = create_refresh_token(username, family=family)
        claimed = db["refresh_tokens"].update_one(
            {"_id": record["_id"], "rotated_at": {"$exists": False}},
            {"$set": {"rotated_at": now, "replaced_by": successor}},
        )
        if claimed.modified_count == 1:
            return username, successor
        # A parallel refresh spent it first: drop ours, answer like it did.
        db["refresh_tokens"].delete_one({"token": successor})
        record = db["refresh_tokens"].find_one({"_id": record["_id"]})
        if not record or not record.get("rotated_at"):
            return None

    successor = record.get("replaced_by")
    in_grace = now - _aware(record["rotated_at"]) <= timedelta(seconds=REFRESH_REUSE_GRACE_SECONDS)
    if in_grace and successor and db["refresh_tokens"].find_one({"token": successor}, {"_id": 1}):
        return username, successor

    logger.warning(f"Refresh token reused, sign-in revoked: user={username}")
    db["refresh_tokens"].delete_many({"$or": [{"family": family}, {"jti": family}]})
    return None


def try_refresh_access_token():
    """The session behind the refresh cookie, renewed: ``(access, refresh)``
    tokens, or None."""
    rotated = rotate_refresh_token(request.cookies.get("refresh_token"))
    if rotated is None:
        return None
    username, refresh_token = rotated
    return create_access_token(username), refresh_token


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
        new_token = new_refresh_token = None

        if token:
            payload = verify_token(token, "access")

        if not payload:
            # Token missing or invalid, try to refresh
            renewed = try_refresh_access_token()
            new_token, new_refresh_token = renewed if renewed else (None, None)
            if new_token:
                payload = verify_token(new_token, "access")
                if not payload:
                    new_token = None

        if not payload or not is_active_user(payload.get("username"), payload.get("iat")):
            return error_response("unauthorized")

        # Store username in request context
        username = payload.get("username")
        set_sentry_user(username)
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
        # no longer depends on where the decorator sits.
        if new_token:
            response = make_response(response)
            set_auth_cookie(
                response,
                "access_token",
                new_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )
            set_auth_cookie(
                response,
                "refresh_token",
                new_refresh_token,
                max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
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
