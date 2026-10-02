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
scheduled 08:00" (or "N days before expiry") is interpreted in: the
owner's, or, when only someone the pet is shared with subscribed, theirs.
Every subscribed person with access to the pet gets its reminders.

Usage:
    python -m scripts.send_medication_reminders
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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
from web.courses import course_covers
from web.medical_records import SOON_DAYS, record_states, repeating_document_ids
from web.medications import UPCOMING_LOOKAHEAD_DAYS, compute_taken_counts
from web.push_delivery import send_push_to_subscriptions

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


# Reminders that go by the calendar day (a document's end, a repeat date) have no time of their own, and sent on the
# day's first tick they arrived at 00:01 local time. They go out from this hour on, when someone can act on them.
DATE_REMINDER_HOUR = 9


# A vaccination or a treatment whose repeat date passed up to this many days ago
# still gets one «просрочено» push (if nobody heard about it before). Older
# than that is not news, and the first tick after a deploy must not shower
# people with pushes about records from long ago.
MEDICAL_OVERDUE_GRACE_DAYS = 3

# One push is easy to miss, so a repeat date is reminded about in steps: «скоро» (the first day it is inside the
# window of its kind), «скоро» again with three days left, on the day itself, just after it, and once more a week
# after, when it is still not done. The same grace as above bounds each late step, so nothing old is brought up.
MEDICAL_CLOSE_DAYS = 3
MEDICAL_LATE_DAYS = 7

# kind: (soon, today, overdue, still overdue)
MEDICAL_KIND_TITLES = {
    "vaccination": ("Скоро прививка", "Сегодня прививка", "Прививка просрочена", "Прививка всё ещё просрочена"),
    "parasite": (
        "Скоро обработка от паразитов",
        "Сегодня обработка от паразитов",
        "Обработка от паразитов просрочена",
        "Обработка от паразитов всё ещё просрочена",
    ),
}


def medical_stage(kind: str, days_until: int):
    """Which step of the reminders a repeat date is at, or None when it is between steps (or out of range).

    Exactly one stage at a time, so a record that is found late (a new subscriber, a restart, a record entered
    when its date is close) gets one push for where it is now, not a pile for the steps it has missed.
    """
    if days_until == 0:
        return "today"
    if 1 <= days_until <= MEDICAL_CLOSE_DAYS:
        return "soon3"
    if MEDICAL_CLOSE_DAYS < days_until <= SOON_DAYS[kind]:
        return "soon"
    if -MEDICAL_OVERDUE_GRACE_DAYS <= days_until < 0:
        return "overdue"
    if -(MEDICAL_LATE_DAYS + MEDICAL_OVERDUE_GRACE_DAYS - 1) <= days_until <= -MEDICAL_LATE_DAYS:
        return "late"
    return None


def _days_phrase(days: int) -> str:
    if days == 0:
        return "сегодня"
    if days == 1:
        return "завтра"
    word = (
        "день"
        if days % 10 == 1 and days % 100 != 11
        else "дня"
        if 2 <= days % 10 <= 4 and not 12 <= days % 100 <= 14
        else "дней"
    )
    return f"через {days} {word}"


def medical_reminder_payload(item: dict) -> dict:
    """The push for one due record: what it is, for which pet, when, and a link
    to the pet's medical card (the pet in the URL, so it opens the right one)."""
    record, pet = item["record"], item["pet"]
    soon_title, today_title, overdue_title, late_title = MEDICAL_KIND_TITLES[record["kind"]]
    stage = item["stage"]
    if stage in ("soon", "soon3"):
        title, when = soon_title, _days_phrase(item["days_until"])
    elif stage == "today":
        title, when = today_title, "сегодня"
    else:
        due = datetime.strptime(record["next_due"], "%Y-%m-%d").strftime("%d.%m.%Y")
        title, when = (late_title if stage == "late" else overdue_title), f"срок был {due}"
    return {
        "title": title,
        "body": f"{pet.get('name', 'Питомец')}: {record.get('title', '')}, {when}",
        # «Вся карта»: an overdue or due record is put right there, and a card that is complete would open for the vet.
        "url": f"/pets/{pet['_id']}/medical-card?mode=fill",
    }


