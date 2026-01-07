"""Health records endpoints (asthma, defecation, litter, weight, feeding, eye drops, tooth brushing, ear cleaning).

JSON Naming Convention:
- All fields use snake_case (e.g., pet_id, date_time, food_weight, eye_drops, tooth_brushing, ear_cleaning)
- See docs/api-naming-conventions.md for full naming rules
"""

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response
from bson import ObjectId
from datetime import datetime, timedelta

import web.app as app  # Import app module to access db and logger
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
    AsthmaAttackCreate,
    AsthmaAttackUpdate,
    AsthmaAttackListResponse,
    AsthmaAttackItem,
    DefecationCreate,
    DefecationUpdate,
    DefecationListResponse,
    DefecationItem,
    LitterChangeCreate,
    LitterChangeUpdate,
    LitterChangeListResponse,
    LitterChangeItem,
    WeightRecordCreate,
    WeightRecordUpdate,
    WeightRecordListResponse,
    WeightRecordItem,
    FeedingCreate,
    FeedingUpdate,
    FeedingListResponse,
    FeedingItem,
    EyeDropsCreate,
    EyeDropsUpdate,
    EyeDropsListResponse,
    EyeDropsItem,
    ToothBrushingCreate,
    ToothBrushingUpdate,
    ToothBrushingListResponse,
    ToothBrushingItem,
    EarCleaningCreate,
    EarCleaningUpdate,
    EarCleaningListResponse,
    EarCleaningItem,
    PetIdPaginationQuery,
    HealthStatsQuery,
    HealthStatsResponse,
    SuccessResponse,
    ErrorResponse,
)

health_records_bp = Blueprint("health_records", __name__)


