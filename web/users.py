"""Admin-only user management routes."""

from datetime import datetime, timezone

import bcrypt
from flask import Blueprint, jsonify, request

from web.app import logger  # shared logger
from web.security import login_required, admin_required
import web.app as app  # to access patched app.db in tests
from web.security import ADMIN_USERNAME


users_bp = Blueprint("users", __name__)


@users_bp.route("/api/users", methods=["GET"])
@login_required
@admin_required
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
def create_user():
    """Create a new user (admin only)."""
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "")
        full_name = data.get("full_name", "").strip()
        email = data.get("email", "").strip()

        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400

        existing = app.db["users"].find_one({"username": username})
        if existing:
            return jsonify({"error": "Пользователь с таким именем уже существует"}), 400

        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        current_user = getattr(request, "current_user", "admin")

        user_data = {
            "username": username,
            "password_hash": password_hash,
            "full_name": full_name,
            "email": email,
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
        return jsonify({"success": True, "user": user_data, "message": "Пользователь создан"}), 201

    except ValueError as e:
        logger.warning(f"Invalid input data for user creation: created_by={current_user}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error creating user: created_by={current_user}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@users_bp.route("/api/users/<username>", methods=["GET"])
@login_required
@admin_required
def get_user(username):
    """Get user information (admin only)."""
    user = app.db["users"].find_one({"username": username})
    if not user:
        return jsonify({"error": "Пользователь не найден"}), 404

    user["_id"] = str(user["_id"])
    user.pop("password_hash", None)
    if isinstance(user.get("created_at"), datetime):
        user["created_at"] = user["created_at"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"user": user})


@users_bp.route("/api/users/<username>", methods=["PUT"])
@login_required
@admin_required
def update_user(username):
    """Update user information (admin only)."""
    try:
        user = app.db["users"].find_one({"username": username})
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404

        data = request.get_json()
        update_data = {}

        if "full_name" in data:
            update_data["full_name"] = data.get("full_name", "").strip()
        if "email" in data:
            update_data["email"] = data.get("email", "").strip()
        if "is_active" in data:
            update_data["is_active"] = bool(data.get("is_active"))

        if not update_data:
            return jsonify({"error": "Нет данных для обновления"}), 400

        result = app.db["users"].update_one({"username": username}, {"$set": update_data})

        if result.matched_count == 0:
            return jsonify({"error": "Пользователь не найден"}), 404

        logger.info(f"User updated: username={username}, updated_by={getattr(request, 'current_user', 'admin')}")
        return jsonify({"success": True, "message": "Пользователь обновлен"}), 200

    except ValueError as e:
        logger.warning(f"Invalid input data for user update: username={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error updating user: username={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@users_bp.route("/api/users/<username>", methods=["DELETE"])
@login_required
@admin_required
def delete_user(username):
    """Deactivate user (admin only)."""
    try:
        if username == ADMIN_USERNAME:
            return jsonify({"error": "Нельзя деактивировать администратора"}), 400

        result = app.db["users"].update_one({"username": username}, {"$set": {"is_active": False}})

        if result.matched_count == 0:
            return jsonify({"error": "Пользователь не найден"}), 404

        logger.info(
            f"User deactivated: username={username}, deactivated_by={getattr(request, 'current_user', 'admin')}"
        )
        return jsonify({"success": True, "message": "Пользователь деактивирован"}), 200

    except ValueError as e:
        logger.warning(f"Invalid input data for user deactivation: username={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error deactivating user: username={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@users_bp.route("/api/users/<username>/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_user_password(username):
    """Reset user password (admin only)."""
    try:
        data = request.get_json()
        new_password = data.get("password", "")

        if not new_password:
            return jsonify({"error": "Новый пароль обязателен"}), 400

        user = app.db["users"].find_one({"username": username})
        if not user:
            return jsonify({"error": "Пользователь не найден"}), 404

        password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

        result = app.db["users"].update_one({"username": username}, {"$set": {"password_hash": password_hash}})

        if result.matched_count == 0:
            return jsonify({"error": "Пользователь не найден"}), 404

        logger.info(f"Password reset: username={username}, reset_by={getattr(request, 'current_user', 'admin')}")
        return jsonify({"success": True, "message": "Пароль изменен"}), 200

    except ValueError as e:
        logger.warning(f"Invalid input data for password reset: username={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        logger.error(f"Error resetting password: username={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500
