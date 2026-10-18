"""Personal access tokens: a long-lived key for a script or an assistant (an MCP server), with the scopes it may use.

The owner makes one while signed in with their login, since a token cannot make tokens, and sees its secret once:

- the secret is ``ptz_`` and 43 random characters; only its SHA-256 is kept, so a copy of the database opens nothing;
- it lists what it may do (scopes), has a name, and ends after 1 to 365 days (90 by default);
- it reaches only the routes marked ``pat_allowed`` (web/decorators.py), and only with the scope each of them names;
- it can be revoked at once, and a person has at most 10 working tokens.

The check on each request is in web/security.py (``check_personal_token``).
"""

import secrets
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response

import web.app as app  # db and logger, so the test patches are visible
from web.app import api, logger
from web.errors import error_response
from web.helpers import utc_iso
from web.schemas import (
    ErrorResponse,
    PersonalTokenCreate,
    PersonalTokenCreated,
    PersonalTokenList,
    PersonalTokenRevoked,
)
from web.security import (
    PERSONAL_TOKEN_PREFIX,
    PERSONAL_TOKEN_SCOPES,
    get_current_user,
    hash_personal_token,
    login_required,
)

personal_tokens_bp = Blueprint("personal_tokens", __name__)

# A person does not need more than this many working tokens; more is a sign of tokens left lying around.
MAX_ACTIVE_TOKENS = 10
MAX_EXPIRES_IN_DAYS = 365


def _now() -> datetime:
    """UTC, naive: what the database gives back."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(moment: datetime) -> str:
    return utc_iso(moment)


def _active(now: datetime) -> dict:
    return {"revoked_at": None, "expires_at": {"$gt": now}}


def _item(record: dict) -> dict:
    """A token as the list shows it. Its secret is not kept, so it cannot be shown."""
    return {
        "id": str(record["_id"]),
        "name": record.get("name") or "",
        "scopes": list(record.get("scopes") or []),
        "prefix": record.get("prefix") or "",
        "created_at": _iso(record["created_at"]),
        "expires_at": _iso(record["expires_at"]),
        "last_used_at": _iso(record["last_used_at"]) if record.get("last_used_at") else None,
        "revoked_at": _iso(record["revoked_at"]) if record.get("revoked_at") else None,
    }


@personal_tokens_bp.route("/api/me/tokens", methods=["POST"])
@login_required
@api.validate(
    body=Request(PersonalTokenCreate),
    resp=Response(HTTP_201=PersonalTokenCreated, HTTP_422=ErrorResponse),
    tags=["tokens"],
)
def create_personal_token():
    """Make a personal access token for a script or an assistant. Its secret is in this answer, once.

    Only a sign-in with the login makes one: a personal token is refused here (403 ``token_not_allowed``). ``scopes``
    holds at least one of ``pets:read``, ``events:write``, ``history:read`` and ``medical:read``; another name answers
    422 ``personal_token_scope_unknown``. ``expires_in_days`` is from 1 to 365, 90 by default, and any other value
    answers 422 ``personal_token_expiry_invalid``. At most 10 working tokens a person: the next one answers 422
    ``personal_token_limit`` until one of them is revoked or runs out.
    """
    username, _ = get_current_user()
    body = request.context.body  # type: ignore[attr-defined]
    if not body.scopes:
        return error_response("personal_token_scope_required")
    if any(scope not in PERSONAL_TOKEN_SCOPES for scope in body.scopes):
        return error_response("personal_token_scope_unknown")
    if not 1 <= body.expires_in_days <= MAX_EXPIRES_IN_DAYS:
        return error_response("personal_token_expiry_invalid")

    now = _now()
    tokens = app.db["api_tokens"]
    if tokens.count_documents({"username": username, **_active(now)}) >= MAX_ACTIVE_TOKENS:
        return error_response("personal_token_limit")

    token = PERSONAL_TOKEN_PREFIX + secrets.token_urlsafe(32)
    record = {
        "username": username,
        "name": body.name,
        "token_hash": hash_personal_token(token),
        "prefix": token[:8],
        "scopes": list(dict.fromkeys(body.scopes)),
        "created_at": now,
        "expires_at": now + timedelta(days=body.expires_in_days),
        "last_used_at": None,
        "revoked_at": None,
    }
    record["_id"] = tokens.insert_one(record).inserted_id
    logger.info(f"Personal token made: id={record['_id']}, user={username}")

    response = jsonify(
        {
            "id": str(record["_id"]),
            "name": record["name"],
            "scopes": record["scopes"],
            "expires_at": _iso(record["expires_at"]),
            "prefix": record["prefix"],
            "token": token,
        }
    )
    response.status_code = 201
    response.headers["Cache-Control"] = "no-store"
    return response


@personal_tokens_bp.route("/api/me/tokens", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=PersonalTokenList), tags=["tokens"])
def list_personal_tokens():
    """List your personal access tokens, newest first, without their secrets.

    Revoked and expired tokens stay in the list, with their last use, so a token that stopped working can be told
    apart from one that was never used. Only the first eight characters of a token (``prefix``) are shown here.
    """
    username, _ = get_current_user()
    found = app.db["api_tokens"].find({"username": username}).sort("created_at", -1)
    response = jsonify({"tokens": [_item(record) for record in found]})
    response.headers["Cache-Control"] = "private, no-store"
    return response


@personal_tokens_bp.route("/api/me/tokens/<token_id>", methods=["DELETE"])
@login_required
@api.validate(resp=Response(HTTP_200=PersonalTokenRevoked, HTTP_404=ErrorResponse), tags=["tokens"])
def revoke_personal_token(token_id):
    """Revoke one of your personal access tokens, or delete one that is already revoked.

    The first call revokes a working token: it stops working at once, and it stays in the list, revoked, until it is
    deleted. A second call on that token takes its record out of the database, and the answer says so (``deleted``:
    true). After that the token is gone: a call on it answers 404 ``personal_token_not_found``, as does a token of
    another person, or an id that is not one.
    """
    username, _ = get_current_user()
    try:
        oid = ObjectId(token_id)
    except (InvalidId, TypeError):
        return error_response("personal_token_not_found")
    tokens = app.db["api_tokens"]
    if tokens.update_one(
        {"_id": oid, "username": username, "revoked_at": None}, {"$set": {"revoked_at": _now()}}
    ).matched_count:
        logger.info(f"Personal token revoked: id={token_id}, user={username}")
        return jsonify({"revoked": True, "deleted": False})
    # Already revoked: this call takes the record out of the database.
    if tokens.delete_one({"_id": oid, "username": username, "revoked_at": {"$ne": None}}).deleted_count:
        logger.info(f"Personal token deleted: id={token_id}, user={username}")
        return jsonify({"revoked": True, "deleted": True})
    return error_response("personal_token_not_found")