# Asthma routes
@health_records_bp.route("/api/asthma", methods=["POST"])
@login_required
@api.validate(
    body=Request(AsthmaAttackCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["health-records"],
)
def add_asthma_attack():
    """Add asthma attack event."""
    try:
        # `context` is injected by flask-pydantic-spec at runtime; static checker doesn't know this attribute.
        data = request.context.body  # type: ignore[attr-defined]
        pet_id = request.args.get("pet_id") or data.pet_id

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success and access_error:
            return access_error[0], access_error[1]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "asthma attack", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        attack_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "duration": data.duration or "",
            "reason": data.reason or "",
            "inhalation": data.inhalation,
            "comment": data.comment or "",
            "username": username,
        }

        app.db["asthma_attacks"].insert_one(attack_data)
        app.logger.info(f"Asthma attack recorded: pet_id={pet_id}, user={username}")
        return get_message("asthma_created", status=201)

    except ValueError as e:
        app.logger.warning(f"Invalid input data for asthma attack: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/asthma", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=AsthmaAttackListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_asthma_attacks():
    """Get asthma attacks for current pet with pagination."""
    # `context` is injected by flask-pydantic-spec at runtime; static checker doesn't know this attribute.
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = query_params.pet_id
    page = query_params.page
    page_size = query_params.page_size

    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    success, access_error = validate_pet_access(pet_id, username)
    if not success and access_error:
        return access_error[0], access_error[1]

    # Get total count
    total = app.db["asthma_attacks"].count_documents({"pet_id": pet_id})

    # Apply pagination
    from web.helpers import apply_pagination

    base_query = app.db["asthma_attacks"].find({"pet_id": pet_id}).sort("date_time", -1)
    paginated_query, _ = apply_pagination(base_query, page, page_size)
    attacks = list(paginated_query)

    for attack in attacks:
        attack["_id"] = str(attack["_id"])
        attack["pet_id"] = str(attack.get("pet_id", ""))
        attack["username"] = attack.get("username", "")
        if isinstance(attack.get("date_time"), datetime):
            attack["date_time"] = attack["date_time"].strftime("%Y-%m-%d %H:%M")
    
    # Debug logging
    # app.logger.info(f"Asthma attacks returning: {attacks}")

    return jsonify({"attacks": attacks, "page": page, "page_size": page_size, "total": total})


@health_records_bp.route("/api/asthma/<record_id>", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=AsthmaAttackItem, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_asthma_attack(record_id):
    """Get single asthma attack event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "asthma_attacks", username)
        if access_error:
            return access_error[0], access_error[1]

        record = existing
        record["_id"] = str(record["_id"])
        record["pet_id"] = str(record.get("pet_id", ""))
        record["username"] = record.get("username", "")
        if isinstance(record.get("date_time"), datetime):
            record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify(record)
    except Exception as e:
        app.logger.error(f"Error fetching record: {e}")
        return error_response("internal_error")


@health_records_bp.route("/api/asthma/<record_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(AsthmaAttackUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def update_asthma_attack(record_id):
    """Update asthma attack event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "asthma_attacks", username)
        if access_error:
            return access_error[0], access_error[1]

        data = request.context.body  # type: ignore[attr-defined]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "asthma attack update", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        attack_data = {}
        if event_dt is not None:
            attack_data["date_time"] = event_dt
        if data.duration is not None:
            attack_data["duration"] = data.duration
        if data.reason is not None:
            attack_data["reason"] = data.reason
        if data.inhalation is not None:
            attack_data["inhalation"] = data.inhalation
        if data.comment is not None:
            attack_data["comment"] = data.comment

        result = app.db["asthma_attacks"].update_one({"_id": ObjectId(record_id)}, {"$set": attack_data})

        if result.matched_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Asthma attack updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("asthma_updated")

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for asthma attack update: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/asthma/<record_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def delete_asthma_attack(record_id):
    """Delete asthma attack event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "asthma_attacks", username)
        if access_error:
            return access_error[0], access_error[1]

        result = app.db["asthma_attacks"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Asthma attack deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("asthma_deleted")

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for asthma attack deletion: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("invalid_record_id")


# Defecation routes
@health_records_bp.route("/api/defecation", methods=["POST"])
@login_required
@api.validate(
    body=Request(DefecationCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["health-records"],
)
def add_defecation():
    """Add defecation event."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        pet_id = request.args.get("pet_id") or data.pet_id

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success and access_error:
            return access_error[0], access_error[1]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "defecation", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        defecation_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "stool_type": data.stool_type or "",
            "color": data.color or "Коричневый",
            "food": data.food or "",
            "comment": data.comment or "",
            "username": username,
        }

        app.db["defecations"].insert_one(defecation_data)
        app.logger.info(f"Defecation recorded: pet_id={pet_id}, user={username}")
        return get_message("defecation_created", status=201)

    except ValueError as e:
        app.logger.warning(f"Invalid input data for defecation: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/defecation", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=DefecationListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_defecations():
    """Get defecations for current pet with pagination."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = query_params.pet_id
    page = query_params.page
    page_size = query_params.page_size

    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    success, access_error = validate_pet_access(pet_id, username)
    if not success and access_error:
        return access_error[0], access_error[1]

    # Get total count
    total = app.db["defecations"].count_documents({"pet_id": pet_id})

    # Apply pagination
    from web.helpers import apply_pagination

    base_query = app.db["defecations"].find({"pet_id": pet_id}).sort("date_time", -1)
    paginated_query, _ = apply_pagination(base_query, page, page_size)
    defecations = list(paginated_query)

    for defecation in defecations:
        defecation["_id"] = str(defecation["_id"])
        defecation["pet_id"] = str(defecation.get("pet_id", ""))
        defecation["username"] = defecation.get("username", "")
        if isinstance(defecation.get("date_time"), datetime):
            defecation["date_time"] = defecation["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"defecations": defecations, "page": page, "page_size": page_size, "total": total})


@health_records_bp.route("/api/defecation/<record_id>", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=DefecationItem, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_defecation(record_id):
    """Get single defecation event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "defecations", username)
        if access_error:
            return access_error[0], access_error[1]

        record = existing
        record["_id"] = str(record["_id"])
        record["pet_id"] = str(record.get("pet_id", ""))
        record["username"] = record.get("username", "")
        if isinstance(record.get("date_time"), datetime):
            record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify(record)
    except Exception as e:
        app.logger.error(f"Error fetching record: {e}")
        return error_response("internal_error")


