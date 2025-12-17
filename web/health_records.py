"""Health records endpoints (asthma, defecation, litter, weight, feeding)."""

from flask import Blueprint, jsonify, request
from bson import ObjectId
from datetime import datetime

import web.app as app  # Import app module to access db, logger, and helper functions
from web.security import get_current_user, login_required

health_records_bp = Blueprint("health_records", __name__)


# Asthma routes
@health_records_bp.route("/api/asthma", methods=["POST"])
@login_required
def add_asthma_attack():
    """Add asthma attack event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = app.validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(date_str, time_str, "asthma attack", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        attack_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "duration": data.get("duration", ""),
            "reason": data.get("reason", ""),
            "inhalation": data.get("inhalation", False),
            "comment": data.get("comment", ""),
            "username": username,
        }

        app.db["asthma_attacks"].insert_one(attack_data)
        app.logger.info(f"Asthma attack recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Приступ астмы записан"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for asthma attack: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error adding asthma attack: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/asthma", methods=["GET"])
@login_required
def get_asthma_attacks():
    """Get asthma attacks for current pet."""
    pet_id = request.args.get("pet_id")

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = app.validate_pet_access(pet_id, username)
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
def update_asthma_attack(record_id):
    """Update asthma attack event."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "asthma_attacks", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(
            date_str, time_str, "asthma attack update", pet_id, username
        )
        if error_response:
            return error_response[0], error_response[1]

        attack_data = {
            "date_time": event_dt,
            "duration": data.get("duration", ""),
            "reason": data.get("reason", ""),
            "inhalation": data.get("inhalation", False),
            "comment": data.get("comment", ""),
        }

        result = app.db["asthma_attacks"].update_one({"_id": ObjectId(record_id)}, {"$set": attack_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Asthma attack updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Приступ астмы обновлен"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for asthma attack update: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error updating asthma attack: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/asthma/<record_id>", methods=["DELETE"])
@login_required
def delete_asthma_attack(record_id):
    """Delete asthma attack event."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "asthma_attacks", username)
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
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        app.logger.error(f"Error deleting asthma attack: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# Defecation routes
@health_records_bp.route("/api/defecation", methods=["POST"])
@login_required
def add_defecation():
    """Add defecation event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = app.validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(date_str, time_str, "defecation", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        defecation_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "stool_type": data.get("stool_type", ""),
            "color": data.get("color", "Коричневый"),
            "food": data.get("food", ""),
            "comment": data.get("comment", ""),
            "username": username,
        }

        app.db["defecations"].insert_one(defecation_data)
        app.logger.info(f"Defecation recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дефекация записана"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for defecation: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error adding defecation: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/defecation", methods=["GET"])
@login_required
def get_defecations():
    """Get defecations for current pet."""
    pet_id = request.args.get("pet_id")

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = app.validate_pet_access(pet_id, username)
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
def update_defecation(record_id):
    """Update defecation event."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "defecations", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(date_str, time_str, "defecation update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        defecation_data = {
            "date_time": event_dt,
            "stool_type": data.get("stool_type", ""),
            "color": data.get("color", "Коричневый"),
            "food": data.get("food", ""),
            "comment": data.get("comment", ""),
        }

        result = app.db["defecations"].update_one({"_id": ObjectId(record_id)}, {"$set": defecation_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Defecation updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дефекация обновлена"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid input data for defecation update: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error updating defecation: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/defecation/<record_id>", methods=["DELETE"])
@login_required
def delete_defecation(record_id):
    """Delete defecation event."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "defecations", username)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["defecations"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Defecation deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дефекация удалена"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid record_id for defecation deletion: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        app.logger.error(f"Error deleting defecation: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# Litter routes
@health_records_bp.route("/api/litter", methods=["POST"])
@login_required
def add_litter():
    """Add litter change event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = app.validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(date_str, time_str, "litter change", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        litter_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "comment": data.get("comment", ""),
            "username": username,
        }

        app.db["litter_changes"].insert_one(litter_data)
        app.logger.info(f"Litter change recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Смена лотка записана"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for litter change: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error adding litter change: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/litter", methods=["GET"])
@login_required
def get_litter_changes():
    """Get litter changes for current pet."""
    pet_id = request.args.get("pet_id")

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = app.validate_pet_access(pet_id, username)
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
def update_litter(record_id):
    """Update litter change event."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "litter_changes", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(
            date_str, time_str, "litter change update", pet_id, username
        )
        if error_response:
            return error_response[0], error_response[1]

        litter_data = {"date_time": event_dt, "comment": data.get("comment", "")}

        result = app.db["litter_changes"].update_one({"_id": ObjectId(record_id)}, {"$set": litter_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Litter change updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Смена лотка обновлена"}), 200

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for litter change update: record_id={record_id}, user={username}, error={e}"
        )
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error updating litter change: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/litter/<record_id>", methods=["DELETE"])
@login_required
def delete_litter(record_id):
    """Delete litter change event."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "litter_changes", username)
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
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        app.logger.error(f"Error deleting litter change: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# Weight routes
@health_records_bp.route("/api/weight", methods=["POST"])
@login_required
def add_weight():
    """Add weight measurement."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = app.validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(date_str, time_str, "weight", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        weight_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "weight": data.get("weight", ""),
            "food": data.get("food", ""),
            "comment": data.get("comment", ""),
            "username": username,
        }

        app.db["weights"].insert_one(weight_data)
        app.logger.info(f"Weight recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Вес записан"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for weight: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error adding weight: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/weight", methods=["GET"])
@login_required
def get_weights():
    """Get weight measurements for current pet."""
    pet_id = request.args.get("pet_id")

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = app.validate_pet_access(pet_id, username)
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
def update_weight(record_id):
    """Update weight measurement."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "weights", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(date_str, time_str, "weight update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        weight_data = {
            "date_time": event_dt,
            "weight": data.get("weight", ""),
            "food": data.get("food", ""),
            "comment": data.get("comment", ""),
        }

        result = app.db["weights"].update_one({"_id": ObjectId(record_id)}, {"$set": weight_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Weight updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Вес обновлен"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid input data for weight update: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error updating weight: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/weight/<record_id>", methods=["DELETE"])
@login_required
def delete_weight(record_id):
    """Delete weight measurement."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "weights", username)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["weights"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Weight deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Вес удален"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid record_id for weight deletion: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        app.logger.error(f"Error deleting weight: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


# Feeding routes
@health_records_bp.route("/api/feeding", methods=["POST"])
@login_required
def add_feeding():
    """Add feeding event."""
    try:
        data = request.get_json()
        pet_id = request.args.get("pet_id") or data.get("pet_id")

        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        success, error_response = app.validate_pet_access(pet_id, username)
        if not success:
            return error_response[0], error_response[1]

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(date_str, time_str, "feeding", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        feeding_data = {
            "pet_id": pet_id,
            "date_time": event_dt,
            "food_weight": data.get("food_weight", ""),
            "comment": data.get("comment", ""),
            "username": username,
        }

        app.db["feedings"].insert_one(feeding_data)
        app.logger.info(f"Feeding recorded: pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дневная порция записана"}), 201

    except ValueError as e:
        app.logger.warning(f"Invalid input data for feeding: pet_id={pet_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error adding feeding: pet_id={pet_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/feeding", methods=["GET"])
@login_required
def get_feedings():
    """Get feedings for current pet."""
    pet_id = request.args.get("pet_id")

    username, error_response = get_current_user()
    if error_response:
        return error_response[0], error_response[1]

    success, error_response = app.validate_pet_access(pet_id, username)
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
def update_feeding(record_id):
    """Update feeding event."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "feedings", username)
        if error_response:
            return error_response[0], error_response[1]

        data = request.get_json()

        date_str = data.get("date")
        time_str = data.get("time")
        event_dt, error_response = app.parse_event_datetime_safe(date_str, time_str, "feeding update", pet_id, username)
        if error_response:
            return error_response[0], error_response[1]

        feeding_data = {
            "date_time": event_dt,
            "food_weight": data.get("food_weight", ""),
            "comment": data.get("comment", ""),
        }

        result = app.db["feedings"].update_one({"_id": ObjectId(record_id)}, {"$set": feeding_data})

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Feeding updated: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дневная порция обновлена"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid input data for feeding update: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid input data"}), 400
    except Exception as e:
        app.logger.error(f"Error updating feeding: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500


@health_records_bp.route("/api/feeding/<record_id>", methods=["DELETE"])
@login_required
def delete_feeding(record_id):
    """Delete feeding event."""
    try:
        username, error_response = get_current_user()
        if error_response:
            return error_response[0], error_response[1]

        existing, pet_id, error_response = app.get_record_and_validate_access(record_id, "feedings", username)
        if error_response:
            return error_response[0], error_response[1]

        result = app.db["feedings"].delete_one({"_id": ObjectId(record_id)})

        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404

        app.logger.info(f"Feeding deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
        return jsonify({"success": True, "message": "Дневная порция удалена"}), 200

    except ValueError as e:
        app.logger.warning(f"Invalid record_id for feeding deletion: record_id={record_id}, user={username}, error={e}")
        return jsonify({"error": "Invalid record_id format"}), 400
    except Exception as e:
        app.logger.error(f"Error deleting feeding: record_id={record_id}, user={username}, error={e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

