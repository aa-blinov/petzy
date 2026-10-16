"""Личный доступ Petzy (ptz_...): как он приходит в заголовке и какой вид должен иметь.

Токен только проходит через сервер: его не хранят, не пишут в журнал и не возвращают в ответе.
"""

import re

TOKEN_PATTERN = re.compile(r"ptz_[A-Za-z0-9_-]+")

MISSING_TOKEN_TEXT = (
    "Нужен личный доступ Petzy. Создайте его в настройках Petzy, раздел «Доступ для ассистентов», "
    "и передайте в заголовке Authorization"
)
MALFORMED_TOKEN_TEXT = (
    "Личный доступ Petzy начинается с ptz_. Скопируйте его из раздела «Доступ для ассистентов» целиком"
)


class TokenError(ValueError):
    """Заголовок Authorization не годится: код для ответа и текст для человека. Сам токен в текст не попадает."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def is_token(value: str) -> bool:
    """Похоже ли значение на личный доступ Petzy: префикс ptz_ и только символы, которые можно передать в заголовке."""
    return TOKEN_PATTERN.fullmatch(value) is not None


def bearer_value(authorization: str | None) -> str | None:
    """Всё после схемы Bearer в заголовке Authorization, или None, если заголовка нет или схема другая.

    Схема читается без учёта регистра, как того требует RFC 7235. Само значение здесь не проверяется.
    """
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    return value


def personal_token(authorization: str | None) -> str:
    """Личный доступ из заголовка Authorization. Для любого другого заголовка бросает TokenError."""
    value = bearer_value(authorization)
    if value is None:
        raise TokenError("token_missing", MISSING_TOKEN_TEXT)
    if not is_token(value):
        raise TokenError("token_malformed", MALFORMED_TOKEN_TEXT)
    return value
