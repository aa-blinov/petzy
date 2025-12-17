"""Shared helper utilities for datetime parsing and pet/access validation.

This module is intentionally independent from `web.app` to avoid circular imports.
Helpers are imported into `web.app` and used by blueprints via `web.app.*`.
"""

from datetime import datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from flask import jsonify

import web.app as app  # use app.db and app.logger so test patches (web.app.db) are visible


logger = app.logger


def handle_error(error, context="", status_code=500):
    """Safely handle errors with logging and user-friendly messages."""
    if isinstance(error, ValueError):
        logger.warning(f"Invalid input data: {context}, error={error}")
        return jsonify({"error": "Invalid input data"}), 400
    elif isinstance(error, (KeyError, AttributeError)):
        logger.warning(f"Missing required data: {context}, error={error}")
        return jsonify({"error": "Missing required data"}), 400
    else:
        logger.error(f"Unexpected error: {context}, error={error}", exc_info=True)
        return jsonify({"error": "Internal server error"}), status_code


def parse_datetime(date_str, time_str=None, allow_future=True, max_future_days=1, max_past_years=50):
    """
    Safely parse datetime from date and optional time strings.

    Args:
        date_str: Date string in format "YYYY-MM-DD"
        time_str: Optional time string in format "HH:MM"
        allow_future: Whether to allow future dates (default: True)
        max_future_days: Maximum days in the future allowed (default: 1)
        max_past_years: Maximum years in the past allowed (default: 50)

    Returns:
        datetime object if parsing and validation succeed

    Raises:
        ValueError: If date format is invalid or date is out of allowed range
    """
    if not date_str:
        raise ValueError("Date string is required")

    try:
        if time_str:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        if time_str:
            raise ValueError(f"Invalid date/time format. Expected YYYY-MM-DD HH:MM, got '{date_str} {time_str}'")
        else:
            raise ValueError(f"Invalid date format. Expected YYYY-MM-DD, got '{date_str}'")

    now = datetime.now()
    max_future = now + timedelta(days=max_future_days) if allow_future else now
    max_past = now - timedelta(days=max_past_years * 365)

    if dt > max_future:
        raise ValueError(f"Date cannot be more than {max_future_days} day(s) in the future")

    if dt < max_past:
        raise ValueError(f"Date cannot be more than {max_past_years} years in the past")

    return dt


def parse_date(date_str, allow_future=False, max_past_years=50):
    """
    Safely parse date string (for birth_date).

    Args:
        date_str: Date string in format "YYYY-MM-DD"
        allow_future: Whether to allow future dates (default: False for birth dates)
        max_past_years: Maximum years in the past allowed (default: 50)

    Returns:
        datetime object if parsing and validation succeed, None if date_str is empty

    Raises:
        ValueError: If date format is invalid or date is out of allowed range
    """
    if not date_str:
        return None

    return parse_datetime(
        date_str,
        time_str=None,
        allow_future=allow_future,
        max_future_days=0,
        max_past_years=max_past_years,
    )


def parse_event_datetime(date_str, time_str, context=""):
    """
    Safely parse event datetime with proper error handling.

    Args:
        date_str: Date string in format "YYYY-MM-DD"
        time_str: Time string in format "HH:MM"
        context: Context string for error messages

    Returns:
        datetime object if parsing succeeds, current datetime if both date_str and time_str are empty

    Raises:
        ValueError: If date format is invalid or date is out of allowed range
    """
    if date_str and time_str:
        return parse_datetime(date_str, time_str, allow_future=True, max_future_days=1)
    elif date_str or time_str:
        raise ValueError("Both date and time must be provided together")
    else:
        return datetime.now()


def validate_pet_id(pet_id):
    """Validate that pet_id is a valid ObjectId string."""
    if not pet_id or not isinstance(pet_id, str):
        return False
    try:
        ObjectId(pet_id)
        return True
    except (InvalidId, TypeError, ValueError):
        return False


def check_pet_access(pet_id, username):
    """Check if user has access to pet."""
    if not validate_pet_id(pet_id):
        return False
    try:
        pet = app.db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return False
        return pet.get("owner") == username or username in pet.get("shared_with", [])
    except Exception:
        return False


def validate_pet_access(pet_id, username):
    """
    Validate pet_id format and check if user has access to the pet.

    Returns:
        tuple: (success, error_response) where success is True if access granted,
               or (False, (jsonify_response, status_code)) if validation/access fails
    """
    if not pet_id:
        return False, (jsonify({"error": "pet_id обязателен"}), 400)

    if not validate_pet_id(pet_id):
        return False, (jsonify({"error": "Неверный формат pet_id"}), 400)

    if not check_pet_access(pet_id, username):
        return False, (jsonify({"error": "Нет доступа к этому животному"}), 403)

    return True, None


def parse_event_datetime_safe(date_str, time_str, context="", pet_id=None, username=None):
    """
    Safely parse event datetime with error handling and logging.

    Returns:
        tuple: (datetime_object, error_response) where error_response is None if parsing succeeds,
               or (None, (jsonify_response, status_code)) if parsing fails
    """
    if date_str and time_str:
        try:
            event_dt = parse_datetime(date_str, time_str, allow_future=True, max_future_days=1)
            return event_dt, None
        except ValueError as e:
            log_context = f"pet_id={pet_id}, user={username}" if pet_id and username else ""
            logger.warning(f"Invalid datetime format for {context}: {log_context}, error={e}")
            return None, (jsonify({"error": f"Неверный формат даты/времени: {str(e)}"}), 400)
    else:
        return datetime.now(), None


def get_record_and_validate_access(record_id, collection_name, username):
    """
    Get record by ID and validate user access.

    Returns:
        tuple: (record, pet_id, error_response) where error_response is None if successful,
               or (None, None, (jsonify_response, status_code)) if validation fails
    """
    try:
        record_id_obj = ObjectId(record_id)
    except (InvalidId, TypeError, ValueError):
        return None, None, (jsonify({"error": "Invalid record_id format"}), 400)

    existing = app.db[collection_name].find_one({"_id": record_id_obj})
    if not existing:
        return None, None, (jsonify({"error": "Record not found"}), 404)

    pet_id = existing.get("pet_id")
    if not pet_id:
        return None, None, (jsonify({"error": "Invalid record"}), 400)

    if not check_pet_access(pet_id, username):
        return None, None, (jsonify({"error": "Нет доступа к этому животному"}), 403)

    return existing, pet_id, None


def get_pet_and_validate(pet_id, username, require_owner=False):
    """
    Get pet by ID and validate user access.

    Returns:
        tuple: (pet, error_response) where error_response is None if successful,
               or (None, (jsonify_response, status_code)) if validation fails
    """
    if not validate_pet_id(pet_id):
        return None, (jsonify({"error": "Неверный формат pet_id"}), 400)

    pet = app.db["pets"].find_one({"_id": ObjectId(pet_id)})
    if not pet:
        return None, (jsonify({"error": "Питомец не найден"}), 404)

    if require_owner:
        if pet.get("owner") != username:
            return None, (jsonify({"error": "Только владелец может выполнить это действие"}), 403)
    else:
        if not check_pet_access(pet_id, username):
            return None, (jsonify({"error": "Нет доступа к этому животному"}), 403)

    return pet, None
