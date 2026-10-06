"""Admin-only user management routes."""

import re
from datetime import datetime, timezone

import bcrypt
from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response

from web.app import api, logger  # shared logger and api
from web.security import login_required, admin_required, is_admin, revoke_user_sessions
import web.app as app  # to access patched app.db in tests
from web.security import ADMIN_USERNAME
from web.messages import get_message
from web.schemas import (
    UserCreate,
    UserUpdate,
    UserResponseWrapper,
    UserListResponse,
    UserSearchResponse,
    UserPasswordResetRequest,
    UserPublicProfile,
    FormDefaults,
    SuccessResponse,
    ErrorResponse,
)
from web.errors import error_response


users_bp = Blueprint("users", __name__)

# One page of the admin account list. Small enough to read through and
# scroll further, so a big table of accounts does not arrive in one answer.
USERS_PER_PAGE = 20


@users_bp.route("/api/users", methods=["GET"])
@login_required
@admin_required
@api.validate(resp=Response(HTTP_200=UserListResponse), tags=["users"])
def get_users():
    """One page of the account list, newest first, with a search by login or name (admin only).

    The search runs over every account whatever is typed into it, which is
    why both this route and the search sit behind @admin_required: see
    search_users() for the account lookup every signed-in person may run,
    deliberately narrowed to their own circle.
    """
    users, total, page, per_page = users_page(request.args.get("q", "").strip(), request.args.get("page"))
    return jsonify({"users": users, "total": total, "page": page, "per_page": per_page})


def _page_number(raw_page) -> int:
    """A 1-based page number, whatever came in the query string."""
    try:
        return max(1, int(raw_page)) if raw_page else 1
    except (TypeError, ValueError):
        return 1


def users_page(query: str, raw_page, per_page: int = USERS_PER_PAGE):
    """A page of accounts, newest first, and how many the search found in all.

    Returns (users, total, page, per_page): the client needs the total to
    say how many there are and to refuse a page past the end.
    """
    page = _page_number(raw_page)

    mongo_query: dict = {}
    if query:
        # re.escape: the query is text to look for, not a pattern to run.
        pattern = {"$regex": re.escape(query), "$options": "i"}
        mongo_query["$or"] = [{"username": pattern}, {"full_name": pattern}]

    total = app.db["users"].count_documents(mongo_query)
    users = list(app.db["users"].find(mongo_query).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page))

    for user in users:
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        if isinstance(user.get("created_at"), datetime):
            user["created_at"] = user["created_at"].strftime("%Y-%m-%d %H:%M")

    return users, total, page, per_page


@users_bp.route("/api/users/search", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=UserSearchResponse), tags=["users"])
def search_users():
    """Who to share a pet with: people you already share pets with, and
    anyone by their exact login.

    This used to be a substring search over every account, which any
    logged-in user could run (an empty query listed twenty): a way to see
    the people of every other household. Suggestions now come only from
    your own circle, people you share a pet with either way round, whose
    logins you already see on those pets; anyone else is found by typing
    the whole login (case-insensitive), the way other apps share by email.
    """
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify({"users": []})
    me = request.current_user

    circle: set[str] = set()
    for pet in app.db.pets.find({"$or": [{"owner": me}, {"shared_with": me}]}, {"owner": 1, "shared_with": 1}):
        circle.add(pet.get("owner"))
        circle.update(pet.get("shared_with") or [])
    circle.discard(me)
    circle.discard(None)

    lowered = query.lower()
    found = {u for u in circle if u.lower().startswith(lowered)}
    # re.escape: the query is a login, not a pattern to run.
    exact = app.db["users"].find_one(
        {"is_active": True, "username": {"$regex": f"^{re.escape(query)}$", "$options": "i"}},
        {"username": 1},
    )
    if exact and exact["username"] != me:
        found.add(exact["username"])
    active = {u["username"] for u in app.db["users"].find({"username": {"$in": sorted(found)}, "is_active": True})}
    return jsonify({"users": [{"username": u} for u in sorted(active)][:20]})


@users_bp.route("/api/me/form-defaults", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=FormDefaults), tags=["users"])
def get_form_defaults():
    """The signed-in user's form defaults («Настройки форм»)."""
    user = app.db["users"].find_one({"username": request.current_user}, {"form_defaults": 1}) or {}
    return jsonify({"form_defaults": user.get("form_defaults") or {}})


