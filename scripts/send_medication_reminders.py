"""Sends a Web Push notification when a scheduled medication dose becomes due.

Runs as its own long-lived process (the ``reminders`` service in
docker-compose.yml) rather than inside the gunicorn app — gunicorn runs
several worker processes (see gunicorn.conf.py), and an in-process thread
there would fire once per worker, sending every reminder that many times
over.

Timezone: the app has never stored one anywhere (every other "what time is
it" check takes the client's own wall clock instead), but a background job
has no client to ask. A push subscription now carries the browser's own
IANA timezone name, captured once at subscribe time — that's what "the
scheduled 08:00" is interpreted in for a pet's owner. A pet whose owner
hasn't subscribed has no timezone to go on, so its reminders simply never
fire (documented v1 limitation), even if a shared_with user has.

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


def find_due_reminders(db, now_utc: datetime, tick_seconds: int = TICK_SECONDS) -> list:
    """Active medications whose next scheduled slot just became due, not
    yet taken, and not yet notified about.

    Returns a list of ``{"medication": <doc>, "date": "YYYY-MM-DD", "time":
    "HH:MM", "subscriptions": [<push_subscriptions doc>, ...]}`` — one
    entry per due slot, carrying every subscription (owner's own devices
    plus any shared_with user's) that should be notified about it.
    """
    subscriptions_by_username: dict = {}
    for sub in db.push_subscriptions.find({}):
        subscriptions_by_username.setdefault(sub["username"], []).append(sub)

    if not subscriptions_by_username:
        return []

    pets = list(db.pets.find({"owner": {"$in": list(subscriptions_by_username.keys())}}))
    if not pets:
        return []
    pets_by_id = {str(p["_id"]): p for p in pets}

    pet_ids = list(pets_by_id.keys())
    medications = list(db.medications.find({"pet_id": {"$in": pet_ids}, "is_active": True}))
    if not medications:
        return []

    meds_by_pet: dict = {}
    for med in medications:
        meds_by_pet.setdefault(med["pet_id"], []).append(med)

    due = []
    for pet_id, pet_meds in meds_by_pet.items():
        pet = pets_by_id.get(pet_id)
        if not pet:
            continue

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
            logger.warning(f"Unknown timezone {owner_subs[0]['timezone']!r} for user {owner}; skipping pet {pet_id}")
            continue

        # Naive, representing the owner's local wall clock — matching how
        # every intake's own date_time is already stored (parse_datetime
        # builds it straight from client-supplied date+time strings, no
        # tzinfo at all), so it compares directly against them.
        #
        # Known gap: a dose scheduled inside a spring-forward DST gap
        # (e.g. 02:30 on the day Europe/Berlin jumps 02:00->03:00) can
        # never equal any real UTC instant's local time, so it's silently
        # skipped for that one day, once a year, in DST-observing zones —
        # accepted as a v1 limitation rather than tracking each owner's
        # last-checked local time to catch skipped slots after the fact.
        now_local = now_utc.astimezone(owner_tz).replace(tzinfo=None)
        weekday = now_local.weekday()
        today_start = datetime(now_local.year, now_local.month, now_local.day)
        window_end = today_start + timedelta(days=UPCOMING_LOOKAHEAD_DAYS + 1)
        date_key = today_start.strftime("%Y-%m-%d")

        pet_med_ids = [str(m["_id"]) for m in pet_meds]
        taken_counts = compute_taken_counts(db, pet_med_ids, today_start, window_end)

        recipient_subs = list(owner_subs)
        for shared_username in pet.get("shared_with", []):
            recipient_subs.extend(subscriptions_by_username.get(shared_username, []))

        for med in pet_meds:
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


def send_reminders(db, now_utc: datetime, vapid_private_key: str, vapid_claims: dict) -> int:
    """find_due_reminders + push each one, recording a dedupe row per slot
    and pruning subscriptions the push service reports as gone.

    Returns the number of notifications actually delivered.
    """
    sent = 0
    for slot in find_due_reminders(db, now_utc):
        medication = slot["medication"]
        payload = json.dumps(
            {
                "title": "Пора дать лекарство",
                "body": f"{medication['name']} — {slot['time']}",
                "url": "/",
            }
        )

        for sub in slot["subscriptions"]:
            try:
                webpush(
                    subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]},
                    data=payload,
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

    logger.info("Medication reminder sender started (60s poll interval).")
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
