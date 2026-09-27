"""Authentication routes (JSON API only — the UI is the React app)."""

import os
import re
from datetime import datetime, timezone

import bcrypt
from flask import (
    Blueprint,
    jsonify,
    request,
)
from pymongo.errors import DuplicateKeyError


from flask_pydantic_spec import Request, Response

from web.app import api, limiter, logger  # app-level singletons
import web.app as app  # use app.db so test patches (web.app.db) are visible
from web.configs import RATE_LIMIT_CONFIG  # per-route limits overridable via env
from web.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    get_current_user,
    login_required,
    set_auth_cookie,
    validate_refresh_token,
    create_access_token,
    create_refresh_token,
    verify_user_credentials,
    ADMIN_USERNAME,
)
from web.schemas import (
    AuthLoginRequest,
    AuthRefreshRequest,
    AuthTokensResponse,
    AuthRefreshResponse,
    AdminStatusResponse,
    AuthSessionResponse,
    RegisterRequest,
    RegistrationStatusResponse,
    SuccessResponse,
    ErrorResponse,
)
from web.errors import error_response
from web.messages import get_message


auth_bp = Blueprint("auth", __name__)


def registration_open() -> bool:
    """Self sign-up, on unless REGISTRATION_ENABLED=false (to close it fast
    if it's abused; accounts made so far keep working)."""
    return os.getenv("REGISTRATION_ENABLED", "true").strip().lower() not in ("false", "0", "no", "off")


# Lowercase ASCII only: no «Anna» next to «anna», no Cyrillic «а» posing
# as a Latin one — a login is what people share pets by.
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,29}$")
# Names that would read as the service itself. Refused as «занят», the
# same as a real account, so the list isn't a thing to probe.
RESERVED_USERNAMES = {
    "admin",
    "administrator",
    "root",
    "system",
    "support",
    "help",
    "petzy",
    "api",
    "moderator",
    "owner",
    "null",
    "undefined",
}
# The most guessed passwords that pass the length rule.
COMMON_PASSWORDS = {
    "12345678",
    "123456789",
    "1234567890",
    "123123123",
    "11111111",
    "00000000",
    "87654321",
    "password",
    "password1",
    "qwertyui",
    "qwerty123",
    "qwertyuiop",
    "1q2w3e4r",
    "1q2w3e4r5t",
    "iloveyou",
    "sunshine",
    "princess",
    "football",
    "baseball",
    "welcome1",
    "admin123",
    "zaq12wsx",
    "abcd1234",
    "asdfghjk",
    "йцукенгш",
}


def password_problem(password: str, username: str):
    """The error code for a password that won't do, or None. The same rules
    for sign-up, a reset link and a change in Settings."""
    if len(password) < 8:
        return "register_password_short"
    # bcrypt looks at the first 72 bytes only (36 Cyrillic letters).
    if len(password.encode()) > 72:
        return "register_password_long"
    if password.lower() in COMMON_PASSWORDS or password.lower() == username.lower() or len(set(password)) < 3:
        return "register_password_weak"
    return None


