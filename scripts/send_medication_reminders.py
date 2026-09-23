"""Sends a Web Push notification for two kinds of due reminders:
medication doses, and documents whose expiry date is coming up.

Runs as its own long-lived process (the ``reminders`` service in
docker-compose.yml) rather than inside the gunicorn app — gunicorn runs
several worker processes (see gunicorn.conf.py), and an in-process thread
there would fire once per worker, sending every reminder that many times
over.

Timezone: the app has never stored one anywhere (every other "what time is
it" check takes the client's own wall clock instead), but a background job
has no client to ask. A push subscription now carries the browser's own
IANA timezone name, captured once at subscribe time — that's what "the
scheduled 08:00" (or "N days before expiry") is interpreted in for a pet's
owner. A pet whose owner hasn't subscribed has no timezone to go on, so its
reminders simply never fire (documented v1 limitation), even if a
shared_with user has.

Usage:
    python -m scripts.send_medication_reminders
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pywebpush import webpush, WebPushException

# Must be imported before web.medications: that module does `import web.app
# as app` for shared app.db/app.logger access (the convention every
# blueprint uses), and web/app.py's own bottom-of-file
# `from web.medications import medications_bp` only succeeds if
# web.medications is imported as a *side effect* of web.app loading first
# — importing web.medications directly, as the very first thing this
# process does, makes Python start loading web.app mid-way through
# web.medications's own import, which then can't find medications_bp on
# the still-partially-initialized module. Every other entrypoint (the
# gunicorn app itself, dev_local.py) happens to import web.app first for
# unrelated reasons; this script has no such reason of its own, so it
# has to be explicit.
import web.app  # noqa: F401
from web.medications import UPCOMING_LOOKAHEAD_DAYS, compute_taken_counts

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("send_medication_reminders")

# How wide a window counts as "the dose just became due". Matched to a bit
# more than the outer loop's own poll interval (60s) so a slow tick or a
# GC pause doesn't let a slot fall through the gap between two polls.
TICK_SECONDS = 90

# How many days ahead of a document's own expires_at to send the one-time
# "this is expiring soon" heads up (a vaccination certificate, insurance
# policy, etc.) — long enough to actually book a vet appointment before
# it lapses.
DOCUMENT_EXPIRY_REMINDER_DAYS_BEFORE = 14


def _iter_subscribed_pets(db, now_utc: datetime):
    """Yields ``(pet, now_local, recipient_subs)`` for every pet whose
    owner has an active push subscription — shared groundwork for both
    medication-dose and document-expiry due-checking below.

    ``now_local`` is naive, in the owner's own IANA timezone (captured at
    subscribe time), so it compares directly against other naive local
    values already stored elsewhere (medication_intakes.date_time, a
    document's plain "YYYY-MM-DD" expires_at). ``recipient_subs`` is the
    owner's own subscriptions plus any shared_with user's.
    """
    subscriptions_by_username: dict = {}
    for sub in db.push_subscriptions.find({}):
        subscriptions_by_username.setdefault(sub["username"], []).append(sub)
    if not subscriptions_by_username:
        return

    for pet in db.pets.find({"owner": {"$in": list(subscriptions_by_username.keys())}}):
        owner = pet.get("owner")
        owner_subs = subscriptions_by_username.get(owner)
        if not owner_subs:
            continue

        # A user with several subscribed devices could in principle have
        # subscribed each from a different timezone (traveling) — the
        # first one on record is treated as canonical for this pet's
        # schedule rather than trying to reconcile several.
        try:
            owner_tz = ZoneInfo(owner_subs[0]["timezone"])
        except Exception:
            logger.warning(
                f"Unknown timezone {owner_subs[0]['timezone']!r} for user {owner}; skipping pet {pet['_id']}"
            )
            continue

        # Known gap: a moment scheduled inside a spring-forward DST gap
        # (e.g. 02:30 on the day Europe/Berlin jumps 02:00->03:00) can
        # never equal any real UTC instant's local time, so a medication
        # dose there is silently skipped for that one day, once a year,
        # in DST-observing zones — accepted as a v1 limitation rather
        # than tracking each owner's last-checked local time to catch
        # skipped slots after the fact. Document-expiry checks (whole
        # calendar days, not exact times) aren't affected by this.
        now_local = now_utc.astimezone(owner_tz).replace(tzinfo=None)

        recipient_subs = list(owner_subs)
        for shared_username in pet.get("shared_with", []):
            recipient_subs.extend(subscriptions_by_username.get(shared_username, []))

        yield pet, now_local, recipient_subs


def find_due_medication_reminders(db, now_utc: datetime, tick_seconds: int = TICK_SECONDS) -> list:
    """Active medications whose next scheduled slot just became due, not
    yet taken, and not yet notified about.

    Returns a list of ``{"medication": <doc>, "date": "YYYY-MM-DD", "time":
    "HH:MM", "subscriptions": [<push_subscriptions doc>, ...]}`` — one
    entry per due slot, carrying every subscription (owner's own devices
    plus any shared_with user's) that should be notified about it.
    """
    due = []
    for pet, now_local, recipient_subs in _iter_subscribed_pets(db, now_utc):
        pet_id = str(pet["_id"])
        medications = list(db.medications.find({"pet_id": pet_id, "is_active": True}))
        if not medications:
            continue

        weekday = now_local.weekday()
        today_start = datetime(now_local.year, now_local.month, now_local.day)
        window_end = today_start + timedelta(days=UPCOMING_LOOKAHEAD_DAYS + 1)
        date_key = today_start.strftime("%Y-%m-%d")

        pet_med_ids = [str(m["_id"]) for m in medications]
        taken_counts = compute_taken_counts(db, pet_med_ids, today_start, window_end)

        for med in medications:
            schedule = med.get("schedule", {})
            if weekday not in schedule.get("days", []):
                continue
            sched_times = sorted(schedule.get("times", []))
            if not sched_times:
                continue

            med_id_str = str(med["_id"])
            taken_count = taken_counts.get((med_id_str, date_key), 0)

            for slot_index, t in enumerate(sched_times):
                if slot_index < taken_count:
                    continue  # already given today

                try:
                    dose_hour, dose_min = map(int, t.split(":"))
                except (ValueError, TypeError):
                    continue
                slot_time = today_start.replace(hour=dose_hour, minute=dose_min, second=0, microsecond=0)
                seconds_since_due = (now_local - slot_time).total_seconds()
                if not (0 <= seconds_since_due < tick_seconds):
                    continue  # not due yet, or due too long ago to still be "just now"

                if db.medication_reminders_sent.find_one({"medication_id": med_id_str, "date": date_key, "time": t}):
                    continue  # already notified for this exact slot

                due.append({"medication": med, "date": date_key, "time": t, "subscriptions": recipient_subs})

    return due


def find_due_document_expiry_reminders(
    db, now_utc: datetime, days_before: int = DOCUMENT_EXPIRY_REMINDER_DAYS_BEFORE
) -> list:
    """Documents with a set ``expires_at`` that has just entered the
    "remind me" window (0 to ``days_before`` days out), not yet notified
    about for that exact expiry date.

    Unlike medication doses, this fires once per document (not once per
    day) — dedupe is keyed on (document_id, expires_at), so editing a
    document's expiry date (e.g. after renewing a vaccination) naturally
    produces a fresh reminder instead of staying silenced by the old one.
    """
    due = []
    for pet, now_local, recipient_subs in _iter_subscribed_pets(db, now_utc):
        pet_id = str(pet["_id"])
        today = now_local.date()

        for document in db.documents.find({"pet_id": pet_id, "expires_at": {"$nin": [None, ""]}}):
            expires_at_str = document.get("expires_at")
            try:
                expires_date = datetime.strptime(expires_at_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue

            days_until = (expires_date - today).days
            if not (0 <= days_until <= days_before):
                continue

            doc_id_str = str(document["_id"])
            already_sent = db.document_expiry_reminders_sent.find_one(
                {"document_id": doc_id_str, "expires_at": expires_at_str}
            )
            if already_sent:
                continue

            due.append({"document": document, "expires_at": expires_at_str, "subscriptions": recipient_subs})

    return due


def _send_push_to_subscriptions(
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


def send_reminders(db, now_utc: datetime, vapid_private_key: str, vapid_claims: dict) -> int:
    """find_due_medication_reminders + find_due_document_expiry_reminders,
    push each one, and record a dedupe row per item. Returns the number
    of notifications actually delivered.
    """
    sent = 0

    for slot in find_due_medication_reminders(db, now_utc):
        medication = slot["medication"]
        payload = {"title": "Пора дать лекарство", "body": f"{medication['name']} — {slot['time']}", "url": "/"}
        sent += _send_push_to_subscriptions(db, slot["subscriptions"], payload, vapid_private_key, vapid_claims)

        # Written after the sends above, not before: if the process is
        # killed between a successful webpush() call and this insert, a
        # fast container restart (docker-compose's restart policy) can
        # find the same slot still inside its window on the next tick and
        # send it again — one duplicate notification. The alternative
        # (write the dedupe row first) trades that for the opposite
        # failure — a crash in that gap would silently mark the slot
        # "sent" and skip it forever — which is worse for a medication
        # reminder than an occasional duplicate.
        try:
            db.medication_reminders_sent.insert_one(
                {
                    "medication_id": str(medication["_id"]),
                    "date": slot["date"],
                    "time": slot["time"],
                    "created_at": now_utc,
                    "expires_at": now_utc + timedelta(days=30),
                }
            )
        except Exception:
            # Unique-index race from two overlapping runs — the slot is
            # recorded either way, nothing more to do.
            logger.warning(f"Could not record dedupe row for medication={medication['_id']}, slot={slot['time']}")

    for expiry in find_due_document_expiry_reminders(db, now_utc):
        document = expiry["document"]
        payload = {
            "title": "Скоро истекает срок документа",
            "body": f"{document.get('title', 'Документ')} — до {expiry['expires_at']}",
            "url": "/documents",
        }
        sent += _send_push_to_subscriptions(db, expiry["subscriptions"], payload, vapid_private_key, vapid_claims)

        try:
            db.document_expiry_reminders_sent.insert_one(
                {
                    "document_id": str(document["_id"]),
                    "expires_at": expiry["expires_at"],
                    "created_at": now_utc,
                    # Named differently from medication_reminders_sent's
                    # own "expires_at" TTL field on purpose — this
                    # collection's "expires_at" already means the
                    # document's own expiry date (the dedupe key), so the
                    # TTL trigger needs a field name of its own.
                    "purge_at": now_utc + timedelta(days=90),
                }
            )
        except Exception:
            logger.warning(
                f"Could not record dedupe row for document={document['_id']}, expires_at={expiry['expires_at']}"
            )

    return sent


if __name__ == "__main__":
    import os

    from web.db import db as real_db

    vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
    vapid_claims_email = os.getenv("VAPID_CLAIMS_EMAIL", "admin@example.com")

    if not vapid_private_key:
        logger.error("VAPID_PRIVATE_KEY is not set — reminders cannot be sent. Exiting.")
        raise SystemExit(1)

    vapid_claims = {"sub": f"mailto:{vapid_claims_email}"}

    logger.info("Reminder sender started (60s poll interval).")
    while True:
        try:
            sent = send_reminders(real_db, datetime.now(timezone.utc), vapid_private_key, vapid_claims)
            if sent:
                logger.info(f"Sent {sent} reminder(s).")
        except Exception:
            # Never let one bad tick kill the whole process — the next
            # tick tries again on its own.
            logger.exception("Reminder tick failed")
        time.sleep(60)
