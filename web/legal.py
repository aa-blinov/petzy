"""The privacy policy's facts and the user's consent to it (152-ФЗ, and Kazakhstan's Law No. 94-V).

The policy and consent texts live in the app (frontend/src/pages/Privacy.tsx);
what only the person running this server knows comes from the environment,
so a fork or a new operator changes it without touching code:

  PRIVACY_OPERATOR         who processes the data: full name or organisation
  PRIVACY_CONTACT_EMAIL    where to write about it
  PRIVACY_SERVER_LOCATION  the country the database server is in

Consent is asked once per policy version: at sign-up, and again from
everyone signed in when PRIVACY_POLICY_VERSION changes.
"""

import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response

import web.app as app
from web.app import api, logger
from web.errors import error_response
from web.messages import get_message
from web.schemas import ErrorResponse, LegalInfoResponse, PrivacyConsentRequest, SuccessResponse
from web.security import login_required

legal_bp = Blueprint("legal", __name__)

# The date of the current wording («.2» for a second one that day). Bump it
# when the policy or the consent text changes in substance: everyone is
# asked to agree again.
# 2026-09-28.2: the server's country among the countries data goes to.
# 2026-09-28.3: users from Kazakhstan too (Law No. 94-V alongside 152-ФЗ).
PRIVACY_POLICY_VERSION = "2026-09-28.3"


def consent_record() -> dict:
    return {"version": PRIVACY_POLICY_VERSION, "accepted_at": datetime.now(timezone.utc)}


def consent_needed(user: dict) -> bool:
    return (user.get("privacy_consent") or {}).get("version") != PRIVACY_POLICY_VERSION


@legal_bp.route("/api/legal", methods=["GET"])
@api.validate(resp=Response(HTTP_200=LegalInfoResponse), tags=["account"])
def legal_info():
    """What the privacy policy page fills in: operator, contact, where the data is."""
    return jsonify(
        {
            "policy_version": PRIVACY_POLICY_VERSION,
            "operator": os.getenv("PRIVACY_OPERATOR", "").strip(),
            "contact_email": os.getenv("PRIVACY_CONTACT_EMAIL", "").strip(),
            "server_location": os.getenv("PRIVACY_SERVER_LOCATION", "").strip(),
            "backups_kept_days": max(1, int(os.getenv("BACKUP_KEEP", "3") or 3)),
        }
    )


@legal_bp.route("/api/me/privacy-consent", methods=["POST"])
@login_required
@api.validate(
    body=Request(PrivacyConsentRequest),
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse),
    tags=["account"],
)
def accept_privacy_policy():
    """Agree to the current policy version (the app asks when it changes)."""
    data = request.context.body  # type: ignore[attr-defined]
    if data.version != PRIVACY_POLICY_VERSION:
        # The page was open while a new wording came out: show the new one.
        return error_response("privacy_version_outdated")
    app.db.users.update_one({"username": request.current_user}, {"$set": {"privacy_consent": consent_record()}})
    logger.info(f"Privacy consent: user={request.current_user}, version={PRIVACY_POLICY_VERSION}")
    return get_message("privacy_consent_saved")
