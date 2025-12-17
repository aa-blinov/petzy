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

from web.app import limiter, logger  # app-level singletons
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


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/login", methods=["POST"])
@limiter.limit("5 per 5 minutes", error_message="Too many login attempts. Please try again later.")
def api_login():
    """API endpoint for login - returns JWT tokens."""
    data = request.get_json()
    username = data.get("username", "").strip() if data else ""
    password = data.get("password", "") if data else ""
    client_ip = request.remote_addr

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

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
    return jsonify({"error": "Invalid username or password"}), 401


@auth_bp.route("/api/auth/refresh", methods=["POST"])
def api_refresh():
    """Refresh access token using refresh token."""
    refresh_token = request.cookies.get("refresh_token") or (request.get_json() or {}).get("refresh_token")

    if not refresh_token:
        return jsonify({"error": "Refresh token required"}), 401

    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")
    if not payload:
        return jsonify({"error": "Invalid or expired refresh token"}), 401

    # Check if token exists in database
    token_record = app.db["refresh_tokens"].find_one({"token": refresh_token})
    if not token_record:
        return jsonify({"error": "Refresh token not found"}), 401

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
def check_admin():
    """Check if current user is admin (returns 200 with isAdmin flag, no 403)."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        # Check if user is admin; normalize to strict bool and use app.db (patched in tests)
        user = app.db["users"].find_one({"username": username})
        is_admin = bool(user and user.get("is_admin", False))

        return jsonify({"isAdmin": is_admin}), 200
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
    # GET request - render login page
    return render_template("login.html")


