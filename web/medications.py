"""Medication management and intake logging endpoints."""

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response
from bson import ObjectId
from datetime import datetime, timedelta

import web.app as app
from web.app import api
from web.errors import error_response
from web.messages import get_message
from web.security import get_current_user, login_required
from web.helpers import (
    validate_pet_access,
    parse_event_datetime_safe,
    get_record_and_validate_access,
    apply_pagination,
)
from web.schemas import (
    MedicationCreate,
    MedicationUpdate,
    MedicationItem,
    MedicationListResponse,
    MedicationIntakeCreate,
    MedicationIntakeItem,
    MedicationIntakeListResponse,
    UpcomingDoseItem,
    UpcomingDosesResponse,
    SuccessResponse,
    ErrorResponse,
    PetIdQuery,
    PetIdPaginationQuery,
)

medications_bp = Blueprint("medications", __name__)


@medications_bp.route("/api/medications", methods=["POST"])
@login_required
@api.validate(
    body=Request(MedicationCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_400=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def add_medication():
    """Create a new medication course."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        pet_id = data.pet_id

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success:
            return access_error[0], access_error[1]

        medication_data = data.model_dump()
        medication_data["username"] = username
        medication_data["created_at"] = datetime.utcnow()

        result = app.db.medications.insert_one(medication_data)
        
        return jsonify({"message": "Medication course created", "id": str(result.inserted_id)}), 201
    except Exception as e:
        app.logger.error(f"Error adding medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications", methods=["GET"])
@login_required
@api.validate(
    query=PetIdQuery,
    resp=Response(HTTP_200=MedicationListResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def get_medications():
    """List medication courses for a pet."""
    try:
        pet_id = request.args.get("pet_id")
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success:
            return access_error[0], access_error[1]

        cursor = app.db.medications.find({"pet_id": pet_id}).sort("created_at", -1)
        meds = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            
            # Get last intake
            last_intake = app.db.medication_intakes.find_one(
                {"medication_id": doc["_id"]},
                sort=[("date_time", -1)]
            )
            
            # Count intakes today
            now = datetime.utcnow() # UTC
            # Note: This simple check assumes UTC for "today". Ideally we need user timezone.
            # But the app seems to rely on server time or UTC generally. 
            # Ideally we'd use the offset if known, but let's stick to UTC start of day for consistency with other parts if any.
            # actually better: check against 24h window or just same calendar day?
            # Let's try same calendar day in UTC for now.
            today_start = datetime(now.year, now.month, now.day)
            
            intakes_today = app.db.medication_intakes.count_documents({
                "medication_id": doc["_id"],
                "date_time": {"$gte": today_start}
            })
            doc["intakes_today"] = intakes_today

            if last_intake and last_intake.get("date_time"):
                dt = last_intake["date_time"]
                doc["last_taken_at"] = dt.strftime("%Y-%m-%d %H:%M")
            else:
                doc["last_taken_at"] = None

            meds.append(doc)

        return jsonify({"medications": meds})
    except Exception as e:
        app.logger.error(f"Error fetching medications: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>", methods=["PATCH"])
@login_required
@api.validate(
    body=Request(MedicationUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def update_medication(id):
    """Update a medication course."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        
        if not update_data:
            return error_response("bad_request", "No data to update")

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        medication = app.db.medications.find_one({"_id": ObjectId(id)})
        if not medication:
            return error_response("not_found")

        success, access_error = validate_pet_access(medication["pet_id"], username)
        if not success:
            return access_error[0], access_error[1]

        app.db.medications.update_one({"_id": ObjectId(id)}, {"$set": update_data})
        
        return jsonify({"message": "Medication updated"})
    except Exception as e:
        app.logger.error(f"Error updating medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def delete_medication(id):
    """Delete a medication course."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        medication = app.db.medications.find_one({"_id": ObjectId(id)})
        if not medication:
            return error_response("not_found")

        success, access_error = validate_pet_access(medication["pet_id"], username)
        if not success:
            return access_error[0], access_error[1]

        app.db.medications.delete_one({"_id": ObjectId(id)})
        # Also cleanup intakes? Usually good practice
        app.db.medication_intakes.delete_many({"medication_id": id})
        
        return jsonify({"message": "Medication course and history deleted"})
    except Exception as e:
        app.logger.error(f"Error deleting medication: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/<id>/log", methods=["POST"])
@login_required
@api.validate(
    body=Request(MedicationIntakeCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def log_intake(id):
    """Log a medication intake."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        medication = app.db.medications.find_one({"_id": ObjectId(id)})
        if not medication:
            return error_response("not_found")

        success, access_error = validate_pet_access(medication["pet_id"], username)
        if not success:
            return access_error[0], access_error[1]

        event_dt, dt_error = parse_event_datetime_safe(data.date, data.time, "medication intake", medication["pet_id"], username)
        if dt_error:
            return dt_error[0], dt_error[1]

        intake_data = {
            "medication_id": id,
            "pet_id": medication["pet_id"],
            "date_time": event_dt,
            "dose_taken": data.dose_taken,
            "comment": data.comment or "",
            "username": username,
            "created_at": datetime.utcnow()
        }

        app.db.medication_intakes.insert_one(intake_data)

        # Update inventory if enabled
        if medication.get("inventory_enabled") and medication.get("inventory_current") is not None:
            new_inventory = max(0, medication["inventory_current"] - data.dose_taken)
            app.db.medications.update_one(
                {"_id": ObjectId(id)},
                {"$set": {"inventory_current": new_inventory}}
            )

        return jsonify({"message": "Intake logged"}), 201
    except Exception as e:
        app.logger.error(f"Error logging intake: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/intakes", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=MedicationIntakeListResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def get_medication_intakes():
    """Get list of medication intakes with pagination."""
    try:
        query_params = request.context.query  # type: ignore[attr-defined]
        pet_id = query_params.pet_id
        page = query_params.page
        page_size = query_params.page_size
        
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success:
            return access_error[0], access_error[1]

        total = app.db.medication_intakes.count_documents({"pet_id": pet_id})
        
        base_query = app.db.medication_intakes.find({"pet_id": pet_id}).sort("date_time", -1)
        paginated_query, _ = apply_pagination(base_query, page, page_size)
        intakes = list(paginated_query)

        # Enhance with medication name
        med_ids = list(set(i["medication_id"] for i in intakes))
        meds = {str(m["_id"]): m["name"] for m in app.db.medications.find({"_id": {"$in": [ObjectId(mid) for mid in med_ids]}})}

        for i in intakes:
            i["_id"] = str(i["_id"])
            i["medication_name"] = meds.get(i["medication_id"], "Unknown")
            if isinstance(i.get("date_time"), datetime):
                i["date_time"] = i["date_time"].strftime("%Y-%m-%d %H:%M")
        
        return jsonify({
            "intakes": intakes,
            "page": page,
            "page_size": page_size,
            "total": total
        })
    except Exception as e:
        app.logger.error(f"Error fetching intakes: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/intakes/<id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def delete_intake(id):
    """Delete a medication intake record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        intake = app.db.medication_intakes.find_one({"_id": ObjectId(id)})
        if not intake:
            return error_response("not_found")

        success, access_error = validate_pet_access(intake["pet_id"], username)
        if not success:
            return access_error[0], access_error[1]

        # Restore inventory if applicable
        medication = app.db.medications.find_one({"_id": ObjectId(intake["medication_id"])})
        if medication and medication.get("inventory_enabled") and medication.get("inventory_current") is not None:
            # We don't cap at total because total might have changed or been unset, 
            # and it's better to have more than less if logic was wrong.
            # But realistically, just adding back the dose is correct inverse operation.
            new_inventory = (medication.get("inventory_current") or 0) + intake.get("dose_taken", 0)
            app.db.medications.update_one(
                {"_id": ObjectId(intake["medication_id"])},
                {"$set": {"inventory_current": new_inventory}}
            )

        app.db.medication_intakes.delete_one({"_id": ObjectId(id)})
        
        return jsonify({"message": "Intake deleted"})
    except Exception as e:
        app.logger.error(f"Error deleting intake: {e}")
        return error_response("internal_error")


@medications_bp.route("/api/medications/upcoming", methods=["GET"])
@login_required
@api.validate(
    query=PetIdQuery,
    resp=Response(HTTP_200=UpcomingDosesResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def get_upcoming_doses():
    """Get the next doses for the dashboard."""
    try:
        pet_id = request.args.get("pet_id")
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success:
            return access_error[0], access_error[1]

        # Fetch only active medications
        medications = list(app.db.medications.find({"pet_id": pet_id, "is_active": True}))
        
        upcoming = []
        now = datetime.utcnow() # Note: App uses UTC for some things but local for dates?
        # Actually backend usually stores UTC datetime.
        # Front-end sends localized YYYY-MM-DD strings often.
        
        # Simplified logic for now: check current day of week and times
        # 0=Monday, 6=Sunday
        current_day = now.weekday() 
        
        for med in medications:
            schedule = med.get("schedule", {})
            sched_days = schedule.get("days", [])
            sched_times = schedule.get("times", [])
            
            if not sched_days or not sched_times:
                continue
                
            # Find next occurrence
            # This is a bit complex for a simple endpoint without a robust task scheduler
            # We'll just return all doses for 'today' for now as a start.
            if current_day in sched_days:
                for t in sched_times:
                    # Check if already taken today?
                    # For simplicity, we just return the schedule
                    upcoming.append({
                        "medication_id": str(med["_id"]),
                        "name": med["name"],
                        "type": med.get("type", "pill"),
                        "time": t,
                        "date": now.strftime("%Y-%m-%d"),
                        "is_overdue": False, # Logic to compare with now
                        "inventory_warning": bool(
                            med.get("inventory_enabled", False) and 
                            (med.get("inventory_current") or 0) <= (med.get("inventory_warning_threshold") or 0)
                        )
                    })
        
        return jsonify({"doses": upcoming})
    except Exception as e:
        app.logger.error(f"Error fetching upcoming doses: {e}")
        return error_response("internal_error")
