"""Health records endpoints (asthma, defecation, litter, weight, feeding)."""

from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Request, Response
from bson import ObjectId
from datetime import datetime

import web.app as app  # Import app module to access db and logger
from web.app import api
from web.security import get_current_user, login_required
from web.helpers import (
    validate_pet_access,
    parse_event_datetime_safe,
    get_record_and_validate_access,
)
from web.schemas import (
    AsthmaAttackCreate,
    AsthmaAttackUpdate,
    AsthmaAttackListResponse,
    DefecationCreate,
    DefecationUpdate,
    DefecationListResponse,
    LitterChangeCreate,
    LitterChangeUpdate,
    LitterChangeListResponse,
    WeightRecordCreate,
    WeightRecordUpdate,
    WeightRecordListResponse,
    FeedingCreate,
    FeedingUpdate,
    FeedingListResponse,
    EyeDropsCreate,
    EyeDropsUpdate,
    EyeDropsListResponse,
    PetIdQuery,
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
        data = request.context.body
        pet_id = request.args.get("pet_id") or data.pet_id

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "asthma attack", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

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
        return jsonify({"success": True, "message": "Приступ астмы записан"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for asthma attack: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


@health_records_bp.route("/api/asthma", methods=["GET"])
@login_required
@api.validate(
    query=PetIdQuery,
    resp=Response(HTTP_200=AsthmaAttackListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_asthma_attacks():
    """Get asthma attacks for current pet."""
    pet_id = request.context.query.pet_id

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    attacks = list(app.db["asthma_attacks"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for attack in attacks:
        attack["_id"] = str(attack["_id"])
        if isinstance(attack.get("date_time"), datetime):
            attack["date_time"] = attack["date_time"].strftime("%Y-%m-%d %H:%M")
        if attack.get("inhalation") is True:
            attack["inhalation"] = "Да"
        elif attack.get("inhalation") is False:
            attack["inhalation"] = "Нет"

    return jsonify({"attacks": attacks})


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "asthma_attacks", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.context.body

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(
            date_str, time_str, "asthma attack update", pet_id, username
        )
        if error_response:
            return error_response[0], error_response[1]

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
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Asthma attack updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Приступ астмы обновлен"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for asthma attack update: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 422


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "asthma_attacks", username)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["asthma_attacks"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Asthma attack deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Приступ астмы удален"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for asthma attack deletion: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid record_id format"}), 422


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
        data = request.context.body
        pet_id = request.args.get("pet_id") or data.pet_id

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "defecation", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

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
        return jsonify({"success": True, "message": "Дефекация записана"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for defecation: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


@health_records_bp.route("/api/defecation", methods=["GET"])
@login_required
@api.validate(
    query=PetIdQuery,
    resp=Response(HTTP_200=DefecationListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_defecations():
    """Get defecations for current pet."""
    pet_id = request.context.query.pet_id

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    defecations = list(app.db["defecations"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for defecation in defecations:
        defecation["_id"] = str(defecation["_id"])
        if isinstance(defecation.get("date_time"), datetime):
            defecation["date_time"] = defecation["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"defecations": defecations})


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "defecations", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.context.body

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "defecation update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

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
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Defecation updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дефекация обновлена"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for defecation update: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 422


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "defecations", username)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["defecations"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Defecation deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дефекация удалена"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for defecation deletion: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid record_id format"}), 422


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
        data = request.context.body
        pet_id = request.args.get("pet_id") or data.pet_id

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "litter change", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        litter_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "comment": data.comment or "",
            "username": username,
        }

        app.db["litter_changes"].insert_one(litter_data)
        app.logger.info(f"Litter change recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Смена лотка записана"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for litter change: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


@health_records_bp.route("/api/litter", methods=["GET"])
@login_required
@api.validate(
    query=PetIdQuery,
    resp=Response(HTTP_200=LitterChangeListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_litter_changes():
    """Get litter changes for current pet."""
    pet_id = request.context.query.pet_id

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    litter_changes = list(app.db["litter_changes"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for change in litter_changes:
        change["_id"] = str(change["_id"])
        if isinstance(change.get("date_time"), datetime):
            change["date_time"] = change["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"litter_changes": litter_changes})


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "litter_changes", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.context.body

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(
            date_str, time_str, "litter change update", pet_id, username
        )
        if error_response:
            return error_response[0], error_response[1]

        litter_data = {}
        if event_dt is not None:
            litter_data["date_time"] = event_dt
        if data.comment is not None:
            litter_data["comment"] = data.comment

        result = app.db["litter_changes"].update_one({"_id": ObjectId(record_id)}, {"$set": litter_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Litter change updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Смена лотка обновлена"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for litter change update: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 422


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "litter_changes", username)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["litter_changes"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Litter change deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Смена лотка удалена"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for litter change deletion: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid record_id format"}), 422


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
        data = request.context.body
        pet_id = request.args.get("pet_id") or data.pet_id

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "weight", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

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
        return jsonify({"success": True, "message": "Вес записан"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for weight: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


@health_records_bp.route("/api/weight", methods=["GET"])
@login_required
@api.validate(
    query=PetIdQuery,
    resp=Response(HTTP_200=WeightRecordListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_weights():
    """Get weight measurements for current pet."""
    pet_id = request.context.query.pet_id

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    weights = list(app.db["weights"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for weight in weights:
        weight["_id"] = str(weight["_id"])
        if isinstance(weight.get("date_time"), datetime):
            weight["date_time"] = weight["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"weights": weights})


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "weights", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.context.body

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "weight update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        weight_data = {
            "date_time": event_dt,
            "weight": data.weight or "",
            "food": data.food or "",
            "comment": data.comment or "",
        }

        result = app.db["weights"].update_one({"_id": ObjectId(record_id)}, {"$set": weight_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Weight updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Вес обновлен"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid input data for weight update: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "weights", username)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["weights"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Weight deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Вес удален"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid record_id for weight deletion: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid record_id format"}), 422


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
        data = request.context.body
        pet_id = request.args.get("pet_id") or data.pet_id

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "feeding", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        feeding_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "food_weight": data.food_weight or "",
            "comment": data.comment or "",
            "username": username,
        }

        app.db["feedings"].insert_one(feeding_data)
        app.logger.info(f"Feeding recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дневная порция записана"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for feeding: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


@health_records_bp.route("/api/feeding", methods=["GET"])
@login_required
@api.validate(
    query=PetIdQuery,
    resp=Response(HTTP_200=FeedingListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_feedings():
    """Get feedings for current pet."""
    pet_id = request.context.query.pet_id

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    feedings = list(app.db["feedings"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for feeding in feedings:
        feeding["_id"] = str(feeding["_id"])
        if isinstance(feeding.get("date_time"), datetime):
            feeding["date_time"] = feeding["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"feedings": feedings})


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "feedings", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.context.body

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "feeding update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        feeding_data = {
            "date_time": event_dt,
            "food_weight": data.food_weight or "",
            "comment": data.comment or "",
        }

        result = app.db["feedings"].update_one({"_id": ObjectId(record_id)}, {"$set": feeding_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Feeding updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дневная порция обновлена"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid input data for feeding update: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "feedings", username)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["feedings"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Feeding deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дневная порция удалена"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid record_id for feeding deletion: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid record_id format"}), 422


# Eye drops routes
@health_records_bp.route("/api/eye-drops", methods=["POST"])
@login_required
@api.validate(
    body=Request(EyeDropsCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["health-records"],
)
def add_eye_drops():
    """Add eye drops record."""
    try:
        data = request.context.body
        pet_id = request.args.get("pet_id") or data.pet_id

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "eye drops", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        eye_drops_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "drops_type": data.drops_type or "Обычные",
            "comment": data.comment or "",
            "username": username,
        }

        app.db["eye_drops"].insert_one(eye_drops_data)
        app.logger.info(f"Eye drops recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Запись о каплях создана"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for eye drops: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 422


@health_records_bp.route("/api/eye-drops", methods=["GET"])
@login_required
@api.validate(
    query=PetIdQuery,
    resp=Response(HTTP_200=EyeDropsListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["health-records"],
)
def get_eye_drops():
    """Get eye drops records for current pet."""
    pet_id = request.context.query.pet_id

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = validate_pet_access(pet_id, username)
    if not success:
        return error_response[0], error_response[1]

    eye_drops = list(app.db["eye_drops"].find({"pet_id": pet_id}).sort("date_time", -1).limit(100))

    for item in eye_drops:
        item["_id"] = str(item["_id"])
        if isinstance(item.get("date_time"), datetime):
            item["date_time"] = item["date_time"].strftime("%Y-%m-%d %H:%M")

    return jsonify({"eye-drops": eye_drops})


@health_records_bp.route("/api/eye-drops/<record_id>", methods=["PUT"])
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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "eye_drops", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.context.body

        date_str = data.date
        time_str = data.time
        event_dt, error_response = parse_event_datetime_safe(date_str, time_str, "eye drops update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        eye_drops_data = {}
        if event_dt is not None:
            eye_drops_data["date_time"] = event_dt
        if data.drops_type is not None:
            eye_drops_data["drops_type"] = data.drops_type
        if data.comment is not None:
            eye_drops_data["comment"] = data.comment

        result = app.db["eye_drops"].update_one({"_id": ObjectId(record_id)}, {"$set": eye_drops_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Eye drops updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Запись о каплях обновлена"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for eye drops update: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 422


@health_records_bp.route("/api/eye-drops/<record_id>", methods=["DELETE"])
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
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = get_record_and_validate_access(record_id, "eye_drops", username)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["eye_drops"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Eye drops deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Запись о каплях удалена"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid record_id for eye drops deletion: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid record_id format"}), 422