@users_bp.route("/api/me/form-defaults", methods=["PUT"])
@login_required
@api.validate(body=Request(FormDefaults), resp=Response(HTTP_200=FormDefaults), tags=["users"])
def put_form_defaults():
    """Replace the signed-in user's form defaults, for all of their devices."""
    form_defaults = request.context.body.form_defaults  # type: ignore[attr-defined]
    app.db["users"].update_one({"username": request.current_user}, {"$set": {"form_defaults": form_defaults}})
    return jsonify({"form_defaults": form_defaults})


@users_bp.route("/api/users/<username>/profile", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=UserPublicProfile, HTTP_404=ErrorResponse), tags=["users"])
def get_user_public_profile(username):
    """A co-owner's public profile — name and pets you both have access to.

    Deliberately not admin-only (unlike GET /api/users/<username>): the
    point is letting a shared user see who they're sharing a pet with.
    Gated on actually sharing a pet instead, so it can't be used to look
    up an arbitrary username — a mismatch returns the same 404 as a
    genuinely nonexistent one, rather than a distinguishable 403, so it
    doesn't confirm a username exists to someone who isn't sharing
    anything with them.
    """
    requester = request.current_user

    target = app.db["users"].find_one({"username": username})
    if not target:
        return error_response("user_not_found")

    # id and name, not the name alone: on the person's card each pet's name
    # opens its medical card. Access to that card is still the card's own
    # check on the server (require_pet_access), so a name that came from
    # somewhere else opens nothing extra.
    common_pets: list[dict] = []
    if requester != username and not is_admin(requester):
        pets_cursor = app.db["pets"].find(
            {
                "$and": [
                    {"$or": [{"owner": requester}, {"shared_with": requester}]},
                    {"$or": [{"owner": username}, {"shared_with": username}]},
                ]
            },
            {"name": 1},
        )
        common_pets = [{"id": str(p["_id"]), "name": p["name"]} for p in pets_cursor]
        if not common_pets:
            return error_response("user_not_found")
    else:
        # Self, or an admin looking someone up — no sharing requirement,
        # but still worth surfacing the pets in common for an admin.
        pets_cursor = app.db["pets"].find({"$or": [{"owner": username}, {"shared_with": username}]}, {"name": 1})
        common_pets = [{"id": str(p["_id"]), "name": p["name"]} for p in pets_cursor]

    created_at = target.get("created_at")
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%Y-%m-%d %H:%M")

    return jsonify(
        {
            "username": target["username"],
            "full_name": target.get("full_name") or None,
            "created_at": created_at or "",
            "shared_pets": common_pets,
        }
    )


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
        # Nobody switches himself off, whoever sends the request: deactivation ends every session of that
        # account, and the admin list is then the one screen the person cannot open to undo it. The delete
        # route has always refused the built-in admin; this is the same boundary on the update route, where
        # it was missing — one request was enough to lock oneself out of it.
        if data.is_active is False and username == getattr(request, "current_user", None):
            return error_response("validation_error_admin_deactivation", "Нельзя деактивировать самого себя")
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
        # A new password or a disabled account ends the sessions already open.
        if data.password is not None or data.is_active is False:
            revoke_user_sessions(username)

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
        # Nobody deactivates himself, not only the built-in admin: the account the person is standing in
        # loses its rights at once, and the admin list is then the one screen that person cannot open to
        # undo it. The list has always hidden the swipe for your own row; the rule belonged here too.
        if username == getattr(request, "current_user", None):
            return error_response("validation_error_admin_deactivation", "Нельзя деактивировать самого себя")

        result = app.db["users"].update_one({"username": username}, {"$set": {"is_active": False}})

        if result.matched_count == 0:
            return error_response("user_not_found")
        revoke_user_sessions(username)

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
        revoke_user_sessions(username)

        logger.info(f"Password reset: username={username}, reset_by={getattr(request, 'current_user', 'admin')}")
        return get_message("user_password_reset")

    except ValueError as e:
        current_user = getattr(request, "current_user", "admin")
        logger.warning(f"Invalid input data for password reset: username={username}, user={current_user}, error={e}")
        return error_response("validation_error", str(e))
