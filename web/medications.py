"""Medication management and intake logging endpoints."""

from flask import Blueprint, jsonify, request, g
from flask_pydantic_spec import Request, Response
from bson import ObjectId
from datetime import datetime, timezone, timedelta

import web.app as app
from web.app import api
from web.errors import error_response, MedicationNotFoundDuringDeletion
from web.courses import course_covers, course_status
from web.dose_slots import CARRY_OVER_HOURS, DUPLICATE_WINDOW_MINUTES, group_by_day, minutes_of_day, open_slots
from web.decorators import require_pet_access, require_record_access
from web.helpers import (
    parse_event_datetime_safe,
    apply_pagination,
    valid_tz,
)
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
    MedicationListQuery,
    UpcomingDosesQuery,
)

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


@medications_bp.route("/api/medications", methods=["POST"])
@api.validate(
    body=Request(MedicationCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_400=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_pet_access
def add_medication():
    """Create a new medication course."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        username = g.username

        medication_data = data.model_dump()
        medication_data["username"] = username
        medication_data["created_at"] = datetime.now(timezone.utc)

        result = app.db.medications.insert_one(medication_data)

        return jsonify({"message": "Medication course created", "id": str(result.inserted_id)}), 201
    except Exception as e:
        app.logger.error(f"Error adding medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications", methods=["GET"])
@api.validate(
    query=MedicationListQuery,
    resp=Response(HTTP_200=MedicationListResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_pet_access
def get_medications():
    """List medication courses for a pet."""
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

        # Determine "today" based on client date if provided
        now_utc = datetime.now(timezone.utc)
        if client_date_str:
            try:
                today_start = datetime.strptime(client_date_str, "%Y-%m-%d")
            except ValueError:
                app.logger.warning(
                    f"Unparseable client_date {client_date_str!r}; falling "
                    'back to server UTC — "taken today" may land on the '
                    "wrong day"
                )
                today_start = datetime(now_utc.year, now_utc.month, now_utc.day)
        else:
            today_start = datetime(now_utc.year, now_utc.month, now_utc.day)

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
            med_id_str = doc["_id"]

            last_intake = last_intakes.get(med_id_str)
            if last_intake and last_intake.get("date_time"):
                dt = last_intake["date_time"]
                doc["last_taken_at"] = dt.strftime("%Y-%m-%d %H:%M")
                doc["last_taken_by"] = last_intake.get("username")
            else:
                doc["last_taken_at"] = None
                doc["last_taken_by"] = None

            doc["intakes_today"] = today_counts.get(med_id_str, 0)
            today_key = today_start.strftime("%Y-%m-%d")
            schedule = doc.get("schedule") or {}
            due_today = today_start.weekday() in schedule.get("days", []) and course_covers(doc, today_key)
            doc["scheduled_today"] = bool(due_today and schedule.get("times"))
            doc["open_slots_today"] = (
                open_slots(schedule.get("times", []), today_intakes.get((med_id_str, today_key), []))
                if doc["scheduled_today"]
                else []
            )
            doc["course_status"] = course_status(doc, today_key)
            _add_stock_status(doc)

        return jsonify({"medications": meds})
    except Exception as e:
        app.logger.error(f"Error fetching medications: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>", methods=["GET"])
@api.validate(
    resp=Response(HTTP_200=MedicationDetailResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications")
def get_medication(id):
    """Fetch a single medication course by id.

    The decorator already loads the record into ``g.record`` after
    verifying ownership via ``@require_record_access``; we only need
    to serialise ``_id`` and return the document.
    """
    try:
        record = g.record
        record["_id"] = str(record["_id"])
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
                record["last_taken_at"] = dt.strftime("%Y-%m-%d %H:%M")
            else:
                record.setdefault("last_taken_at", None)

            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            record["intakes_today"] = app.db.medication_intakes.count_documents(
                {"medication_id": str(record["_id"]), "date_time": {"$gte": today_start}}
            )
        _add_stock_status(record)
        return jsonify({"medication": record})
    except Exception as e:
        app.logger.error(f"Error fetching medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>", methods=["PUT"])
@api.validate(
    body=Request(MedicationUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications")
def update_medication(id):
    """Update a medication course."""
    try:
        medication = g.record
        medication_id = medication["_id"]

        data = request.context.body  # type: ignore[attr-defined]
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}

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

        app.db.medications.update_one({"_id": medication_id}, {"$set": update_data})

        return jsonify({"message": "Medication updated"})
    except Exception as e:
        app.logger.error(f"Error updating medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications")
def delete_medication(id):
    """Delete a medication course and all related intakes atomically."""
    try:
        medication = g.record
        medication_id = medication["_id"]

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

        return jsonify({"message": "Medication course and history deleted"})
    except Exception as e:
        app.logger.error(f"Error deleting medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>/log", methods=["POST"])
@api.validate(
    body=Request(MedicationIntakeCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications")
def log_intake(id):
    """Log a medication intake."""
    try:
        medication = g.record
        medication_id = medication["_id"]
        username = g.username

        data = request.context.body  # type: ignore[attr-defined]

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
        )
        if dt_error:
            return dt_error[0], dt_error[1]

        skipped = bool(data.skipped)
        dose_taken = data.dose_taken
        if skipped:
            dose_taken = 0.0
        elif dose_taken is None:
            dose_taken = medication.get("default_dose", 1.0)

        # The same dose marked twice (two people, a second tap): asked about, not recorded silently. A course with no
        # schedule (a dose when needed) can be given again at any time, and a skip is not a dose.
        if not skipped and not data.force and (medication.get("schedule") or {}).get("times"):
            window = timedelta(minutes=DUPLICATE_WINDOW_MINUTES)
            near = app.db.medication_intakes.find_one(
                {
                    "medication_id": id,
                    "skipped": {"$ne": True},
                    "date_time": {"$gt": event_dt - window, "$lt": event_dt + window},
                },
                sort=[("date_time", -1)],
            )
            if near:
                return (
                    jsonify(
                        {
                            "success": False,
                            "code": "duplicate_intake",
                            "error": "Этот приём уже отмечен",
                            "existing": {
                                "date": near["date_time"].strftime("%Y-%m-%d"),
                                "time": near["date_time"].strftime("%H:%M"),
                                "username": near.get("username"),
                                "own": near.get("username") == username,
                            },
                        }
                    ),
                    409,
                )

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
                    {"$set": {"inventory_current": new_inventory}},
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
            "date_time": event_dt,
            "dose_taken": dose_taken,
            # What actually left the stock (less than the dose when it ran
            # out); deleting the intake gives back exactly this.
            "inventory_deducted": inventory_decremented_by,
            "comment": data.comment or "",
            "username": username,
            "created_at": datetime.now(timezone.utc),
        }
        if valid_tz(data.tz):
            intake_data["tz"] = data.tz
        if skipped:
            intake_data["skipped"] = True
        # The slot it was for, when the client knows (the dose widget does): that slot is closed, not the earliest one.
        if data.slot_date and data.slot_time and minutes_of_day(data.slot_time) is not None:
            intake_data["slot_date"] = data.slot_date
            intake_data["slot_time"] = data.slot_time

        try:
            inserted = app.db.medication_intakes.insert_one(intake_data)
        except Exception:
            # The stock was already decremented above. Without this the
            # dose would stay spent on an intake that does not exist —
            # the original ordering claimed to be "for consistency" but
            # had no compensation behind it.
            if inventory_decremented_by:
                app.db.medications.update_one(
                    {"_id": medication_id},
                    {"$inc": {"inventory_current": inventory_decremented_by}},
                )
                app.logger.warning(
                    f"Intake insert failed for medication {id}; restored {inventory_decremented_by} to inventory"
                )
            raise

        # The id lets the client offer «Отменить» for a dose logged by mistake.
        return jsonify({"message": "Intake logged", "id": str(inserted.inserted_id), "ran_out": ran_out}), 201
    except Exception as e:
        app.logger.error(f"Error logging intake: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>/restock", methods=["POST"])
@api.validate(
    body=Request(MedicationRestock),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medications")
def restock_medication(id):
    """Add a bought pack to the stock (and start tracking it if it wasn't)."""
    try:
        medication = g.record
        amount = request.context.body.amount  # type: ignore[attr-defined]
        if medication.get("inventory_current") is None:
            app.db.medications.update_one(
                {"_id": medication["_id"]},
                {"$set": {"inventory_current": amount, "inventory_enabled": True}},
            )
        else:
            # $inc, not read-add-write: two restocks at once both count.
            app.db.medications.update_one(
                {"_id": medication["_id"]},
                {"$inc": {"inventory_current": amount}, "$set": {"inventory_enabled": True}},
            )
        updated = app.db.medications.find_one({"_id": medication["_id"]}, {"inventory_current": 1})
        return jsonify({"message": "Stock added", "inventory_current": updated.get("inventory_current")})
    except Exception as e:
        app.logger.error(f"Error restocking medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/intakes", methods=["GET"])
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=MedicationIntakeListResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_pet_access
def get_medication_intakes():
    """Get list of medication intakes with pagination."""
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
            if isinstance(i.get("date_time"), datetime):
                i["date_time"] = i["date_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify({"intakes": intakes, "page": page, "page_size": page_size, "total": total})
    except Exception as e:
        app.logger.error(f"Error fetching intakes: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/intakes/<id>", methods=["PUT"])
@api.validate(
    body=Request(MedicationIntakeUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medication_intakes")
def update_intake(id):
    """Move an intake to when the dose was really given (marked late, or
    by mistake at the wrong time). Only the time: the dose and the stock
    it took stay as they were."""
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
        )
        if dt_error:
            return dt_error[0], dt_error[1]
        changes = {"date_time": event_dt}
        if event_dt != intake.get("date_time") and valid_tz(data.tz):
            changes["tz"] = data.tz  # the clock moved: it is now in the editor's zone
        update: dict = {"$set": changes}
        if event_dt != intake.get("date_time"):
            # Said to have been given at another time: it no longer vouches for the slot it was marked for, and
            # closes the one that time is nearest to (see web/dose_slots.py).
            update["$unset"] = {"slot_date": "", "slot_time": ""}
        app.db.medication_intakes.update_one({"_id": intake["_id"]}, update)
        return jsonify({"message": "Intake updated"})
    except Exception as e:
        app.logger.error(f"Error updating intake: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/intakes/<id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_record_access("medication_intakes")
def delete_intake(id):
    """Delete a medication intake record."""
    try:
        intake = g.record
        intake_id = intake["_id"]

        # Give back what this intake took from the stock. Intakes from
        # before inventory_deducted was stored took their whole dose.
        medication_id = ObjectId(intake["medication_id"])
        to_restore = intake.get("inventory_deducted", intake.get("dose_taken", 0)) or 0
        if to_restore:
            app.db.medications.update_one(
                {"_id": medication_id, "inventory_enabled": True, "inventory_current": {"$ne": None}},
                {"$inc": {"inventory_current": to_restore}},
            )

        app.db.medication_intakes.delete_one({"_id": intake_id})

        return jsonify({"message": "Intake deleted"})
    except Exception as e:
        app.logger.error(f"Error deleting intake: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/upcoming", methods=["GET"])
@api.validate(
    query=UpcomingDosesQuery,
    resp=Response(HTTP_200=UpcomingDosesResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
@require_pet_access
def get_upcoming_doses():
    """Get the next doses for the dashboard."""
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
            try:
                # Handle ISO format including potentially 'T' and maybe timezone
                # Simplest is to assume frontend sends ISO string
                if "T" in client_datetime_str:
                    now = datetime.fromisoformat(client_datetime_str.replace("Z", "+00:00"))
                else:
                    # Fallback or simple format
                    now = datetime.strptime(client_datetime_str, "%Y-%m-%d %H:%M")
            except ValueError:
                app.logger.warning(
                    f"Unparseable client_datetime {client_datetime_str!r}; "
                    "falling back to server UTC — dose timing will be off "
                    "by the caller's offset"
                )
                now = datetime.now(timezone.utc)
        else:
            app.logger.warning(
                "client_datetime missing; falling back to server UTC — dose timing will be off by the caller's offset"
            )
            now = datetime.now(timezone.utc)

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