def _iter_subscribed_pets(db, now_utc: datetime):
    """Yields ``(pet, now_local, recipient_subs)`` for every pet at least
    one of whose people (the owner or anyone it's shared with) has an
    active push subscription — shared groundwork for both medication-dose
    and document-expiry due-checking below.

    ``now_local`` is naive, in the pet's timezone (see below), so it
    compares directly against other naive local values already stored
    elsewhere (medication_intakes.date_time, a document's plain
    "YYYY-MM-DD" expires_at). ``recipient_subs`` is every subscription of
    the owner and of each shared_with user: whoever gives the dose gets
    the reminder, not only the owner.
    """
    subscriptions_by_username: dict = {}
    for sub in db.push_subscriptions.find({}):
        subscriptions_by_username.setdefault(sub["username"], []).append(sub)
    if not subscriptions_by_username:
        return

    subscribed = list(subscriptions_by_username.keys())
    for pet in db.pets.find({"$or": [{"owner": {"$in": subscribed}}, {"shared_with": {"$in": subscribed}}]}):
        people = [pet.get("owner"), *pet.get("shared_with", [])]
        recipient_subs = [sub for username in people for sub in subscriptions_by_username.get(username, [])]
        if not recipient_subs:
            continue

        # The schedule's «08:00» is read in the owner's timezone when the
        # owner is subscribed, otherwise in the first subscribed person's
        # (a family lives in one). A user with several devices could have
        # subscribed each from a different timezone (traveling): the first
        # one on record is canonical rather than trying to reconcile them.
        tz_name = recipient_subs[0]["timezone"]
        try:
            pet_tz = ZoneInfo(tz_name)
        except Exception:
            logger.warning(f"Unknown timezone {tz_name!r}; skipping pet {pet['_id']}")
            continue

        # Known gap: a moment scheduled inside a spring-forward DST gap
        # (e.g. 02:30 on the day Europe/Berlin jumps 02:00->03:00) can
        # never equal any real UTC instant's local time, so a medication
        # dose there is silently skipped for that one day, once a year,
        # in DST-observing zones — accepted as a v1 limitation rather
        # than tracking each owner's last-checked local time to catch
        # skipped slots after the fact. Document-expiry checks (whole
        # calendar days, not exact times) aren't affected by this.
        now_local = now_utc.astimezone(pet_tz).replace(tzinfo=None)

        yield pet, now_local, recipient_subs


def find_due_medication_reminders(
    db, now_utc: datetime, tick_seconds: int = TICK_SECONDS, subscribed_pets=None
) -> list:
    """Active medications whose next scheduled slot just became due, not
    yet taken, and not yet notified about.

    Returns a list of ``{"medication": <doc>, "date": "YYYY-MM-DD", "time":
    "HH:MM", "subscriptions": [<push_subscriptions doc>, ...]}`` — one
    entry per due slot, carrying every subscription (owner's own devices
    plus any shared_with user's) that should be notified about it.

    ``subscribed_pets`` lets a caller that also needs
    ``find_due_document_expiry_reminders`` in the same tick pass in an
    already-materialized ``list(_iter_subscribed_pets(...))`` instead of
    this function running that same subscriptions+pets scan a second time
    (see ``send_reminders``). Defaults to computing it itself so this stays
    usable on its own.
    """
    due = []
    pets_iter = subscribed_pets if subscribed_pets is not None else _iter_subscribed_pets(db, now_utc)
    for pet, now_local, recipient_subs in pets_iter:
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
            # Not before the course begins, not after it ends.
            if not course_covers(med, date_key):
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

                due.append(
                    {"medication": med, "pet": pet, "date": date_key, "time": t, "subscriptions": recipient_subs}
                )

    return due


def find_due_document_expiry_reminders(
    db, now_utc: datetime, days_before: int = DOCUMENT_EXPIRY_REMINDER_DAYS_BEFORE, subscribed_pets=None
) -> list:
    """Documents with a set ``expires_at`` that has just entered the
    "remind me" window (0 to ``days_before`` days out), not yet notified
    about for that exact expiry date.

    Unlike medication doses, this fires once per document (not once per
    day) — dedupe is keyed on (document_id, expires_at), so editing a
    document's expiry date (e.g. after renewing a vaccination) naturally
    produces a fresh reminder instead of staying silenced by the old one.

    See ``find_due_medication_reminders`` for what ``subscribed_pets`` is for.
    """
    due = []
    pets_iter = subscribed_pets if subscribed_pets is not None else _iter_subscribed_pets(db, now_utc)
    for pet, now_local, recipient_subs in pets_iter:
        if now_local.hour < DATE_REMINDER_HOUR:
            continue
        pet_id = str(pet["_id"])
        today = now_local.date()

        # A certificate that is part of a vaccination or treatment record has that
        # record's reminder; the document's own would be the second push for one shot.
        covered = repeating_document_ids(pet_id, db)
        for document in db.documents.find({"pet_id": pet_id, "expires_at": {"$nin": [None, ""]}}):
            if str(document["_id"]) in covered:
                continue
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

            due.append(
                {"document": document, "pet": pet, "expires_at": expires_at_str, "subscriptions": recipient_subs}
            )

    return due


