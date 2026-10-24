"""Medication management and intake logging endpoints."""

from flask import Blueprint, jsonify, request, g
from flask_pydantic_spec import Request, Response
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from typing import Optional
from pymongo.errors import DuplicateKeyError

import web.app as app
from web.security import login_required
from web.app import api
from web.errors import error_response, MedicationNotFoundDuringDeletion
from web.courses import course_covers, course_status
from web.dose_slots import (
    CARRY_OVER_HOURS,
    DUPLICATE_WINDOW_MINUTES,
    group_by_day,
    minutes_of_day,
    open_slots,
    slot_closers,
)
from web.decorators import require_pet_access, require_record_access
from web.helpers import (
    parse_event_datetime_safe,
    apply_pagination,
    local_day_start,
    local_now,
    ru_dose_unit,
    valid_tz,
)
from web.messages import get_message
from web.schemas import (
    MedicationCreate,
    MedicationRestock,
    MedicationUpdate,
    MedicationListResponse,
    MedicationDetailResponse,
    MedicationIntakeCreate,
    MedicationIntakeUpdate,
    MedicationIntakeListResponse,
    UpcomingDosesResponse,
    SuccessResponse,
    ErrorResponse,
    PetIdPaginationQuery,
    MedicationDetailQuery,
    MedicationListQuery,
    UpcomingDosesQuery,
)
from web.idempotency import idempotent
from web.offline import (
    conflict_answer,
    is_stale,
    record_version,
    require_local_record_access,
    tombstone_for_name,
    version_guard,
)
from web.sync import log_deletion, now_utc
from web.helpers import clock_in_zone, utc_iso, zoned_iso

medications_bp = Blueprint("medications", __name__)

# How far ahead get_upcoming_doses will look for the next scheduled dose
# once today's are all given (see its own "look ahead" branch below).
# log_intake's own future-date bound must cover the same span — otherwise
# the dashboard widget could offer a dose as "pre-loggable" that logging
# it would then reject.
UPCOMING_LOOKAHEAD_DAYS = 7

# «Заканчивается» once the stock covers this many days or fewer, unless
# the course sets its own (inventory_warning_days) or, for courses made
# before that, an amount (inventory_warning_threshold).
DEFAULT_WARNING_DAYS = 3

# A skipped dose is an intake too, so the slot counts as handled
# (web/dose_slots.py, intakes_today) and the reminder stops; it just
# isn't a dose given: no stock taken, not «последний приём», not in stats.
GIVEN_ONLY = {"skipped": {"$ne": True}}


def is_as_needed(med: dict) -> bool:
    """Whether this course is «по необходимости», as it is stored or as it was written before.

    A course made before the flag kept its mode in the schedule: no times meant
    «по необходимости». Those are read that way still, so an old course keeps
    the doses it has always had (and keeps not being reminded about); only a
    course with a real schedule is due at its times.

    A course with the flag may keep a schedule: it is stored and shown in the
    card, but nothing is reminded about it.
    """
    flag = med.get("as_needed")
    if flag is None:
        return not ((med.get("schedule") or {}).get("times") or [])
    return bool(flag)


def daily_use(med: dict) -> float:
    """How much of the stock the schedule uses per day, on average."""
    schedule = med.get("schedule") or {}
    times = len(schedule.get("times") or [])
    days = len(schedule.get("days") or [])
    return float(med.get("default_dose") or 1.0) * times * days / 7


def stock_status(med: dict) -> "tuple[float | None, bool]":
    """(days the stock lasts, whether it's running low). (None, False) when
    stock isn't tracked; days is None for a course with no schedule."""
    current = med.get("inventory_current")
    if not med.get("inventory_enabled") or current is None:
        return None, False
    use = daily_use(med)
    days_left = round(current / use, 1) if use > 0 else None
    if current <= 0:
        return days_left, True
    warning_days = med.get("inventory_warning_days")
    threshold = med.get("inventory_warning_threshold")
    if warning_days is None and threshold is not None:
        return days_left, current <= threshold
    if warning_days is None:
        warning_days = DEFAULT_WARNING_DAYS
    return days_left, days_left is not None and days_left <= warning_days


def _add_stock_status(doc: dict) -> None:
    doc["inventory_days_left"], doc["inventory_low"] = stock_status(doc)


def load_day_intakes(db, med_ids: list, window_start: datetime, window_end: datetime) -> dict:
    """(medication_id, 'YYYY-MM-DD') -> the intakes that count for that day, with the slot each carries.

    Shared by the dose widget (get_upcoming_doses), the medication list and the reminder sender, so «is this dose
    already given» cannot drift between them. See web/dose_slots.py for how an intake closes a slot.
    """
    found = db.medication_intakes.find(
        {"medication_id": {"$in": med_ids}, "date_time": {"$gte": window_start, "$lt": window_end}}
    )
    return group_by_day(found)


# A dose left unmarked this long after its time is overdue enough to be shown on a tab: marked a little late is normal.
OVERDUE_DOSE_GRACE_MINUTES = 60


def has_overdue_dose(db, pet_id: str, now_local: datetime) -> bool:
    """Whether an active course of the pet has a dose of today (or last evening, still carried over) that nobody has
    marked and whose time passed more than an hour ago. One read for the tab and the pet switcher, same slot rule as
    the dose widget (web/dose_slots.py)."""
    medications = list(db.medications.find({"pet_id": pet_id, "is_active": True}))
    if not medications:
        return False
    today_start = datetime(now_local.year, now_local.month, now_local.day)
    start = today_start - timedelta(days=1)
    day_intakes = load_day_intakes(db, [str(m["_id"]) for m in medications], start, today_start + timedelta(days=1))
    grace = timedelta(minutes=OVERDUE_DOSE_GRACE_MINUTES)
    for med in medications:
        if is_as_needed(med):
            # «По необходимости» is never due at a time, whatever it keeps in its schedule.
            continue
        schedule = med.get("schedule") or {}
        times = schedule.get("times") or []
        for day_start in (start, today_start):
            day_key = day_start.strftime("%Y-%m-%d")
            if day_start.weekday() not in schedule.get("days", []) or not course_covers(med, day_key):
                continue
            for t in open_slots(times, day_intakes.get((str(med["_id"]), day_key), [])):
                minutes = minutes_of_day(t)
                if minutes is None:
                    continue
                due = day_start + timedelta(minutes=minutes)
                if now_local - due > grace and (
                    day_start == today_start or now_local - due < timedelta(hours=CARRY_OVER_HOURS)
                ):
                    return True
    return False


