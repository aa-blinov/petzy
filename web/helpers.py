"""Shared helper utilities for datetime parsing and pet/access validation.

This module is intentionally independent from `web.app` to avoid circular imports.
Helpers are imported into `web.app` and used by blueprints via `web.app.*`.
"""

from datetime import datetime, timedelta
from io import BytesIO
from typing import Optional, Tuple

from bson import ObjectId
from bson.errors import InvalidId
from werkzeug.datastructures import FileStorage

from PIL import Image, ImageOps

try:
    # iPhones upload HEIC by default; without this Pillow can't open it, so
    # optimize_image fell back to storing the raw HEIC (uncompressed, and
    # undisplayable in Chrome/Firefox) instead of converting it to WebP.
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover - optional dependency
    pass

import web.app as app  # use app.db and app.logger so test patches (web.app.db) are visible
from web.errors import error_response


logger = app.logger


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
        raise ValueError("Требуется строка с датой")

    try:
        if time_str:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        if time_str:
            raise ValueError(
                f"Неверный формат даты/времени. Ожидается YYYY-MM-DD HH:MM, получено '{date_str} {time_str}'"
            )
        else:
            raise ValueError(f"Неверный формат даты. Ожидается YYYY-MM-DD, получено '{date_str}'")

    # Compare against current local time (naive, matching the contract that user input is local).
    now = datetime.now()
    max_future = now + timedelta(days=max_future_days) if allow_future else now
    max_past = now - timedelta(days=max_past_years * 365)

    if dt > max_future:
        raise ValueError(f"Дата не может быть более чем на {max_future_days} день(дней) в будущем")

    if dt < max_past:
        raise ValueError(f"Дата не может быть более чем на {max_past_years} лет в прошлом")

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
        raise ValueError("Дата и время должны быть указаны вместе")
    else:
        return datetime.now()


def check_pet_access(pet_id, username):
    """Check if user has access to pet."""
    try:
        pet = app.db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return False
        return pet.get("owner") == username or username in pet.get("shared_with", [])
    except (InvalidId, TypeError, ValueError):
        return False


def validate_pet_access_and_get(pet_id, username):
    """
    Same validation as validate_pet_access, but also returns the pet
    document on success — for callers (e.g. require_pet_access) that need
    the pet right after checking access, so they don't have to fetch it
    a second time later in the same request.

    Returns:
        tuple: (pet, error_response) where error_response is None if
               successful, or (None, (jsonify_response, status_code)) if
               validation/access fails.
    """
    if not pet_id:
        return None, error_response("validation_error_pet_id_required")

    try:
        object_id = ObjectId(pet_id)
    except (InvalidId, TypeError, ValueError):
        return None, error_response("invalid_pet_id")

    pet = app.db["pets"].find_one({"_id": object_id})
    if not pet or not (pet.get("owner") == username or username in pet.get("shared_with", [])):
        return None, error_response("pet_forbidden")

    return pet, None


def validate_pet_access(pet_id, username):
    """
    Validate pet_id format and check if user has access to the pet.

    Returns:
        tuple: (success, error_response) where success is True if access granted,
               or (False, (jsonify_response, status_code)) if validation/access fails
    """
    pet, error = validate_pet_access_and_get(pet_id, username)
    return pet is not None, error


def parse_event_datetime_safe(date_str, time_str, context="", pet_id=None, username=None, max_future_days=1):
    """
    Safely parse event datetime with error handling and logging.

    Returns:
        tuple: (datetime_object, error_response) where error_response is None if parsing succeeds,
               or (None, (jsonify_response, status_code)) if parsing fails
    """
    if date_str and time_str:
        try:
            event_dt = parse_datetime(date_str, time_str, allow_future=True, max_future_days=max_future_days)
            return event_dt, None
        except ValueError as e:
            log_context = f"pet_id={pet_id}, user={username}" if pet_id and username else ""
            logger.warning(f"Invalid datetime format for {context}: {log_context}, error={e}")
            return None, error_response("validation_error", str(e))
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
        return None, None, error_response("invalid_record_id")

    existing = app.db[collection_name].find_one({"_id": record_id_obj})
    if not existing:
        return None, None, error_response("record_not_found")

    pet_id = existing.get("pet_id")
    if not pet_id:
        return None, None, error_response("validation_error_invalid_record")

    if not check_pet_access(pet_id, username):
        return None, None, error_response("pet_forbidden")

    return existing, pet_id, None


