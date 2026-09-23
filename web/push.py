"""Web Push subscription management.

Registers/removes a browser's PushManager subscription so the medication
reminder sender (``scripts/send_medication_reminders.py``) knows where to
deliver a notification, and in what timezone the pet owner's "08:00" is
meant. Sending itself lives entirely in that separate script, not here —
this blueprint only manages the subscription rows it reads.
"""

from datetime import datetime, timezone

from flask import jsonify, request, Blueprint
from flask_pydantic_spec import Request, Response

import web.app as app  # to access patched app.db in tests
from web.app import api
from web.configs import PUSH_CONFIG
from web.errors import error_response
from web.messages import get_message
from web.schemas import (
    ErrorResponse,
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    SuccessResponse,
    VapidPublicKeyResponse,
)
from web.security import login_required

push_bp = Blueprint("push", __name__)


@push_bp.route("/api/push/vapid-public-key", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=VapidPublicKeyResponse, HTTP_422=ErrorResponse),
    tags=["push"],
)
def get_vapid_public_key():
    """Return the VAPID public key PushManager.subscribe() needs.

    422 when the server has no VAPID keys configured — push is an
    optional feature, not something the app requires to run, so the
    frontend treats this the same as "browser doesn't support push".
    """
    public_key = PUSH_CONFIG["vapid_public_key"]
    if not public_key:
        return error_response("push_not_configured")
    return jsonify({"public_key": public_key})


@push_bp.route("/api/push/subscribe", methods=["POST"])
@login_required
@api.validate(
    body=Request(PushSubscribeRequest),
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse),
    tags=["push"],
)
def subscribe():
    """Save (or refresh) a browser's push subscription.

    Upserts on ``endpoint`` — a browser's own subscription URL is already
    a stable per-device identity, so re-subscribing the same browser
    (e.g. after clearing the toggle off and on) updates the row in place
    instead of accumulating duplicates.
    """
    try:
        username = request.current_user
        data = request.context.body  # type: ignore[attr-defined]

        # A browser's own subscription endpoint is inherently per-device,
        # not per-account — on a shared computer, a second person signing
        # in and flipping the same toggle will get the *same* endpoint
        # back from pushManager.subscribe(), silently reassigning this
        # row (and this device's reminders) from the first user to them.
        # That's the Push API's own semantics, not a bug to prevent here,
        # but it should at least be visible in the logs rather than
        # invisible when it happens.
        existing = app.db.push_subscriptions.find_one({"endpoint": data.endpoint}, {"username": 1})
        if existing and existing.get("username") != username:
            app.logger.warning(
                f"Push subscription endpoint reassigned from user={existing.get('username')} to user={username}"
            )

        app.db.push_subscriptions.update_one(
            {"endpoint": data.endpoint},
            {
                "$set": {
                    "username": username,
                    "keys": data.keys.model_dump(),
                    "timezone": data.timezone,
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
        app.logger.info(f"Push subscription saved: user={username}, timezone={data.timezone}")
        return get_message("push_subscribed")
    except Exception as e:
        app.logger.error(f"Error saving push subscription: {e}")
        return error_response("internal_error")


@push_bp.route("/api/push/unsubscribe", methods=["POST"])
@login_required
@api.validate(
    body=Request(PushUnsubscribeRequest),
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse),
    tags=["push"],
)
def unsubscribe():
    """Remove a browser's push subscription.

    Scoped to the requesting user's own ``endpoint`` so one account can't
    unsubscribe another user's device by guessing/replaying its endpoint.
    Removing an endpoint that's already gone is not an error — the end
    state ("this browser has no subscription") is identical either way.
    """
    try:
        username = request.current_user
        data = request.context.body  # type: ignore[attr-defined]

        app.db.push_subscriptions.delete_one({"endpoint": data.endpoint, "username": username})
        app.logger.info(f"Push subscription removed: user={username}")
        return get_message("push_unsubscribed")
    except Exception as e:
        app.logger.error(f"Error removing push subscription: {e}")
        return error_response("internal_error")
