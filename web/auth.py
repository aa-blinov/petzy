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
from web.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    get_current_user,
    get_token_from_request,
    login_required,
    try_refresh_access_token,
    verify_token,
    create_access_token,
    create_refresh_token,
    verify_user_credentials,
)
from web.schemas import (
    AuthLoginRequest,
    AuthTokensResponse,
    AuthRefreshResponse,
    AdminStatusResponse,
    SuccessResponse,
    ErrorResponse,
)
from web.errors import error_response


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


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/login", methods=["POST"])
@limiter.limit("5 per 5 minutes", error_message="Too many login attempts. Please try again later.")
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

        response = jsonify(
            {
                "success": True,
                "message": "Login successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        )

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
    return error_response("unauthorized_invalid_credentials")


@auth_bp.route("/api/auth/refresh", methods=["POST"])
@api.validate(
    resp=Response(HTTP_200=AuthRefreshResponse, HTTP_401=ErrorResponse),
    tags=["auth"],
)
def api_refresh():
    """Refresh access token using refresh token."""
    refresh_token = request.cookies.get("refresh_token") or (request.get_json() or {}).get("refresh_token")

    if not refresh_token:
        return error_response("unauthorized_refresh_token_required")

    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")
    if not payload:
        return error_response("unauthorized_refresh_token_invalid")

    # Check if token exists in database
    token_record = app.db["refresh_tokens"].find_one({"token": refresh_token})
    if not token_record:
        return error_response("unauthorized_refresh_token_not_found")

    username = payload.get("username") or ""

    # Create new access token
    access_token = create_access_token(username)

    response = jsonify({"success": True, "access_token": access_token})

    response.set_cookie(
        "access_token",
        access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=False,
        samesite="Lax",
    )

    return response


@auth_bp.route("/api/auth/logout", methods=["POST"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse),
    tags=["auth"],
)
def api_logout():
    """Logout - invalidate refresh token."""
    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        # Remove refresh token from database (must see patched app.db in tests)
        app.db["refresh_tokens"].delete_one({"token": refresh_token})

    response = jsonify({"success": True, "message": "Logged out"})
    response.set_cookie("access_token", "", max_age=0)
    response.set_cookie("refresh_token", "", max_age=0)

    return response


@auth_bp.route("/api/auth/check-admin", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=AdminStatusResponse),
    tags=["auth"],
)
def check_admin():
    """Check if current user is admin (returns 200 with isAdmin flag, no 403)."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Use shared is_admin helper for consistency
        from web.security import is_admin as is_admin_check

        is_admin_flag = is_admin_check(username)

        return jsonify({"isAdmin": is_admin_flag}), 200
    except Exception as e:
        logger.error(
            f"Error checking admin status: user={getattr(request, 'current_user', None)}, error={e}",
            exc_info=True,
        )
        return jsonify({"isAdmin": False}), 200  # Return false instead of error


@auth_bp.route("/login", methods=["GET", "POST"], endpoint="login")
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

            # Set tokens in cookies
            response.set_cookie(
                "access_token",
                access_token,
                max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                httponly=True,
                secure=False,
                samesite="Lax",
            )
            response.set_cookie(
                "refresh_token",
                refresh_token,
                max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
                httponly=True,
                secure=False,
                samesite="Lax",
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
