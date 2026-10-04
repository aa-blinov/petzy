"""A link to a pet's medical card for a vet: read-only, with an end, and one that can be taken back.

The card holds what a vet asks for (allergies, medicines, vaccinations, the clinic's phone), so the link is made
on purpose, by someone who can see the pet, and is dropped by the same hand or by itself:

- the secret is 256 random bits, shown once; only its SHA-256 is kept, so a copy of the database opens nothing;
- it works for 1, 7 or 30 days and can be revoked at once;
- what it opens is the card and its PDF, built as for a viewer who cannot edit; no account, no other route;
- every answer says «do not store, do not index», and the page for the link is not offered to search engines.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from bson import ObjectId
from flask import Blueprint, jsonify, make_response, request
from flask_pydantic_spec import Request, Response

import web.app as app  # db, logger
from web.app import api, limiter
from web.errors import error_response
from web.helpers import get_pet_and_validate
from web.medical_card import _today, build_medical_card
from web.schemas import (
    ErrorResponse,
    MedicalCardQuery,
    MedicalShareCreate,
    MedicalShareCreated,
    MedicalShareRevoked,
    MedicalSharesResponse,
    SharedMedicalCardResponse,
)
from web.security import get_current_user, login_required

medical_share_bp = Blueprint("medical_share", __name__)

# A pet does not need more than a few links at once; more is a sign of links left lying around.
MAX_ACTIVE_SHARES = 10
# A link that has ended is kept for a while (who made it, when), then the database drops it.
KEEP_AFTER_END = timedelta(days=30)
PUBLIC_LIMIT = "60 per minute"


def _now() -> datetime:
    """UTC, naive: what the database gives back."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _item(share: dict) -> dict:
    return {
        "id": str(share["_id"]),
        "username": share.get("username") or "",
        "created_at": share["created_at"].isoformat() + "Z",
        "expires_at": share["expires_at"].isoformat() + "Z",
    }


def _active(now: datetime) -> dict:
    return {"revoked_at": None, "expires_at": {"$gt": now}}


@medical_share_bp.route("/api/pets/<pet_id>/medical-card/shares", methods=["POST"])
@login_required
@api.validate(
    body=Request(MedicalShareCreate),
    resp=Response(HTTP_201=MedicalShareCreated, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["pets"],
)
def create_share(pet_id):
    """Make a link to the card for a vet. The secret is in the answer once and is not kept."""
    username, _ = get_current_user()
    pet, access_error = get_pet_and_validate(pet_id, username, require_owner=False)
    if access_error:
        return access_error[0], access_error[1]
    now = _now()
    shares = app.db["medical_shares"]
    if shares.count_documents({"pet_id": pet_id, **_active(now)}) >= MAX_ACTIVE_SHARES:
        return error_response("validation_error", "Слишком много действующих ссылок. Отзовите ненужные")
    days = request.context.body.days  # type: ignore[attr-defined]
    token = secrets.token_urlsafe(32)
    doc = {
        "pet_id": pet_id,
        "username": username,
        "token_hash": hash_token(token),
        "created_at": now,
        "expires_at": now + timedelta(days=days),
        "purge_at": now + timedelta(days=days) + KEEP_AFTER_END,
        "revoked_at": None,
    }
    doc["_id"] = shares.insert_one(doc).inserted_id
    response = jsonify({"share": _item(doc), "token": token, "path": f"/share/medical/{token}"})
    response.status_code = 201
    response.headers["Cache-Control"] = "private, no-store"
    return response


@medical_share_bp.route("/api/pets/<pet_id>/medical-card/shares", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=MedicalSharesResponse, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse),
    tags=["pets"],
)
def list_shares(pet_id):
    """The links to the card that work now, newest first. Without their secrets: those are not kept."""
    username, _ = get_current_user()
    pet, access_error = get_pet_and_validate(pet_id, username, require_owner=False)
    if access_error:
        return access_error[0], access_error[1]
    found = app.db["medical_shares"].find({"pet_id": pet_id, **_active(_now())}).sort("created_at", -1)
    response = jsonify({"shares": [_item(s) for s in found]})
    response.headers["Cache-Control"] = "private, no-store"
    return response


@medical_share_bp.route("/api/pets/<pet_id>/medical-card/shares/<share_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(HTTP_200=MedicalShareRevoked, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse),
    tags=["pets"],
)
def revoke_share(pet_id, share_id):
    """Take a link back: it stops opening the card at once."""
    username, _ = get_current_user()
    pet, access_error = get_pet_and_validate(pet_id, username, require_owner=False)
    if access_error:
        return access_error[0], access_error[1]
    try:
        oid = ObjectId(share_id)
    except Exception:
        return error_response("not_found")
    result = app.db["medical_shares"].update_one(
        {"_id": oid, "pet_id": pet_id, "revoked_at": None}, {"$set": {"revoked_at": _now()}}
    )
    if result.matched_count == 0:
        return error_response("not_found")
    return jsonify({"revoked": True})


def _shared_pet(token: str) -> tuple[Optional[dict], Optional[dict]]:
    """``(pet, share)`` for a link that works, else ``(None, None)``: a wrong, ended or revoked one all look the same."""
    if not token or len(token) > 128:
        return None, None
    share = app.db["medical_shares"].find_one({"token_hash": hash_token(token), **_active(_now())})
    if not share:
        return None, None
    try:
        pet = app.db["pets"].find_one({"_id": ObjectId(share["pet_id"])})
    except Exception:
        pet = None
    return (pet, share) if pet else (None, None)


def _private(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@medical_share_bp.route("/api/shared/medical-card/<token>", methods=["GET"])
@limiter.limit(PUBLIC_LIMIT)
@api.validate(
    query=MedicalCardQuery,
    resp=Response(HTTP_200=SharedMedicalCardResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["pets"],
)
def get_shared_card(token):
    """The card by a link: no sign-in, read-only, only while the link works."""
    pet, share = _shared_pet(token)
    if not pet:
        return error_response("not_found")
    today = _today(request.context.query.tz)  # type: ignore[attr-defined]
    card = build_medical_card(pet, "", today)
    return _private(jsonify({"card": card, "expires_at": share["expires_at"].isoformat() + "Z"}))


@medical_share_bp.route("/api/shared/medical-card/<token>/pdf", methods=["GET"])
@limiter.limit(PUBLIC_LIMIT)
@api.validate(
    query=MedicalCardQuery,
    resp=Response(HTTP_200=None, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["pets"],
)
def get_shared_card_pdf(token):
    """The same card as a PDF, by the link."""
    from web.medical_card_full import build_full_card
    from web.medical_card_pdf import render_medical_card_pdf

    pet, _ = _shared_pet(token)
    if not pet:
        return error_response("not_found")
    today = _today(request.context.query.tz)  # type: ignore[attr-defined]
    try:
        content = render_medical_card_pdf(build_full_card(pet, "", today))
    except Exception as e:
        app.logger.error(f"Shared medical card PDF failed: pet_id={pet['_id']}, error={e}", exc_info=True)
        return error_response("internal_error")
    name = "".join(c for c in pet.get("name", "") if c.isalnum() or c in " -_").strip().replace(" ", "_") or "pet"
    filename = f"медкарта_{name}_{today.strftime('%Y%m%d')}.pdf"
    response = make_response(content)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
    return _private(response)