def find_due_medical_reminders(db, now_utc: datetime, subscribed_pets=None) -> list:
    """Vaccinations and parasite treatments whose repeat date is near (within
    ``SOON_DAYS`` of its kind) or has just passed (up to
    ``MEDICAL_OVERDUE_GRACE_DAYS``), not yet notified about for that exact date
    and stage.

    Like the document-expiry reminder: no time of day, dedupe on
    (record, next_due, stage), so entering the next shot (a newer record with
    the same title replaces the old one, see web.medical_records) or moving
    the date makes a fresh reminder, and the replaced record is never
    reminded about.
    """
    due = []
    pets_iter = subscribed_pets if subscribed_pets is not None else _iter_subscribed_pets(db, now_utc)
    for pet, now_local, recipient_subs in pets_iter:
        if now_local.hour < DATE_REMINDER_HOUR:
            continue
        today = now_local.date()
        records = list(db.medical_records.find({"pet_id": str(pet["_id"]), "kind": {"$in": list(SOON_DAYS)}}))
        if not records:
            continue
        states = record_states(records, today)
        for record in records:
            if states[str(record["_id"])]["superseded"] or not record.get("next_due"):
                continue
            try:
                days_until = (datetime.strptime(record["next_due"], "%Y-%m-%d").date() - today).days
            except (ValueError, TypeError):
                continue
            stage = medical_stage(record["kind"], days_until)
            if stage is None:
                continue
            if db.medical_due_reminders_sent.find_one(
                {"record_id": str(record["_id"]), "next_due": record["next_due"], "stage": stage}
            ):
                continue
            due.append(
                {
                    "record": record,
                    "pet": pet,
                    "stage": stage,
                    "days_until": days_until,
                    "subscriptions": recipient_subs,
                }
            )
    return due


def send_reminders(db, now_utc: datetime, vapid_private_key: str, vapid_claims: dict) -> int:
    """find_due_medication_reminders + find_due_document_expiry_reminders,
    push each one, and record a dedupe row per item. Returns the number
    of notifications actually delivered.
    """
    sent = 0
    # Computed once and shared — otherwise each of the two finders below
    # would independently re-run the same push_subscriptions + pets scan.
    subscribed_pets = list(_iter_subscribed_pets(db, now_utc))

    for slot in find_due_medication_reminders(db, now_utc, subscribed_pets=subscribed_pets):
        medication = slot["medication"]
        pet = slot["pet"]
        # The pet in the text and in the link: with two pets «Синулокс, 08:00» does not say whose dose it is, and the
        # feed opens on the pet last chosen on that phone.
        payload = {
            "title": "Пора дать лекарство",
            "body": f"{pet.get('name', 'Питомец')}: {medication['name']}, {slot['time']}",
            "url": f"/?pet={pet['_id']}",
        }
        sent += send_push_to_subscriptions(db, slot["subscriptions"], payload, vapid_private_key, vapid_claims)

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

    for expiry in find_due_document_expiry_reminders(db, now_utc, subscribed_pets=subscribed_pets):
        document = expiry["document"]
        pet = expiry["pet"]
        payload = {
            "title": "Скоро истекает срок документа",
            "body": f"{pet.get('name', 'Питомец')}: {document.get('title', 'Документ')}, до {expiry['expires_at']}",
            "url": f"/documents?pet={pet['_id']}",
        }
        sent += send_push_to_subscriptions(db, expiry["subscriptions"], payload, vapid_private_key, vapid_claims)

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

    for item in find_due_medical_reminders(db, now_utc, subscribed_pets=subscribed_pets):
        record = item["record"]
        sent += send_push_to_subscriptions(
            db, item["subscriptions"], medical_reminder_payload(item), vapid_private_key, vapid_claims
        )
        try:
            db.medical_due_reminders_sent.insert_one(
                {
                    "record_id": str(record["_id"]),
                    "next_due": record["next_due"],
                    "stage": item["stage"],
                    "created_at": now_utc,
                    # purge_at, not expires_at: next_due is the dedupe key's own date.
                    "purge_at": now_utc + timedelta(days=90),
                }
            )
        except Exception:
            logger.warning(f"Could not record dedupe row for medical record={record['_id']}, stage={item['stage']}")

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

    # Sentry started with the web app's import above; tell this process apart.
    import sentry_sdk

    sentry_sdk.set_tag("component", "reminders")

    from web.storage import cleanup_abandoned_uploads

    logger.info("Reminder sender started (60s poll interval).")
    tick = 0
    while True:
        try:
            sent = send_reminders(real_db, datetime.now(timezone.utc), vapid_private_key, vapid_claims)
            if sent:
                logger.info(f"Sent {sent} reminder(s).")
        except Exception:
            # Never let one bad tick kill the whole process — the next
            # tick tries again on its own.
            logger.exception("Reminder tick failed")
        # This is the app's one periodic worker, so it also sweeps scan
        # uploads that were never confirmed, about once an hour.
        if tick % 60 == 0:
            try:
                removed = cleanup_abandoned_uploads(real_db)
                if removed:
                    logger.info(f"Removed {removed} abandoned scan upload(s).")
            except Exception:
                logger.exception("Scan upload cleanup failed")
        tick += 1
        time.sleep(60)
