"""Success messages definitions for API responses."""

from dataclasses import dataclass, field
from typing import Dict, Any, Tuple

from flask import jsonify, Response


@dataclass(frozen=True)
class MessageDef:
    """Definition of a single success message with all response fields."""

    message: str
    extra_fields: Dict[str, Any] = field(default_factory=dict)


MESSAGES: Dict[str, MessageDef] = {
    # Auth messages
    "auth_login_success": MessageDef("Вход выполнен успешно"),
    "auth_logout_success": MessageDef("Выход выполнен успешно"),
    "auth_refresh_success": MessageDef("Токен обновлен"),
    # Pet messages
    "pet_created": MessageDef("Питомец создан"),
    "pet_updated": MessageDef("Данные питомца обновлены"),
    "pet_deleted": MessageDef("Питомец удален"),
    "pet_shared": MessageDef("Доступ предоставлен пользователю {username}"),
    "pet_unshared": MessageDef("Доступ убран у пользователя {username}"),
    # User messages
    "user_created": MessageDef("Пользователь создан"),
    "user_updated": MessageDef("Пользователь обновлен"),
    "user_deactivated": MessageDef("Пользователь деактивирован"),
    "user_password_reset": MessageDef("Пароль изменен"),
    # Events (generic engine — one message per action, parametrized by the
    # event type's own label, since "запись" is feminine regardless of what
    # kind of event it is).
    "event_created": MessageDef("Запись «{label}» добавлена"),
    "event_updated": MessageDef("Запись «{label}» обновлена"),
    "event_deleted": MessageDef("Запись «{label}» удалена"),
    "event_type_deleted": MessageDef("Тип события удалён"),
    # Documents
    "document_created": MessageDef("Документ добавлен"),
    "document_updated": MessageDef("Документ обновлён"),
    "document_deleted": MessageDef("Документ удалён"),
}


def get_message(key: str, status: int = 200, **kwargs) -> Tuple[Response, int]:
    """Build a JSON success response using predefined message definitions.

    Args:
        key: Message key from MESSAGES dictionary.
        status: HTTP status code (default: 200).
        **kwargs: Optional keyword arguments for:
            - Message formatting (if message contains placeholders like {username})
            - Additional fields to include in response (e.g., pet, user, access_token)

    Returns:
        Tuple of (Response, status_code) with JSON success response.

    Example:
        get_message("pet_created", status=201, pet=pet_data)  # Adds 'pet' field, status 201
        get_message("pet_shared", username="john")  # Formats message with username, status 200
    """
    msg_def = MESSAGES.get(key)
    if msg_def is None:
        # Fallback for unknown message keys (should not happen in production)
        return jsonify({"success": True, "message": f"Операция выполнена успешно ({key})"}), status

    # Format message with kwargs if it contains placeholders
    message = msg_def.message
    if kwargs:
        try:
            message = message.format(**kwargs)
        except KeyError:
            # If formatting fails, use message as-is
            pass

    # Build response dictionary
    response = {"success": True, "message": message}

    # Add extra fields from definition
    response.update(msg_def.extra_fields)

    # Add any additional fields from kwargs (excluding those used for formatting)
    # Extract formatting keys from message template
    format_keys = set()
    if "{" in msg_def.message:
        import re

        format_keys = set(re.findall(r"\{(\w+)\}", msg_def.message))

    # Add kwargs that weren't used for formatting
    for k, v in kwargs.items():
        if k not in format_keys:
            response[k] = v

    return jsonify(response), status
