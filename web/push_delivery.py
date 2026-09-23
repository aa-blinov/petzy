"""Shared Web Push sending helper.

Used by two very different callers: the standalone reminders process
(``scripts/send_medication_reminders.py``, its own long-lived loop deciding
*when* something is due) and the Flask app itself (a newly-created event
whose value looks abnormal notifies the pet's subscribers immediately, from
inside the request that created it — see ``web/trend_alerts.py`` and
``web/events.py``). Both need the exact same "send this payload to these
subscriptions, prune the dead ones" logic, so it lives here once instead of
twice.
"""

import json
import logging

from pywebpush import webpush, WebPushException

logger = logging.getLogger("push_delivery")

# A push service that's slow or unreachable must not be able to hang the
# caller indefinitely — this bounds how long `web/events.py`'s create_event
# (which calls this synchronously, in-request, on the anomaly path) can be
# blocked by any single subscription.
WEBPUSH_TIMEOUT_SECONDS = 5


def send_push_to_subscriptions(
    db, subscriptions: list, payload: dict, vapid_private_key: str, vapid_claims: dict
) -> int:
    """Send one push payload to each subscription; on 404/410 the push
    service is telling us the subscription is gone, so prune it. Returns
    the number of subscriptions actually delivered to."""
    data = json.dumps(payload)
    sent = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                data=data,
                vapid_private_key=vapid_private_key,
                # webpush() sets claims["aud"] from the endpoint's own
                # origin — a fresh copy per call, or the second
                # subscription in the loop would inherit the first
                # endpoint's audience.
                vapid_claims=dict(vapid_claims),
                timeout=WEBPUSH_TIMEOUT_SECONDS,
            )
            sent += 1
        except WebPushException as e:
            status = e.response.status_code if e.response is not None else None
            if status in (404, 410):
                db.push_subscriptions.delete_one({"endpoint": sub["endpoint"]})
                logger.info(f"Removed expired push subscription: endpoint={sub['endpoint']}")
            else:
                logger.warning(f"webpush failed (status={status}): {e}")
        except Exception:
            logger.exception(f"Unexpected error sending push notification to endpoint={sub['endpoint']}")
    return sent


def get_pet_push_subscriptions(db, pet: dict) -> list:
    """The owner's + every shared_with user's active push subscriptions
    for one pet — the recipient list for a notification about that pet,
    computed on demand rather than by scanning every subscribed pet (the
    reminders process's ``_iter_subscribed_pets`` does the reverse: given
    the time, find which pets are due; this is given one pet, right now)."""
    usernames = [pet.get("owner"), *pet.get("shared_with", [])]
    return list(db.push_subscriptions.find({"username": {"$in": usernames}}))
