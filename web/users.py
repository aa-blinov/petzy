"""Admin-only user management routes."""

from datetime import datetime, timezone

import bcrypt
from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response

from web.app import api, logger  # shared logger and api
from web.security import login_required, admin_required
import web.app as app  # to access patched app.db in tests
from web.security import ADMIN_USERNAME
from web.messages import get_message
from web.schemas import (
    UserCreate,
    UserUpdate,
    UserResponseWrapper,
    UserListResponse,
    UserPasswordResetRequest,
    SuccessResponse,
    ErrorResponse,
)
from web.errors import error_response


users_bp = Blueprint("users", __name__)


@users_bp.route("/api/users", methods=["GET"])
@login_required
@admin_required
@api.validate(resp=Response(HTTP_200=UserListResponse), tags=["users"])
def get_users():
    """Get list of all users (admin only)."""
    users = list(app.db["users"].find({}).sort("created_at", -1))

    for user in users:
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        if isinstance(user.get("created_at"), datetime):
            user["created_at"] = user["created_at"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"users": users})


@users_bp.route("/api/users", methods=["POST"])
@login_required
@admin_required
@api.validate(
    body=Request(UserCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["users"],
)
def create_user():
    """Create a new user (admin only)."""
    try:
        # `context` is injected by flask-pydantic-spec at runtime; static type checker doesn't know this attribute.
        data = request.context.body  # type: ignore[attr-defined]
        username = data.username
        password = data.password

        existing = app.db["users"].find_one({"username": username})
        if existing:
            return error_response("user_exists")

        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        current_user = getattr(request, "current_user", "admin")

        user_data = {
            "username": username,
            "password_hash": password_hash,
            "full_name": data.full_name or "",
            "email": data.email or "",
            "created_at": datetime.now(timezone.utc),
            "created_by": current_user,
            "is_active": True,
        }

        result = app.db["users"].insert_one(user_data)
        user_data["_id"] = str(result.inserted_id)
        user_data.pop("password_hash", None)
        if isinstance(user_data.get("created_at"), datetime):
            user_data["created_at"] = user_data["created_at"].strftime("%Y-%m-%d %H:%M")

        logger.info(f"User created: username={user_data['username']}, created_by={current_user}")
        return get_message("user_created", status=201, user=user_data)

    except ValueError as e:
        current_user = getattr(request, "current_user", "admin")
        logger.warning(f"Invalid input data for user creation: user={current_user}, error={e}")
        return error_response("validation_error", str(e))


@users_bp.route("/api/users/<username>", methods=["GET"])
@login_required
@admin_required
@api.validate(
    resp=Response(HTTP_200=UserResponseWrapper, HTTP_404=ErrorResponse),
    tags=["users"],
)
def get_user(username):
    """Get user information (admin only)."""
    user = app.db["users"].find_one({"username": username})
    if not user:
        return error_response("user_not_found")

    user["_id"] = str(user["_id"])
    user.pop("password_hash", None)
    if isinstance(user.get("created_at"), datetime):
        user["created_at"] = user["created_at"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"user": user})


@users_bp.route("/api/users/<username>", methods=["PUT"])
@login_required
@admin_required
@api.validate(
    body=Request(UserUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_404=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["users"],
)
def update_user(username):
    """Update user information (admin only)."""
    try:
        user = app.db["users"].find_one({"username": username})
        if not user:
            return error_response("user_not_found")

        # `context` is injected by flask-pydantic-spec at runtime; static checker doesn't know this attribute.
        data = request.context.body  # type: ignore[attr-defined]
        update_data = {}

        if data.full_name is not None:
            update_data["full_name"] = data.full_name
        if data.email is not None:
            update_data["email"] = data.email
        if data.is_active is not None:
            update_data["is_active"] = data.is_active
        if data.password is not None:
            # Hash the new password
            password_hash = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
            update_data["password_hash"] = password_hash

        if not update_data:
            return error_response("validation_error_no_update_data")

        result = app.db["users"].update_one({"username": username}, {"$set": update_data})

        if result.matched_count == 0:
            return error_response("user_not_found")

        logger.info(f"User updated: username={username}, updated_by={getattr(request, 'current_user', 'admin')}")
        return get_message("user_updated")

    except ValueError as e:
        current_user = getattr(request, "current_user", "admin")
        logger.warning(f"Invalid input data for user update: username={username}, user={current_user}, error={e}")
        return error_response("validation_error", str(e))


@users_bp.route("/api/users/<username>", methods=["DELETE"])
@login_required
@admin_required
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_404=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["users"],
)
def delete_user(username):
    """Deactivate user (admin only)."""
    try:
        if username == ADMIN_USERNAME:
            return error_response("validation_error_admin_deactivation")

        result = app.db["users"].update_one({"username": username}, {"$set": {"is_active": False}})

        if result.matched_count == 0:
            return error_response("user_not_found")

        logger.info(
            f"User deactivated: username={username}, deactivated_by={getattr(request, 'current_user', 'admin')}"
        )
        return get_message("user_deactivated")

    except ValueError as e:
        current_user = getattr(request, "current_user", "admin")
        logger.warning(f"Invalid input data for user deactivation: username={username}, user={current_user}, error={e}")
        return error_response("validation_error", str(e))


@users_bp.route("/api/users/<username>/reset-password", methods=["POST"])
@login_required
@admin_required
@api.validate(
    body=Request(UserPasswordResetRequest),
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_404=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["users"],
)
def reset_user_password(username):
    """Reset user password (admin only)."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        new_password = data.password

        user = app.db["users"].find_one({"username": username})
        if not user:
            return error_response("user_not_found")

        password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

        result = app.db["users"].update_one({"username": username}, {"$set": {"password_hash": password_hash}})

        if result.matched_count == 0:
            return error_response("user_not_found")

        logger.info(f"Password reset: username={username}, reset_by={getattr(request, 'current_user', 'admin')}")
        return get_message("user_password_reset")

    except ValueError as e:
        current_user = getattr(request, "current_user", "admin")
        logger.warning(f"Invalid input data for password reset: username={username}, user={current_user}, error={e}")
        return error_response("validation_error", str(e))
