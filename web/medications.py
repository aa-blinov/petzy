"""Medication management and intake logging endpoints."""

from flask import Blueprint, jsonify, request, g
from flask_pydantic_spec import Request, Response
from bson import ObjectId
from datetime import datetime, timezone, timedelta

import web.app as app
from web.app import api
from web.errors import error_response, MedicationNotFoundDuringDeletion
from web.decorators import require_pet_access, require_record_access
from web.helpers import (
    parse_event_datetime_safe,
    apply_pagination,
)
from web.schemas import (
    MedicationCreate,
    MedicationUpdate,
    MedicationListResponse,
    MedicationDetailResponse,
    MedicationIntakeCreate,
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


def compute_taken_counts(db, med_ids: list, window_start: datetime, window_end: datetime) -> dict:
    """(medication_id, 'YYYY-MM-DD') -> how many intakes already exist that day.

    Deliberately a plain count, not a match against the schedule's own
    HH:MM — an intake's date_time is whenever it was actually logged
    (e.g. MedicationsList's "Отметить приём" stamps the real tap time,
    not the schedule's "08:00"), so comparing HH:MM strings against the
    schedule almost never matched. Same convention get_medications
    already uses for intakes_today: consume the day's scheduled slots in
    chronological order against this count, regardless of which screen
    (or, for the reminder sender, which cron tick) logged them.

    Shared by get_upcoming_doses below and
    scripts/send_medication_reminders.py, so "is this dose already
    given today" can't quietly drift between the two.
    """
    window_intakes = db.medication_intakes.find(
        {"medication_id": {"$in": med_ids}, "date_time": {"$gte": window_start, "$lt": window_end}}
    )
    taken_count_by_med_day: dict = {}
    for intake in window_intakes:
        med_id = intake.get("medication_id")
        dt = intake.get("date_time")
        if not dt:
            continue
        key = (med_id, dt.strftime("%Y-%m-%d"))
        taken_count_by_med_day[key] = taken_count_by_med_day.get(key, 0) + 1
    return taken_count_by_med_day


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
            {"$match": {"medication_id": {"$in": med_ids}}},
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

        # Process results
        for doc in meds:
            doc["_id"] = str(doc["_id"])
            med_id_str = doc["_id"]

            last_intake = last_intakes.get(med_id_str)
            if last_intake and last_intake.get("date_time"):
                dt = last_intake["date_time"]
                doc["last_taken_at"] = dt.strftime("%Y-%m-%d %H:%M")
            else:
                doc["last_taken_at"] = None

            doc["intakes_today"] = today_counts.get(med_id_str, 0)

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
                {"medication_id": str(record["_id"])},
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

        if not update_data:
            return error_response("validation_error_no_update_data")

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

        dose_taken = data.dose_taken
        if dose_taken is None:
            dose_taken = medication.get("default_dose", 1.0)

        # Reserve stock before recording the intake; the insert below
        # gives it back if it fails.
        inventory_decremented_by = 0.0
        if medication.get("inventory_enabled") and medication.get("inventory_current") is not None:
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
                if current_inventory < dose_taken:
                    return error_response("validation_error", "Недостаточно лекарства в остатке")

                new_inventory = current_inventory - dose_taken

                # Use atomic update with condition to prevent race conditions
                result = app.db.medications.update_one(
                    {"_id": medication_id, "inventory_current": current_inventory},
                    {"$set": {"inventory_current": new_inventory}},
                )

                if result.matched_count > 0:
                    inventory_updated = True
                    inventory_decremented_by = dose_taken
                    break
                # If matched_count == 0, inventory was changed by concurrent request, retry
                app.logger.warning(
                    f"Inventory update conflict for medication {id}, attempt {retry_attempt + 1}/{max_retries}"
                )

            if not inventory_updated:
                # All retries exhausted, return error to user instead of silently proceeding
                app.logger.error(f"Failed to update inventory for medication {id} after {max_retries} retries")
                return error_response(
                    "conflict", "Не удалось обновить остаток лекарства из-за конкуренции запросов. Попробуйте снова"
                )

        intake_data = {
            "medication_id": id,
            "pet_id": medication["pet_id"],
            "date_time": event_dt,
            "dose_taken": dose_taken,
            "comment": data.comment or "",
            "username": username,
            "created_at": datetime.now(timezone.utc),
        }

        try:
            app.db.medication_intakes.insert_one(intake_data)
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

        return jsonify({"message": "Intake logged"}), 201
    except Exception as e:
        app.logger.error(f"Error logging intake: {e}")
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

        # Restore inventory if applicable
        medication_id = ObjectId(intake["medication_id"])
        medication = app.db.medications.find_one({"_id": medication_id})
        if medication and medication.get("inventory_enabled") and medication.get("inventory_current") is not None:
            # Optimistic concurrency control for inventory restoration
            # Retry loop to handle concurrent updates
            max_retries = 3
            for _ in range(max_retries):
                # Fetch current state
                current_med = app.db.medications.find_one({"_id": medication_id})
                if not current_med:
                    break

                current_inventory = current_med.get("inventory_current")
                if current_inventory is None:
                    break

                dose_to_restore = intake.get("dose_taken", 0)
                new_inventory = current_inventory + dose_to_restore

                # Cap at inventory_total if set
                if current_med.get("inventory_total") is not None:
                    new_inventory = min(new_inventory, current_med["inventory_total"])

                # Try to update with version check (using current inventory value as version)
                result = app.db.medications.update_one(
                    {"_id": medication_id, "inventory_current": current_inventory},
                    {"$set": {"inventory_current": new_inventory}},
                )

                if result.matched_count > 0:
                    break
                # If matched_count == 0, Loop will retry fetch and update

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
        taken_count_by_med_day = compute_taken_counts(app.db, med_ids, today_start, window_end)

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

                med_id_str = str(med["_id"])
                taken_count = taken_count_by_med_day.get((med_id_str, day_key), 0)

                for slot_index, t in enumerate(sched_times):
                    # The earliest `taken_count` slots are considered given.
                    if slot_index < taken_count:
                        continue

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
                            "inventory_warning": bool(
                                med.get("inventory_enabled", False)
                                and (med.get("inventory_current") or 0) <= (med.get("inventory_warning_threshold") or 0)
                            ),
                        }
                    )

        return jsonify({"doses": upcoming})
    except Exception as e:
        app.logger.error(f"Error fetching upcoming doses: {e}")
        return error_response("internal_error")
