"""Medication management and intake logging endpoints."""

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime

import web.app as app
from web.app import api
from web.errors import error_response
from web.security import get_current_user, login_required
from web.helpers import (
    validate_pet_access,
    parse_event_datetime_safe,
    apply_pagination,
)
from web.schemas import (
    MedicationCreate,
    MedicationUpdate,
    MedicationListResponse,
    MedicationIntakeCreate,
    MedicationIntakeListResponse,
    UpcomingDosesResponse,
    SuccessResponse,
    ErrorResponse,
    PetIdQuery,
    PetIdPaginationQuery,
    MedicationListQuery,
    UpcomingDosesQuery,
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
    query=MedicationListQuery,
    resp=Response(HTTP_200=MedicationListResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def get_medications():
    """List medication courses for a pet."""
    try:
        query_params = request.context.query
        pet_id = query_params.pet_id
        client_date_str = query_params.client_date
        
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success:
            return access_error[0], access_error[1]

        cursor = app.db.medications.find({"pet_id": pet_id}).sort("created_at", -1)
        meds = list(cursor)
        
        if not meds:
            return jsonify({"medications": []})
        
        # Optimize: batch fetch all intake data at once
        med_ids = [str(med["_id"]) for med in meds]
        
        # Determine "today" based on client date if provided
        now_utc = datetime.utcnow()
        if client_date_str:
            try:
                today_start = datetime.strptime(client_date_str, "%Y-%m-%d")
            except ValueError:
                # Fallback to UTC if invalid
                today_start = datetime(now_utc.year, now_utc.month, now_utc.day)
        else:
            today_start = datetime(now_utc.year, now_utc.month, now_utc.day)
        
        # Get all last intakes in one query using aggregation
        last_intakes_pipeline = [
            {"$match": {"medication_id": {"$in": med_ids}}},
            {"$sort": {"date_time": -1}},
            {"$group": {
                "_id": "$medication_id",
                "last_intake": {"$first": "$$ROOT"}
            }}
        ]
        last_intakes = {
            item["_id"]: item["last_intake"]
            for item in app.db.medication_intakes.aggregate(last_intakes_pipeline)
        }
        
        # Count intakes today for all medications in one aggregation
        today_intakes_pipeline = [
            {"$match": {
                "medication_id": {"$in": med_ids},
                "date_time": {"$gte": today_start}
            }},
            {"$group": {
                "_id": "$medication_id",
                "count": {"$sum": 1}
            }}
        ]
        today_counts = {
            item["_id"]: item["count"]
            for item in app.db.medication_intakes.aggregate(today_intakes_pipeline)
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
        try:
            medication_id = ObjectId(id)
        except (InvalidId, TypeError, ValueError):
            return error_response("invalid_record_id")
        
        data = request.context.body  # type: ignore[attr-defined]
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        
        if not update_data:
            return error_response("validation_error_no_update_data")

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        medication = app.db.medications.find_one({"_id": medication_id})
        if not medication:
            return error_response("not_found")

        success, access_error = validate_pet_access(medication["pet_id"], username)
        if not success:
            return access_error[0], access_error[1]

        app.db.medications.update_one({"_id": medication_id}, {"$set": update_data})
        
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
    """Delete a medication course and all related intakes atomically."""
    try:
        try:
            medication_id = ObjectId(id)
        except (InvalidId, TypeError, ValueError):
            return error_response("invalid_record_id")
        
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        medication = app.db.medications.find_one({"_id": medication_id})
        if not medication:
            return error_response("not_found")

        success, access_error = validate_pet_access(medication["pet_id"], username)
        if not success:
            return access_error[0], access_error[1]

        # Atomic deletion: use session-based transaction if replica set is available
        # Otherwise, use best-effort approach with proper error handling
        try:
            # Try to start a transaction (requires replica set)
            with app.db.client.start_session() as session:
                with session.start_transaction():
                    # Delete related intakes first
                    intakes_result = app.db.medication_intakes.delete_many(
                        {"medication_id": id}, session=session
                    )
                    # Then delete medication
                    med_result = app.db.medications.delete_one(
                        {"_id": medication_id}, session=session
                    )
                    
                    if med_result.deleted_count == 0:
                        # Should not happen as we already checked existence
                        raise Exception("Medication not found during deletion")
                    
                    app.logger.info(
                        f"Deleted medication {id} and {intakes_result.deleted_count} related intakes"
                    )
        except Exception as tx_error:
            # If transactions are not supported (standalone MongoDB or mongomock),
            # fall back to sequential deletion with error handling
            error_msg = str(tx_error).lower()
            if ("transaction" in error_msg or "replica" in error_msg or 
                "session" in error_msg or "mongomock" in error_msg):
                app.logger.warning(
                    f"Transactions not supported, using fallback deletion: {tx_error}"
                )
                
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
                    app.logger.error(
                        f"Failed to delete intakes for medication {id}: {intake_error}"
                    )
            else:
                # Re-raise if it's not a transaction-related error
                raise
        
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
        try:
            medication_id = ObjectId(id)
        except (InvalidId, TypeError, ValueError):
            return error_response("invalid_record_id")
        
        data = request.context.body  # type: ignore[attr-defined]
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        medication = app.db.medications.find_one({"_id": medication_id})
        if not medication:
            return error_response("not_found")

        success, access_error = validate_pet_access(medication["pet_id"], username)
        if not success:
            return access_error[0], access_error[1]

        event_dt, dt_error = parse_event_datetime_safe(data.date, data.time, "medication intake", medication["pet_id"], username)
        if dt_error:
            return dt_error[0], dt_error[1]

        dose_taken = data.dose_taken
        if dose_taken is None:
            dose_taken = medication.get("default_dose", 1.0)

        # Update inventory if enabled (before inserting intake to maintain consistency)
        if medication.get("inventory_enabled") and medication.get("inventory_current") is not None:
            current_inventory = medication["inventory_current"]
            if current_inventory < dose_taken:
                return error_response("validation_error", "Недостаточно лекарства в остатке")
            new_inventory = current_inventory - dose_taken
            # Use atomic update with condition to prevent race conditions
            result = app.db.medications.update_one(
                {"_id": medication_id, "inventory_current": current_inventory},
                {"$set": {"inventory_current": new_inventory}}
            )
            if result.matched_count == 0:
                # Inventory was changed by another request, refetch and retry once
                medication = app.db.medications.find_one({"_id": medication_id})
                if medication and medication.get("inventory_enabled") and medication.get("inventory_current") is not None:
                    current_inventory = medication["inventory_current"]
                    if current_inventory < dose_taken:
                        return error_response("validation_error", "Недостаточно лекарства в остатке")
                    new_inventory = current_inventory - dose_taken
                    app.db.medications.update_one(
                        {"_id": medication_id},
                        {"$set": {"inventory_current": new_inventory}}
                    )

        intake_data = {
            "medication_id": id,
            "pet_id": medication["pet_id"],
            "date_time": event_dt,
            "dose_taken": dose_taken,
            "comment": data.comment or "",
            "username": username,
            "created_at": datetime.utcnow()
        }

        app.db.medication_intakes.insert_one(intake_data)

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
        try:
            intake_id = ObjectId(id)
        except (InvalidId, TypeError, ValueError):
            return error_response("invalid_record_id")
        
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        intake = app.db.medication_intakes.find_one({"_id": intake_id})
        if not intake:
            return error_response("not_found")

        success, access_error = validate_pet_access(intake["pet_id"], username)
        if not success:
            return access_error[0], access_error[1]

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
                    {
                        "_id": medication_id,
                        "inventory_current": current_inventory
                    },
                    {"$set": {"inventory_current": new_inventory}}
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
@login_required
@api.validate(
    query=UpcomingDosesQuery,
    resp=Response(HTTP_200=UpcomingDosesResponse, HTTP_403=ErrorResponse),
    tags=["medications"],
)
def get_upcoming_doses():
    """Get the next doses for the dashboard."""
    try:
        query_params = request.context.query
        pet_id = query_params.pet_id
        client_datetime_str = query_params.client_datetime
        
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success:
            return access_error[0], access_error[1]

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
                if 'T' in client_datetime_str:
                    now = datetime.fromisoformat(client_datetime_str.replace('Z', '+00:00'))
                else:
                    # Fallback or simple format
                    now = datetime.strptime(client_datetime_str, "%Y-%m-%d %H:%M")
            except ValueError:
                now = datetime.utcnow()
        else:
            now = datetime.utcnow()

        current_day = now.weekday()
        today_start = datetime(now.year, now.month, now.day)
        
        # Optimize: batch fetch all today's intakes in one query
        med_ids = [str(med["_id"]) for med in medications]
        today_intakes_all = list(app.db.medication_intakes.find({
            "medication_id": {"$in": med_ids},
            "date_time": {"$gte": today_start}
        }))
        
        # Group intakes by medication_id
        taken_times_by_med = {}
        for intake in today_intakes_all:
            med_id = intake.get("medication_id")
            if med_id not in taken_times_by_med:
                taken_times_by_med[med_id] = set()
            if intake.get("date_time"):
                intake_time = intake["date_time"].strftime("%H:%M")
                taken_times_by_med[med_id].add(intake_time)
        
        for med in medications:
            schedule = med.get("schedule", {})
            sched_days = schedule.get("days", [])
            sched_times = schedule.get("times", [])
            
            if not sched_days or not sched_times:
                continue
                
            med_id_str = str(med["_id"])
            taken_times = taken_times_by_med.get(med_id_str, set())
            
            # Find next occurrence
            # We'll return all doses for 'today' that haven't been taken yet
            if current_day in sched_days:
                for t in sched_times:
                    # Skip if already taken today
                    if t in taken_times:
                        continue
                    
                    # Check if time is overdue
                    try:
                        dose_hour, dose_min = map(int, t.split(':'))
                        dose_time = now.replace(hour=dose_hour, minute=dose_min, second=0, microsecond=0)
                        is_overdue = now > dose_time
                    except (ValueError, TypeError):
                        is_overdue = False
                    
                    upcoming.append({
                        "medication_id": med_id_str,
                        "name": med["name"],
                        "type": med.get("type", "pill"),
                        "time": t,
                        "date": now.strftime("%Y-%m-%d"),
                        "is_overdue": is_overdue,
                        "inventory_warning": bool(
                            med.get("inventory_enabled", False) and 
                            (med.get("inventory_current") or 0) <= (med.get("inventory_warning_threshold") or 0)
                        )
                    })
        
        return jsonify({"doses": upcoming})
    except Exception as e:
        app.logger.error(f"Error fetching upcoming doses: {e}")
        return error_response("internal_error")
