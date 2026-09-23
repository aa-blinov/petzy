"""Authentication and login-related routes (API + HTML)."""

from flask import (
    Blueprint,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)

from functools import wraps

from flask_pydantic_spec import Request, Response

from web.app import api, limiter, logger  # app-level singletons
import web.app as app  # use app.db so test patches (web.app.db) are visible
from web.configs import RATE_LIMIT_CONFIG  # per-route limits overridable via env
from web.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    get_current_user,
    get_token_from_request,
    login_required,
    set_auth_cookie,
    try_refresh_access_token,
    validate_refresh_token,
    verify_token,
    create_access_token,
    create_refresh_token,
    verify_user_credentials,
)
from web.schemas import (
    AuthLoginRequest,
    AuthRefreshRequest,
    AuthTokensResponse,
    AuthRefreshResponse,
    AdminStatusResponse,
    AuthSessionResponse,
    SuccessResponse,
    ErrorResponse,
)
from web.errors import error_response
from web.messages import get_message


def page_login_required(f):
    """Login-required decorator for HTML pages (redirects to login instead of JSON 401)."""

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
            # No valid token available -> redirect to login page
            return redirect(url_for("auth.login"))

        # We have valid token (either original or refreshed)
        request.current_user = payload.get("username")

        # Execute the function
        response = f(*args, **kwargs)

        # If we refreshed the token, set it in the response cookie
        if new_token:
            if isinstance(response, tuple):
                response_obj, status_code = response[0], response[1] if len(response) > 1 else 200
                response = make_response(response_obj, status_code)
            elif not hasattr(response, "set_cookie"):
                response = make_response(response)

            set_auth_cookie(
                response,
                "access_token",
                new_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            )

        return response

    return decorated_function


auth_bp = Blueprint("auth", __name__)


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

    # Verify username and password
    if verify_user_credentials(username, password):
        # Create tokens
        access_token = create_access_token(username)
        refresh_token = create_refresh_token(username)

        logger.info(f"Successful login: user={username}, ip={client_ip}")

        response, status = get_message("auth_login_success", access_token=access_token, refresh_token=refresh_token)

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


@auth_bp.route("/login", methods=["GET", "POST"], endpoint="login")
@limiter.limit(
    lambda: RATE_LIMIT_CONFIG["login_page_limit"],
    error_message="Слишком много запросов. Попробуйте позже",
)
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
            set_auth_cookie(
                response,
                "access_token",
                new_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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

            # Set tokens in cookies
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

            return response

        # Failed login
        logger.warning(f"Failed login attempt (HTML): user={username}, ip={client_ip}")
        return render_template("login.html", error="Неверный логин или пароль")

    # GET request - render login page
    return render_template("login.html")


@auth_bp.route("/logout", methods=["GET"], endpoint="logout")
def logout():
    """Logout route - clear tokens and redirect to login."""
    response = make_response(redirect(url_for("auth.login")))
    response.set_cookie("access_token", "", max_age=0)
    response.set_cookie("refresh_token", "", max_age=0)
    return response
