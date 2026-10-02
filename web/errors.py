"""Common error definitions and helpers for API responses."""

import logging
from dataclasses import dataclass
from typing import Dict, Tuple

from flask import jsonify, Response

logger = logging.getLogger(__name__)


class TransactionRollback(Exception):
    """Raised inside a MongoDB transaction to force a rollback.

    Use this when business logic detects an inconsistency that should
    abort the transaction (e.g. a document disappeared between read and
    delete). Catch and translate at the route boundary.
    """


class PetNotFoundDuringDeletion(TransactionRollback):
    """Pet disappeared between access check and transaction delete."""


class MedicationNotFoundDuringDeletion(TransactionRollback):
    """Medication disappeared between access check and transaction delete."""


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
    "owner_action_forbidden": ErrorDef("owner_action_forbidden", "Это действие доступно только владельцу", 403),
    # Not found (404)
    "not_found": ErrorDef("not_found", "Ресурс не найден", 404),
    "record_not_found": ErrorDef("record_not_found", "Запись не найдена", 404),
    "pet_not_found": ErrorDef("pet_not_found", "Питомец не найден", 404),
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
    "account_wrong_password": ErrorDef("account_wrong_password", "Неверный текущий пароль", 422),
    "privacy_consent_required": ErrorDef(
        "privacy_consent_required", "Чтобы создать аккаунт, нужно согласие на обработку персональных данных", 422
    ),
    "privacy_version_outdated": ErrorDef(
        "privacy_version_outdated", "Политика обновилась, пока страница была открыта. Откройте её заново", 422
    ),
    "account_admin_undeletable": ErrorDef(
        "account_admin_undeletable",
        "Аккаунт администратора удалить нельзя: без него никто не сможет управлять Petzy",
        422,
    ),
    "account_delete_failed": ErrorDef(
        "account_delete_failed", "Не получилось удалить аккаунт. Попробуйте ещё раз позже", 500
    ),
    "account_email_invalid": ErrorDef("account_email_invalid", "Проверьте адрес почты", 422),
    "account_email_taken": ErrorDef("account_email_taken", "Эта почта уже подтверждена в другом аккаунте Petzy", 422),
    "account_no_pending_email": ErrorDef("account_no_pending_email", "Нет почты, которая ждёт подтверждения", 422),
    "account_link_invalid": ErrorDef(
        "account_link_invalid", "Ссылка устарела или уже использована. Запросите новую", 422
    ),
    "mail_not_configured": ErrorDef("mail_not_configured", "Отправка писем пока не настроена", 503),
    "mail_send_failed": ErrorDef("mail_send_failed", "Не удалось отправить письмо. Попробуйте позже", 503),
    "registration_closed": ErrorDef("registration_closed", "Регистрация сейчас закрыта", 403),
    "register_username_invalid": ErrorDef(
        "register_username_invalid",
        "Логин: от 3 до 30 символов, латинские буквы, цифры, точка, дефис или подчёркивание. Начинается с буквы или цифры",
        422,
    ),
    "register_name_required": ErrorDef("register_name_required", "Напишите, как к вам обращаться", 422),
    "register_email_required": ErrorDef(
        "register_email_required", "Укажите почту: на неё придёт ссылка, если забудете пароль", 422
    ),
    "register_username_taken": ErrorDef("register_username_taken", "Этот логин занят, выберите другой", 422),
    "register_password_short": ErrorDef("register_password_short", "Пароль должен быть не короче 8 символов", 422),
    "register_password_long": ErrorDef("register_password_long", "Пароль слишком длинный", 422),
    "register_password_weak": ErrorDef("register_password_weak", "Такой пароль легко угадать. Придумайте другой", 422),
    "share_already_invited": ErrorDef("share_already_invited", "Приглашение этому пользователю уже отправлено", 422),
    "share_invite_not_found": ErrorDef("share_invite_not_found", "Приглашение не найдено или уже отменено", 404),
    "share_not_member": ErrorDef("share_not_member", "У вас нет доступа к этому питомцу по приглашению", 404),
    "validation_error_already_shared": ErrorDef(
        "validation_error_already_shared", "Доступ уже предоставлен этому пользователю", 422
    ),
    "export_invalid_type": ErrorDef("export_invalid_type", "Неверный тип экспорта", 422),
    "export_invalid_format": ErrorDef("export_invalid_format", "Неверный тип формата", 422),
    "user_exists": ErrorDef("user_exists", "Пользователь с таким именем уже существует", 422),
    "invalid_type": ErrorDef("invalid_type", "Неподдерживаемый тип записи", 422),
    "event_type_not_found": ErrorDef("event_type_not_found", "Тип события не найден", 404),
    "event_type_builtin_admin_only": ErrorDef(
        "event_type_builtin_admin_only", "Встроенный тип общий для всех, его меняет администратор", 403
    ),
    "event_type_not_yours": ErrorDef("event_type_not_yours", "Этот тип создал другой пользователь", 403),
    "event_type_builtin_immutable": ErrorDef(
        "event_type_builtin_immutable", "Встроенный тип события нельзя удалить", 422
    ),
    "event_type_has_events": ErrorDef("event_type_has_events", "У этого типа есть записи. Сначала удалите их", 422),
    # Documents
    "document_file_required": ErrorDef("document_file_required", "Файл обязателен", 422),
    "document_unsupported_type": ErrorDef("document_unsupported_type", "Неподдерживаемый тип файла", 422),
    "document_file_too_large": ErrorDef(
        "document_file_too_large",
        "Файл больше 10 МБ. Если это снимки, упакуйте их в ZIP: архивы принимаются до 500 МБ",
        422,
    ),
    "request_too_large": ErrorDef(
        "request_too_large", "Файл больше 10 МБ. Если это снимки, упакуйте их в ZIP: архивы принимаются до 500 МБ", 413
    ),
    # Scans (web/storage.py)
    "storage_not_configured": ErrorDef(
        "storage_not_configured", "Хранилище файлов сейчас недоступно. Попробуйте позже", 503
    ),
    "scan_unsupported_type": ErrorDef(
        "scan_unsupported_type", "Этот формат не подходит. Нужен ZIP, 7Z, RAR, TAR, GZ, DICOM или ISO", 422
    ),
    "document_content_mismatch": ErrorDef(
        "document_content_mismatch", "Файл не похож на свой тип. Загрузите PDF или фотографию", 422
    ),
    "storage_quota_exceeded": ErrorDef(
        "storage_quota_exceeded",
        "Место для документов закончилось. Удалите ненужные файлы или напишите администратору",
        422,
    ),
    "too_many_pending_uploads": ErrorDef(
        "too_many_pending_uploads", "Уже идут другие загрузки. Дождитесь их или отмените", 429
    ),
    "scan_too_large": ErrorDef("scan_too_large", "Файл больше 500 МБ. Разделите архив на части", 422),
    "scan_upload_not_found": ErrorDef(
        "scan_upload_not_found", "Загрузка не найдена или устарела. Выберите файл ещё раз", 404
    ),
    "scan_upload_incomplete": ErrorDef(
        "scan_upload_incomplete", "Файл загрузился не полностью. Попробуйте ещё раз", 422
    ),
    "scan_category_fixed": ErrorDef("scan_category_fixed", "Архив со снимками нельзя перенести из «Снимков»", 422),
    "scan_content_mismatch": ErrorDef(
        "scan_content_mismatch",
        "Содержимое файла не совпадает с его расширением: это не архив и не DICOM. Проверьте файл и выберите его ещё раз",
        422,
    ),
    # Push notifications
    "push_subscription_taken": ErrorDef(
        "push_subscription_taken",
        "Эта подписка на уведомления принадлежит другому аккаунту",
        422,
    ),
    "push_not_configured": ErrorDef("push_not_configured", "Push-уведомления не настроены на сервере", 422),
    # Other
    "no_data_for_export": ErrorDef("no_data_for_export", "У этого питомца пока нет записей для выгрузки", 404),
    "upload_error": ErrorDef("upload_error", "Не удалось загрузить файл", 404),
    # Rate limit (429)
    "rate_limit_exceeded": ErrorDef("rate_limit_exceeded", "Превышен лимит запросов", 429),
    # Conflict (409)
    "conflict": ErrorDef("conflict", "Конфликт при обновлении данных", 409),
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