@health_records_bp.route("/api/defecation/<record_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(DefecationUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def update_defecation(record_id):
    """Update defecation event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "defecations", username)
        if access_error:
            return access_error[0], access_error[1]

        data = request.context.body  # type: ignore[attr-defined]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "defecation update", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        defecation_data = {}
        if event_dt is not None:
            defecation_data["date_time"] = event_dt
        if data.stool_type is not None:
            defecation_data["stool_type"] = data.stool_type
        if data.color is not None:
            defecation_data["color"] = data.color
        if data.food is not None:
            defecation_data["food"] = data.food
        if data.comment is not None:
            defecation_data["comment"] = data.comment

        result = app.db["defecations"].update_one({"_id": ObjectId(record_id)}, {"$set": defecation_data})

        if result.matched_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Defecation updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("defecation_updated")

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for defecation update: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/defecation/<record_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def delete_defecation(record_id):
    """Delete defecation event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "defecations", username)
        if access_error:
            return access_error[0], access_error[1]

        result = app.db["defecations"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Defecation deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("defecation_deleted")

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for defecation deletion: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("invalid_record_id", str(e))


# Litter routes
@health_records_bp.route("/api/litter", methods=["POST"])
@login_required
@api.validate(
    body=Request(LitterChangeCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["health-records"],
)
def add_litter():
    """Add litter change event."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        pet_id = request.args.get("pet_id") or data.pet_id

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success and access_error:
            return access_error[0], access_error[1]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "litter change", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        litter_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "comment": data.comment or "",
            "username": username,
        }

        app.db["litter_changes"].insert_one(litter_data)
        app.logger.info(f"Litter change recorded: pet_id={pet_id}, user={username}")
        return get_message("litter_created", status=201)

    except ValueError as e:
        app.logger.warning(f"Invalid input data for litter change: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/litter", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=LitterChangeListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_litter_changes():
    """Get litter changes for current pet with pagination."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = query_params.pet_id
    page = query_params.page
    page_size = query_params.page_size

    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    success, access_error = validate_pet_access(pet_id, username)
    if not success and access_error:
        return access_error[0], access_error[1]

    # Get total count
    total = app.db["litter_changes"].count_documents({"pet_id": pet_id})

    # Apply pagination
    from web.helpers import apply_pagination

    base_query = app.db["litter_changes"].find({"pet_id": pet_id}).sort("date_time", -1)
    paginated_query, _ = apply_pagination(base_query, page, page_size)
    litter_changes = list(paginated_query)

    for change in litter_changes:
        change["_id"] = str(change["_id"])
        change["pet_id"] = str(change.get("pet_id", ""))
        change["username"] = change.get("username", "")
        if isinstance(change.get("date_time"), datetime):
            change["date_time"] = change["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"litter_changes": litter_changes, "page": page, "page_size": page_size, "total": total})


@health_records_bp.route("/api/litter/<record_id>", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=LitterChangeItem, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_litter(record_id):
    """Get single litter change event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "litter_changes", username)
        if access_error:
            return access_error[0], access_error[1]

        record = existing
        record["_id"] = str(record["_id"])
        record["pet_id"] = str(record.get("pet_id", ""))
        record["username"] = record.get("username", "")
        if isinstance(record.get("date_time"), datetime):
            record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify(record)
    except Exception as e:
        app.logger.error(f"Error fetching record: {e}")
        return error_response("internal_error")


@health_records_bp.route("/api/litter/<record_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(LitterChangeUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def update_litter(record_id):
    """Update litter change event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "litter_changes", username)
        if access_error:
            return access_error[0], access_error[1]

        data = request.context.body  # type: ignore[attr-defined]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "litter change update", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        litter_data = {}
        if event_dt is not None:
            litter_data["date_time"] = event_dt
        if data.comment is not None:
            litter_data["comment"] = data.comment

        result = app.db["litter_changes"].update_one({"_id": ObjectId(record_id)}, {"$set": litter_data})

        if result.matched_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Litter change updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("litter_updated")

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for litter change update: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/litter/<record_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def delete_litter(record_id):
    """Delete litter change event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "litter_changes", username)
        if access_error:
            return access_error[0], access_error[1]

        result = app.db["litter_changes"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Litter change deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("litter_deleted")

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for litter change deletion: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("invalid_record_id", str(e))


# Weight routes
@health_records_bp.route("/api/weight", methods=["POST"])
@login_required
@api.validate(
    body=Request(WeightRecordCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["health-records"],
)
def add_weight():
    """Add weight measurement."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        pet_id = request.args.get("pet_id") or data.pet_id

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success and access_error:
            return access_error[0], access_error[1]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "weight", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        weight_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "weight": data.weight or "",
            "food": data.food or "",
            "comment": data.comment or "",
            "username": username,
        }

        app.db["weights"].insert_one(weight_data)
        app.logger.info(f"Weight recorded: pet_id={pet_id}, user={username}")
        return get_message("weight_created", status=201)

    except ValueError as e:
        app.logger.warning(f"Invalid input data for weight: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/weight", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=WeightRecordListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_weights():
    """Get weight measurements for current pet with pagination."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = query_params.pet_id
    page = query_params.page
    page_size = query_params.page_size

    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    success, access_error = validate_pet_access(pet_id, username)
    if not success and access_error:
        return access_error[0], access_error[1]

    # Get total count
    total = app.db["weights"].count_documents({"pet_id": pet_id})

    # Apply pagination
    from web.helpers import apply_pagination

    base_query = app.db["weights"].find({"pet_id": pet_id}).sort("date_time", -1)
    paginated_query, _ = apply_pagination(base_query, page, page_size)
    weights = list(paginated_query)

    for weight in weights:
        weight["_id"] = str(weight["_id"])
        weight["pet_id"] = str(weight.get("pet_id", ""))
        weight["username"] = weight.get("username", "")
        if isinstance(weight.get("date_time"), datetime):
            weight["date_time"] = weight["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"weights": weights, "page": page, "page_size": page_size, "total": total})


@health_records_bp.route("/api/weight/<record_id>", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=WeightRecordItem, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_weight(record_id):
    """Get single weight measurement."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "weights", username)
        if access_error:
            return access_error[0], access_error[1]

        record = existing
        record["_id"] = str(record["_id"])
        record["pet_id"] = str(record.get("pet_id", ""))
        record["username"] = record.get("username", "")
        if isinstance(record.get("date_time"), datetime):
            record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify(record)
    except Exception as e:
        app.logger.error(f"Error fetching record: {e}")
        return error_response("internal_error")


@health_records_bp.route("/api/weight/<record_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(WeightRecordUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def update_weight(record_id):
    """Update weight measurement."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "weights", username)
        if access_error:
            return access_error[0], access_error[1]

        data = request.context.body  # type: ignore[attr-defined]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "weight update", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        weight_data = {
            "date_time": event_dt,
            "weight": data.weight or "",
            "food": data.food or "",
            "comment": data.comment or "",
        }

        result = app.db["weights"].update_one({"_id": ObjectId(record_id)}, {"$set": weight_data})

        if result.matched_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Weight updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("weight_updated")

    except ValueError as e:
        app.logger.warning(f"Invalid input data for weight update: record_id={record_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/weight/<record_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def delete_weight(record_id):
    """Delete weight measurement."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "weights", username)
        if access_error:
            return access_error[0], access_error[1]

        result = app.db["weights"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Weight deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("weight_deleted")

    except ValueError as e:
        app.logger.warning(f"Invalid record_id for weight deletion: record_id={record_id}, user={username}, error={e}")
        return error_response("invalid_record_id", str(e))


# Feeding routes
@health_records_bp.route("/api/feeding", methods=["POST"])
@login_required
@api.validate(
    body=Request(FeedingCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["health-records"],
)
def add_feeding():
    """Add feeding event."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        pet_id = request.args.get("pet_id") or data.pet_id

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success and access_error:
            return access_error[0], access_error[1]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "feeding", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        feeding_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "food_weight": data.food_weight if data.food_weight is not None else None,
            "comment": data.comment or "",
            "username": username,
        }

        app.db["feedings"].insert_one(feeding_data)
        app.logger.info(f"Feeding recorded: pet_id={pet_id}, user={username}")
        return get_message("feeding_created", status=201)

    except ValueError as e:
        app.logger.warning(f"Invalid input data for feeding: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/feeding", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=FeedingListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_feedings():
    """Get feedings for current pet with pagination."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = query_params.pet_id
    page = query_params.page
    page_size = query_params.page_size

    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    success, access_error = validate_pet_access(pet_id, username)
    if not success and access_error:
        return access_error[0], access_error[1]

    # Get total count
    total = app.db["feedings"].count_documents({"pet_id": pet_id})

    # Apply pagination
    from web.helpers import apply_pagination

    base_query = app.db["feedings"].find({"pet_id": pet_id}).sort("date_time", -1)
    paginated_query, _ = apply_pagination(base_query, page, page_size)
    feedings = list(paginated_query)

    for feeding in feedings:
        feeding["_id"] = str(feeding["_id"])
        feeding["pet_id"] = str(feeding.get("pet_id", ""))
        feeding["username"] = feeding.get("username", "")
        if isinstance(feeding.get("date_time"), datetime):
            feeding["date_time"] = feeding["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"feedings": feedings, "page": page, "page_size": page_size, "total": total})


@health_records_bp.route("/api/feeding/<record_id>", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=FeedingItem, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_feeding(record_id):
    """Get single feeding event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "feedings", username)
        if access_error:
            return access_error[0], access_error[1]

        record = existing
        record["_id"] = str(record["_id"])
        record["pet_id"] = str(record.get("pet_id", ""))
        record["username"] = record.get("username", "")
        if isinstance(record.get("date_time"), datetime):
            record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify(record)
    except Exception as e:
        app.logger.error(f"Error fetching record: {e}")
        return error_response("internal_error")


@health_records_bp.route("/api/feeding/<record_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(FeedingUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def update_feeding(record_id):
    """Update feeding event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "feedings", username)
        if access_error:
            return access_error[0], access_error[1]

        data = request.context.body  # type: ignore[attr-defined]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "feeding update", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        feeding_data = {
            "date_time": event_dt,
            "food_weight": data.food_weight if data.food_weight is not None else None,
            "comment": data.comment or "",
        }

        result = app.db["feedings"].update_one({"_id": ObjectId(record_id)}, {"$set": feeding_data})

        if result.matched_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Feeding updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("feeding_updated")

    except ValueError as e:
        app.logger.warning(f"Invalid input data for feeding update: record_id={record_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/feeding/<record_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def delete_feeding(record_id):
    """Delete feeding event."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "feedings", username)
        if access_error:
            return access_error[0], access_error[1]

        result = app.db["feedings"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Feeding deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("feeding_deleted")

    except ValueError as e:
        app.logger.warning(f"Invalid record_id for feeding deletion: record_id={record_id}, user={username}, error={e}")
        return error_response("invalid_record_id", str(e))


# Eye drops routes
@health_records_bp.route("/api/eye_drops", methods=["POST"])
@login_required
@api.validate(
    body=Request(EyeDropsCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["health-records"],
)
def add_eye_drops():
    """Add eye drops record."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        pet_id = request.args.get("pet_id") or data.pet_id

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success and access_error:
            return access_error[0], access_error[1]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "eye drops", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        eye_drops_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "drops_type": data.drops_type or "Обычные",
            "comment": data.comment or "",
            "username": username,
        }

        app.db["eye_drops"].insert_one(eye_drops_data)
        app.logger.info(f"Eye drops recorded: pet_id={pet_id}, user={username}")
        return get_message("eye_drops_created", status=201)

    except ValueError as e:
        app.logger.warning(f"Invalid input data for eye drops: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/eye_drops", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=EyeDropsListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_eye_drops():
    """Get eye drops records for current pet with pagination."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = query_params.pet_id
    page = query_params.page
    page_size = query_params.page_size

    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    success, access_error = validate_pet_access(pet_id, username)
    if not success and access_error:
        return access_error[0], access_error[1]

    # Get total count
    total = app.db["eye_drops"].count_documents({"pet_id": pet_id})

    # Apply pagination
    from web.helpers import apply_pagination

    base_query = app.db["eye_drops"].find({"pet_id": pet_id}).sort("date_time", -1)
    paginated_query, _ = apply_pagination(base_query, page, page_size)
    eye_drops = list(paginated_query)

    for item in eye_drops:
        item["_id"] = str(item["_id"])
        item["pet_id"] = str(item.get("pet_id", ""))
        item["username"] = item.get("username", "")
        if isinstance(item.get("date_time"), datetime):
            item["date_time"] = item["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"eye_drops": eye_drops, "page": page, "page_size": page_size, "total": total})


@health_records_bp.route("/api/eye_drops/<record_id>", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=EyeDropsItem, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_eye_drop(record_id):
    """Get single eye drops record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "eye_drops", username)
        if access_error:
            return access_error[0], access_error[1]

        record = existing
        record["_id"] = str(record["_id"])
        record["pet_id"] = str(record.get("pet_id", ""))
        record["username"] = record.get("username", "")
        if isinstance(record.get("date_time"), datetime):
            record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify(record)
    except Exception as e:
        app.logger.error(f"Error fetching record: {e}")
        return error_response("internal_error")


@health_records_bp.route("/api/eye_drops/<record_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(EyeDropsUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def update_eye_drops(record_id):
    """Update eye drops record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "eye_drops", username)
        if access_error:
            return access_error[0], access_error[1]

        data = request.context.body  # type: ignore[attr-defined]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "eye drops update", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        eye_drops_data = {}
        if event_dt is not None:
            eye_drops_data["date_time"] = event_dt
        if data.drops_type is not None:
            eye_drops_data["drops_type"] = data.drops_type
        if data.comment is not None:
            eye_drops_data["comment"] = data.comment

        result = app.db["eye_drops"].update_one({"_id": ObjectId(record_id)}, {"$set": eye_drops_data})

        if result.matched_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Eye drops updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("eye_drops_updated")

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for eye drops update: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/eye_drops/<record_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def delete_eye_drops(record_id):
    """Delete eye drops record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "eye_drops", username)
        if access_error:
            return access_error[0], access_error[1]

        result = app.db["eye_drops"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Eye drops deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("eye_drops_deleted")

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for eye drops deletion: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("invalid_record_id", str(e))


# Tooth brushing routes
@health_records_bp.route("/api/tooth_brushing", methods=["POST"])
@login_required
@api.validate(
    body=Request(ToothBrushingCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["health-records"],
)
def add_tooth_brushing():
    """Add tooth brushing record."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        pet_id = request.args.get("pet_id") or data.pet_id

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success and access_error:
            return access_error[0], access_error[1]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "tooth brushing", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        tooth_brushing_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "brushing_type": data.brushing_type or "Щетка",
            "comment": data.comment or "",
            "username": username,
        }

        app.db["tooth_brushing"].insert_one(tooth_brushing_data)
        app.logger.info(f"Tooth brushing recorded: pet_id={pet_id}, user={username}")
        return get_message("tooth_brushing_created", status=201)

    except ValueError as e:
        app.logger.warning(f"Invalid input data for tooth brushing: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/tooth_brushing", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=ToothBrushingListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_tooth_brushing():
    """Get tooth brushing records for current pet with pagination."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = query_params.pet_id
    page = query_params.page
    page_size = query_params.page_size

    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    success, access_error = validate_pet_access(pet_id, username)
    if not success and access_error:
        return access_error[0], access_error[1]

    # Get total count
    total = app.db["tooth_brushing"].count_documents({"pet_id": pet_id})

    # Apply pagination
    base_query = app.db["tooth_brushing"].find({"pet_id": pet_id}).sort("date_time", -1)
    paginated_query, _ = apply_pagination(base_query, page, page_size)
    tooth_brushing = list(paginated_query)

    for item in tooth_brushing:
        item["_id"] = str(item["_id"])
        item["pet_id"] = str(item.get("pet_id", ""))
        item["username"] = item.get("username", "")
        if isinstance(item.get("date_time"), datetime):
            item["date_time"] = item["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"tooth_brushing": tooth_brushing, "page": page, "page_size": page_size, "total": total})


@health_records_bp.route("/api/tooth_brushing/<record_id>", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=ToothBrushingItem, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_tooth_brushing_record(record_id):
    """Get single tooth brushing record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "tooth_brushing", username)
        if access_error:
            return access_error[0], access_error[1]

        record = existing
        record["_id"] = str(record["_id"])
        record["pet_id"] = str(record.get("pet_id", ""))
        record["username"] = record.get("username", "")
        if isinstance(record.get("date_time"), datetime):
            record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify(record)
    except Exception as e:
        app.logger.error(f"Error fetching record: {e}")
        return error_response("internal_error")


@health_records_bp.route("/api/tooth_brushing/<record_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(ToothBrushingUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def update_tooth_brushing(record_id):
    """Update tooth brushing record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "tooth_brushing", username)
        if access_error:
            return access_error[0], access_error[1]

        data = request.context.body  # type: ignore[attr-defined]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "tooth brushing update", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        tooth_brushing_data = {}
        if event_dt is not None:
            tooth_brushing_data["date_time"] = event_dt
        if data.brushing_type is not None:
            tooth_brushing_data["brushing_type"] = data.brushing_type
        if data.comment is not None:
            tooth_brushing_data["comment"] = data.comment

        result = app.db["tooth_brushing"].update_one({"_id": ObjectId(record_id)}, {"$set": tooth_brushing_data})

        if result.matched_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Tooth brushing updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("tooth_brushing_updated")

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for tooth brushing update: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/tooth_brushing/<record_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def delete_tooth_brushing(record_id):
    """Delete tooth brushing record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "tooth_brushing", username)
        if access_error:
            return access_error[0], access_error[1]

        result = app.db["tooth_brushing"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Tooth brushing deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("tooth_brushing_deleted")

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for tooth brushing deletion: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("invalid_record_id")


# Ear cleaning routes
@health_records_bp.route("/api/ear_cleaning", methods=["POST"])
@login_required
@api.validate(
    body=Request(EarCleaningCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["health-records"],
)
def add_ear_cleaning():
    """Add ear cleaning record."""
    try:
        data = request.context.body  # type: ignore[attr-defined]
        pet_id = request.args.get("pet_id") or data.pet_id

        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        success, access_error = validate_pet_access(pet_id, username)
        if not success and access_error:
            return access_error[0], access_error[1]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "ear cleaning", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        ear_cleaning_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "cleaning_type": data.cleaning_type or "Салфетка/Марля",
            "comment": data.comment or "",
            "username": username,
        }

        app.db["ear_cleaning"].insert_one(ear_cleaning_data)
        app.logger.info(f"Ear cleaning recorded: pet_id={pet_id}, user={username}")
        return get_message("ear_cleaning_created", status=201)

    except ValueError as e:
        app.logger.warning(f"Invalid input data for ear cleaning: pet_id={pet_id}, user={username}, error={e}")
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/ear_cleaning", methods=["GET"])
@login_required
@api.validate(
    query=PetIdPaginationQuery,
    resp=Response(HTTP_200=EarCleaningListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_ear_cleaning():
    """Get ear cleaning records for current pet with pagination."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = query_params.pet_id
    page = query_params.page
    page_size = query_params.page_size

    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    success, access_error = validate_pet_access(pet_id, username)
    if not success and access_error:
        return access_error[0], access_error[1]

    total = app.db["ear_cleaning"].count_documents({"pet_id": pet_id})

    base_query = app.db["ear_cleaning"].find({"pet_id": pet_id}).sort("date_time", -1)
    paginated_query, _ = apply_pagination(base_query, page, page_size)
    ear_cleaning_records = list(paginated_query)

    for item in ear_cleaning_records:
        item["_id"] = str(item["_id"])
        item["pet_id"] = str(item.get("pet_id", ""))
        item["username"] = item.get("username", "")
        if isinstance(item.get("date_time"), datetime):
            item["date_time"] = item["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"ear_cleaning": ear_cleaning_records, "page": page, "page_size": page_size, "total": total})


@health_records_bp.route("/api/ear_cleaning/<record_id>", methods=["GET"])
@login_required
@api.validate(
    resp=Response(HTTP_200=EarCleaningItem, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_ear_cleaning_record(record_id):
    """Get single ear cleaning record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "ear_cleaning", username)
        if access_error:
            return access_error[0], access_error[1]

        record = existing
        record["_id"] = str(record["_id"])
        record["pet_id"] = str(record.get("pet_id", ""))
        record["username"] = record.get("username", "")
        if isinstance(record.get("date_time"), datetime):
            record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")

        return jsonify(record)
    except Exception as e:
        app.logger.error(f"Error fetching record: {e}")
        return error_response("internal_error")


@health_records_bp.route("/api/ear_cleaning/<record_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(EarCleaningUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def update_ear_cleaning(record_id):
    """Update ear cleaning record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "ear_cleaning", username)
        if access_error:
            return access_error[0], access_error[1]

        data = request.context.body  # type: ignore[attr-defined]

        date_str = data.date
        time_str = data.time
        event_dt, dt_error = parse_event_datetime_safe(date_str, time_str, "ear cleaning update", pet_id, username)
        if dt_error:
            return dt_error[0], dt_error[1]

        ear_cleaning_data = {}
        if event_dt is not None:
            ear_cleaning_data["date_time"] = event_dt
        if data.cleaning_type is not None:
            ear_cleaning_data["cleaning_type"] = data.cleaning_type
        if data.comment is not None:
            ear_cleaning_data["comment"] = data.comment

        result = app.db["ear_cleaning"].update_one({"_id": ObjectId(record_id)}, {"$set": ear_cleaning_data})

        if result.matched_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Ear cleaning updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("ear_cleaning_updated")

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for ear cleaning update: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("validation_error", str(e))


@health_records_bp.route("/api/ear_cleaning/<record_id>", methods=["DELETE"])
@login_required
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["health-records"],
)
def delete_ear_cleaning(record_id):
    """Delete ear cleaning record."""
    try:
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]

        existing, pet_id, access_error = get_record_and_validate_access(record_id, "ear_cleaning", username)
        if access_error:
            return access_error[0], access_error[1]

        result = app.db["ear_cleaning"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return error_response("record_not_found")

        app.logger.info(f"Ear cleaning deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return get_message("ear_cleaning_deleted")

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for ear cleaning deletion: record_id={record_id}, user={username}, error={e}"
        )
        return error_response("invalid_record_id")


# Statistics routes
@health_records_bp.route("/api/stats/health", methods=["GET"])
@login_required
@api.validate(
    query=HealthStatsQuery,
    resp=Response(HTTP_200=HealthStatsResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["stats"],
)
def get_health_stats():
    """Get health statistics for charts."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = query_params.pet_id
    record_type = query_params.type
    days = query_params.days or 30

    username, auth_error = get_current_user()
    if auth_error:
        return auth_error[0], auth_error[1]

    success, access_error = validate_pet_access(pet_id, username)
    if not success and access_error:
        return access_error[0], access_error[1]

    # Map record types to collection names and value fields
    type_mapping = {
        "feeding": ("feedings", "food_weight"),
        "asthma": ("asthma_attacks", "count"),
        "defecation": ("defecations", "count"),
        "litter": ("litter_changes", "count"),
        "weight": ("weights", "weight"),
        "eye_drops": ("eye_drops", "count"),
        "tooth_brushing": ("tooth_brushing", "count"),
        "ear_cleaning": ("ear_cleaning", "count"),
        "medications": ("medication_intakes", "count"),
    }

    if record_type not in type_mapping:
        return error_response("invalid_type", f"Unsupported record type: {record_type}")

    collection_name, value_field = type_mapping[record_type]
    
    # Calculate date range
    since_date = datetime.now() - timedelta(days=days)
    
    # Fetch records
    records = list(app.db[collection_name].find({
        "pet_id": pet_id,
        "date_time": {"$gte": since_date}
    }).sort("date_time", 1))

    stats_data = []
    for record in records:
        dt = record.get("date_time")
        if isinstance(dt, datetime):
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        else:
            date_str = str(dt)

        if value_field == "count":
            value = 1
        else:
            value = record.get(value_field, 0)

        stats_data.append({
            "date": date_str,
            "value": value
        })

    return jsonify({"data": stats_data})