def get_pet_and_validate(pet_id, username, require_owner=False):
    """
    Get pet by ID and validate user access.

    Returns:
        tuple: (pet, error_response) where error_response is None if successful,
               or (None, (jsonify_response, status_code)) if validation fails
    """
    try:
        pet = app.db["pets"].find_one({"_id": ObjectId(pet_id)})
        if not pet:
            return None, error_response("pet_not_found")

        if require_owner:
            if pet.get("owner") != username:
                return None, error_response("owner_action_forbidden")
        else:
            if not check_pet_access(pet_id, username):
                return None, error_response("pet_forbidden")

        return pet, None
    except (InvalidId, TypeError, ValueError):
        return None, error_response("invalid_pet_id")


def apply_pagination(query, page: int, page_size: int):
    """
    Apply pagination to MongoDB query.

    Args:
        query: MongoDB query object
        page: Page number (1-based)
        page_size: Number of items per page

    Returns:
        tuple: (paginated_query, skip_value) where paginated_query has limit and skip applied
    """
    skip = (page - 1) * page_size
    return query.skip(skip).limit(page_size), skip


def optimize_image(
    file_storage: FileStorage, max_width: int = 1920, max_height: int = 1920, quality: int = 85
) -> Optional[Tuple[BytesIO, str]]:
    """
    Optimize image by converting to WebP format and resizing if necessary.

    Args:
        file_storage: Werkzeug FileStorage object containing the image
        max_width: Maximum width for the image (default: 1920)
        max_height: Maximum height for the image (default: 1920)
        quality: WebP quality (0-100, default: 85)

    Returns:
        Tuple of (BytesIO object with optimized image, content_type) or None if optimization fails
    """

    try:
        # Read the original image
        file_storage.seek(0)
        image = Image.open(file_storage)
        # Phones store rotation as an EXIF tag rather than rotating the
        # pixels; re-encoding to WebP drops that tag, so without this a
        # portrait photo was stored (and shown) sideways.
        image = ImageOps.exif_transpose(image)

        # Convert RGBA to RGB if necessary (WebP supports both, but RGB is smaller)
        if image.mode in ("RGBA", "LA", "P"):
            # Create white background for transparency
            rgb_image = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            rgb_image.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
            image = rgb_image
        elif image.mode != "RGB":
            image = image.convert("RGB")

        # Resize if image is too large
        if image.width > max_width or image.height > max_height:
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Save to WebP format
        output = BytesIO()
        image.save(output, format="WEBP", quality=quality, method=6)
        output.seek(0)

        # Reset original file position
        file_storage.seek(0)

        return output, "image/webp"
    except Exception as e:
        logger.warning(f"Failed to optimize image: {e}", exc_info=True)
        return None


# Private, per-user files: fine to cache forever in the viewer's own
# browser (every URL is versioned or immutable), never in a shared cache.
PRIVATE_IMMUTABLE_CACHE = "private, max-age=31536000, immutable"


def resize_image_bytes(data: bytes, width: Optional[int], height: Optional[int]) -> Optional[bytes]:
    """Downscale stored image bytes for a ``?w=&h=`` request, as WebP.

    Returns None when no resize applies (no size given, or the image is
    already smaller). Runs on every cache miss, so it uses WebP ``method=4``
    — much faster than the ``method=6`` used once at upload, for a
    negligible size difference at thumbnail sizes.
    """
    if not width and not height:
        return None
    img = Image.open(BytesIO(data))
    if width and not height:
        height = max(1, int(img.height * (width / img.width)))
    elif height and not width:
        width = max(1, int(img.width * (height / img.height)))
    if img.width <= width and img.height <= height:
        return None
    img.thumbnail((width, height), Image.Resampling.LANCZOS)
    output = BytesIO()
    img.save(output, format="WEBP", quality=85, method=4)
    return output.getvalue()