def _course_named(local_id: str) -> Optional[dict]:
    """The course the device named with ``local_id``. A name is unique on the stand, so there is at most one."""
    return app.db.medications.find_one({"local_id": local_id})


def _answer_for_course_name(existing: Optional[dict], pet_id: str, local_id: str):
    """The answer to a create that names a course: the one already there (200), or why the name cannot be used.

    The same pet's course: answered as saved, and nothing is written. A course of another pet holds the name: 409
    ``local_id_taken``. No course, but a deleted one had the name: 409 ``record_deleted``, so a repeat does not bring
    the course back.
    """
    if existing is None:
        if tombstone_for_name("medication", local_id, pet_id):
            return error_response("record_deleted")
        return None
    if str(existing.get("pet_id")) != str(pet_id):
        return error_response("local_id_taken")
    return get_message("medication_created", status=200, id=str(existing["_id"]), local_id=local_id)


@medications_bp.route("/api/medications", methods=["POST"])
@login_required
@api.validate(
    body=Request(MedicationCreate),
    resp=Response(HTTP_404=ErrorResponse, HTTP_201=SuccessResponse, HTTP_409=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["medications"],
)
@require_pet_access
@idempotent
def add_medication():
    """Create a new medication course.

    The course, not the dose. A schedule is days of the week and times of day; a medicine given by occasion is sent with ``as_needed: true`` (or a schedule with no times), and then it has no reminders. If the stock is being counted, the first pack sets it. A ``local_id`` the device gives makes the request repeatable: sent again, it is answered with the course it already made (200) and nothing is written twice; a name that belongs to another pet's course is 409 ``local_id_taken``, and a name of a course that was deleted is 409 ``record_deleted``.
    """
    try:
        data = request.context.body  # type: ignore[attr-defined]
        username = g.username

        if data.local_id:
            answer = _answer_for_course_name(_course_named(data.local_id), g.pet_id, data.local_id)
            if answer:
                return answer

        medication_data = data.model_dump()
        # Признак «по необходимости» не подставляем, если клиент его не прислал: так пишет
        # установленное приложение прежней версии, и его курс «по необходимости» без времени
        # должен остаться таким, а не стать расписанием без времени.
        if medication_data.get("as_needed") is None:
            medication_data.pop("as_needed", None)
        # A course without a name keeps no field: the sparse index over names leaves an absent field out, not a null.
        if not medication_data.get("local_id"):
            medication_data.pop("local_id", None)
        medication_data["username"] = username
        medication_data["created_at"] = datetime.now(timezone.utc)
        medication_data["updated_at"] = now_utc()

        try:
            result = app.db.medications.insert_one(medication_data)
        except DuplicateKeyError:
            # Two requests naming one course at the same moment: the second one finds what the first one wrote.
            answer = _answer_for_course_name(_course_named(data.local_id), g.pet_id, data.local_id or "")
            if not data.local_id or not answer:
                raise
            return answer

        named = {"local_id": data.local_id} if data.local_id else {}
        return get_message("medication_created", status=201, id=str(result.inserted_id), **named)
    except Exception as e:
        app.logger.error(f"Error adding medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications", methods=["GET"])
@login_required
@api.validate(
    query=MedicationListQuery,
    resp=Response(HTTP_404=ErrorResponse, HTTP_200=MedicationListResponse),
    tags=["medications"],
)
@require_pet_access
def get_medications():
    """List medication courses for a pet.

    Newest first, and a finished course stays in the list with its mark instead of disappearing: the medical card wants the whole story, and a finished course is part of it. Today is the day of the zone ``tz`` names; without a known zone it is the device's ``client_date``, and UTC's day when neither is sent. Today's doses (``intakes_today``, ``scheduled_today``, ``open_slots_today``) and the course status are read against it. ``intakes_today`` counts every intake from the start of that day on, skips and doses logged ahead included. The list is not paged.
    """
    try:
        query_params = request.context.query
        pet_id = g.pet_id
        client_date_str = query_params.client_date

        cursor = app.db.medications.find({"pet_id": pet_id}).sort("created_at", -1)
        meds = list(cursor)

        if not meds:
            return jsonify({"medications": []})

        # Optimize: batch fetch all intake data at once
        med_ids = [str(med["_id"]) for med in meds]

        # Today: the zone's day when the zone is known; otherwise the device's own date; otherwise UTC's day, as before.
        today_start = local_day_start(query_params.tz)
        if client_date_str and not valid_tz(query_params.tz):
            try:
                today_start = datetime.strptime(client_date_str, "%Y-%m-%d")
            except ValueError:
                app.logger.warning(
                    f"Unparseable client_date {client_date_str!r}; falling "
                    'back to UTC — "taken today" may land on the '
                    "wrong day"
                )

        # Get all last intakes in one query using aggregation
        last_intakes_pipeline = [
            {"$match": {"medication_id": {"$in": med_ids}, **GIVEN_ONLY}},
            {"$sort": {"date_time": -1}},
            {"$group": {"_id": "$medication_id", "last_intake": {"$first": "$$ROOT"}}},
        ]
        last_intakes = {
            item["_id"]: item["last_intake"] for item in app.db.medication_intakes.aggregate(last_intakes_pipeline)
        }

        # Count intakes today for all medications in one aggregation
        today_intakes_pipeline = [
            {"$match": {"medication_id": {"$in": med_ids}, "date_time": {"$gte": today_start}}},
            {"$group": {"_id": "$medication_id", "count": {"$sum": 1}}},
        ]
        today_counts = {
            item["_id"]: item["count"] for item in app.db.medication_intakes.aggregate(today_intakes_pipeline)
        }

        # Today's intakes themselves (not only the count): which slot each one closes.
        today_intakes = load_day_intakes(
            app.db, med_ids, today_start - timedelta(days=1), today_start + timedelta(days=1)
        )

        # Process results
        for doc in meds:
            doc["_id"] = str(doc["_id"])
            # The project's date format, the same documents and pets already send, rather
            # than the web-server date a raw datetime turns into.
            # The version an edit is made from, in the same format as every other timestamp.
            doc["updated_at"] = record_version(doc) or None
            if isinstance(doc.get("created_at"), datetime):
                doc["created_at"] = utc_iso(doc["created_at"])
            med_id_str = doc["_id"]

            last_intake = last_intakes.get(med_id_str)
            if last_intake and last_intake.get("date_time"):
                dt = last_intake["date_time"]
                doc["last_taken_at"] = zoned_iso(dt, last_intake.get("tz"))
                doc["last_taken_by"] = last_intake.get("username")
                # The zone of the clock it was marked on, so a phone in another zone shows it on its own clock.
                doc["last_taken_tz"] = last_intake.get("tz")
            else:
                doc["last_taken_at"] = None
                doc["last_taken_by"] = None
                doc["last_taken_tz"] = None

            doc["intakes_today"] = today_counts.get(med_id_str, 0)
            today_key = today_start.strftime("%Y-%m-%d")
            schedule = doc.get("schedule") or {}
            # The flag, resolved for a course made before it existed, so the client
            # never has to tell «по необходимости» from an empty schedule itself.
            as_needed = is_as_needed(doc)
            doc["as_needed"] = as_needed
            due_today = (
                doc.get("is_active", True)
                and not as_needed
                and today_start.weekday() in schedule.get("days", [])
                and course_covers(doc, today_key)
            )
            doc["scheduled_today"] = bool(due_today and schedule.get("times"))
            doc["open_slots_today"] = (
                open_slots(schedule.get("times", []), today_intakes.get((med_id_str, today_key), []))
                if doc["scheduled_today"]
                else []
            )
            doc["course_status"] = course_status(doc, today_key)
            # «По 1 таб» even when the course was written with «tablet»: the list is read by a
            # person, and the stored value is left as it was written.
            doc["dose_unit"] = ru_dose_unit(doc.get("dose_unit") or doc.get("unit"))
            _add_stock_status(doc)

        return jsonify({"medications": meds})
    except Exception as e:
        app.logger.error(f"Error fetching medications: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>", methods=["GET"])
@api.validate(
    query=MedicationDetailQuery,
    resp=Response(HTTP_200=MedicationDetailResponse, HTTP_404=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications")
def get_medication(id):
    """Fetch a single medication course by id.

    The course with its stock and last dose. Thinner than an item of the list: no ``last_taken_by``,
    ``last_taken_tz``, ``scheduled_today`` or ``open_slots_today``; ``intakes_today`` is counted from
    midnight of the zone ``tz`` names, or UTC without one.
    """
    try:
        return jsonify({"medication": _medication_detail(g.record, request.context.query.tz)})  # type: ignore[attr-defined]
    except Exception as e:
        app.logger.error(f"Error fetching medication: {e}")
        return error_response("internal_error")


def _medication_detail(record: dict, tz) -> dict:
    """A course as the detail endpoint reads it: also what a rejected edit brings back as ``record``."""
    record["_id"] = str(record["_id"])
    record["as_needed"] = is_as_needed(record)
    # The list's reading of the course, so the form opened from either screen offers the same
    # buttons: «Возобновить курс» for a finished one.
    today_start = local_day_start(tz)
    record["course_status"] = course_status(record, today_start.strftime("%Y-%m-%d"))
    # Mirror the enrichment the list endpoint provides so consumers
    # don't see a stripped shape when switching from list→detail.
    pet_id = record.get("pet_id")
    if pet_id:
        last_intake = app.db.medication_intakes.find_one(
            {"medication_id": str(record["_id"]), **GIVEN_ONLY},
            sort=[("date_time", -1)],
        )
        if last_intake and last_intake.get("date_time"):
            dt = last_intake["date_time"]
            record["last_taken_at"] = zoned_iso(dt, last_intake.get("tz"))
        else:
            record.setdefault("last_taken_at", None)

        record["intakes_today"] = app.db.medication_intakes.count_documents(
            {"medication_id": str(record["_id"]), "date_time": {"$gte": today_start}}
        )
    # The same reading as in the list, so a course does not change its unit between the two
    # screens it is opened from.
    record["dose_unit"] = ru_dose_unit(record.get("dose_unit") or record.get("unit"))
    _add_stock_status(record)
    # The version an edit is made from: as the list says it.
    record["updated_at"] = record_version(record) or None
    # The list's format, not Flask's HTTP date («Tue, 13 Oct 2026 08:00:00 GMT»).
    if isinstance(record.get("created_at"), datetime):
        record["created_at"] = utc_iso(record["created_at"])
    return record


@medications_bp.route("/api/medications/<id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(MedicationUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_409=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications", deleted_kind="medication")
def update_medication(id):
    """Update a medication course.

    Fields left out keep their value; ``null`` means "not sent", and a date is cleared with an empty string. Switching the course back on (``is_active: true``) removes its end date unless a new one is sent. An empty body answers 422 ``validation_error_no_update_data``. Turning a schedule on or off says nothing about what has already been taken: the intakes keep the slots they closed. ``base_version`` is the ``updated_at`` the device last read: a course changed since answers 409 ``conflict`` with the course as it is now in ``record``; without it the change is applied. A course that was deleted answers 409 ``record_deleted``.
    """
    return _update_course(g.record, request.context.body)  # type: ignore[attr-defined]


@medications_bp.route("/api/medications/local/<local_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(MedicationUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_409=ErrorResponse),
    tags=["medications"],
)
@require_local_record_access("medications", "medication")
def update_medication_by_local_id(local_id):
    """Update a course by the ``local_id`` the device gave it, for when the device has not got the course's id.

    The same update as by id, with the same ``base_version`` check. The name stays as it was created.
    """
    return _update_course(g.record, request.context.body)  # type: ignore[attr-defined]


def _update_course(medication: dict, data):
    """The update of one course found by the access check, by its id or by the local_id the device named."""
    try:
        medication_id = medication["_id"]

        if is_stale(data.base_version, medication):
            return conflict_answer(_medication_detail(dict(medication), None))

        update_data = {k: v for k, v in data.model_dump(exclude={"base_version"}).items() if v is not None}

        # A date is cleared with "" (None is «not sent»); it is stored as None.
        for date_field in ("started_on", "ended_on"):
            if update_data.get(date_field) == "":
                update_data[date_field] = None
        # Switching a course back on while leaving its end date in the past
        # would leave it ended: turning it on takes the end away, unless the
        # same request sets a new one.
        if data.is_active is True and "ended_on" not in update_data:
            update_data["ended_on"] = None

        if not update_data:
            return error_response("validation_error_no_update_data")

        # The order of the two dates is checked against what is stored too.
        started = update_data["started_on"] if "started_on" in update_data else medication.get("started_on")
        ended = update_data["ended_on"] if "ended_on" in update_data else medication.get("ended_on")
        if started and ended and ended < started:
            return error_response("validation_error", "Окончание курса раньше его начала")

        update_data["updated_at"] = now_utc()
        result = app.db.medications.update_one(
            {"_id": medication_id, **version_guard(medication, data.base_version)}, {"$set": update_data}
        )
        if result.matched_count == 0:
            latest = app.db.medications.find_one({"_id": medication_id})
            if latest is None:
                return error_response("record_deleted")
            # Saved by someone else between the check above and the write.
            return conflict_answer(_medication_detail(latest, None))

        return get_message("medication_updated")
    except Exception as e:
        app.logger.error(f"Error updating medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications")
def delete_medication(id):
    """Delete a medication course and all related intakes.

    In one transaction where the database supports it; on a standalone server (production) the course goes first and then its intakes, and an intake left behind by a failure there is only logged. The intakes go from the medical card too. There is no undo, so the app asks first.
    """
    return _delete_course(g.record)


@medications_bp.route("/api/medications/local/<local_id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse),
    tags=["medications"],
)
@require_local_record_access("medications", "medication", tell_deleted=False)
def delete_medication_by_local_id(local_id):
    """Delete a course by the ``local_id`` the device gave it, for when the device has not got the course's id.

    The same delete as by id. An unknown name, a deleted course and someone else's course answer 404 ``record_not_found``.
    """
    return _delete_course(g.record)


def _delete_course(medication: dict):
    """The delete of one course found by the access check, by its id or by the local_id the device named."""
    try:
        medication_id = medication["_id"]
        id = str(medication_id)

        intake_rows = list(app.db.medication_intakes.find({"medication_id": id}, {"_id": 1, "pet_id": 1}))
        # Atomic deletion: use session-based transaction if replica set is available
        # Otherwise, use best-effort approach with proper error handling
        try:
            # Try to start a transaction (requires replica set)
            with app.db.client.start_session() as session:
                with session.start_transaction():
                    # Delete related intakes first
                    intakes_result = app.db.medication_intakes.delete_many({"medication_id": id}, session=session)
                    # Then delete medication
                    med_result = app.db.medications.delete_one({"_id": medication_id}, session=session)

                    if med_result.deleted_count == 0:
                        # Should not happen as we already checked existence
                        raise MedicationNotFoundDuringDeletion("Medication not found during deletion")

                    app.logger.info(f"Deleted medication {id} and {intakes_result.deleted_count} related intakes")
        except Exception as tx_error:
            # If transactions are not supported (standalone MongoDB or mongomock),
            # fall back to sequential deletion with error handling
            error_msg = str(tx_error).lower()
            if (
                "transaction" in error_msg
                or "replica" in error_msg
                or "session" in error_msg
                or "mongomock" in error_msg
            ):
                app.logger.warning(f"Transactions not supported, using fallback deletion: {tx_error}")

                # Best-effort deletion: delete medication first, then intakes
                # This way, if intakes deletion fails, orphaned intakes won't affect functionality
                med_result = app.db.medications.delete_one({"_id": medication_id})
                if med_result.deleted_count == 0:
                    return error_response("not_found")

                try:
                    intakes_result = app.db.medication_intakes.delete_many({"medication_id": id})
                    app.logger.info(
                        f"Deleted medication {id} and {intakes_result.deleted_count} related intakes (fallback)"
                    )
                except Exception as intake_error:
                    # Log error but don't fail the request since medication is deleted
                    app.logger.error(f"Failed to delete intakes for medication {id}: {intake_error}")
            else:
                # Re-raise if it's not a transaction-related error
                raise

        for row in intake_rows:
            log_deletion("medication_intake", row["_id"], row["pet_id"])
        log_deletion("medication", medication_id, medication["pet_id"], local_id=medication.get("local_id"))
        return get_message("medication_deleted")
    except Exception as e:
        app.logger.error(f"Error deleting medication: {e}")
        return error_response("internal_error")


def _slot_of_the_mark(data) -> "tuple[str, str] | None":
    """The (day, time) slot this mark is for, when the client named one."""
    if not data.slot_date or not data.slot_time or minutes_of_day(data.slot_time) is None:
        return None
    return data.slot_date, data.slot_time


def _already_handled(id: str, medication: dict, data, event_dt: datetime, username: str) -> "dict | None":
    """Whether this dose is already recorded, and who/when, or None to write it.

    Two cases, and the slot decides which. A mark that carries the slot it was for closes exactly
    that slot, so a slot already closed by anybody (an hour earlier or a day earlier) is the same
    dose marked twice, and it says «слот», because that is what the person was closing. Without a
    slot there is nothing but the time of the mark, so a dose within DUPLICATE_WINDOW_MINUTES of a
    given one is the finger landing twice.
    """
    slot = _slot_of_the_mark(data)
    if slot is None:
        window = timedelta(minutes=DUPLICATE_WINDOW_MINUTES)
        near = app.db.medication_intakes.find_one(
            {
                "medication_id": id,
                "skipped": {"$ne": True},
                "date_time": {"$gt": event_dt - window, "$lt": event_dt + window},
            },
            sort=[("date_time", -1)],
        )
        if not near:
            return None
        return {
            "error": "Этот приём уже отмечен",
            "existing": {
                "date": near["date_time"].strftime("%Y-%m-%d"),
                "time": near["date_time"].strftime("%H:%M"),
                "username": near.get("username"),
                "own": near.get("username") == username,
                "slot": False,
            },
        }

    slot_date, slot_time = slot
    times = (medication.get("schedule") or {}).get("times") or []
    day_start = datetime.strptime(slot_date, "%Y-%m-%d")
    # The window is the slot's day plus a day either side: a slot is closed by an intake marked for
    # it, which can sit hours away from the slot (given late, or yesterday's evening after midnight).
    day_intakes = load_day_intakes(app.db, [id], day_start - timedelta(days=1), day_start + timedelta(days=2))
    closers = slot_closers(times, day_intakes.get((id, slot_date), []))
    taken = closers.get(slot_time)
    if taken is None:
        return None
    return {
        "error": f"Приём на {slot_time} уже отмечен",
        "existing": {
            "date": slot_date,
            "time": slot_time,
            "username": taken.get("username"),
            "own": taken.get("username") == username,
            "slot": True,
        },
    }


def _duplicate_answer(existing: dict):
    """The 409 for a dose already recorded: who closed that slot, and when."""
    return (
        jsonify(
            {
                "success": False,
                "code": "duplicate_intake",
                "error": existing["error"],
                "existing": existing["existing"],
            }
        ),
        409,
    )


def _duplicate_from_slot_key(id: str, data, username: str) -> "dict | None":
    """The 409 for a slot closed by the unique index when the schedule can no longer name it.

    _already_handled answers from the times the course has now, so it has nothing to say once the
    dose has been taken off the schedule while a stale copy of it was still on a screen (two phones
    offline, the evening dose removed between them), or the client named a time the course never
    had. The index already settled it: the mark holding the key is who closed the slot.
    """
    slot = _slot_of_the_mark(data)
    if slot is None:
        return None
    slot_date, slot_time = slot
    holder = app.db.medication_intakes.find_one(
        {"slot_key": f"{id}|{slot_date}|{minutes_of_day(slot_time)}"},
        {"_id": 0, "username": 1},
    )
    if not holder:
        return None
    return {
        "error": f"Приём на {slot_time} уже отмечен",
        "existing": {
            "date": slot_date,
            "time": slot_time,
            "username": holder.get("username"),
            "own": holder.get("username") == username,
            "slot": True,
        },
    }


def _answer_for_intake_name(existing: dict, medication_id: str, username: str):
    """The answer to a mark that names an intake which is already there.

    The same course and the same person: this mark sent again, answered as saved (200), and nothing is written, so the
    stock is taken once. Any other mark holding the name is not this request's: 409 ``local_id_taken``.
    """
    if existing.get("medication_id") != medication_id or existing.get("username") != username:
        return error_response("local_id_taken")
    return get_message(
        "intake_logged",
        status=200,
        id=str(existing["_id"]),
        ran_out=bool(existing.get("ran_out")),
        local_id=existing["local_id"],
    )


@medications_bp.route("/api/medications/<id>/log", methods=["POST"])
@login_required
@api.validate(
    body=Request(MedicationIntakeCreate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_201=SuccessResponse, HTTP_404=ErrorResponse, HTTP_409=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications")
@idempotent
def log_intake(id):
    """Log a medication intake.

    Closes one slot of the course. With ``slot_date`` and ``slot_time`` it closes that slot: marking at 14:30 closes the 08:00 dose it was given late for. Without them it closes the nearest open slot. A dose already marked, by anybody in the household, is not written twice: 409 ``duplicate_intake`` with ``existing`` says who and when. With a slot, a slot closed by a skip counts as marked too; without one, «already marked» is a given dose of this course within 30 minutes either side. ``force: true`` records it anyway, and then the new intake closes the nearest other open slot of that day (the evening dose, say). Skips and courses without scheduled times are not checked. A date or time that is invalid or more than 8 days ahead answers 422, and so does a dose of zero or less. The stock is drawn down here (a skip takes nothing), the answer says ``ran_out``, and the reminder for that slot stops. A ``local_id`` the device gives makes the mark repeatable: sent again by the same person for the same course, it is answered with the mark it already made (200, the stock taken once) even though that mark closed the slot, and not with 409 ``duplicate_intake``; a name held by another mark answers 409 ``local_id_taken``. Without ``local_id`` a second mark of a closed slot is still 409 ``duplicate_intake``.
    """
    try:
        medication = g.record
        medication_id = medication["_id"]
        username = g.username

        data = request.context.body  # type: ignore[attr-defined]

        if data.local_id:
            # The device names the mark itself, so the name decides, and the checks below do not judge a repeat: the
            # slot is closed by this very mark, and that is what «already marked» would say about it.
            named = app.db.medication_intakes.find_one({"local_id": data.local_id})
            if named:
                return _answer_for_intake_name(named, id, username)

        # +1 beyond the lookahead itself: a dose offered for day+7 can sit
        # at any hour of that day, and the bound below is a rolling window
        # from the exact current moment, not a calendar-day cutoff — the
        # extra day covers day+7 at 23:59 even when "now" is 00:00 today.
        event_dt, dt_error = parse_event_datetime_safe(
            data.date,
            data.time,
            "medication intake",
            medication["pet_id"],
            username,
            max_future_days=UPCOMING_LOOKAHEAD_DAYS + 1,
            tz=data.tz,
        )
        if dt_error:
            return dt_error[0], dt_error[1]

        skipped = bool(data.skipped)
        dose_taken = data.dose_taken
        if skipped:
            dose_taken = 0.0
        elif dose_taken is None:
            dose_taken = medication.get("default_dose", 1.0)
            if not (dose_taken or 0) > 0:
                # A course stored with a zero dose before the rule: it would write an intake that gives nothing.
                return error_response("validation_error", "Доза курса должна быть больше нуля")

        # The same dose marked twice is asked about, not recorded silently. Two ways of telling, and
        # the slot is the stronger one: an intake that carries the slot it was for (the dose widget
        # sends it) can only close a slot that is still open, so two people an hour apart on the same
        # 08:00 dose are caught too, and only that slot. Without a slot there is nothing but the
        # time window, which stands for the finger that lands twice. A course with no schedule (a
        # dose when needed) can be given again at any time, and a skip is not a dose.
        if (
            not skipped
            and not data.force
            and not is_as_needed(medication)
            and (medication.get("schedule") or {}).get("times")
        ):
            existing = _already_handled(id, medication, data, event_dt, username)
            if existing:
                return _duplicate_answer(existing)

        # Take the dose from the stock before recording the intake; the
        # insert below gives it back if it fails. A dose is always
        # recorded: when the stock can't cover it (a new pack not entered
        # yet), the stock goes to zero and the client is told it ran out,
        # instead of the diary refusing a dose the pet did get.
        inventory_decremented_by = 0.0
        ran_out = False
        if not skipped and medication.get("inventory_enabled") and medication.get("inventory_current") is not None:
            # Optimistic concurrency control with retry loop (similar to delete_intake)
            max_retries = 3
            inventory_updated = False

            for retry_attempt in range(max_retries):
                # Fetch current state on each retry (skip on first attempt, use cached medication)
                if retry_attempt > 0:
                    medication = app.db.medications.find_one({"_id": medication_id})
                    if not medication:
                        return error_response("not_found")
                    if not medication.get("inventory_enabled") or medication.get("inventory_current") is None:
                        # Inventory was disabled during retry, skip inventory update
                        inventory_updated = True
                        break

                current_inventory = medication["inventory_current"]
                deducted = max(0.0, min(float(current_inventory), float(dose_taken)))
                new_inventory = current_inventory - deducted

                # Use atomic update with condition to prevent race conditions
                result = app.db.medications.update_one(
                    {"_id": medication_id, "inventory_current": current_inventory},
                    {"$set": {"inventory_current": new_inventory, "updated_at": now_utc()}},
                )

                if result.matched_count > 0:
                    inventory_updated = True
                    inventory_decremented_by = deducted
                    ran_out = new_inventory <= 0
                    break
                # If matched_count == 0, inventory was changed by concurrent request, retry
                app.logger.warning(
                    f"Inventory update conflict for medication {id}, attempt {retry_attempt + 1}/{max_retries}"
                )

            if not inventory_updated:
                # All retries exhausted, return error to user instead of silently proceeding
                app.logger.error(f"Failed to update inventory for medication {id} after {max_retries} retries")
                return error_response(
                    "conflict",
                    "Не удалось обновить остаток лекарства: одновременно пришло несколько запросов. Попробуйте снова",
                )

        intake_data = {
            "medication_id": id,
            "pet_id": medication["pet_id"],
            "updated_at": now_utc(),
            "date_time": event_dt,
            "dose_taken": dose_taken,
            # What actually left the stock (less than the dose when it ran
            # out); deleting the intake gives back exactly this.
            "inventory_deducted": inventory_decremented_by,
            "comment": data.comment or "",
            "username": username,
            "created_at": datetime.now(timezone.utc),
        }
        if data.local_id:
            intake_data["local_id"] = data.local_id
            # What the answer to the first send said, for the repeat of it.
            intake_data["ran_out"] = ran_out
        if valid_tz(data.tz):
            intake_data["tz"] = data.tz
        if skipped:
            intake_data["skipped"] = True
        if data.force:
            # This slot is written a second time on purpose, so the mark stays out of the unique
            # slot index (web/db.py) that catches two phones marking the same dose at once.
            intake_data["forced"] = True
        # The slot it was for, when the client knows (the dose widget does): that slot is closed, not the earliest one.
        if data.slot_date and data.slot_time and minutes_of_day(data.slot_time) is not None:
            intake_data["slot_date"] = data.slot_date
            intake_data["slot_time"] = data.slot_time
            if not data.force:
                # One key per closed slot, and only for a slot that was closed on purpose: the unique
                # index over it (web/db.py) turns two phones marking the same dose into one answer.
                # A forced mark leaves the key out, it was recorded after the person was asked.
                intake_data["slot_key"] = f"{id}|{data.slot_date}|{minutes_of_day(data.slot_time)}"

        try:
            inserted = app.db.medication_intakes.insert_one(intake_data)
        except Exception as insert_error:
            # The stock was already decremented above. Without this the
            # dose would stay spent on an intake that does not exist —
            # the original ordering claimed to be "for consistency" but
            # had no compensation behind it.
            if inventory_decremented_by:
                app.db.medications.update_one(
                    {"_id": medication_id},
                    {"$inc": {"inventory_current": inventory_decremented_by}, "$set": {"updated_at": now_utc()}},
                )
                app.logger.warning(
                    f"Intake insert failed for medication {id}; restored {inventory_decremented_by} to inventory"
                )
            if not isinstance(insert_error, DuplicateKeyError):
                raise
            # Two sends of one mark at the same moment: the second one finds what the first one wrote.
            named = app.db.medication_intakes.find_one({"local_id": data.local_id}) if data.local_id else None
            if named:
                return _answer_for_intake_name(named, id, username)
            # The slot was closed in the moment between the check above and this write, and the
            # unique index caught what the check could not see yet. Answered as the check answers.
            existing = _already_handled(id, medication, data, event_dt, username) or _duplicate_from_slot_key(
                id, data, username
            )
            if existing:
                return _duplicate_answer(existing)
            raise

        # The id lets the client offer «Отменить» for a dose logged by mistake.
        named_by = {"local_id": data.local_id} if data.local_id else {}
        return get_message("intake_logged", status=201, id=str(inserted.inserted_id), ran_out=ran_out, **named_by)
    except Exception as e:
        app.logger.error(f"Error logging intake: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>/restock", methods=["POST"])
@login_required
@api.validate(
    body=Request(MedicationRestock),
    # 409 is what the three attempts below end in, and the client is told to try again.
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_409=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications")
def restock_medication(id):
    """Add a bought pack to the stock (and start tracking it if it wasn't).

    If the course has no stock count yet, or counting was switched off, the amount becomes the stock; otherwise it is added to it. Two packs entered at the same moment both count. The answer carries the new ``inventory_current``. No dose is recorded, so no reminder moves.
    """
    try:
        medication = g.record
        amount = request.context.body.amount  # type: ignore[attr-defined]
        # Compare-and-set, the same way log_intake draws the stock down: the branch below is taken from
        # the state just read, so the write carries that state in its filter. Two packs entered at the same
        # moment read the same course; the second one's write matches nothing and the next try adds it to
        # the count the first one wrote, instead of overwriting it with a pack of its own.
        for attempt in range(3):
            current = app.db.medications.find_one(
                {"_id": medication["_id"]}, {"inventory_current": 1, "inventory_enabled": 1}
            )
            count = current.get("inventory_current")
            # A count kept while counting was off says nothing about the shelf: the pack starts the count again.
            if count is None or not current.get("inventory_enabled"):
                result = app.db.medications.update_one(
                    {"_id": medication["_id"], "inventory_current": count},
                    {"$set": {"inventory_current": amount, "inventory_enabled": True, "updated_at": now_utc()}},
                )
            else:
                # $inc, not read-add-write: two restocks at once both count.
                result = app.db.medications.update_one(
                    {"_id": medication["_id"]},
                    {
                        "$inc": {"inventory_current": amount},
                        "$set": {"inventory_enabled": True, "updated_at": now_utc()},
                    },
                )
            if result.matched_count:
                break
            app.logger.warning(f"Restock conflict for medication {id}, attempt {attempt + 1}/3")
        else:
            return error_response(
                "conflict",
                "Не удалось обновить остаток лекарства: одновременно пришло несколько запросов. Попробуйте снова",
            )
        updated = app.db.medications.find_one({"_id": medication["_id"]}, {"inventory_current": 1})
        return get_message("stock_added", inventory_current=updated.get("inventory_current"))
    except Exception as e:
        app.logger.error(f"Error restocking medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/intakes", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_404=ErrorResponse, HTTP_200=MedicationIntakeListResponse),
    tags=["medications"],
)
@require_pet_access
def get_medication_intakes():
    """Get list of medication intakes with pagination.

    Every marked dose of a pet, newest first, page by page; no filters besides the pet. An intake keeps the slot it closed when the client named one (``slot_date``, ``slot_time``), which is what lets a later mark notice that the same dose was already taken. Items also carry ``medication_name``, ``tz`` and ``inventory_deducted``.
    """
    try:
        query_params = request.context.query  # type: ignore[attr-defined]
        pet_id = g.pet_id
        page = query_params.page
        page_size = query_params.page_size

        total = app.db.medication_intakes.count_documents({"pet_id": pet_id})

        base_query = app.db.medication_intakes.find({"pet_id": pet_id}).sort("date_time", -1)
        paginated_query, _ = apply_pagination(base_query, page, page_size)
        intakes = list(paginated_query)

        # Enhance with medication name
        med_ids = list(set(i["medication_id"] for i in intakes))
        meds = {
            str(m["_id"]): m["name"]
            for m in app.db.medications.find({"_id": {"$in": [ObjectId(mid) for mid in med_ids]}})
        }

        for i in intakes:
            i["_id"] = str(i["_id"])
            i["medication_name"] = meds.get(i["medication_id"], "Unknown")
            # What the answer to a repeated mark remembers, not part of the mark.
            i.pop("ran_out", None)
            if isinstance(i.get("date_time"), datetime):
                i["date_time"] = zoned_iso(i["date_time"], i.get("tz"))
            if isinstance(i.get("created_at"), datetime):
                i["created_at"] = utc_iso(i["created_at"])

        return jsonify({"intakes": intakes, "page": page, "page_size": page_size, "total": total})
    except Exception as e:
        app.logger.error(f"Error fetching intakes: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/intakes/<id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(MedicationIntakeUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medication_intakes")
def update_intake(id):
    """Move an intake to when the dose was really given, marked late or at the wrong time.

    Only the time moves. The dose and the stock it took stay as they were. A moved intake no longer holds the slot it was marked for and counts for the slot nearest its new time; ``tz`` becomes the editor's. A date more than 8 days ahead answers 422.
    """
    try:
        intake = g.record
        data = request.context.body  # type: ignore[attr-defined]
        event_dt, dt_error = parse_event_datetime_safe(
            data.date,
            data.time,
            "medication intake update",
            intake.get("pet_id"),
            g.username,
            max_future_days=UPCOMING_LOOKAHEAD_DAYS + 1,
            tz=data.tz,
            allow_now=False,
        )
        if dt_error:
            return dt_error[0], dt_error[1]
        changes = {"date_time": event_dt}
        if event_dt != intake.get("date_time") and valid_tz(data.tz):
            changes["tz"] = data.tz  # the clock moved: it is now in the editor's zone
        changes["updated_at"] = now_utc()
        update: dict = {"$set": changes}
        if event_dt != intake.get("date_time"):
            # Said to have been given at another time: it no longer vouches for the slot it was marked for, and
            # closes the one that time is nearest to (see web/dose_slots.py). The slot key goes with them, or
            # the unique index (web/db.py) would keep that slot closed by a mark that no longer names it.
            update["$unset"] = {"slot_date": "", "slot_time": "", "slot_key": ""}
        app.db.medication_intakes.update_one({"_id": intake["_id"]}, update)
        return get_message("intake_updated")
    except Exception as e:
        app.logger.error(f"Error updating intake: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/intakes/<id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medication_intakes")
def delete_intake(id):
    """Delete a medication intake record.

    For a mark made by mistake. The dose goes back to the stock it took, and its reminders are back on. Two requests for the same mark give the dose back once: the one that does not get the mark answers 404, as for a mark that is not there.
    """
    try:
        intake_id = g.record["_id"]

        # Take the mark out first, in one step. Of two requests that both found it, only the one that gets it gives the
        # dose back, and the other answers as for a mark that is not there.
        intake = app.db.medication_intakes.find_one_and_delete({"_id": intake_id})
        if intake is None:
            return error_response("record_not_found")

        # Give back what this intake took from the stock. Intakes from
        # before inventory_deducted was stored took their whole dose.
        log_deletion("medication_intake", intake_id, intake["pet_id"])
        medication_id = ObjectId(intake["medication_id"])
        to_restore = intake.get("inventory_deducted", intake.get("dose_taken", 0)) or 0
        if to_restore:
            app.db.medications.update_one(
                {"_id": medication_id, "inventory_enabled": True, "inventory_current": {"$ne": None}},
                {"$inc": {"inventory_current": to_restore}, "$set": {"updated_at": now_utc()}},
            )

        return get_message("intake_deleted")
    except Exception as e:
        app.logger.error(f"Error deleting intake: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/upcoming", methods=["GET"])
@login_required
@api.validate(
    query=UpcomingDosesQuery,
    resp=Response(HTTP_404=ErrorResponse, HTTP_200=UpcomingDosesResponse),
    tags=["medications"],
)
@require_pet_access
def get_upcoming_doses():
    """Get the next doses for the dashboard.

    What the feed shows above the records: today's unmarked doses, overdue ones included, plus last evening's still unmarked; if today has none, the doses of the next day that has any, up to 7 days ahead. Active courses with a schedule only. ``client_datetime`` (ISO or ``YYYY-MM-DD HH:MM``) is the device's local now, so the row does not turn over before the phone does. Without it, the now is the clock of the zone ``tz`` names, and UTC when neither is sent.
    """
    try:
        query_params = request.context.query
        pet_id = g.pet_id
        client_datetime_str = query_params.client_datetime

        # Fetch only active medications
        medications = list(app.db.medications.find({"pet_id": pet_id, "is_active": True}))

        if not medications:
            return jsonify({"doses": []})

        upcoming = []

        # Determine "now" and "today" based on client datetime
        if client_datetime_str:
            # A moment with its zone (the offset, or Z), or a clock without one that comes with its zone in tz.
            try:
                moment = datetime.fromisoformat(client_datetime_str.replace("Z", "+00:00"))
            except ValueError:
                return error_response(
                    "validation_error", "Время клиента: ISO 8601 с поясом, например 2026-10-18T08:12:00+05:00"
                )
            if moment.tzinfo is None and not valid_tz(query_params.tz):
                return error_response("validation_error", "Для времени без пояса укажите часовой пояс tz")
            now = clock_in_zone(moment, query_params.tz)
        else:
            app.logger.warning(
                "client_datetime missing; falling back to the clock of tz, or UTC — dose timing will be off by the "
                "caller's offset"
            )
            now = local_now(query_params.tz)

        current_day = now.weekday()
        today_start = datetime(now.year, now.month, now.day)
        window_end = today_start + timedelta(days=UPCOMING_LOOKAHEAD_DAYS + 1)

        # "Отметить заранее" lets a dose several days out be pre-logged,
        # and without checking the whole lookahead window (not just
        # today) the day it landed on kept re-offering it as still due —
        # exactly like the original same-day bug this endpoint already
        # had to fix once.
        med_ids = [str(med["_id"]) for med in medications]
        day_intakes = load_day_intakes(app.db, med_ids, today_start - timedelta(days=1), window_end)

        # A dose of last evening that nobody marked is still offered for a few hours after midnight (it was due
        # yesterday, and giving it now must not close this morning's slot): see web/dose_slots.py.
        carried = []
        y_start = today_start - timedelta(days=1)
        y_key = y_start.strftime("%Y-%m-%d")
        for med in medications:
            if is_as_needed(med):
                continue
            schedule = med.get("schedule", {})
            if (current_day - 1) % 7 not in schedule.get("days", []) or not schedule.get("times"):
                continue
            if not course_covers(med, y_key):
                continue
            med_id_str = str(med["_id"])
            for t in open_slots(schedule["times"], day_intakes.get((med_id_str, y_key), [])):
                try:
                    hour, minute = map(int, t.split(":"))
                except (ValueError, TypeError):
                    continue
                slot_moment = now.replace(hour=hour, minute=minute, second=0, microsecond=0) - timedelta(days=1)
                if now - slot_moment < timedelta(hours=CARRY_OVER_HOURS):
                    carried.append(
                        {
                            "medication_id": med_id_str,
                            "name": med["name"],
                            "type": med.get("type", "pill"),
                            "time": t,
                            "date": y_key,
                            "is_overdue": True,
                            "inventory_warning": stock_status(med)[1],
                            "carried_over": True,
                        }
                    )

        # Walk today, then each following day in the lookahead window,
        # stopping at the first day that still has anything due — showing
        # the whole week would bury the one dose that matters. Today is
        # always walked in full (even when empty) so "nothing left today"
        # correctly falls through to tomorrow instead of stopping short.
        for offset in range(0, UPCOMING_LOOKAHEAD_DAYS + 1):
            if offset > 0 and upcoming:
                break

            day_date = today_start + timedelta(days=offset)
            day_key = day_date.strftime("%Y-%m-%d")
            weekday = (current_day + offset) % 7

            for med in medications:
                schedule = med.get("schedule", {})
                sched_days = schedule.get("days", [])
                sched_times = sorted(schedule.get("times", []))

                # «По необходимости» is given when it is given, not at a time: whatever
                # schedule it keeps is not something to be reminded about.
                if is_as_needed(med):
                    continue
                if weekday not in sched_days or not sched_times:
                    continue
                # A course that hasn't begun or has ended isn't offered that day.
                if not course_covers(med, day_key):
                    continue

                med_id_str = str(med["_id"])

                for t in open_slots(sched_times, day_intakes.get((med_id_str, day_key), [])):
                    is_overdue = False
                    if offset == 0:
                        try:
                            dose_hour, dose_min = map(int, t.split(":"))
                            dose_time = now.replace(hour=dose_hour, minute=dose_min, second=0, microsecond=0)
                            is_overdue = now > dose_time
                        except (ValueError, TypeError):
                            is_overdue = False

                    upcoming.append(
                        {
                            "medication_id": med_id_str,
                            "name": med["name"],
                            "type": med.get("type", "pill"),
                            "time": t,
                            "date": day_key,
                            "is_overdue": is_overdue,
                            "inventory_warning": stock_status(med)[1],
                            "carried_over": False,
                        }
                    )

        # In time order across courses: the widget shows the first one, and
        # walking course by course put a 08:00 dose ahead of a 07:00 one.
        upcoming = carried + upcoming
        upcoming.sort(key=lambda dose: (dose["date"], dose["time"]))
        return jsonify({"doses": upcoming})
    except Exception as e:
        app.logger.error(f"Error fetching upcoming doses: {e}")
        return error_response("internal_error")
