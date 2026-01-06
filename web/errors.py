"""Common error definitions and helpers for API responses."""

import logging
from dataclasses import dataclass
from typing import Dict, Tuple

from flask import jsonify, Response

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ErrorDef:
    """Definition of a single error type."""

    code: str
    message: str
    status: int


ERRORS: Dict[str, ErrorDef] = {
    # Generic errors
    "validation_error": ErrorDef("validation_error", "Неверные данные", 422),
    "internal_error": ErrorDef("internal_error", "Внутренняя ошибка сервера", 500),
    # Auth / access (401)
    "unauthorized": ErrorDef("unauthorized", "Не авторизован", 401),
    "unauthorized_invalid_credentials": ErrorDef(
        "unauthorized_invalid_credentials", "Неверное имя пользователя или пароль", 401
    ),
    "unauthorized_refresh_token_required": ErrorDef(
        "unauthorized_refresh_token_required", "Требуется refresh token", 401
    ),
    "unauthorized_refresh_token_invalid": ErrorDef(
        "unauthorized_refresh_token_invalid", "Неверный или истекший refresh token", 401
    ),
    "unauthorized_refresh_token_not_found": ErrorDef(
        "unauthorized_refresh_token_not_found", "Refresh token не найден", 401
    ),
    # Forbidden (403)
    "forbidden": ErrorDef("forbidden", "Нет доступа к этому ресурсу", 403),
    "forbidden_admin_only": ErrorDef("forbidden_admin_only", "Доступ только для администратора", 403),
    "pet_forbidden": ErrorDef("pet_forbidden", "Нет доступа к этому животному", 403),
    "owner_action_forbidden": ErrorDef("owner_action_forbidden", "Это действие доступно только владельцу", 403),
    # Not found (404)
    "not_found": ErrorDef("not_found", "Ресурс не найден", 404),
    "record_not_found": ErrorDef("record_not_found", "Запись не найдена", 404),
    "pet_not_found": ErrorDef("pet_not_found", "Животное не найдено", 404),
    "user_not_found": ErrorDef("user_not_found", "Пользователь не найден", 404),
    "photo_not_found": ErrorDef("photo_not_found", "Фото не найдено", 404),
    # Validation errors (422)
    "invalid_pet_id": ErrorDef("invalid_pet_id", "Неверный формат pet_id", 422),
    "invalid_record_id": ErrorDef("invalid_record_id", "Неверный формат record_id", 422),
    "validation_error_pet_id_required": ErrorDef("validation_error_pet_id_required", "pet_id обязателен", 422),
    "validation_error_invalid_record": ErrorDef("validation_error_invalid_record", "Неверная запись", 422),
    "validation_error_no_update_data": ErrorDef("validation_error_no_update_data", "Нет данных для обновления", 422),
    "validation_error_admin_deactivation": ErrorDef(
        "validation_error_admin_deactivation", "Нельзя деактивировать администратора", 422
    ),
    "validation_error_username_required": ErrorDef(
        "validation_error_username_required", "Имя пользователя обязательно", 422
    ),
    "validation_error_self_share": ErrorDef("validation_error_self_share", "Нельзя поделиться с самим собой", 422),
    "validation_error_already_shared": ErrorDef(
        "validation_error_already_shared", "Доступ уже предоставлен этому пользователю", 422
    ),
    "export_invalid_type": ErrorDef("export_invalid_type", "Неверный тип экспорта", 422),
    "export_invalid_format": ErrorDef("export_invalid_format", "Неверный тип формата", 422),
    "user_exists": ErrorDef("user_exists", "Пользователь с таким именем уже существует", 422),
    # Other
    "no_data_for_export": ErrorDef("no_data_for_export", "Нет данных для экспорта", 404),
    "upload_error": ErrorDef("upload_error", "Ошибка при загрузке файла", 404),
    # Rate limit (429)
    "rate_limit_exceeded": ErrorDef("rate_limit_exceeded", "Превышен лимит запросов", 429),
    # Method not allowed (405)
    "method_not_allowed": ErrorDef("method_not_allowed", "Метод не разрешен", 405),
}


def error_response(key: str, custom_message: str = None) -> Tuple[Response, int]:
    """Build a JSON error response using predefined error definitions.

    Args:
        key: Error key from ERRORS dictionary.
        custom_message: Optional custom message to override the default one.

    Returns:
        Tuple of (Response, status_code) with JSON error response.

    Raises:
        KeyError: If key is not found in ERRORS (should not happen in production).
    """
    err = ERRORS.get(key)
    if err is None:
        # Fallback for unknown error keys (should not happen in production)
        logger.warning(f"Unknown error key: {key}")
        return jsonify({"success": False, "error": custom_message or "Неизвестная ошибка", "code": key}), 500

    return jsonify({"success": False, "error": custom_message or err.message, "code": err.code}), err.status