def _set_session_cookies(response, username: str) -> None:
    set_auth_cookie(response, "access_token", create_access_token(username), max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    set_auth_cookie(
        response,
        "refresh_token",
        create_refresh_token(username),
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )


@auth_bp.route("/api/auth/registration", methods=["GET"])
@api.validate(resp=Response(HTTP_200=RegistrationStatusResponse), tags=["auth"])
def registration_status():
    """Whether the sign-up form should be offered."""
    from web import mail

    return jsonify({"open": registration_open(), "mail_enabled": mail.mail_configured()})


@auth_bp.route("/api/auth/register", methods=["POST"])
# Accounts made from one address: only a sign-up that went through counts,
# so someone fumbling the password rules isn't locked out for an hour.
@limiter.limit(
    lambda: RATE_LIMIT_CONFIG["register_limit"],
    deduct_when=lambda response: response.status_code == 201,
    error_message="Too many sign-ups from this address. Please try again later.",
)
# Every attempt, looser: «этот логин занят» mustn't become a way to check
# thousands of logins.
@limiter.limit(
    lambda: RATE_LIMIT_CONFIG["register_attempt_limit"],
    error_message="Too many sign-up attempts. Please try again later.",
)
@api.validate(
    body=Request(RegisterRequest),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["auth"],
)
def api_register():
    """Create an account and sign it in."""
    if not registration_open():
        return error_response("registration_closed")
    data = request.context.body  # type: ignore[attr-defined]
    username = data.username.strip().lower()
    password = data.password

    if not USERNAME_RE.match(username):
        return error_response("register_username_invalid")
    taken = app.db["users"].find_one({"username": {"$regex": f"^{re.escape(username)}$", "$options": "i"}}, {"_id": 1})
    if username in RESERVED_USERNAMES or username == ADMIN_USERNAME.lower() or taken:
        return error_response("register_username_taken")
    problem = password_problem(password, username)
    if problem:
        return error_response(problem)

    from web import mail
    from web.account import EMAIL_RE, _email_taken, send_verification

    email = (data.email or "").strip()
    if email:
        if not EMAIL_RE.match(email):
            return error_response("account_email_invalid")
        if _email_taken(email, username):
            return error_response("account_email_taken")

    try:
        app.db["users"].insert_one(
            {
                "username": username,
                "password_hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                "full_name": (data.full_name or "").strip(),
                "email": "",
                "email_verified": False,
                # Becomes the recovery email once the letter's link is opened.
                **({"pending_email": email} if email else {}),
                "created_at": datetime.now(timezone.utc),
                "created_by": "self",
                "is_active": True,
            }
        )
    except DuplicateKeyError:
        # Someone took it between the check and the insert.
        return error_response("register_username_taken")

    if email and mail.mail_configured():
        try:
            send_verification(username, email)
        except Exception as e:
            # The account is made; the letter can be sent again from Settings.
            logger.error(f"Verification letter not sent at sign-up: user={username}, error={e}")
    logger.info(f"Account registered: user={username}, ip={request.remote_addr}")
    response, status = get_message("auth_registered", status=201)
    _set_session_cookies(response, username)
    return response, status


@auth_bp.route("/api/auth/login", methods=["POST"])
@limiter.limit(
    lambda: RATE_LIMIT_CONFIG["login_limit"],
    error_message="Too many login attempts. Please try again later.",
)
@api.validate(
    body=Request(AuthLoginRequest),
    resp=Response(HTTP_200=AuthTokensResponse, HTTP_422=ErrorResponse, HTTP_401=ErrorResponse),
    tags=["auth"],
)
def api_login():
    """API endpoint for login - returns JWT tokens."""
    # `context` is injected by flask-pydantic-spec at runtime; static type checker doesn't know this attribute.
    data = request.context.body  # type: ignore[attr-defined]
    username = data.username.strip()
    password = data.password
    client_ip = request.remote_addr
    # Self-made logins are lowercase; a phone capitalising «Vera» shouldn't
    # lock her out. Accounts an admin made keep their exact spelling.
    if username != username.lower() and not app.db["users"].find_one({"username": username}, {"_id": 1}):
        username = username.lower()

    # Verify username and password
    if verify_user_credentials(username, password):
        # Create tokens
        access_token = create_access_token(username)
        refresh_token = create_refresh_token(username)

        logger.info(f"Successful login: user={username}, ip={client_ip}")

        # The tokens go in httpOnly cookies only: in the body, a script
        # injected into the page could read the 7-day refresh token.
        response, status = get_message("auth_login_success")

        # Set tokens in httpOnly cookies
        set_auth_cookie(
            response,
            "access_token",
            access_token,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        set_auth_cookie(
            response,
            "refresh_token",
            refresh_token,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

        return response, status

    # Failed login
    logger.warning(f"Failed login attempt: user={username}, ip={client_ip}")
    return error_response("unauthorized_invalid_credentials")


@auth_bp.route("/api/auth/refresh", methods=["POST"])
@api.validate(
    body=Request(AuthRefreshRequest),
    resp=Response(HTTP_200=AuthRefreshResponse, HTTP_401=ErrorResponse),
    tags=["auth"],
)
def api_refresh():
    """Refresh access token using refresh token."""
    # Try to get refresh_token from body (validated by @api.validate) or cookies
    refresh_token = None
    if hasattr(request, "context") and hasattr(request.context, "body") and request.context.body:  # type: ignore[attr-defined]
        refresh_token = request.context.body.refresh_token  # type: ignore[attr-defined]
    if not refresh_token:
        refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        return error_response("unauthorized_refresh_token_required")

    # Verify refresh token end-to-end (signature + DB lookup + TTL
    # defensive cleanup). Returning None means "treat as unauthorised".
    result = validate_refresh_token(refresh_token)
    if result is None:
        return error_response("unauthorized_refresh_token_invalid")
    username, _token_record = result

    # Create new access token
    access_token = create_access_token(username)

    response, status = get_message("auth_refresh_success", access_token=access_token)

    set_auth_cookie(
        response,
        "access_token",
        access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return response, status


@auth_bp.route("/api/auth/logout", methods=["POST"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse),
    tags=["auth"],
)
def api_logout():
    """Logout — invalidate this user's refresh tokens.

    We delete the specific token the cookie carries, AND any other
    tokens belonging to the same user. Logging out is supposed to
    mean "sign me out of everything" — if a user had refresh tokens
    cached from older devices/sessions and only the current cookie
    got deleted, a stolen token from a different device would still
    happily mint access tokens. Deleting by username keeps the
    invariant "after logout, no refresh token for this user exists".
    """
    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        # Must see patched app.db in tests
        from web.security import verify_token

        # Find the user this token belongs to (verify_token only checks
        # signature/expiry, doesn't touch the DB).
        payload = verify_token(refresh_token, "refresh")
        username = payload.get("username") if payload else None

        if username:
            # Drop every refresh token for this user. Cheap because
            # refresh_tokens collection is small (TTL keeps it bounded).
            app.db["refresh_tokens"].delete_many({"username": username})
        else:
            # Couldn't decode — fall back to removing the specific token.
            app.db["refresh_tokens"].delete_one({"token": refresh_token})

    response, status = get_message("auth_logout_success")
    response.set_cookie("access_token", "", max_age=0)
    response.set_cookie("refresh_token", "", max_age=0)

    return response, status


@auth_bp.route("/api/auth/session", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=AuthSessionResponse, HTTP_401=ErrorResponse),
    tags=["auth"],
)
def api_session():
    """Return the identity behind the current cookies.

    This is the SPA's only auth probe. It used to infer "am I signed
    in?" from GET /api/pets, which conflated a cold cache, a failed
    data fetch and a dead session — so a 500 on the pet roster looked
    exactly like a logout. A dedicated endpoint means a 401 here is the
    single, unambiguous signal that the session is gone.
    """
    # @login_required already guarantees request.current_user is set.
    username, _ = get_current_user()

    from web.security import is_admin as is_admin_check

    return jsonify({"username": username, "is_admin": is_admin_check(username)}), 200


@auth_bp.route("/api/auth/check-admin", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=AdminStatusResponse),
    tags=["auth"],
)
def check_admin():
    """Check if current user is admin (returns 200 with isAdmin flag, no 403)."""
    try:
        # @login_required already guarantees request.current_user is set.
        username, _ = get_current_user()

        # Use shared is_admin helper for consistency
        from web.security import is_admin as is_admin_check

        is_admin_flag = is_admin_check(username)

        return jsonify({"is_admin": is_admin_flag}), 200
    except Exception as e:
        logger.error(
            f"Error checking admin status: user={getattr(request, 'current_user', None)}, error={e}",
            exc_info=True,
        )
        return jsonify({"is_admin": False}), 200  # Return false instead of error
