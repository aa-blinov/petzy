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

    Without VAPID keys on the server the answer is 422 ``push_not_configured``: push is optional, and the
    app treats it like a browser without push.
    """
    public_key = PUSH_CONFIG["vapid_public_key"]
    if not public_key:
        return error_response("push_not_configured")
    return jsonify({"public_key": public_key})


@push_bp.route("/api/push/subscribe", methods=["POST"])
@login_required
@api.validate(
    body=Request(PushSubscribeRequest),
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["push"],
)
def subscribe():
    """Save (or refresh) a browser's push subscription.

    One subscription per ``endpoint``: subscribing the same browser again updates it instead of adding a second.
    ``timezone`` is an IANA zone: medication reminder times are read on this clock (the first subscription on
    record among a pet's recipients decides); an unknown name answers 422.
    ``endpoint`` must be an https URL of a known push service, not an IP
    address. An endpoint already registered to another account with other keys answers 422
    ``push_subscription_taken``; with the same keys the subscription moves to the caller.
    """
    try:
        username = request.current_user
        data = request.context.body  # type: ignore[attr-defined]

        # An endpoint is per browser, not per account: on a shared computer
        # a second person turning notifications on gets the same endpoint
        # back and takes the row over, which is the Push API's own way.
        # Only the browser holds the subscription's keys, though, so a
        # takeover needs the same keys. An endpoint alone (seen in a log,
        # say) doesn't let anyone move another person's device, and with
        # it their reminders, to their own account.
        existing = app.db.push_subscriptions.find_one({"endpoint": data.endpoint}, {"username": 1, "keys": 1})
        if existing and existing.get("username") != username:
            if existing.get("keys") != data.keys.model_dump():
                app.logger.warning(f"Push subscription takeover refused: user={username}")
                return error_response("push_subscription_taken")
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
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["push"],
)
def unsubscribe():
    """Remove a browser's push subscription.

    Only the caller's own subscription is removed, so one account cannot switch off another's device. An endpoint
    that is already gone is not an error: the result is the same.
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
