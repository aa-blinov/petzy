"""Pydantic schemas for request/response validation and OpenAPI documentation.

Naming Convention:
- All JSON fields use snake_case (e.g., pet_id, date_time, food_weight, eye_drops, tooth_brushing)
- See docs/api-naming-conventions.md for full naming rules
"""

from datetime import datetime, timedelta
import re
from typing import Optional, List, Annotated, Any, Dict, Literal
from pydantic import (
    BaseModel as PydanticBaseModel,
    BeforeValidator,
    Field,
    field_validator,
    model_validator,
    ConfigDict,
    StringConstraints,
)


def _not_a_flag(value: Any) -> Any:
    # In a float field pydantic reads true as 1 and false as 0, so a flag sent where a number belongs is refused.
    if isinstance(value, bool):
        raise ValueError("Значение должно быть числом")
    return value


# A number a client sends. The type refuses NaN and Infinity, so a field needs no bound of its own to refuse them,
# and it refuses true and false.
FiniteFloat = Annotated[float, BeforeValidator(_not_a_flag), Field(allow_inf_nan=False)]


def _dose_above_zero(value: Optional[float]) -> Optional[float]:
    # A dose of zero or less would be written as an intake that takes nothing from the stock.
    if value is not None and value <= 0:
        raise ValueError("Доза должна быть больше нуля")
    return value


# Every schema in this module builds on this class. pydantic quotes the value that failed in its error text (a password,
# a health note), and the logs keep that text, so the quoting is switched off for all of them.
class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)


# Custom type for ObjectId strings
ObjectIdString = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{24}$")]


def validate_date_logic(v: str, allow_future: bool = True, max_future_days: int = 1, max_past_years: int = 50):
    """Common logic for date validation."""
    if not v:
        return v
    try:
        dt = datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Неверный формат даты. Используйте YYYY-MM-DD")

    now = datetime.now()
    # The server runs in UTC and the app sends its own calendar date: a phone east of UTC is a day ahead for hours
    # every day. One day of slack, as for an event's date, keeps «today» valid wherever the person is.
    if not allow_future and dt.date() > now.date() + timedelta(days=1):
        raise ValueError("Дата не может быть в будущем")

    if allow_future:
        max_future = now + timedelta(days=max_future_days)
        if dt > max_future:
            raise ValueError(f"Дата не может быть более чем на {max_future_days} день в будущем")

    max_past = now - timedelta(days=max_past_years * 365)
    if dt < max_past:
        raise ValueError(f"Дата не может быть более чем на {max_past_years} лет в прошлом")

    return v


# ============================================================================
# Common Response Models
# ============================================================================


class SuccessResponse(BaseModel):
    """Standard success response."""

    success: bool = True
    message: str
    id: Optional[str] = Field(None, description="id созданной записи, когда запрос её создаёт")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Операция выполнена успешно",
            }
        }
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: str
    code: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "Произошла ошибка",
                "code": "validation_error",
            }
        }
    )


class PaginatedResponse(BaseModel):
    """Base class for paginated list responses."""

    page: int = Field(..., description="Текущая страница")
    page_size: int = Field(..., description="Размер страницы")
    total: int = Field(..., description="Общее количество записей")


# ============================================================================
# Auth Schemas
# ============================================================================


class PasswordForgotRequest(BaseModel):
    login: str = Field(..., min_length=1, max_length=254, description="Логин или почта")
    model_config = ConfigDict(json_schema_extra={"example": {"login": "demo"}})


class PasswordResetRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=1, max_length=256)
    model_config = ConfigDict(
        json_schema_extra={"example": {"token": "the token from the letter", "password": "the new one"}}
    )


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=1, max_length=256)
    model_config = ConfigDict(
        json_schema_extra={"example": {"current_password": "the old one", "new_password": "the new one"}}
    )


class AccountDeleteRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=256, description="Текущий пароль")
    model_config = ConfigDict(json_schema_extra={"example": {"password": "the current one"}})


class DeletionPet(BaseModel):
    id: str
    name: str
    new_owner: Optional[str] = Field(None, description="Кому перейдёт питомец (в transferred)")
    owner: Optional[str] = Field(None, description="Чей это питомец (в left)")
    model_config = ConfigDict(
        json_schema_extra={"example": {"id": "507f1e88bf19b6fcdb027c75", "name": "Рекс", "new_owner": "family"}}
    )


class AccountDeletionPreviewResponse(BaseModel):
    """What deleting the account would do, for the confirmation screen."""

    can_delete: bool = Field(..., description="False для администратора: его аккаунт удалить нельзя")
    deleted: List[DeletionPet] = Field(
        ..., description="Питомцы, которых больше никто не ведёт: удалятся со всеми записями"
    )
    transferred: List[DeletionPet] = Field(
        ..., description="Питомцы, которых ведёт кто-то ещё: перейдут первому, с кем ими поделились"
    )
    left: List[DeletionPet] = Field(..., description="Чужие питомцы, к которым пропадёт доступ")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "can_delete": True,
                "deleted": [{"id": "507f1e88bf19b6fcdb027c75", "name": "Рекс"}],
                "transferred": [{"id": "507f1e88bf19b6fcdb027c76", "name": "Мурзик", "new_owner": "family"}],
                "left": [{"id": "507f1e88bf19b6fcdb027c77", "name": "Писька"}],
            }
        }
    )


class EmailChangeRequest(BaseModel):
    """An empty email removes it."""

    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=256, description="Текущий пароль")
    model_config = ConfigDict(
        json_schema_extra={"example": {"email": "anna@example.com", "password": "the current one"}}
    )


class EmailVerifyRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    model_config = ConfigDict(json_schema_extra={"example": {"token": "the token from the letter"}})


class AccountResponse(BaseModel):
    username: str
    full_name: str = ""
    email: str = Field("", description="Подтверждённая почта для восстановления пароля")
    email_verified: bool = False
    pending_email: str = Field("", description="Указана, но ещё не подтверждена")
    mail_enabled: bool = Field(False, description="Настроена ли отправка писем")
    privacy_consent_needed: bool = Field(
        False, description="Нужно согласие с текущей редакцией политики (POST /api/me/privacy-consent)"
    )
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "demo",
                "full_name": "Анна",
                "email": "anna@example.com",
                "email_verified": True,
                "pending_email": "",
                "mail_enabled": True,
                "privacy_consent_needed": False,
            }
        }
    )


class RegisterRequest(BaseModel):
    """Self sign-up. The login and password rules are checked in the view,
    so each problem gets its own message."""

    username: str = Field(..., min_length=1, max_length=64, description="Логин")
    password: str = Field(..., min_length=1, max_length=256, description="Пароль")
    full_name: Optional[str] = Field(None, max_length=100, description="Как к вам обращаться. Обязательно")
    email: Optional[str] = Field(
        None,
        max_length=254,
        description="Для восстановления пароля. Обязательна, когда почта настроена (mail_enabled в GET /api/auth/registration)",
    )
    privacy_consent: bool = Field(
        False,
        description="Согласие на обработку персональных данных (текст: /consent, политика: /privacy). Без него 422",
    )
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "demo",
                "password": "the new one",
                "full_name": "Анна",
                "email": "anna@example.com",
                "privacy_consent": True,
            }
        }
    )


class PrivacyConsentRequest(BaseModel):
    version: str = Field(..., max_length=32, description="policy_version из GET /api/legal")
    model_config = ConfigDict(json_schema_extra={"example": {"version": "2026-09-28.3"}})


class LegalInfoResponse(BaseModel):
    """Facts the privacy policy page fills in; empty until the operator sets them."""

    policy_version: str
    operator: str = Field("", description="Кто обрабатывает данные")
    contact_email: str = Field("", description="Куда писать о персональных данных")
    server_location: str = Field("", description="Страна, где стоит сервер с базой данных")
    backups_kept_days: int = Field(..., description="Сколько дней живут резервные копии")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "policy_version": "2026-09-28.3",
                "operator": "ИП Иванов",
                "contact_email": "privacy@example.com",
                "server_location": "Казахстан",
                "backups_kept_days": 3,
            }
        }
    )


class VersionResponse(BaseModel):
    """Which commit is answering. Empty fields mean the deploy did not write one, not that it is hidden."""

    commit: str = Field(description="Полный номер коммита, на котором собрано то, что отвечает")
    short: str = Field(description="Первые семь знаков того же коммита, для разговора вслух")
    known: bool = Field(description="False, когда запуск не был сделан деплоем и номера у него нет")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"commit": "d38df68cf0a3b5aa2e177799d759dc5c45c2c3dd", "short": "d38df68", "known": True}
        }
    )


class RegistrationStatusResponse(BaseModel):
    open: bool
    mail_enabled: bool = False
    model_config = ConfigDict(json_schema_extra={"example": {"open": True, "mail_enabled": True}})


class AuthLoginRequest(BaseModel):
    """Login request model."""

    username: str = Field(..., min_length=1, max_length=50, description="Имя пользователя")
    password: str = Field(..., min_length=1, description="Пароль")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "admin",
                "password": "password123",
            }
        }
    )


class AuthRefreshRequest(BaseModel):
    """Refresh token request model (optional - token can be in cookies)."""

    refresh_token: Optional[str] = Field(None, description="Refresh token (optional if provided in cookies)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            }
        }
    )


class AuthTokensResponse(BaseModel):
    """Authentication tokens response."""

    success: bool = True
    message: str
    access_token: Optional[str] = Field(
        None, description="Только для нативного клиента (запрос без заголовка Origin). Живёт 15 минут"
    )
    refresh_token: Optional[str] = Field(
        None, description="Только для нативного клиента. Живёт 7 дней, обменивается на access_token в /api/auth/refresh"
    )
    username: Optional[str] = Field(None, description="Логин, под которым начата сессия (после сброса пароля)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Вы вошли",
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            }
        }
    )


class AuthRefreshResponse(BaseModel):
    """Access token refresh response."""

    success: bool = True
    message: str = Field("Токен обновлён", description="Текст для человека")
    access_token: str
    refresh_token: Optional[str] = Field(
        None,
        description="Новый refresh-токен (только нативному клиенту). Старый после этого работает ещё 30 секунд",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Токен обновлён",
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            }
        }
    )


class AdminStatusResponse(BaseModel):
    """Admin status check response."""

    is_admin: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_admin": True,
            }
        }
    )


class AuthSessionResponse(BaseModel):
    """Identity of the currently signed-in user.

    The SPA's single auth probe: it answers "am I signed in, and as
    whom?" and nothing else. Cheap enough to call on every app boot —
    the username comes straight off the verified JWT and the admin flag
    is a string comparison; the only read is the account's active check.
    """

    username: str
    is_admin: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "anna",
                "is_admin": False,
            }
        }
    )


class UserSearchItem(BaseModel):
    """Simple user item for search/autocomplete."""

    username: str
    model_config = ConfigDict(json_schema_extra={"example": {"username": "anna"}})


# What may be remembered as a default: any plain field of any record type, built-in or the family's own. Only the shape is
# checked here (a type is a short code, a field a short name), since the types and fields of a household are its own.
_DEFAULT_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Not remembered: they say when and for whom, which is never the same twice.
_NOT_DEFAULTABLE = {"date", "time", "comment", "pet_id", "_id", "type", "username"}
_DEFAULTS_MAX_TYPES = 40
_DEFAULTS_MAX_FIELDS = 30
_DEFAULTS_MAX_TOTAL = 300


class PetFormDefaults(BaseModel):
    """PUT /api/pets/<id>/form-defaults: what a new record of each type starts with for this pet.

    The whole set, replacing the old one; empty values are dropped. A pet's food, drops or way of cleaning are about the
    pet, so everyone with access to it gets the same ones."""

    form_defaults: Dict[str, Dict[str, str]] = Field(default_factory=dict)

    @field_validator("form_defaults")
    @classmethod
    def _shaped_and_bounded(cls, value: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        if len(value) > _DEFAULTS_MAX_TYPES:
            raise ValueError("Слишком много значений по умолчанию")
        cleaned: Dict[str, Dict[str, str]] = {}
        total = 0
        for form, fields in value.items():
            if not _DEFAULT_NAME.match(form):
                raise ValueError("Для этой записи значения по умолчанию не задаются")
            if len(fields) > _DEFAULTS_MAX_FIELDS:
                raise ValueError("Слишком много значений по умолчанию")
            kept: Dict[str, str] = {}
            for name, text in fields.items():
                if not _DEFAULT_NAME.match(name) or name in _NOT_DEFAULTABLE:
                    raise ValueError("Для этого поля значение по умолчанию не задаётся")
                text = (text or "").strip()
                if len(text) > 200:
                    raise ValueError("Слишком длинное значение по умолчанию")
                if text:
                    kept[name] = text
            total += len(kept)
            if kept:
                cleaned[form] = kept
        if total > _DEFAULTS_MAX_TOTAL:
            raise ValueError("Слишком много значений по умолчанию")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={"example": {"form_defaults": {"feeding": {"food_weight": "320", "food_type": "сухой"}}}}
    )


class PetFormDefaultsResponse(BaseModel):
    form_defaults: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    model_config = ConfigDict(
        json_schema_extra={"example": {"form_defaults": {"feeding": {"food_weight": "320", "food_type": "сухой"}}}}
    )


# The colours a pet's card can take; the palette itself lives in the frontend (petLook.ts), the server only knows the names.
PET_ACCENTS = ("sage", "sky", "lilac", "rose", "sun", "teal", "slate")
# The hand-written faces the name on the card can take; the files are the frontend's (petLook.ts).
PET_FONTS = ("caveat", "marck", "bad", "pacifico", "neucha", "amatic")
# What lies behind the card (drawn in the frontend): a fill, a gradient, a pattern, the photo blurred, a paper.
PET_BACKDROPS = (
    "plain",
    "fill",
    "gradient",
    "aurora",
    "photo",
    "dots",
    "stripes",
    "grid",
    "waves",
    "paws",
    "stars",
    "hearts",
    "paper",
    "linen",
)
# What lies behind the screens of the pet: the same patterns, minus the photo, which only the card can take (it is a picture of
# the pet, not a backdrop for every screen).
PET_SCENES = tuple(key for key in PET_BACKDROPS if key != "photo")
# The frames the pet's photo can take, drawn in the frontend (petLook.ts).
PET_FRAMES = (
    "story",
    "sticker",
    "neon",
    "holo",
    "polaroid",
    "arch",
    "flower",
    "circle",
    "heart",
    "star",
    "cloud",
    "paw",
    "stamp",
    "film",
    "glitch",
    "popart",
    "aura",
    "gallery",
    "porthole",
    "gold",
    "marble",
    "leather",
    "denim",
    "kraft",
    "velvet",
    "glitter",
    "pearl",
    "glass",
    "carbon",
    "rope",
)
PET_TAGLINE_MAX = 40


class PetLook(BaseModel):
    """PUT /api/pets/<id>/look: how the pet's card shows it, a line about it, a colour, a hand-written face for the name and a frame for the photo.

    The whole look, replacing the old one: a part left empty is dropped, and with every part empty the look is removed.
    Everyone with access to the pet sets it and sees the same look. A save made from an older copy is refused (409) and the
    look as it is now comes back with it, the way the visit note does it."""

    tagline: str = Field("", description="Подпись: пробелы схлопываются, не длиннее 40 символов")
    accent: str = Field("", json_schema_extra={"enum": ["", *PET_ACCENTS]})
    font: str = Field("", json_schema_extra={"enum": ["", *PET_FONTS]})
    frame: str = Field("", json_schema_extra={"enum": ["", *PET_FRAMES]})
    backdrop: str = Field("", json_schema_extra={"enum": ["", *PET_BACKDROPS]})
    # The same catalogue behind the whole feed area of the pet (not the card): its background.
    scene: str = Field("", json_schema_extra={"enum": ["", *PET_SCENES]})
    base_version: Optional[str] = Field(
        None,
        description="Только для запроса: версия оформления, с которой его правили. Без неё сохранение перезаписывает то, что есть, "
        "а с устаревшей версией отвечает 409 и отдаёт оформление как оно сейчас",
    )
    # Which part of the photo each frame shows, in percent of the photo: {frame: {x, y, w, h}}. A frame's window has its
    # own shape, so each has its own; the one the pet wears is read, the others wait for the next time it is chosen.
    crops: Dict[str, Dict[str, FiniteFloat]] = Field(
        default_factory=dict,
        description="По рамке: {x, y, w, h} в процентах фото; x, y от 0 до 100, w, h от 1 до 100, x+w и y+h не больше 100,5",
    )

    @field_validator("tagline")
    @classmethod
    def _tagline(cls, value: str) -> str:
        value = " ".join((value or "").split())
        if len(value) > PET_TAGLINE_MAX:
            raise ValueError(f"Подпись не длиннее {PET_TAGLINE_MAX} символов")
        return value

    @field_validator("accent")
    @classmethod
    def _accent(cls, value: str) -> str:
        value = (value or "").strip()
        if value and value not in PET_ACCENTS:
            raise ValueError("Такого цвета нет")
        return value

    @field_validator("font")
    @classmethod
    def _font(cls, value: str) -> str:
        value = (value or "").strip()
        if value and value not in PET_FONTS:
            raise ValueError("Такого шрифта нет")
        return value

    @field_validator("frame")
    @classmethod
    def _frame(cls, value: str) -> str:
        value = (value or "").strip()
        if value and value not in PET_FRAMES:
            raise ValueError("Такой рамки нет")
        return value

    @field_validator("crops")
    @classmethod
    def _crops(cls, value: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
        cleaned: Dict[str, Dict[str, float]] = {}
        for frame, crop in (value or {}).items():
            if frame not in PET_FRAMES:
                raise ValueError("Такой рамки нет")
            if set(crop) != {"x", "y", "w", "h"}:
                raise ValueError("Область фото задаётся четырьмя числами")
            x, y, w, h = (round(float(crop[k]), 2) for k in ("x", "y", "w", "h"))
            if not (0 <= x <= 100 and 0 <= y <= 100 and 1 <= w <= 100 and 1 <= h <= 100):
                raise ValueError("Область фото вне снимка")
            if x + w > 100.5 or y + h > 100.5:
                raise ValueError("Область фото вне снимка")
            cleaned[frame] = {"x": x, "y": y, "w": w, "h": h}
        return cleaned

    @field_validator("backdrop")
    @classmethod
    def _backdrop(cls, value: str) -> str:
        value = (value or "").strip()
        if value and value not in PET_BACKDROPS:
            raise ValueError("Такой подложки нет")
        return value

    @field_validator("scene")
    @classmethod
    def _scene(cls, value: str) -> str:
        value = (value or "").strip()
        if value and value not in PET_SCENES:
            raise ValueError("Такого фона нет")
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tagline": "Нелюбимый пес",
                "accent": "sun",
                "font": "pacifico",
                "frame": "rope",
                "backdrop": "stripes",
                "scene": "dots",
                "crops": {"kraft": {"x": 56.46, "y": 0, "w": 43.54, "h": 41.51}},
            }
        }
    )


class PetLookResponse(BaseModel):
    look: Dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "look": {
                    "tagline": "Нелюбимый пес",
                    "accent": "sun",
                    "font": "pacifico",
                    "frame": "rope",
                    "backdrop": "stripes",
                }
            }
        }
    )


class UserSearchResponse(BaseModel):
    """List of usernames for autocomplete."""

    users: List[UserSearchItem]
    model_config = ConfigDict(json_schema_extra={"example": {"users": [{"username": "anna"}, {"username": "family"}]}})


# ============================================================================
# User Schemas
# ============================================================================


class UserCreate(BaseModel):
    """User creation request model."""

    username: str = Field(..., min_length=1, max_length=50, description="Имя пользователя")
    password: str = Field(..., min_length=6, max_length=100, description="Пароль")
    full_name: Optional[str] = Field(None, max_length=100, description="Полное имя")
    email: Optional[str] = Field(None, max_length=100, description="Email")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "user1",
                "password": "securepass123",
                "full_name": "Иван Иванов",
                "email": "ivan@example.com",
            }
        }
    )


class UserUpdate(BaseModel):
    """User update request model."""

    full_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=6, max_length=100, description="Новый пароль (опционально)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Иван Иванов",
                "email": "ivan@example.com",
                "is_active": True,
                "password": "newsecurepass123",
            }
        }
    )


class UserResponse(BaseModel):
    """User response model."""

    # Not «_id: str»: pydantic makes an underscore name private, and the
    # id went missing from the published schema.
    id: str = Field(alias="_id")
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    is_active: bool
    created_at: str
    created_by: Optional[str] = None
    # The account document comes whole (without the password hash), so these are in the answer too.
    email_verified: Optional[bool] = Field(None, description="Подтверждена ли почта")
    pending_email: Optional[str] = Field(
        None, description="Новый адрес, который ждёт подтверждения по ссылке из письма"
    )
    is_admin: Optional[bool] = Field(
        None, description="Флаг в записи; администратором считается только встроенный аккаунт ADMIN_USERNAME"
    )
    privacy_consent: Optional[Dict[str, Any]] = Field(None, description="Какая редакция политики принята и когда")
    sessions_valid_after: Optional[int] = Field(
        None, description="Unix-время в секундах: токены, выданные раньше, не действуют"
    )
    form_defaults: Optional[Dict[str, Any]] = Field(None, description="Устаревшие значения форм на аккаунте")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "username": "user1",
                "full_name": "Иван Иванов",
                "email": "ivan@example.com",
                "is_active": True,
                "created_at": "2024-01-15 14:30",
                "created_by": "admin",
            }
        },
    )


class UserResponseWrapper(BaseModel):
    """Wrapper for user response (matches current API structure)."""

    user: UserResponse
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user": {
                    "_id": "507f1f77bcf86cd799439011",
                    "username": "demo",
                    "full_name": "Анна",
                    "email": "anna@example.com",
                    "email_verified": True,
                    "is_active": True,
                    "is_admin": False,
                    "created_at": "2026-01-15 12:00",
                }
            }
        }
    )


class UserListResponse(BaseModel):
    """List of users response.

    With a page and a total: the list is a growing table of accounts, not a
    short one, and until this it printed every row at once.
    """

    users: List[UserResponse]
    total: int = 0
    page: int = 1
    per_page: int = 0
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "users": [
                    {
                        "_id": "507f1f77bcf86cd799439011",
                        "username": "demo",
                        "full_name": "Анна",
                        "email": "anna@example.com",
                        "email_verified": True,
                        "is_active": True,
                        "is_admin": False,
                        "created_at": "2026-01-15 12:00",
                    }
                ],
                "total": 1,
                "page": 1,
                "per_page": 20,
            }
        }
    )


class PasswordResetCheckResponse(BaseModel):
    """Whether a password reset link is still usable, asked before showing the form."""

    valid: bool = False
    model_config = ConfigDict(json_schema_extra={"example": {"valid": True}})


class PasswordCommonCheckRequest(BaseModel):
    """A password to ask about before it is sent anywhere.

    No minimum length on purpose: the answer is «is this one of the common
    ones», and a short password deserves that answer rather than a complaint
    about its length.
    """

    password: str = Field(..., max_length=200, description="Пароль, который проверяется на частоту")

    model_config = ConfigDict(json_schema_extra={"example": {"password": "password123"}})


class PasswordCommonCheckResponse(BaseModel):
    """Whether a password is in the server's list of common ones.

    The list itself stays on the server: it is asked about a password that has not
    been sent anywhere yet, and the answer is what goes to the screen.
    """

    common: bool = False
    model_config = ConfigDict(json_schema_extra={"example": {"common": False}})


class UserPasswordResetRequest(BaseModel):
    """User password reset request model."""

    password: str = Field(..., min_length=6, max_length=100, description="Новый пароль")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "password": "newsecurepass123",
            }
        }
    )


class SharedPetRef(BaseModel):
    """A pet both people can see, as it is given in a person's card: the id opens its medical card."""

    id: str
    name: str

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": {"_id": "507f1e88bf19b6fcdb027c75", "name": "Рекс"}},
    )


class UserPublicProfile(BaseModel):
    """The subset of a user's profile visible to a co-owner they share a
    pet with — not the full admin UserResponse (no email, no is_active)."""

    username: str
    full_name: Optional[str] = None
    created_at: str
    shared_pets: List["SharedPetRef"] = Field(
        default_factory=list, description="Питомцы, доступные обоим: идентификатор и имя, чтобы имя открывало медкарту"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "user2",
                "full_name": "Мария Петрова",
                "created_at": "2024-01-15 14:30",
                "shared_pets": [{"id": "…", "name": "Рекс"}],
            }
        }
    )


# ============================================================================
# Pet Schemas
# ============================================================================


class TilesSettings(BaseModel):
    """Tiles settings model for pet dashboard."""

    order: List[str] = Field(..., description="Order of tiles (list of tile IDs)")
    visible: dict[str, bool] = Field(..., description="Visibility of each tile")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "order": [
                    "weight",
                    "defecation",
                    "feeding",
                    "eye_drops",
                    "asthma",
                    "litter",
                    "ear_cleaning",
                    "tooth_brushing",
                ],
                "visible": {
                    "weight": True,
                    "defecation": True,
                    "feeding": True,
                    "eye_drops": True,
                    "asthma": True,
                    "litter": True,
                    "ear_cleaning": True,
                    "tooth_brushing": True,
                },
            }
        }
    )


# ---- Medical profile: what a vet asks, kept on the pet -----------------------


def _blank_to_none(v):
    """«  » and «» are «not filled»: stored as None so a card doesn't show an empty line."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class Allergy(BaseModel):
    substance: str = Field(..., min_length=1, max_length=100, description="На что аллергия")
    reaction: Optional[str] = Field(None, max_length=200, description="Как проявляется")

    @field_validator("substance", mode="before")
    @classmethod
    def strip_substance(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("reaction", mode="before")
    @classmethod
    def blank_reaction(cls, v):
        return _blank_to_none(v)

    model_config = ConfigDict(
        json_schema_extra={"example": {"substance": "Курица", "reaction": "зуд, покраснение ушей"}}
    )


class Condition(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Хроническое состояние или диагноз")
    since_year: Optional[int] = Field(None, ge=1950, le=2100, description="С какого года")
    note: Optional[str] = Field(None, max_length=300)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("note", mode="before")
    @classmethod
    def blank_note(cls, v):
        return _blank_to_none(v)

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Дисплазия тазобедренных суставов", "note": "Следить"}}
    )


class Clinic(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="Клиника")
    vet: Optional[str] = Field(None, max_length=100, description="Врач")
    phone: Optional[str] = Field(None, max_length=30, description="Телефон")

    @field_validator("name", "vet", "phone", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"name": "Ветклиника «Айболит»", "vet": "Иванова А. П.", "phone": "+7 701 555 01 02"}
        }
    )


class Doctor(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Врач")
    specialty: Optional[str] = Field(None, max_length=60, description="Специальность: терапевт, кардиолог, стоматолог")

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("specialty", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)

    model_config = ConfigDict(json_schema_extra={"example": {"name": "Каримов Д.", "specialty": "терапевт"}})


class ClinicEntry(BaseModel):
    """One clinic the pet is taken to, with the doctors seen there."""

    name: Optional[str] = Field(None, max_length=100, description="Название клиники")
    phone: Optional[str] = Field(None, max_length=30, description="Телефон")
    doctors: List[Doctor] = Field(default_factory=list, max_length=10)

    @field_validator("name", "phone", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Ветклиника «Айболит»",
                "phone": "+7 701 555 01 02",
                "doctors": [{"name": "Иванова А. П.", "specialty": "терапевт"}],
            }
        }
    )


def _same_text(value: str) -> str:
    """What makes two spellings one: the case and the spaces do not count."""
    return " ".join(value.split()).casefold()


def _joined(parts: List[Optional[str]], separator: str, limit: int) -> Optional[str]:
    """The distinct non-empty parts in order, cut to the field's length (never cut in the middle of the join's own text)."""
    seen: set = set()
    kept: List[str] = []
    for part in parts:
        if not part:
            continue
        key = _same_text(part)
        if key and key not in seen:
            seen.add(key)
            kept.append(part)
    text = separator.join(kept)
    return text[:limit] or None


def _merged_allergies(items: List["Allergy"]) -> List["Allergy"]:
    order: List[str] = []
    groups: dict = {}
    for item in items:
        key = _same_text(item.substance)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(item)
    out = []
    for key in order:
        group = groups[key]
        first = group[0]
        out.append(Allergy(substance=first.substance, reaction=_joined([a.reaction for a in group], ", ", 200)))
    return out


def _merged_conditions(items: List["Condition"]) -> List["Condition"]:
    order: List[str] = []
    groups: dict = {}
    for item in items:
        key = _same_text(item.name)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(item)
    out = []
    for key in order:
        group = groups[key]
        years = [c.since_year for c in group if c.since_year]
        out.append(
            Condition(
                name=group[0].name,
                since_year=min(years) if years else None,
                note=_joined([c.note for c in group], "; ", 300),
            )
        )
    return out


class MedicalProfile(BaseModel):
    """PUT /api/pets/<id>/medical-profile: the whole profile, replacing the old one."""

    chip_number: Optional[str] = Field(None, max_length=30, description="Номер чипа или клейма")
    blood_type: Optional[str] = Field(None, max_length=20, description="Группа крови")
    allergies: List[Allergy] = Field(default_factory=list, max_length=30)
    allergies_none_known: bool = Field(
        False, description="Владелец подтверждает: аллергий нет. «Не заполнено» и «нет» для врача разные вещи"
    )
    conditions: List[Condition] = Field(default_factory=list, max_length=30)
    diet: Optional[str] = Field(None, max_length=200, description="Чем и как часто кормят")
    living: Optional[str] = Field(
        None, max_length=200, description="Условия жизни: квартира или улица, другие животные"
    )
    reproduction: Optional[str] = Field(None, max_length=200, description="Беременности, роды, течка, если важно")
    clinics: List[ClinicEntry] = Field(
        default_factory=list,
        max_length=5,
        description="Клиники и врачи с их специальностями; первая клиника основная",
    )
    clinic: Clinic = Field(
        default_factory=Clinic,
        description="Основная клиника и её первый врач: то же, что первая запись в clinics (для старых клиентов)",
    )
    base_version: Optional[str] = Field(
        None,
        max_length=64,
        description="Версия профиля, из которой сделана форма. Если с тех пор профиль сохранил кто-то другой, ответ 409",
    )

    @field_validator("chip_number", "blood_type", "diet", "living", "reproduction", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)

    @model_validator(mode="after")
    def merge_repeats(self):
        """The same allergen written twice («Курица» and «курица ») is one allergen, and the same condition one condition: what
        each said is kept, joined, so that a vet reads a list with no repeats and loses nothing."""
        self.allergies = _merged_allergies(self.allergies)
        self.conditions = _merged_conditions(self.conditions)
        return self

    @model_validator(mode="after")
    def allergies_or_none(self):
        if self.allergies_none_known and self.allergies:
            raise ValueError("Нельзя одновременно указать аллергии и отметить, что их нет")
        return self

    @model_validator(mode="after")
    def clinics_and_the_main_clinic(self):
        """One list is the truth: ``clinics``. The single ``clinic`` of the earlier profile, stored or sent by an
        older client, becomes the first entry when there is no list, and is always written back as the first entry,
        so whatever still reads ``clinic`` (the PDF header, a cached app) keeps seeing the main clinic."""
        legacy = self.clinic
        if not self.clinics and (legacy.name or legacy.vet or legacy.phone):
            doctors = [Doctor(name=legacy.vet)] if legacy.vet else []
            self.clinics = [ClinicEntry(name=legacy.name, phone=legacy.phone, doctors=doctors)]
        main = self.clinics[0] if self.clinics else None
        self.clinic = (
            Clinic(name=main.name, phone=main.phone, vet=main.doctors[0].name if main.doctors else None)
            if main
            else Clinic()
        )
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chip_number": "643094100200311",
                "blood_type": "DEA 1.1+",
                "allergies": [{"substance": "Курица", "reaction": "зуд, покраснение ушей"}],
                "allergies_none_known": False,
                "conditions": [{"name": "Дисплазия тазобедренных суставов", "note": "Следить"}],
                "diet": "Сухой корм, два раза в день",
                "living": "Квартира, две кошки",
                "reproduction": "",
            }
        }
    )


class MedicalProfileOut(MedicalProfile):
    updated_at: Optional[str] = None
    version: Optional[str] = Field(None, description="Версия профиля: меняется при каждом сохранении")
    base_version: Optional[str] = Field(None, description="Только для запроса; в ответе его нет или null")


def _trimmed_name(value: Optional[str]) -> Optional[str]:
    """A name is one line without the spaces around it (a line break or a run of spaces inside is one space), and it cannot
    be nothing: «   » is not a pet."""
    if value is None:
        return None
    value = " ".join(value.split())
    if not value:
        raise ValueError("Имя не может быть пустым")
    return value


class PetCreate(BaseModel):
    """Pet creation request model."""

    name: str = Field(..., min_length=1, max_length=100, description="Имя питомца")
    breed: Optional[str] = Field(None, max_length=100, description="Порода")
    species: Optional[str] = Field(None, max_length=50, description="Вид животного (кот, собака и т.д.)")
    birth_date: Optional[str] = Field(None, description="Дата рождения в формате YYYY-MM-DD")
    tz: Optional[str] = Field(
        None,
        description="IANA-имя часового пояса, в котором введена дата рождения (Asia/Almaty): «сегодня» для неё считается по нему",
    )
    gender: Optional[str] = Field(None, max_length=20, description="Пол")
    is_neutered: Optional[bool] = Field(None, description="Кастрирован/Стерилизована")
    health_notes: Optional[str] = Field(None, max_length=1000, description="Особенности здоровья, аллергии")
    tiles_settings: Optional[TilesSettings] = Field(None, description="Настройки тайлов дневника")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        return _trimmed_name(v)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, v):
        """Validate birth date format and logic (no future dates)."""
        return validate_date_logic(v, allow_future=False)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Мурзик",
                "breed": "Британская короткошерстная",
                "species": "cat",
                "birth_date": "2020-03-15",
                "tz": "Asia/Almaty",
                "gender": "male",
                "is_neutered": True,
                "health_notes": "Здоров, аллергий нет",
                "tiles_settings": {
                    "order": [
                        "weight",
                        "defecation",
                        "feeding",
                        "eye_drops",
                        "asthma",
                        "litter",
                        "ear_cleaning",
                        "tooth_brushing",
                    ],
                    "visible": {
                        "weight": True,
                        "defecation": True,
                        "feeding": True,
                        "eye_drops": True,
                        "asthma": True,
                        "litter": True,
                        "ear_cleaning": True,
                        "tooth_brushing": True,
                    },
                },
            }
        }
    )


class PetUpdate(BaseModel):
    """Pet update request model."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    breed: Optional[str] = Field(None, max_length=100)
    species: Optional[str] = Field(None, max_length=50)
    birth_date: Optional[str] = Field(None, description="Дата рождения в формате YYYY-MM-DD")
    tz: Optional[str] = Field(
        None,
        description="IANA-имя часового пояса, в котором введена дата рождения (Asia/Almaty): «сегодня» для неё считается по нему",
    )
    gender: Optional[str] = Field(None, max_length=20)
    is_neutered: Optional[bool] = None
    health_notes: Optional[str] = Field(None, max_length=1000)
    remove_photo: Optional[bool] = Field(None, description="True, если нужно удалить текущую фотографию")
    tiles_settings: Optional[TilesSettings] = Field(None, description="Настройки тайлов дневника")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        return _trimmed_name(v)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, v):
        """Validate birth date format and logic (no future dates)."""
        return validate_date_logic(v, allow_future=False)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Мурзик Обновленный",
                "breed": "Британская короткошерстная",
                "species": "cat",
                "birth_date": "2020-03-15",
                "gender": "male",
                "is_neutered": True,
                "health_notes": "Аллергия на курицу",
                "remove_photo": False,
                "tiles_settings": {
                    "order": [
                        "weight",
                        "defecation",
                        "feeding",
                        "eye_drops",
                        "asthma",
                        "litter",
                        "ear_cleaning",
                        "tooth_brushing",
                    ],
                    "visible": {
                        "weight": True,
                        "defecation": True,
                        "feeding": True,
                        "eye_drops": True,
                        "asthma": True,
                        "litter": True,
                        "ear_cleaning": True,
                        "tooth_brushing": True,
                    },
                },
            }
        }
    )


class PetResponse(BaseModel):
    """Pet response model."""

    # Not «_id: str»: pydantic makes an underscore name private, and the
    # id went missing from the published schema.
    id: str = Field(alias="_id")
    name: str
    breed: Optional[str] = None
    species: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    is_neutered: Optional[bool] = None
    health_notes: Optional[str] = None
    medical_profile: Optional[MedicalProfileOut] = None
    photo_url: Optional[str] = None
    tiles_settings: Optional[TilesSettings] = None
    owner: str
    shared_with: Optional[List[str]] = None
    # Invited, not yet accepted. Only the owner sees them.
    share_invites: Optional[List[str]] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    current_user_is_owner: Optional[bool] = None
    look: Optional[Dict[str, Any]] = Field(
        None, description="Оформление питомца, как его задаёт PUT /api/pets/{pet_id}/look"
    )
    form_defaults: Optional[Dict[str, Any]] = Field(
        None, description="Значения по умолчанию для новых записей питомца, по типу записи"
    )
    next_owner: Optional[str] = Field(
        None,
        description="Только владельцу: к кому перейдёт питомец, если владелец удалит аккаунт (нет никого: null)",
    )
    visit_prep: Optional[Dict[str, Any]] = Field(
        None, description="Заметка к приёму, как её задаёт PUT /api/pets/{pet_id}/visit-prep"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "Мурзик",
                "breed": "Британская короткошерстная",
                "species": "cat",
                "birth_date": "2020-03-15",
                "gender": "male",
                "is_neutered": True,
                "health_notes": "Здоров",
                "photo_url": "/api/pets/507f1f77bcf86cd799439011/photo?v=abc12345",
                "owner": "admin",
                "shared_with": ["user2"],
                "created_at": "2024-01-15 14:30",
                "created_by": "admin",
                "current_user_is_owner": True,
                "tiles_settings": {
                    "order": [
                        "weight",
                        "defecation",
                        "feeding",
                        "eye_drops",
                        "asthma",
                        "litter",
                        "ear_cleaning",
                        "tooth_brushing",
                    ],
                    "visible": {
                        "weight": True,
                        "defecation": True,
                        "feeding": True,
                        "eye_drops": True,
                        "asthma": True,
                        "litter": True,
                        "ear_cleaning": True,
                        "tooth_brushing": True,
                    },
                },
            }
        },
    )


class PetInviteItem(BaseModel):
    pet_id: str
    pet_name: str
    species: Optional[str] = None
    owner: str
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1e88bf19b6fcdb027c75",
                "pet_name": "Рекс",
                "species": "dog",
                "owner": "family",
            }
        }
    )


class PetInviteListResponse(BaseModel):
    invites: List[PetInviteItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "invites": [
                    {"pet_id": "507f1e88bf19b6fcdb027c75", "pet_name": "Рекс", "species": "dog", "owner": "family"}
                ]
            }
        }
    )


class PetResponseWrapper(BaseModel):
    """Wrapper for pet response (matches current API structure)."""

    pet: PetResponse
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet": {
                    "_id": "507f1f77bcf86cd799439011",
                    "name": "Рекс",
                    "species": "dog",
                    "breed": "Лабрадор",
                    "birth_date": "2021-08-01",
                    "gender": "male",
                    "is_neutered": None,
                    "health_notes": "Не любит фен",
                    "owner": "demo",
                    "shared_with": [],
                    "created_by": "demo",
                    "created_at": "2026-10-03 07:52",
                    "current_user_is_owner": True,
                    "next_owner": None,
                    "form_defaults": {},
                    "photo_url": "/api/pets/507f1f77bcf86cd799439011/photo?v=abc12345",
                    "medical_profile": {
                        "allergies": [{"substance": "Курица", "reaction": "зуд, покраснение ушей"}],
                        "allergies_none_known": False,
                        "blood_type": "DEA 1.1+",
                        "chip_number": "643094100200311",
                    },
                }
            }
        }
    )


class PetCreatedResponse(SuccessResponse):
    """POST /api/pets: the new pet comes back whole."""

    pet: PetResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Питомец создан",
                "pet": {
                    "_id": "507f1f77bcf86cd799439011",
                    "name": "Мурзик",
                    "species": "cat",
                    "owner": "demo",
                    "shared_with": [],
                },
            }
        }
    )


class PetListResponse(BaseModel):
    """List of pets response."""

    pets: List[PetResponse]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pets": [
                    {
                        "_id": "507f1f77bcf86cd799439011",
                        "name": "Рекс",
                        "species": "dog",
                        "breed": "Лабрадор",
                        "birth_date": "2021-08-01",
                        "gender": "male",
                        "is_neutered": None,
                        "health_notes": "",
                        "owner": "demo",
                        "shared_with": [],
                        "created_at": "2026-10-03 07:52",
                        "current_user_is_owner": True,
                        "tiles_settings": {"order": ["feeding", "weight"], "visible": {"weight": True}},
                        "look": {"accent": "sun", "backdrop": "stripes", "font": "pacifico", "frame": "rope"},
                    }
                ]
            }
        }
    )


class PetShareRequest(BaseModel):
    """Pet sharing request model."""

    username: str = Field(..., min_length=1, max_length=50, description="Имя пользователя для предоставления доступа")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "user1",
            }
        }
    )


class PhotoQueryParams(BaseModel):
    """Query parameters for pet photo retrieval with optional resizing."""

    w: Optional[int] = Field(None, gt=0, le=4000, description="Ширина изображения в пикселях")
    h: Optional[int] = Field(None, gt=0, le=4000, description="Высота изображения в пикселях")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "w": 300,
                "h": 300,
            }
        }
    )


# ============================================================================
# Health Record Base Schemas
# ============================================================================


class HealthRecordBase(BaseModel):
    """Base schema for health records."""

    pet_id: ObjectIdString = Field(..., description="ID питомца")
    date: str = Field(..., description="Дата в формате YYYY-MM-DD")
    time: str = Field(..., description="Время в формате HH:MM")
    comment: Optional[str] = Field(None, max_length=500, description="Комментарий")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        """Validate date format and logic."""
        return validate_date_logic(v, allow_future=True, max_future_days=1)

    @field_validator("time")
    @classmethod
    def validate_time(cls, v):
        """Validate time format."""
        if not v:
            return v
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("Неверный формат времени. Используйте HH:MM")
        return v


class HealthRecordUpdateBase(BaseModel):
    """Base schema for health record updates."""

    date: Optional[str] = Field(None, description="Дата в формате YYYY-MM-DD")
    time: Optional[str] = Field(None, description="Время в формате HH:MM")
    comment: Optional[str] = Field(None, max_length=500, description="Комментарий")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        """Validate date format and logic."""
        if v:
            return validate_date_logic(v, allow_future=True, max_future_days=1)
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v):
        """Validate time format."""
        if not v:
            return v
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("Неверный формат времени. Используйте HH:MM")
        return v


# ============================================================================
# Event Type Registry Schemas
# ============================================================================


EVENT_FIELD_TYPES = ("text", "number", "select", "textarea")


class EventFieldOption(BaseModel):
    """A single ``select`` field choice."""

    value: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=100)
    model_config = ConfigDict(json_schema_extra={"example": {"value": "normal", "text": "Как обычно"}})


class EventTypeField(BaseModel):
    """One field of an event type's schema."""

    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{0,49}$", description="Идентификатор поля")
    label: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., description="text | number | select | textarea")
    required: bool = False
    options: Optional[List[EventFieldOption]] = None
    # Only meaningful for type="number" — e.g. a weight field capped at a
    # plausible range instead of accepting any float a fat-fingered digit
    # can produce.
    min: Optional[FiniteFloat] = None
    max: Optional[FiniteFloat] = None
    step: Optional[FiniteFloat] = None
    # How far a new reading may drift from this field's own rolling average
    # before it's pushed as a trend anomaly (see web/trend_alerts.py) — e.g.
    # 0.15 for 15%. A stable field (weight) and a naturally noisy one (a
    # feeding portion) don't belong under the same fixed sensitivity, so
    # this is per-field rather than one constant for every numeric type.
    # None means "use the module default".
    deviation_threshold: Optional[FiniteFloat] = Field(None, gt=0, lt=1)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in EVENT_FIELD_TYPES:
            raise ValueError(f"Тип поля должен быть одним из: {', '.join(EVENT_FIELD_TYPES)}")
        return v

    @model_validator(mode="after")
    def validate_select_has_options(self):
        if self.type == "select" and not self.options:
            raise ValueError("Для поля типа select нужно указать варианты")
        return self

    @model_validator(mode="after")
    def validate_min_max_range(self):
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("Минимум не может быть больше максимума")
        return self

    @model_validator(mode="after")
    def default_number_min_to_zero(self):
        # There's no UI yet for a custom event type to declare a field that
        # can legitimately go negative, so a number field with no explicit
        # min defaults to 0 here — the one place this is decided — rather
        # than every consumer (frontend Zod schema, backend field
        # validation) treating "no min" as "no floor at all".
        if self.type == "number" and self.min is None:
            self.min = 0.0
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "food_weight",
                "label": "Вес корма (г)",
                "type": "number",
                "required": True,
                "min": 0,
                "step": 0.1,
                "options": None,
                "deviation_threshold": 0.35,
            }
        }
    )


class EventChartConfig(BaseModel):
    """How this event type's data is charted."""

    kind: str = Field("count", description="count | value")
    value_field: Optional[str] = Field(None, description="Имя числового поля для графика значений")
    value_label: Optional[str] = Field(None, max_length=50, description="Подпись оси Y")

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v):
        if v not in ("count", "value"):
            raise ValueError("kind должен быть 'count' или 'value'")
        return v

    model_config = ConfigDict(
        json_schema_extra={"example": {"kind": "value", "value_field": "food_weight", "value_label": "Вес порции (г)"}}
    )


# The colours of a tile (TILE_COLORS in the client): another word is a style the app does not have, and the client takes the
# value of a colour it does not know as the CSS of a swatch.
EVENT_TYPE_COLORS = ("brown", "orange", "red", "green", "purple", "teal", "cyan", "yellow", "blue", "pink", "gray")
_ICON_KEY = re.compile(r"^[a-z0-9_-]{1,50}$")


def _tile_color(value):
    if value is not None and value not in EVENT_TYPE_COLORS:
        raise ValueError("Неизвестный цвет плитки")
    return value


def _icon_key(value):
    if value is not None and not _ICON_KEY.match(value):
        raise ValueError("Неверный ключ иконки")
    return value


def _label_without_spaces(value):
    """A name is one line without the spaces around it; «   » is no name."""
    return " ".join(value.split()) if isinstance(value, str) else value


def _chart_names_a_number_field(chart: "EventChartConfig", fields: List["EventTypeField"]) -> None:
    """A chart of values draws a number field the type has."""
    if chart.kind == "value" and chart.value_field not in {f.name for f in fields if f.type == "number"}:
        raise ValueError("Для графика значений нужно выбрать числовое поле типа")


RESERVED_EVENT_FIELD_NAMES = {"pet_id", "date", "time", "comment", "type", "fields"}


def _validate_field_names(fields: List[EventTypeField]) -> List[EventTypeField]:
    names = [f.name for f in fields]
    if len(names) != len(set(names)):
        raise ValueError("Имена полей должны быть уникальными")
    reserved = RESERVED_EVENT_FIELD_NAMES.intersection(names)
    if reserved:
        raise ValueError(f"Имя поля зарезервировано: {', '.join(sorted(reserved))}")
    return fields


class EventTypeCreate(BaseModel):
    """Create a new (always custom) event type."""

    label: str = Field(..., min_length=1, max_length=100, description="Название типа события")
    icon: str = Field(
        ..., min_length=1, max_length=50, description="Ключ иконки", json_schema_extra={"pattern": "^[a-z0-9_-]{1,50}$"}
    )
    color: str = Field(
        ..., min_length=1, max_length=20, description="Цвет плитки", json_schema_extra={"enum": list(EVENT_TYPE_COLORS)}
    )
    fields: List[EventTypeField] = Field(default_factory=list)
    chart: EventChartConfig = Field(default_factory=EventChartConfig)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v):
        return _validate_field_names(v)

    @field_validator("label", mode="before")
    @classmethod
    def label_without_spaces(cls, v):
        return _label_without_spaces(v)

    @field_validator("color")
    @classmethod
    def known_color(cls, v):
        return _tile_color(v)

    @field_validator("icon")
    @classmethod
    def icon_key(cls, v):
        return _icon_key(v)

    @model_validator(mode="after")
    def chart_has_its_field(self):
        _chart_names_a_number_field(self.chart, self.fields)
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "label": "Игра",
                "icon": "paw",
                "color": "blue",
                "fields": [{"name": "duration_min", "label": "Длительность (мин)", "type": "number", "required": True}],
                "chart": {"kind": "count"},
            }
        }
    )


class EventTypeUpdate(BaseModel):
    """Update an existing event type (builtin or custom)."""

    label: Optional[str] = Field(None, min_length=1, max_length=100)
    icon: Optional[str] = Field(None, min_length=1, max_length=50, json_schema_extra={"pattern": "^[a-z0-9_-]{1,50}$"})
    color: Optional[str] = Field(None, min_length=1, max_length=20, json_schema_extra={"enum": list(EVENT_TYPE_COLORS)})
    fields: Optional[List[EventTypeField]] = None
    chart: Optional[EventChartConfig] = None

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v):
        return v if v is None else _validate_field_names(v)

    @field_validator("label", mode="before")
    @classmethod
    def label_without_spaces(cls, v):
        return _label_without_spaces(v)

    @field_validator("color")
    @classmethod
    def known_color(cls, v):
        return _tile_color(v)

    @field_validator("icon")
    @classmethod
    def icon_key(cls, v):
        return _icon_key(v)

    @model_validator(mode="after")
    def chart_has_its_field(self):
        # Here only when the same request carries both; the view checks a chart or fields sent alone against what is stored.
        if self.chart is not None and self.fields is not None:
            _chart_names_a_number_field(self.chart, self.fields)
        return self

    model_config = ConfigDict(json_schema_extra={"example": {"label": "Кормление и угощение", "color": "yellow"}})


class EventTypeItem(BaseModel):
    """An event type as returned by the API."""

    key: str
    label: str
    icon: str
    color: str
    is_builtin: bool
    # Where a built-in type belongs in the catalogue (food, health, care...); empty for the family's own.
    category: Optional[str] = None
    created_by: Optional[str] = None
    fields: List[EventTypeField]
    chart: EventChartConfig
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "feeding",
                "label": "Кормление",
                "icon": "utensils",
                "color": "brown",
                "is_builtin": True,
                "category": "food",
                "created_by": None,
                "fields": [
                    {
                        "name": "food_weight",
                        "label": "Вес корма (г)",
                        "type": "number",
                        "required": True,
                        "min": 0,
                        "step": 0.1,
                        "options": None,
                    }
                ],
                "chart": {"kind": "value", "value_field": "food_weight", "value_label": "Вес порции (г)"},
            }
        }
    )


class EventTypeListResponse(BaseModel):
    """List of event types."""

    event_types: List[EventTypeItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_types": [
                    {
                        "key": "feeding",
                        "label": "Кормление",
                        "icon": "utensils",
                        "color": "brown",
                        "is_builtin": True,
                        "category": "food",
                        "created_by": None,
                        "fields": [],
                        "chart": {"kind": "count"},
                    }
                ]
            }
        }
    )


# ============================================================================
# Event Schemas (the generic events collection)
# ============================================================================


class EventCreate(HealthRecordBase):
    """Create a new event of any registered type."""

    type: str = Field(..., min_length=1, max_length=60, description="Ключ типа события")
    fields: dict[str, Any] = Field(default_factory=dict, description="Значения полей, специфичных для типа")
    tz: Optional[str] = Field(
        None,
        max_length=64,
        description="IANA-имя часового пояса, в котором введено время (Asia/Almaty): по нему выгрузка показывает время на часах выгружающего",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "type": "defecation",
                "date": "2024-01-15",
                "time": "14:30",
                "fields": {"stool_type": "Обычный", "color": "Коричневый"},
                "comment": "Все в порядке",
            }
        }
    )


class EventUpdate(HealthRecordUpdateBase):
    """Update an existing event."""

    fields: Optional[dict[str, Any]] = Field(None, description="Значения полей, специфичных для типа")
    tz: Optional[str] = Field(
        None,
        max_length=64,
        description="IANA-имя часового пояса, в котором введено время (Asia/Almaty): по нему выгрузка показывает время на часах выгружающего",
    )
    model_config = ConfigDict(json_schema_extra={"example": {"fields": {"weight": 29.3}, "tz": "Asia/Almaty"}})


class EventItem(BaseModel):
    """An event as returned by the API."""

    # Not «_id: str»: pydantic makes an underscore name private, and the
    # id went missing from the published schema.
    id: str = Field(alias="_id")
    pet_id: str
    type: str
    date_time: str
    username: str
    comment: Optional[str] = None
    fields: dict[str, Any] = Field(default_factory=dict)
    # Optional because records written before the field existed do not have it. Sent in the
    # project's date format like everything else around it; it used to reach the client as a
    # web-server date, «Sun, 11 Oct 2026 12:18:21 GMT», next to a date_time in «YYYY-MM-DD HH:MM».
    created_at: Optional[str] = Field(default=None, description="Когда запись создана, UTC, «YYYY-MM-DD HH:MM»")
    tz: Optional[str] = Field(
        default=None,
        description="IANA-зона, в которой введено время (Asia/Almaty); клиент переводит date_time на свои часы. Нет у старых записей",
    )
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "pet_id": "507f1e88bf19b6fcdb027c75",
                "type": "weight",
                "date_time": "2026-10-04 08:02",
                "username": "demo",
                "comment": "После прогулки",
                "fields": {"weight": 29.3},
                "tz": "Asia/Almaty",
            }
        }
    )


class EventListResponse(PaginatedResponse):
    """List of events with pagination."""

    items: List[EventItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "_id": "507f1f77bcf86cd799439011",
                        "pet_id": "507f1e88bf19b6fcdb027c75",
                        "type": "weight",
                        "date_time": "2026-10-04 08:02",
                        "username": "demo",
                        "comment": "",
                        "fields": {"weight": 29.3},
                        "tz": "Asia/Almaty",
                    }
                ],
                "page": 1,
                "page_size": 100,
                "total": 263,
            }
        }
    )


# ============================================================================
# Query Parameter Schemas
# ============================================================================


class PaginationQuery(BaseModel):
    """Pagination query parameters."""

    page: int = Field(1, ge=1, description="Номер страницы (начиная с 1)")
    page_size: int = Field(100, ge=1, le=1000, description="Количество элементов на странице (1-1000)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page": 1,
                "page_size": 100,
            }
        }
    )


class PetIdQuery(BaseModel):
    """Query parameter for pet_id."""

    pet_id: ObjectIdString = Field(..., description="ID питомца")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
            }
        }
    )


class UsedEventTypesResponse(BaseModel):
    """The event types a pet has at least one record of."""

    types: List[str] = Field(..., description="Ключи типов событий, по алфавиту")

    model_config = ConfigDict(json_schema_extra={"example": {"types": ["feeding", "walk", "weight"]}})


class PetDeletionImpactResponse(BaseModel):
    """What deleting a pet takes with it, counted."""

    events: int = Field(..., description="Записи событий")
    medications: int = Field(..., description="Курсы лекарств")
    documents: int = Field(..., description="Документы")
    medical_records: int = Field(..., description="Записи медкарты")

    model_config = ConfigDict(
        json_schema_extra={"example": {"events": 214, "medications": 3, "documents": 5, "medical_records": 12}}
    )


class ExportQuery(PetIdQuery):
    """Query of a data export: the pet, and the user's time zone."""

    tz: Optional[str] = Field(
        None,
        max_length=64,
        description="IANA-имя часового пояса пользователя (Asia/Almaty): по нему считаются время в имени файла и время записей в файле",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"pet_id": "507f1e88bf19b6fcdb027c75", "tz": "Asia/Almaty"}}
    )


class PetIdPaginationQuery(PetIdQuery, PaginationQuery):
    """Query parameters for pet_id with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "page": 1,
                "page_size": 100,
            }
        }
    )


class EventListQuery(PetIdPaginationQuery):
    """Query parameters for listing events, optionally filtered by type."""

    type: Optional[str] = Field(None, description="Фильтр по ключу типа события (без него все типы)")


# The longest period the History chart asks for («Всё время»). A count past
# this is refused: timedelta and datetime overflow on a huge one, which answered 500.
HEALTH_STATS_MAX_DAYS = 3650


class HealthStatsQuery(PetIdQuery):
    """Query parameters for statistics."""

    type: str = Field(..., description="Тип записи (feeding, asthma, weight и т.д.)")
    days: Optional[int] = Field(30, description=f"Количество дней, от 1 до {HEALTH_STATS_MAX_DAYS}")

    model_config = ConfigDict(
        json_schema_extra={"example": {"pet_id": "507f1e88bf19b6fcdb027c75", "type": "weight", "days": 90}}
    )

    @field_validator("days")
    @classmethod
    def _days_in_range(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and not 1 <= value <= HEALTH_STATS_MAX_DAYS:
            raise ValueError(f"Период: от 1 до {HEALTH_STATS_MAX_DAYS} дней")
        return value


class HealthStatsItem(BaseModel):
    """Simplified health record item for charts."""

    date: str = Field(..., description="Время записи, «YYYY-MM-DD HH:MM»")
    value: Any = Field(..., description="1 для считаемого типа или значение поля графика")
    model_config = ConfigDict(json_schema_extra={"example": {"date": "2026-10-04 08:02", "value": 29.3}})


class HealthStatsResponse(BaseModel):
    """Statistics response for charts."""

    data: List[HealthStatsItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {"date": "2026-10-03 08:10", "value": 29.2},
                    {"date": "2026-10-04 08:02", "value": 29.3},
                ]
            }
        }
    )


# ============================================================================
# Medication Schemas
# ============================================================================


class MedicationSchedule(BaseModel):
    days: List[int] = Field(..., description="Дни недели (0-6, где 0 - Пн, 6 - Вс)")
    times: List[str] = Field(..., description="Время приема (HH:mm)")

    @field_validator("times")
    @classmethod
    def times_are_clock_times_without_repeats(cls, v):
        """Each is a real HH:MM, and a time given twice is one dose: kept once, in order. Two slots at one time would
        ask to be marked twice."""
        for t in v:
            if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
                raise ValueError(f"Время «{t}» должно быть в виде ЧЧ:ММ")
        return sorted(set(v))

    model_config = ConfigDict(json_schema_extra={"example": {"days": [0, 6], "times": ["08:00", "20:00"]}})


def _course_date(v: Optional[str]) -> Optional[str]:
    """A course date: empty (clears it), or a real YYYY-MM-DD within a year ahead and fifty back."""
    if v is None or v == "":
        return v
    return validate_date_logic(v, allow_future=True, max_future_days=366)


COURSE_FIELDS_NOTE = "YYYY-MM-DD; пустая строка убирает дату"


class MedicationDetailQuery(BaseModel):
    """Query of one course: the user's zone, for «сегодня» (``intakes_today``). Any other value reads as UTC."""

    tz: Optional[str] = Field(
        None,
        description="IANA-имя часового пояса человека (Asia/Almaty): по нему «сегодня» для intakes_today. Без него, или если имя неизвестно, UTC",
    )


class MedicationListQuery(PetIdQuery):
    """Query parameters for listing medications with timezone support."""

    client_date: Optional[str] = Field(None, description="Client local date (YYYY-MM-DD)")
    tz: Optional[str] = Field(
        None,
        description="IANA-имя часового пояса человека (Asia/Almaty): по нему «сегодня» для intakes_today. Без него, или если имя неизвестно, берётся client_date, а без него UTC",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"pet_id": "507f1e88bf19b6fcdb027c75", "client_date": "2026-10-13"}}
    )


class UpcomingDosesQuery(PetIdQuery):
    """Query parameters for upcoming doses with timezone support."""

    client_datetime: Optional[str] = Field(None, description="Client local datetime (ISO format)")
    tz: Optional[str] = Field(
        None,
        description="IANA-имя часового пояса человека (Asia/Almaty): без client_datetime «сейчас» берётся по нему. Без него, или если имя неизвестно, UTC",
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"pet_id": "507f1e88bf19b6fcdb027c75", "client_datetime": "2026-10-13 08:30"}}
    )


class MedicationCreate(PetIdQuery):
    name: str = Field(..., max_length=100)
    type: str = Field(..., max_length=50, description="Ингаляция, Таблетка, Капли и т.д.")
    form_factor: Optional[str] = Field(None, max_length=20, description="tablet, liquid, injection, other")
    strength: Optional[str] = Field(None, max_length=50, description="50 mg, 5 mg/ml")
    dosage: Optional[str] = Field(None, max_length=50, description="Legacy dosage string")
    unit: Optional[str] = Field(None, max_length=20, description="Legacy unit string")
    dose_unit: Optional[str] = Field(None, max_length=20, description="tablet, ml, etc")
    default_dose: FiniteFloat = Field(1.0, le=10_000, description="Default amount to subtract from inventory")
    schedule: MedicationSchedule
    # «По необходимости» хранится отдельно, а не выводится из пустого расписания: у курса
    # без напоминаний может быть расписание, и раньше оно молча пропадало вместе с режимом.
    # None, а не False: клиент, который этого поля не знает (установленное приложение прежней
    # версии), его не присылает, и такой курс должен читаться по старому правилу «нет времени =
    # по необходимости», а не стать «расписанием без времени».
    as_needed: Optional[bool] = None
    inventory_enabled: bool = False
    inventory_total: Optional[FiniteFloat] = Field(None, ge=0, le=1_000_000)
    inventory_current: Optional[FiniteFloat] = Field(None, ge=0, le=1_000_000)
    inventory_warning_threshold: Optional[FiniteFloat] = Field(None, ge=0, le=1_000_000)
    inventory_warning_days: Optional[FiniteFloat] = Field(
        None, ge=0, le=60, description="Предупредить, когда запаса останется на столько дней"
    )
    is_active: bool = True
    comment: Optional[str] = Field(None, max_length=500)
    started_on: Optional[str] = Field(None, description="Начало курса, " + COURSE_FIELDS_NOTE)
    ended_on: Optional[str] = Field(None, description="Окончание курса, " + COURSE_FIELDS_NOTE)
    purpose: Optional[str] = Field(None, max_length=200, description="От чего или для чего назначен")
    prescribed_by: Optional[str] = Field(None, max_length=100, description="Кто назначил (врач, клиника)")

    @field_validator("default_dose")
    @classmethod
    def validate_default_dose(cls, v):
        return _dose_above_zero(v)

    @field_validator("started_on", "ended_on")
    @classmethod
    def validate_course_dates(cls, v):
        return _course_date(v) or None

    @model_validator(mode="after")
    def validate_course_order(self):
        if self.started_on and self.ended_on and self.ended_on < self.started_on:
            raise ValueError("Окончание курса раньше его начала")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1e88bf19b6fcdb027c75",
                "name": "Дронтал Плюс",
                "type": "Таблетка",
                "dose_unit": "таб",
                "default_dose": 1,
                "schedule": {"days": [6], "times": ["10:00"]},
                "inventory_enabled": True,
                "inventory_current": 6,
            }
        }
    )


class MedicationUpdate(BaseModel):
    # The same limits as MedicationCreate: an edit could store what a new
    # medication couldn't.
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type: Optional[str] = Field(None, max_length=50)
    form_factor: Optional[str] = Field(None, max_length=20)
    strength: Optional[str] = Field(None, max_length=50)
    dosage: Optional[str] = Field(None, max_length=50)
    unit: Optional[str] = Field(None, max_length=20)
    dose_unit: Optional[str] = Field(None, max_length=20)
    default_dose: Optional[FiniteFloat] = Field(None, le=10_000)
    schedule: Optional[MedicationSchedule] = None
    as_needed: Optional[bool] = None
    inventory_enabled: Optional[bool] = None
    inventory_total: Optional[FiniteFloat] = Field(None, ge=0, le=1_000_000)
    inventory_current: Optional[FiniteFloat] = Field(None, ge=0, le=1_000_000)
    inventory_warning_threshold: Optional[FiniteFloat] = Field(None, ge=0, le=1_000_000)
    inventory_warning_days: Optional[FiniteFloat] = Field(None, ge=0, le=60)
    is_active: Optional[bool] = None
    comment: Optional[str] = Field(None, max_length=500)
    # A date or text is cleared with an empty string (None means «not sent»).
    started_on: Optional[str] = Field(None, description="Начало курса, " + COURSE_FIELDS_NOTE)
    ended_on: Optional[str] = Field(None, description="Окончание курса, " + COURSE_FIELDS_NOTE)
    purpose: Optional[str] = Field(None, max_length=200)
    prescribed_by: Optional[str] = Field(None, max_length=100)

    @field_validator("default_dose")
    @classmethod
    def validate_default_dose(cls, v):
        return _dose_above_zero(v)

    @field_validator("started_on", "ended_on")
    @classmethod
    def validate_course_dates(cls, v):
        return _course_date(v)

    @model_validator(mode="after")
    def validate_course_order(self):
        if self.started_on and self.ended_on and self.ended_on < self.started_on:
            raise ValueError("Окончание курса раньше его начала")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Дронтал Плюс",
                "default_dose": 1,
                "dose_unit": "таб",
                "schedule": {"days": [6], "times": ["10:00"]},
            }
        }
    )


class MedicationItem(BaseModel):
    # Not «_id: str»: pydantic makes an underscore name private, and the
    # id went missing from the published schema.
    id: str = Field(alias="_id")
    pet_id: str
    name: str
    type: str
    form_factor: Optional[str] = None
    strength: Optional[str] = None
    dosage: Optional[str] = None
    unit: Optional[str] = None
    dose_unit: Optional[str] = None
    default_dose: float = 1.0
    schedule: MedicationSchedule
    # Отсутствует у курсов, созданных до этого поля: у них режим выводился из расписания.
    as_needed: bool = False
    inventory_enabled: bool
    inventory_total: Optional[float] = None
    inventory_current: Optional[float] = None
    inventory_warning_threshold: Optional[float] = None
    inventory_warning_days: Optional[float] = None
    inventory_days_left: Optional[float] = Field(None, description="На сколько дней хватит остатка по расписанию")
    inventory_low: bool = False
    is_active: bool
    comment: Optional[str] = None
    started_on: Optional[str] = None
    ended_on: Optional[str] = None
    purpose: Optional[str] = None
    prescribed_by: Optional[str] = None
    course_status: Optional[str] = Field(
        None, description="active (идёт), planned (ещё не началась), ended (закончена)"
    )
    last_taken_at: Optional[str] = None
    last_taken_by: Optional[str] = Field(None, description="Кто отметил последний приём")
    last_taken_tz: Optional[str] = Field(None, description="Часовой пояс часов, на которых отмечен последний приём")
    intakes_today: int = 0
    scheduled_today: Optional[bool] = Field(None, description="Сегодня по расписанию есть приёмы (день недели и курс)")
    open_slots_today: Optional[List[str]] = Field(
        None, description="Сегодняшние приёмы по расписанию, которые ещё ничем не закрыты, по времени"
    )
    username: Optional[str] = None
    created_at: Optional[str] = Field(None, description="Когда курс создан")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "_id": "507f1d77bcf86cd799439012",
                "name": "Дронтал Плюс",
                "type": "Таблетка",
                "as_needed": False,
                "dosage": None,
                "default_dose": 1,
                "dose_unit": "таб",
                "comment": None,
                "course_status": "active",
                "ended_on": None,
                "intakes_today": 1,
                "form_factor": "tablet",
                "inventory_enabled": True,
                "inventory_current": 12,
                "inventory_days_left": 24,
                "inventory_low": False,
            }
        }
    )


class MedicationRestock(BaseModel):
    """Add a bought pack (or any amount) to the stock."""

    amount: FiniteFloat = Field(..., gt=0, le=100000, description="Сколько добавить к остатку")
    model_config = ConfigDict(json_schema_extra={"example": {"amount": 12}})


class MedicationListResponse(BaseModel):
    medications: List[MedicationItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "medications": [
                    {
                        "_id": "507f1d77bcf86cd799439012",
                        "name": "Дронтал Плюс",
                        "type": "Таблетка",
                        "as_needed": False,
                        "dosage": None,
                        "default_dose": 1,
                        "dose_unit": "таб",
                        "comment": None,
                        "course_status": "active",
                        "ended_on": None,
                        "intakes_today": 1,
                        "form_factor": "tablet",
                        "inventory_enabled": True,
                        "inventory_current": 12,
                        "inventory_days_left": 24,
                        "inventory_low": False,
                    }
                ],
            }
        }
    )


class MedicationDetailResponse(BaseModel):
    """Wrapper for the single-medication GET response."""

    medication: MedicationItem
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "medication": {
                    "_id": "507f1d77bcf86cd799439012",
                    "name": "Дронтал Плюс",
                    "type": "Таблетка",
                    "default_dose": 1,
                    "dose_unit": "таб",
                    "schedule": {"days": [6], "times": ["10:00"]},
                    "as_needed": False,
                    "is_active": True,
                    "inventory_enabled": True,
                    "inventory_current": 12,
                }
            }
        }
    )


class MedicationIntakeCreate(BaseModel):
    date: str
    time: str
    dose_taken: Optional[FiniteFloat] = None  # Uses default_dose if not provided
    comment: Optional[str] = Field(None, max_length=500)
    # «Пропустить»: the slot is handled, nothing is given or taken from the stock.
    skipped: bool = False
    slot_date: Optional[str] = Field(
        None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="День приёма по расписанию, который закрывает эта отметка"
    )
    slot_time: Optional[str] = Field(
        None, pattern=r"^\d{2}:\d{2}$", description="Время приёма по расписанию (08:00), которое закрывает эта отметка"
    )
    force: bool = Field(
        False,
        description="Записать, даже если такой же приём уже отмечен рядом по времени (ответ 409 duplicate_intake)",
    )
    tz: Optional[str] = Field(
        None,
        max_length=64,
        description="IANA-имя часового пояса, в котором введено время (Asia/Almaty): по нему выгрузка показывает время на часах выгружающего",
    )

    @model_validator(mode="after")
    def dose_is_above_zero(self):
        # A skip takes no dose, so a number sent with one is not checked: the server writes 0 for a skip.
        if not self.skipped:
            _dose_above_zero(self.dose_taken)
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2026-10-06",
                "time": "08:43",
                "dose_taken": 2.5,
                "comment": "",
                "skipped": False,
                "slot_date": "2026-10-06",
                "slot_time": "08:00",
            }
        }
    )


class MedicationIntakeUpdate(BaseModel):
    date: str
    time: str
    tz: Optional[str] = Field(
        None,
        max_length=64,
        description="IANA-имя часового пояса, в котором введено время (Asia/Almaty): по нему выгрузка показывает время на часах выгружающего",
    )
    model_config = ConfigDict(
        json_schema_extra={"example": {"date": "2026-10-06", "time": "09:15", "tz": "Asia/Almaty"}}
    )


class MedicationIntakeItem(BaseModel):
    # Not «_id: str»: pydantic makes an underscore name private, and the
    # id went missing from the published schema.
    id: str = Field(alias="_id")
    medication_id: str
    pet_id: str
    date_time: str
    dose_taken: float
    username: str
    comment: Optional[str] = None
    skipped: bool = False
    medication_name: Optional[str] = Field(None, description="Название курса")
    tz: Optional[str] = Field(None, description="IANA-зона, в которой отмечен приём")
    slot_date: Optional[str] = Field(None, description="Дата приёма по расписанию, который закрыт этой отметкой")
    slot_time: Optional[str] = Field(None, description="Время этого приёма по расписанию")
    inventory_deducted: Optional[float] = Field(None, description="Сколько списано с остатка")
    created_at: Optional[str] = Field(None, description="Когда отметка сделана")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "pet_id": "507f1e88bf19b6fcdb027c75",
                "medication_id": "507f1d77bcf86cd799439012",
                "medication_name": "Мелоксидил",
                "date_time": "2026-10-06 08:43",
                "dose_taken": 2.5,
                "inventory_deducted": 0,
                "comment": "",
                "username": "demo",
                "tz": "Asia/Almaty",
            }
        }
    )


class MedicationIntakeListResponse(PaginatedResponse):
    intakes: List[MedicationIntakeItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "intakes": [
                    {
                        "_id": "507f1f77bcf86cd799439011",
                        "pet_id": "507f1e88bf19b6fcdb027c75",
                        "medication_id": "507f1d77bcf86cd799439012",
                        "medication_name": "Мелоксидил",
                        "date_time": "2026-10-06 08:43",
                        "dose_taken": 2.5,
                        "inventory_deducted": 0,
                        "comment": "",
                        "username": "demo",
                        "tz": "Asia/Almaty",
                    }
                ],
                "page": 1,
                "page_size": 100,
                "total": 75,
            }
        }
    )


class UpcomingDoseItem(BaseModel):
    medication_id: str
    name: str
    type: str = "pill"
    time: str
    date: str
    is_overdue: bool
    inventory_warning: bool
    carried_over: bool = Field(False, description="Приём со вчерашнего вечера, который ещё не отмечен")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "medication_id": "507f1d77bcf86cd799439012",
                "name": "Дронтал Плюс",
                "type": "Таблетка",
                "date": "2026-10-17",
                "time": "10:00",
                "carried_over": False,
                "is_overdue": False,
                "inventory_warning": True,
            }
        }
    )


class UpcomingDosesResponse(BaseModel):
    doses: List[UpcomingDoseItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "doses": [
                    {
                        "medication_id": "507f1d77bcf86cd799439012",
                        "name": "Дронтал Плюс",
                        "type": "Таблетка",
                        "date": "2026-10-17",
                        "time": "10:00",
                        "carried_over": False,
                        "is_overdue": False,
                        "inventory_warning": True,
                    }
                ]
            }
        }
    )


# ============================================================================
# Document Schemas
# ============================================================================
# `category` is a plain str in the schema (it is also the list filter), but a document can only be filed under a kind the app
# knows: one it does not draw has no section on the Documents screen and would be a file that is there and cannot be found.
DOCUMENT_CATEGORIES = ("vaccination", "lab_result", "conclusion", "imaging", "insurance", "other")


def _known_category(value):
    if value is not None and value not in DOCUMENT_CATEGORIES:
        raise ValueError("Неизвестная категория документа")
    return value


def _title_without_spaces(value):
    """A title is one line without the spaces around it; «   » is no title."""
    return " ".join(value.split()) if isinstance(value, str) else value


class DocumentCreate(PetIdQuery):
    # IANA-имя зоны, в которой документ был загружен. Без него «Добавлен <дата>»
    # считалась по зоне того, кто смотрит, и два человека видели разное время
    # одного файла. Старые документы поля не имеют: у них зоны неизвестно, и
    # для них время по-прежнему показывается по зоне смотрящего.
    tz: Optional[str] = Field(None, max_length=64, description="IANA-имя часового пояса, в котором документ загружен")
    category: str = Field(..., description="Категория документа")
    title: str = Field(..., min_length=1, max_length=100)
    note: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[str] = Field(
        None, description="Срок действия (YYYY-MM-DD) для прививок, страховки и т.п., необязателен"
    )

    @field_validator("category")
    @classmethod
    def known_category(cls, v):
        return _known_category(v)

    @field_validator("title", mode="before")
    @classmethod
    def title_without_spaces(cls, v):
        return _title_without_spaces(v)

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v):
        # Unlike birth_date, a document's own validity is legitimately in
        # the future (that's the whole point) — parse_date's allow_future
        # path hardcodes max_future_days=0, which would reject literally
        # any future date, so this goes through validate_date_logic
        # directly instead, with a generous ~10-year ceiling (long enough
        # for any real insurance/vaccination cycle, still catching a typo
        # landing centuries out).
        return validate_date_logic(v, allow_future=True, max_future_days=3650)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1e88bf19b6fcdb027c75",
                "category": "vaccination",
                "title": "Паспорт, прививки 2025",
                "expires_at": "2027-04-21",
                "tz": "Asia/Almaty",
            }
        }
    )


class ScanUploadRequest(PetIdQuery):
    """Ask for a slot to upload a scan archive straight to object storage."""

    filename: str = Field(..., min_length=1, max_length=255, description="Имя файла с расширением")
    size: int = Field(..., gt=0, description="Размер файла в байтах")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"pet_id": "507f1e88bf19b6fcdb027c75", "filename": "КТ грудной клетки.zip", "size": 184549376}
        }
    )


class ScanUploadSlot(BaseModel):
    upload_id: str
    upload_url: str = Field(..., description="Куда отправить файл методом PUT")
    content_type: str = Field(..., description="Заголовок Content-Type для PUT")
    max_bytes: int
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "upload_id": "3f9a1c0e7b2d4e6f8a9b0c1d2e3f4a5b",
                "upload_url": "https://s3.eu-central-003.backblazeb2.com/put/3f9a1c0e7b2d4e6f8a9b0c1d2e3f4a5b",
                "content_type": "application/zip",
                "max_bytes": 524288000,
            }
        }
    )


class ScanUploadComplete(BaseModel):
    """Turn an uploaded scan into a document."""

    title: str = Field(..., min_length=1, max_length=100)

    @field_validator("title", mode="before")
    @classmethod
    def title_without_spaces(cls, v):
        return _title_without_spaces(v)

    note: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[str] = Field(None, description="Срок действия (YYYY-MM-DD)")

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v):
        return validate_date_logic(v, allow_future=True, max_future_days=3650)

    model_config = ConfigDict(
        json_schema_extra={"example": {"title": "Сканы 2025", "note": "Папка целиком", "expires_at": "2027-08-29"}}
    )


class StorageStatus(BaseModel):
    scans_enabled: bool
    max_scan_bytes: int
    model_config = ConfigDict(json_schema_extra={"example": {"scans_enabled": True, "max_scan_bytes": 524288000}})


class DownloadLink(BaseModel):
    url: str = Field(..., description="Куда перейти, чтобы скачать файл")
    expires_in: Optional[int] = Field(None, description="Сколько секунд ссылка действует (для снимков)")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "/api/documents/507f1f77bcf86cd799439011/file",
                "expires_in": None,
            }
        }
    )


class DocumentUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    note: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[str] = Field(None, description="Срок действия (YYYY-MM-DD)")

    @field_validator("category")
    @classmethod
    def known_category(cls, v):
        return _known_category(v)

    @field_validator("title", mode="before")
    @classmethod
    def title_without_spaces(cls, v):
        return _title_without_spaces(v)

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v):
        return validate_date_logic(v, allow_future=True, max_future_days=3650)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"title": "Паспорт, прививки 2025", "note": "Страница с наклейками", "expires_at": "2027-08-29"}
        }
    )


class DocumentListQuery(PetIdPaginationQuery):
    category: Optional[str] = Field(None, description="Фильтр по категории (без него все)")


class DocumentRecordRef(BaseModel):
    id: str
    kind: Optional[str] = None
    title: str = ""
    date: Optional[str] = None
    diagnosis: Optional[str] = None
    clinic: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1a77bcf86cd799439013",
                "kind": "vaccination",
                "title": "Нобивак DHPPi",
                "date": "2025-08-29",
                "clinic": "Ортовет",
                "diagnosis": None,
            }
        }
    )


class DocumentItem(BaseModel):
    id: str = Field(alias="_id")
    pet_id: str
    username: str
    # Зона документа, а не зона смотрящего; у документов до этого поля её нет.
    tz: Optional[str] = None
    category: str
    title: str
    note: Optional[str] = None
    expires_at: Optional[str] = None
    original_filename: str
    content_type: str
    file_size: int
    created_at: str
    medical_record_kinds: List[str] = Field(
        default_factory=list,
        description="Виды записей медкарты (vaccination, visit...), которые ссылаются на этот документ",
    )
    record_reminds: bool = Field(
        default=False,
        description="Запись с датой повтора ссылается на документ: напоминает о сроке сама, срок документа не дублируется",
    )
    medical_records: List[DocumentRecordRef] = Field(
        default_factory=list,
        description="Записи медкарты, к которым прикреплён документ, новые первыми: откуда файл и по чему его искать",
    )
    scan: Optional[bool] = Field(None, description="Скан из хранилища (архив, DICOM): файл отдаётся редиректом 302")
    upload_id: Optional[str] = Field(None, description="Id загрузки, по которому её можно было отменить")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "pet_id": "507f1e88bf19b6fcdb027c75",
                "username": "demo",
                "tz": None,
                "category": "vaccination",
                "title": "Паспорт, прививки 2025",
                "note": "Страница с наклейками",
                "expires_at": None,
                "original_filename": "passport.pdf",
                "content_type": "application/pdf",
                "file_size": 601,
                "created_at": "2026-10-03 07:52",
                "medical_record_kinds": ["vaccination"],
                "record_reminds": True,
                "medical_records": [],
            }
        },
    )


class DocumentListResponse(PaginatedResponse):
    documents: List[DocumentItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "documents": [
                    {
                        "_id": "507f1f77bcf86cd799439011",
                        "pet_id": "507f1e88bf19b6fcdb027c75",
                        "category": "vaccination",
                        "title": "Паспорт, прививки 2025",
                        "original_filename": "passport.pdf",
                        "content_type": "application/pdf",
                        "file_size": 601,
                        "note": "Страница с наклейками",
                        "expires_at": None,
                        "record_reminds": True,
                        "medical_record_kinds": ["vaccination"],
                        "created_at": "2026-10-03 07:52",
                        "username": "demo",
                    }
                ],
                "page": 1,
                "page_size": 100,
                "total": 3,
            }
        }
    )


class DocumentDetailResponse(BaseModel):
    document: DocumentItem
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document": {
                    "_id": "507f1f77bcf86cd799439011",
                    "pet_id": "507f1e88bf19b6fcdb027c75",
                    "category": "vaccination",
                    "title": "Паспорт, прививки 2025",
                    "original_filename": "passport.pdf",
                    "content_type": "application/pdf",
                    "file_size": 601,
                    "note": "Страница с наклейками",
                    "expires_at": None,
                    "record_reminds": True,
                    "medical_record_kinds": ["vaccination"],
                    "medical_records": [
                        {
                            "id": "507f1a77bcf86cd799439013",
                            "kind": "vaccination",
                            "title": "Нобивак DHPPi",
                            "date": "2025-08-29",
                            "clinic": "Ортовет",
                            "diagnosis": None,
                        }
                    ],
                    "created_at": "2026-10-03 07:52",
                    "username": "demo",
                }
            }
        }
    )


# ============================================================================
# Push Notification Schemas
# ============================================================================


class PushSubscriptionKeys(BaseModel):
    """The two keys the browser's PushManager returns alongside an
    endpoint — required by the Web Push encryption scheme (RFC 8291)."""

    p256dh: str
    auth: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"p256dh": "base64 public key", "auth": "base64 auth secret"}}
    )


# The reminder sender later does, on a recurring schedule the subscriber
# fully controls (their own medication's days/times), an authenticated-
# looking server-side HTTP POST to whatever `endpoint` is stored here.
# Without this allowlist, `endpoint` is a self-service SSRF primitive:
# any logged-in user could subscribe an internal address (a cloud
# metadata IP, another service on the docker network) or a third
# party's server and have this app hit it on repeat, indefinitely.
# Real push services are always one of a handful of DNS names — an IP
# literal or an unrelated domain is never a legitimate subscription.
_ALLOWED_PUSH_ENDPOINT_SUFFIXES = (
    "googleapis.com",  # Chrome, Edge, Opera, other Chromium-based (FCM)
    "mozilla.com",  # Firefox
    "apple.com",  # Safari (web.push.apple.com)
    "windows.com",  # legacy Edge (WNS)
)


def _validate_push_endpoint(v: str) -> str:
    from ipaddress import ip_address
    from urllib.parse import urlparse

    parsed = urlparse(v)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Endpoint должен быть https-адресом известного push-сервиса")

    host = parsed.hostname
    try:
        ip_address(host)
        is_ip_literal = True
    except ValueError:
        is_ip_literal = False
    if is_ip_literal:
        raise ValueError("Endpoint не может быть IP-адресом")

    if not any(host == suffix or host.endswith(f".{suffix}") for suffix in _ALLOWED_PUSH_ENDPOINT_SUFFIXES):
        raise ValueError("Endpoint не относится к известному push-сервису")

    return v


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, max_length=2048, description="URL пуш-сервиса браузера")
    keys: PushSubscriptionKeys
    timezone: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="IANA-имя часового пояса (напр. Asia/Almaty): на этих часах читается время напоминаний",
    )

    _check_endpoint = field_validator("endpoint")(_validate_push_endpoint)

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, v):
        # An unknown name was stored as sent, and the reminder sender then skipped the pet without a word.
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise ValueError("Неизвестный часовой пояс")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "endpoint": "https://fcm.googleapis.com/fcm/send/abcd1234",
                "keys": {"p256dh": "base64 public key", "auth": "base64 auth secret"},
                "timezone": "Asia/Almaty",
            }
        }
    )


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=1)
    model_config = ConfigDict(
        json_schema_extra={"example": {"endpoint": "https://fcm.googleapis.com/fcm/send/abcd1234"}}
    )


class VapidPublicKeyResponse(BaseModel):
    public_key: str = Field(..., description="VAPID-ключ для PushManager.subscribe()")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"public_key": "BEAFT_kVkSueKANpSxD1htnxIIKLnnkXKvGWQ4uW5vJi_pBHFqMEQfPFMDDaLLMPU5z3W1gVoLP"}
        }
    )


# ============================================================================
# History Timeline Schemas
# ============================================================================


class TimelineQuery(PetIdPaginationQuery):
    """Query parameters for timeline with optional filtering by type."""

    type: Optional[str] = Field("all", description="Тип записи (all, feeding, asthma и т.д.)")


class TimelineItem(BaseModel):
    # Not «_id: str»: pydantic makes an underscore name private, and the
    # id went missing from the published schema.
    id: str = Field(alias="_id")
    record_type: str = Field(..., description="Тип записи (feeding, weight, asthma, и т.д.)")
    pet_id: str
    date_time: str
    username: str

    # Allows additional dynamic fields from different record types
    model_config = ConfigDict(extra="allow")


class TimelineResponse(PaginatedResponse):
    items: List[dict]  # Use dict to allow flexibility of various record types
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "_id": "507f1f77bcf86cd799439011",
                        "pet_id": "507f1e88bf19b6fcdb027c75",
                        "record_type": "medications",
                        "date_time": "2026-10-06 08:43",
                        "username": "demo",
                        "comment": "",
                        "medication_id": "507f1d77bcf86cd799439012",
                        "medication_name": "Мелоксидил",
                        "dose_taken": 2.5,
                        "dose_unit": "мл",
                        "inventory_deducted": 0,
                    }
                ],
                "page": 1,
                "page_size": 100,
                "total": 338,
            }
        }
    )


# ============================================================================
# Medical records (vaccinations, treatments, visits, procedures)
# ============================================================================

MEDICAL_KINDS = ("vaccination", "parasite", "visit", "procedure")
PARASITE_TARGETS = ("fleas_ticks", "worms", "both")
# What a vaccination is against (web/vaccines.py keeps the labels and the known vaccines).
VACCINE_PROTECTS = ("rabies", "dhpp", "lepto", "kennel", "fvrcp", "felv", "myxo_rhd")


class MedicalRecordBody(BaseModel):
    """What a record holds. Which of the optional fields matter depends on the kind;
    the ones that don't belong to it are dropped, not refused."""

    date: str = Field(..., description="Когда сделано, YYYY-MM-DD (без времени)")
    title: str = Field(
        ..., min_length=1, max_length=100, description="Вакцина, препарат, повод визита, название процедуры"
    )
    next_due: Optional[str] = Field(None, description="Когда повторить, YYYY-MM-DD; пусто, если повтор не нужен")
    clinic: Optional[str] = Field(None, max_length=100)
    vet: Optional[str] = Field(None, max_length=100)
    note: Optional[str] = Field(None, max_length=500)
    batch: Optional[str] = Field(None, max_length=50, description="Серия или лот (прививка)")
    target: Optional[str] = Field(None, description="fleas_ticks, worms или both (обработка от паразитов)")
    protects: Optional[str] = Field(
        None,
        description="От чего прививка: rabies, dhpp, lepto, kennel, fvrcp, felv или myxo_rhd. Смена марки с той же защитой заменяет прежнюю запись",
    )
    complaint: Optional[str] = Field(None, max_length=500, description="С чем пришли на приём (визит)")
    diagnosis: Optional[str] = Field(None, max_length=300, description="Диагноз (визит)")
    recommendations: Optional[str] = Field(None, max_length=500, description="Рекомендации врача (визит)")
    document_ids: List[ObjectIdString] = Field(
        default_factory=list, max_length=10, description="Документы этого питомца"
    )

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator(
        "clinic",
        "vet",
        "note",
        "batch",
        "complaint",
        "diagnosis",
        "recommendations",
        "target",
        "protects",
        "next_due",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)

    @field_validator("date")
    @classmethod
    def validate_record_date(cls, v):
        return validate_date_logic(v, allow_future=True, max_future_days=1)

    @field_validator("next_due")
    @classmethod
    def validate_next_due(cls, v):
        return validate_date_logic(v, allow_future=True, max_future_days=3650) if v else v

    @field_validator("target")
    @classmethod
    def validate_target(cls, v):
        if v is not None and v not in PARASITE_TARGETS:
            raise ValueError("Укажите: от блох и клещей, от глистов или от всего")
        return v

    @field_validator("protects")
    @classmethod
    def validate_protects(cls, v):
        if v is not None and v not in VACCINE_PROTECTS:
            raise ValueError("Неизвестная защита: выберите из списка")
        return v

    @model_validator(mode="after")
    def next_after_date(self):
        if self.next_due and self.next_due < self.date:
            raise ValueError("Дата повтора раньше даты записи")
        return self


class MedicalRecordCreate(MedicalRecordBody, PetIdQuery):
    kind: str = Field(..., description="vaccination, parasite, visit или procedure")

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v):
        if v not in MEDICAL_KINDS:
            raise ValueError("Неизвестный вид записи")
        return v

    @model_validator(mode="after")
    def kind_fields(self):
        # What the kind doesn't have is not kept; a treatment needs to say against what.
        if self.kind != "vaccination":
            self.batch = None
            self.protects = None
        if self.kind != "visit":
            self.complaint = self.diagnosis = self.recommendations = None
        if self.kind == "parasite":
            if not self.target:
                raise ValueError("Укажите, от чего обработка")
        else:
            self.target = None
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1e88bf19b6fcdb027c75",
                "kind": "vaccination",
                "date": "2026-08-29",
                "title": "Нобивак DHPPi",
                "protects": "dhpp",
                "next_due": "2027-08-29",
                "clinic": "Ветклиника «Айболит»",
                "batch": "A123B",
            }
        }
    )


class MedicalRecordUpdate(MedicalRecordBody):
    """The whole record again: its pet and kind stay as they were."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"date": "2026-09-23", "title": "Плановый осмотр", "diagnosis": "Без патологии"}}
    )


class MedicalRecordDocument(BaseModel):
    id: str
    title: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"id": "507f1b77bcf86cd799439014", "title": "Анализ крови"}}
    )


class MedicalRecordItem(BaseModel):
    id: str = Field(alias="_id")
    pet_id: str
    kind: str
    date: str
    title: str
    next_due: Optional[str] = None
    status: str = Field(
        "none", description="overdue (просрочено), soon (скоро), ok, none (повтор не нужен или заменена)"
    )
    days_left: Optional[int] = Field(None, description="Дней до повтора; отрицательное, если просрочен")
    superseded: bool = Field(
        False,
        description="Есть более новая прививка или обработка от того же (та же защита, та же цель, иначе то же название): эта осталась историей",
    )
    clinic: Optional[str] = None
    vet: Optional[str] = None
    note: Optional[str] = None
    batch: Optional[str] = None
    target: Optional[str] = None
    protects: Optional[str] = Field(
        None, description="От чего прививка (ключ); для старых записей определяется по названию"
    )
    protects_label: Optional[str] = Field(None, description="То же словами")
    complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    recommendations: Optional[str] = None
    documents: List[MedicalRecordDocument] = Field(default_factory=list)

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1a77bcf86cd799439013",
                "pet_id": "507f1e88bf19b6fcdb027c75",
                "kind": "visit",
                "date": "2026-09-23",
                "title": "Плановый осмотр",
                "next_due": None,
                "status": "none",
                "days_left": None,
                "clinic": "Ортовет",
                "diagnosis": "Без патологии",
                "documents": [{"id": "507f1b77bcf86cd799439014", "title": "Анализ крови"}],
            }
        },
    )


class MedicalRecordListQuery(PetIdQuery):
    kind: Optional[str] = Field(
        None,
        description="Только этого вида: vaccination, parasite, visit или procedure (другое: 422 `validation_error`)",
    )
    tz: Optional[str] = Field(
        None, max_length=64, description="IANA-имя часового пояса пользователя: по нему считается «сегодня»"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"pet_id": "507f1e88bf19b6fcdb027c75", "kind": "vaccination", "tz": "Asia/Almaty"}
        }
    )


class MedicalRecordResponse(BaseModel):
    record: MedicalRecordItem
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "record": {
                    "_id": "507f1a77bcf86cd799439013",
                    "pet_id": "507f1e88bf19b6fcdb027c75",
                    "kind": "visit",
                    "date": "2026-09-23",
                    "title": "Плановый осмотр",
                    "next_due": None,
                    "status": "none",
                    "days_left": None,
                    "clinic": "Ортовет",
                    "vet": None,
                    "complaint": "Чаще пьёт воду",
                    "diagnosis": "Без патологии",
                    "recommendations": "Повторить анализы через три месяца",
                    "note": None,
                    "batch": None,
                    "protects": None,
                    "protects_label": None,
                    "documents": [{"id": "507f1b77bcf86cd799439014", "title": "Анализ крови"}],
                }
            }
        }
    )


class MedicalRecordListResponse(BaseModel):
    records: List[MedicalRecordItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "records": [
                    {
                        "_id": "507f1a77bcf86cd799439013",
                        "pet_id": "507f1e88bf19b6fcdb027c75",
                        "kind": "visit",
                        "date": "2026-09-23",
                        "title": "Плановый осмотр",
                        "next_due": None,
                        "status": "none",
                        "days_left": None,
                        "clinic": "Ортовет",
                        "diagnosis": "Без патологии",
                        "documents": [{"id": "507f1b77bcf86cd799439014", "title": "Анализ крови"}],
                    }
                ]
            }
        }
    )


# ============================================================================
# Medical card
# ============================================================================


class MedicalCardQuery(BaseModel):
    """Query of the medical card: the user's zone, for «today»."""

    tz: Optional[str] = Field(
        None,
        max_length=64,
        description="IANA-имя часового пояса пользователя: по нему считается «сегодня» (сроки прививок, дата формирования)",
    )


VISIT_CHECKS = ("appetite", "thirst", "stool", "urine", "vomiting", "cough", "activity")


class VisitPrep(BaseModel):
    """PUT /api/pets/<id>/visit-prep: what to tell the vet at the next appointment. Empty clears it."""

    # The version the form was opened from: two phones editing the note used to leave
    # whoever pressed last as the only truth, silently. A stale version answers 409 and
    # brings the other person's text along, as the vet profile's base_version does.
    base_version: Optional[str] = Field(
        None,
        max_length=64,
        description="Версия заметки, из которой открыта форма. Если с тех пор её сохранил кто-то другой, ответ 409",
    )
    complaint: Optional[str] = Field(None, max_length=500, description="Что беспокоит")
    checks: Dict[str, str] = Field(
        default_factory=dict,
        description="Аппетит, жажда, стул, моча, рвота, кашель, активность: normal (как обычно) или changed (изменилось)",
    )

    @field_validator("complaint", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)

    @field_validator("checks")
    @classmethod
    def known_checks(cls, v):
        for key, value in v.items():
            if key not in VISIT_CHECKS:
                raise ValueError(f"Неизвестная отметка: {key}")
            if value not in ("normal", "changed"):
                raise ValueError("Отметка: normal или changed")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "base_version": "9b1c2e7f4a3d48e6b0c5d1f2a7e9c3b8",
                "complaint": "Чаще пьёт воду",
                "checks": {"appetite": "normal", "thirst": "changed", "stool": "normal"},
            }
        }
    )


class VisitPrepOut(VisitPrep):
    updated_at: Optional[str] = None
    version: str = ""
    base_version: Optional[str] = Field(None, description="Только для запроса; в ответе его нет или null")


class VisitPrepResponse(BaseModel):
    visit_prep: Optional[VisitPrepOut] = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "visit_prep": {
                    "complaint": "Чаще пьёт воду",
                    "checks": {"appetite": "normal", "thirst": "changed"},
                    "updated_at": "2026-09-23 18:04",
                    "version": "9b1c2e7f4a3d48e6b0c5d1f2a7e9c3b8",
                }
            }
        }
    )


class MedicalCardPet(BaseModel):
    name: str
    species: Optional[str] = Field(None, description="Вид словами: «Собака», «Кот»")
    breed: Optional[str] = None
    birth_date: Optional[str] = None
    age_text: Optional[str] = Field(None, description="Возраст словами: «5 лет», «8 месяцев»")
    gender: Optional[str] = Field(None, description="Пол словами: «Мальчик», «Девочка»")
    neutered_text: Optional[str] = Field(None, description="«кастрирован», «не стерилизована»; нет, если не указано")
    health_notes: Optional[str] = Field(None, description="Особенности здоровья и аллергии, текстом")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Рекс",
                "species": "Собака",
                "breed": "Лабрадор",
                "birth_date": "2021-08-01",
                "age_text": "5 лет",
                "gender": "Мальчик",
                "neutered_text": "кастрирован",
                "health_notes": None,
            }
        }
    )


class MedicalCardWeightPoint(BaseModel):
    date: str
    value: float
    model_config = ConfigDict(json_schema_extra={"example": {"date": "2026-10-01", "value": 29.0}})


class MedicalCardWeight(BaseModel):
    latest: MedicalCardWeightPoint
    series: List[MedicalCardWeightPoint] = Field(description="Последние замеры, от старых к новым")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "latest": {"date": "2026-10-04", "value": 29.3},
                "series": [
                    {"date": "2026-09-19", "value": 29.0},
                    {"date": "2026-10-03", "value": 29.1},
                    {"date": "2026-10-04", "value": 29.3},
                ],
            }
        }
    )


class MedicalCardMedication(BaseModel):
    id: str
    name: str
    type: Optional[str] = None
    strength: Optional[str] = None
    dose_text: Optional[str] = Field(None, description="Разовая доза: «1 таб», «0,5 мл»")
    schedule_text: str = Field(description="«Ежедневно в 08:00, 20:00» или «По пн, ср в 10:00»")
    comment: Optional[str] = None
    purpose: Optional[str] = Field(None, description="От чего или для чего назначен")
    prescribed_by: Optional[str] = None
    status: str = Field("active", description="active (идёт), planned (ещё не началась), ended (закончена)")
    started_on: Optional[str] = Field(None, description="Начало курса; у старых курсов выводится из приёмов")
    ended_on: Optional[str] = Field(None, description="Окончание курса; у старых выводится из последнего приёма")
    given: int = Field(0, description="Дано доз")
    skipped: int = Field(0, description="Пропущено доз")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1d77bcf86cd799439012",
                "name": "Дронтал Плюс",
                "type": "Таблетка",
                "strength": None,
                "comment": None,
                "dose_text": "1 таб",
                "schedule_text": "По сб в 10:00",
                "started_on": "2026-08-08",
                "ended_on": None,
                "given": 9,
                "skipped": 0,
                "purpose": "Профилактика глистов",
                "prescribed_by": "Каримов Д.",
                "status": "active",
            }
        }
    )


class MedicalCardVaccination(BaseModel):
    """A vaccination certificate kept only as a document, not yet made a record."""

    id: str
    title: str
    expires_at: Optional[str] = None
    status: str = Field(description="none (срок не указан), valid, soon (скоро истекает), expired")
    days_left: Optional[int] = Field(None, description="Дней до окончания; отрицательное, если истёк")
    note: Optional[str] = None
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439031",
                "title": "Паспорт, прививки 2025",
                "expires_at": "2027-04-21",
                "status": "valid",
                "days_left": 190,
                "note": None,
            }
        }
    )


class MedicalCardDocument(BaseModel):
    id: str
    title: str
    category: str
    added: str = Field(description="Дата добавления, YYYY-MM-DD")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1b77bcf86cd799439014",
                "title": "Анализ крови",
                "category": "lab_result",
                "added": "2026-09-23",
            }
        }
    )


class MedicalProfileResponse(BaseModel):
    profile: MedicalProfileOut
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "profile": {
                    "allergies": [],
                    "allergies_none_known": False,
                    "blood_type": "DEA 1.1+",
                    "chip_number": "643094100200311",
                    "clinic": {"name": "Ортовет", "phone": "+7 727 555 03 04", "vet": "Каримов Д."},
                    "clinics": [
                        {
                            "doctors": [{"name": "Каримов Д.", "specialty": "хирург-ортопед"}],
                            "name": "Ортовет",
                            "phone": "+7 727 555 03 04",
                        }
                    ],
                    "conditions": [
                        {
                            "name": "Дисплазия тазобедренных суставов",
                            "note": "обострения после нагрузки",
                            "since_year": 2023,
                        }
                    ],
                    "diet": "Сухой корм для крупных пород, два раза в день",
                    "living": "Квартира, гуляет два раза в день",
                    "reproduction": None,
                    "updated_at": "2026-10-05 11:51",
                    "version": "9b1c2e7f4a3d48e6b0c5d1f2a7e9c3b8",
                }
            }
        }
    )


class MedicalCardData(BaseModel):
    pet: MedicalCardPet
    visit_prep: Optional[VisitPrepOut] = Field(
        None, description="Что сказать врачу на ближайшем приёме; нет, если не заполнено"
    )
    profile: MedicalProfileOut = Field(description="Аллергии, хронические состояния, чип, группа крови, клиника")
    weight: Optional[MedicalCardWeight] = None
    records: Dict[str, List[MedicalRecordItem]] = Field(
        description="По видам (vaccination, parasite, visit, procedure), новые сверху, не больше десяти"
    )
    record_counts: Dict[str, int] = Field(description="Сколько записей каждого вида всего")
    overdue_records: List[MedicalRecordItem] = Field(
        default_factory=list,
        description="Все просроченные прививки и обработки, без «не больше десяти»: полоса и точка говорят об одном",
    )
    medications: List[MedicalCardMedication] = Field(description="Курсы, которые идут сейчас или ещё начнутся")
    past_courses: List[MedicalCardMedication] = Field(
        description="Законченные курсы, последние сверху, не больше десяти"
    )
    past_courses_total: int = Field(description="Сколько законченных курсов всего")
    vaccinations: List[MedicalCardVaccination]
    documents: List[MedicalCardDocument]
    generated_at: str = Field(description="Дата формирования, YYYY-MM-DD, по часовому поясу пользователя")
    # Правку медицинского профиля может любой, у кого есть доступ к питомцу: это общее знание семьи
    # о животном, а не настройка владельца (см. put_medical_profile). Описание здесь прежде говорило
    # обратное, и поле нигде не читалось.
    can_edit: bool = Field(
        description="Владелец ли это: ссылку для врача делает только владелец, приложение по этому флагу показывает её кнопку. Править анкету может любой с доступом"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet": {
                    "name": "Рекс",
                    "species": "Собака",
                    "breed": "Лабрадор",
                    "birth_date": "2021-08-01",
                    "age_text": "5 лет",
                    "gender": "Мальчик",
                    "neutered_text": "кастрирован",
                    "health_notes": None,
                },
                "visit_prep": None,
                "profile": {
                    "allergies": [],
                    "allergies_none_known": False,
                    "base_version": None,
                    "blood_type": "DEA 1.1+",
                    "chip_number": "643094100200311",
                    "clinic": {"name": "Ортовет", "phone": "+7 727 555 03 04", "vet": "Каримов Д."},
                    "clinics": [
                        {
                            "doctors": [{"name": "Каримов Д.", "specialty": "хирург-ортопед"}],
                            "name": "Ортовет",
                            "phone": "+7 727 555 03 04",
                        }
                    ],
                    "conditions": [
                        {
                            "name": "Дисплазия тазобедренных суставов",
                            "note": "обострения после нагрузки",
                            "since_year": 2023,
                        }
                    ],
                    "diet": "Сухой корм для крупных пород, два раза в день",
                    "living": "Квартира, гуляет два раза в день",
                    "reproduction": None,
                    "updated_at": "2026-10-05 11:51",
                    "version": "9b1c2e7f4a3d48e6b0c5d1f2a7e9c3b8",
                },
                "weight": {
                    "latest": {"date": "2026-10-04", "value": 29.3},
                    "series": [
                        {"date": "2026-09-19", "value": 29.0},
                        {"date": "2026-10-03", "value": 29.1},
                        {"date": "2026-10-04", "value": 29.3},
                    ],
                },
                "records": {
                    "vaccination": [],
                    "parasite": [
                        {
                            "_id": "507f1f77bcf86cd799439041",
                            "batch": None,
                            "clinic": None,
                            "complaint": None,
                            "date": "2026-09-08",
                            "days_left": 55,
                            "diagnosis": None,
                            "documents": [],
                            "kind": "parasite",
                            "next_due": "2026-12-07",
                            "note": None,
                            "pet_id": "507f1e88bf19b6fcdb027c75",
                            "protects": None,
                            "protects_label": None,
                            "recommendations": None,
                            "status": "ok",
                            "superseded": False,
                            "target": "worms",
                            "title": "Дронтал Плюс",
                            "vet": None,
                        }
                    ],
                    "visit": [],
                    "procedure": [],
                },
                "record_counts": {"vaccination": 0, "parasite": 1, "visit": 0, "procedure": 0},
                "overdue_records": [],
                "medications": [],
                "past_courses": [],
                "past_courses_total": 0,
                "vaccinations": [
                    {
                        "id": "507f1f77bcf86cd799439031",
                        "title": "Паспорт, прививки 2025",
                        "expires_at": "2027-04-21",
                        "status": "valid",
                        "days_left": 190,
                        "note": None,
                    }
                ],
                "documents": [],
                "generated_at": "2026-10-13",
                "can_edit": True,
            }
        }
    )


class MedicalCardResponse(BaseModel):
    card: MedicalCardData
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "card": {
                    "pet": {
                        "name": "Рекс",
                        "species": "Собака",
                        "breed": "Лабрадор",
                        "birth_date": "2021-08-01",
                        "age_text": "5 лет",
                        "gender": "Мальчик",
                        "neutered_text": "кастрирован",
                        "health_notes": None,
                    },
                    "visit_prep": None,
                    "profile": {
                        "allergies": [],
                        "allergies_none_known": False,
                        "base_version": None,
                        "blood_type": "DEA 1.1+",
                        "chip_number": "643094100200311",
                        "clinic": {"name": "Ортовет", "phone": "+7 727 555 03 04", "vet": "Каримов Д."},
                        "clinics": [
                            {
                                "doctors": [{"name": "Каримов Д.", "specialty": "хирург-ортопед"}],
                                "name": "Ортовет",
                                "phone": "+7 727 555 03 04",
                            }
                        ],
                        "conditions": [
                            {
                                "name": "Дисплазия тазобедренных суставов",
                                "note": "обострения после нагрузки",
                                "since_year": 2023,
                            }
                        ],
                        "diet": "Сухой корм для крупных пород, два раза в день",
                        "living": "Квартира, гуляет два раза в день",
                        "reproduction": None,
                        "updated_at": "2026-10-05 11:51",
                        "version": "9b1c2e7f4a3d48e6b0c5d1f2a7e9c3b8",
                    },
                    "weight": {
                        "latest": {"date": "2026-10-04", "value": 29.3},
                        "series": [
                            {"date": "2026-09-19", "value": 29.0},
                            {"date": "2026-10-03", "value": 29.1},
                            {"date": "2026-10-04", "value": 29.3},
                        ],
                    },
                    "records": {
                        "vaccination": [],
                        "parasite": [
                            {
                                "_id": "507f1f77bcf86cd799439041",
                                "batch": None,
                                "clinic": None,
                                "complaint": None,
                                "date": "2026-09-08",
                                "days_left": 55,
                                "diagnosis": None,
                                "documents": [],
                                "kind": "parasite",
                                "next_due": "2026-12-07",
                                "note": None,
                                "pet_id": "507f1e88bf19b6fcdb027c75",
                                "protects": None,
                                "protects_label": None,
                                "recommendations": None,
                                "status": "ok",
                                "superseded": False,
                                "target": "worms",
                                "title": "Дронтал Плюс",
                                "vet": None,
                            }
                        ],
                        "visit": [],
                        "procedure": [],
                    },
                    "record_counts": {"vaccination": 0, "parasite": 1, "visit": 0, "procedure": 0},
                    "overdue_records": [],
                    "medications": [],
                    "past_courses": [],
                    "past_courses_total": 0,
                    "vaccinations": [
                        {
                            "id": "507f1f77bcf86cd799439031",
                            "title": "Паспорт, прививки 2025",
                            "expires_at": "2027-04-21",
                            "status": "valid",
                            "days_left": 190,
                            "note": None,
                        }
                    ],
                    "documents": [],
                    "generated_at": "2026-10-13",
                    "can_edit": True,
                }
            }
        }
    )


class MedicalAlerts(BaseModel):
    """What is overdue on the card, without the card: one cheap read for the dot on the «Медкарта» tab."""

    vaccination: bool = Field(description="Есть просроченная прививка: запись со сроком или справка с истёкшим сроком")
    parasite: bool = Field(description="Есть просроченная обработка от паразитов")
    medication: bool = Field(
        False, description="Есть приём лекарства по расписанию, который не отмечен больше часа после времени"
    )
    model_config = ConfigDict(
        json_schema_extra={"example": {"vaccination": True, "parasite": True, "medication": False}}
    )


class MedicalAlertsResponse(BaseModel):
    alerts: MedicalAlerts
    model_config = ConfigDict(
        json_schema_extra={"example": {"alerts": {"vaccination": True, "parasite": True, "medication": False}}}
    )


class MedicalShareCreate(BaseModel):
    """A link to the card for a vet: how long it works."""

    days: Literal[1, 7, 30] = Field(7, description="Сколько дней ссылка открывает карту: 1, 7 или 30")
    model_config = ConfigDict(json_schema_extra={"example": {"days": 7}})


class MedicalShareItem(BaseModel):
    id: str = Field(description="Идентификатор ссылки: по нему её отзывают")
    username: str = Field(description="Кто создал ссылку; пусто, если его аккаунт удалён")
    created_at: str = Field(description="Когда создана, UTC, ISO 8601")
    expires_at: str = Field(description="До какого момента работает, UTC, ISO 8601")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439051",
                "username": "demo",
                "created_at": "2026-10-03T07:52:00.123456Z",
                "expires_at": "2026-10-10T07:52:00.123456Z",
            }
        }
    )


class MedicalShareCreated(BaseModel):
    share: MedicalShareItem
    token: str = Field(description="Секрет ссылки. Показывается один раз: на сервере хранится только его хэш")
    path: str = Field(description="Путь страницы для врача на сайте: /share/medical/<token>")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "share": {
                    "id": "507f1f77bcf86cd799439051",
                    "username": "demo",
                    "created_at": "2026-10-03T07:52:00.123456Z",
                    "expires_at": "2026-10-10T07:52:00.123456Z",
                },
                "token": "kq3W9xP2...",
                "path": "/share/medical/kq3W9xP2...",
            }
        }
    )


class MedicalSharesResponse(BaseModel):
    shares: List[MedicalShareItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "shares": [
                    {
                        "id": "507f1f77bcf86cd799439051",
                        "username": "demo",
                        "created_at": "2026-10-03T07:52:00.123456Z",
                        "expires_at": "2026-10-10T07:52:00.123456Z",
                    }
                ]
            }
        }
    )


class MedicalShareRevoked(BaseModel):
    revoked: bool
    model_config = ConfigDict(json_schema_extra={"example": {"revoked": True}})


# ============================================================================
# Personal access tokens (web/personal_tokens.py)
# ============================================================================


class PersonalTokenCreate(BaseModel):
    """A personal access token: the name to know it by, what it may do, how long it works."""

    name: str = Field(..., min_length=1, max_length=60, description="Название, по которому доступ узнают в списке")
    scopes: List[str] = Field(
        ...,
        description="Области доступа, хотя бы одна: pets:read (питомцы), events:write (записи), "
        "history:read (лента и история), medical:read (медкарта)",
    )
    expires_in_days: Annotated[int, BeforeValidator(_not_a_flag)] = Field(
        90, description="Срок в днях: от 1 до 365, по умолчанию 90"
    )

    @field_validator("name")
    @classmethod
    def name_one_line(cls, v):
        return _trimmed_name(v)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"name": "Ассистент для врача", "scopes": ["pets:read", "medical:read"], "expires_in_days": 90}
        }
    )


class PersonalTokenItem(BaseModel):
    """A personal access token as the list shows it: never its secret."""

    id: str = Field(description="Идентификатор доступа: по нему его отзывают")
    name: str = Field(description="Название")
    scopes: List[str] = Field(description="Области доступа")
    prefix: str = Field(description="Первые 8 знаков токена: по ним доступ узнают в списке")
    created_at: str = Field(description="Когда создан, UTC, ISO 8601")
    expires_at: str = Field(description="До какого момента работает, UTC, ISO 8601")
    last_used_at: Optional[str] = Field(
        None, description="Когда в последний раз пускал запрос, UTC; пусто, если ещё нет"
    )
    revoked_at: Optional[str] = Field(None, description="Когда отозван, UTC; пусто, если не отозван")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439061",
                "name": "Ассистент для врача",
                "scopes": ["pets:read", "medical:read"],
                "prefix": "ptz_Ab3d",
                "created_at": "2026-10-03T07:52:00.123456Z",
                "expires_at": "2027-01-01T07:52:00.123456Z",
                "last_used_at": "2026-10-04T09:15:00.000000Z",
                "revoked_at": None,
            }
        }
    )


class PersonalTokenCreated(BaseModel):
    """The new token: its secret is in this answer only."""

    id: str = Field(description="Идентификатор доступа: по нему его отзывают")
    name: str = Field(description="Название")
    scopes: List[str] = Field(description="Области доступа")
    expires_at: str = Field(description="До какого момента работает, UTC, ISO 8601")
    prefix: str = Field(description="Первые 8 знаков токена")
    token: str = Field(description="Полный токен `ptz_...`. Показывается один раз: на сервере хранится только его хэш")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "507f1f77bcf86cd799439061",
                "name": "Ассистент для врача",
                "scopes": ["pets:read", "medical:read"],
                "expires_at": "2027-01-01T07:52:00.123456Z",
                "prefix": "ptz_Ab3d",
                "token": "ptz_Ab3dK9qV2mRx7sT1uWvY4zN8pLcE5hJ6gQ0fA2bC3dE",
            }
        }
    )


class PersonalTokenList(BaseModel):
    tokens: List[PersonalTokenItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tokens": [
                    {
                        "id": "507f1f77bcf86cd799439061",
                        "name": "Ассистент для врача",
                        "scopes": ["pets:read", "medical:read"],
                        "prefix": "ptz_Ab3d",
                        "created_at": "2026-10-03T07:52:00.123456Z",
                        "expires_at": "2027-01-01T07:52:00.123456Z",
                        "last_used_at": None,
                        "revoked_at": None,
                    }
                ]
            }
        }
    )


class PersonalTokenRevoked(BaseModel):
    """What a DELETE on a personal access token answered: revoked, and whether its record is gone now."""

    revoked: bool = Field(description="Доступ отозван: теперь или раньше")
    deleted: bool = Field(
        False, description="Запись удалена из базы: так отвечает повторный вызов по уже отозванному доступу"
    )
    model_config = ConfigDict(json_schema_extra={"example": {"revoked": True, "deleted": False}})


class SharedMedicalCardResponse(BaseModel):
    """What a vet sees by the link: the card, read-only, and when the link ends."""

    card: MedicalCardData
    expires_at: str
    # Whose card this is, and only for the person who owns it or has access: with it the page offers a way back to the
    # app, without it the link stays a copy. Without a session this is null, so a vet opening the link learns nothing
    # about who they got it from.
    pet_id: Optional[str] = Field(None, description="Питомец этой карты, если у открывшего есть сессия и доступ")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "card": {
                    "pet": {
                        "name": "Рекс",
                        "species": "Собака",
                        "breed": "Лабрадор",
                        "birth_date": "2021-08-01",
                        "age_text": "5 лет",
                        "gender": "Мальчик",
                        "neutered_text": "кастрирован",
                        "health_notes": None,
                    },
                    "visit_prep": None,
                    "profile": {
                        "allergies": [],
                        "allergies_none_known": False,
                        "base_version": None,
                        "blood_type": "DEA 1.1+",
                        "chip_number": "643094100200311",
                        "clinic": {"name": "Ортовет", "phone": "+7 727 555 03 04", "vet": "Каримов Д."},
                        "clinics": [
                            {
                                "doctors": [{"name": "Каримов Д.", "specialty": "хирург-ортопед"}],
                                "name": "Ортовет",
                                "phone": "+7 727 555 03 04",
                            }
                        ],
                        "conditions": [
                            {
                                "name": "Дисплазия тазобедренных суставов",
                                "note": "обострения после нагрузки",
                                "since_year": 2023,
                            }
                        ],
                        "diet": "Сухой корм для крупных пород, два раза в день",
                        "living": "Квартира, гуляет два раза в день",
                        "reproduction": None,
                        "updated_at": "2026-10-05 11:51",
                        "version": "9b1c2e7f4a3d48e6b0c5d1f2a7e9c3b8",
                    },
                    "weight": {
                        "latest": {"date": "2026-10-04", "value": 29.3},
                        "series": [
                            {"date": "2026-09-19", "value": 29.0},
                            {"date": "2026-10-03", "value": 29.1},
                            {"date": "2026-10-04", "value": 29.3},
                        ],
                    },
                    "records": {
                        "vaccination": [],
                        "parasite": [
                            {
                                "_id": "507f1f77bcf86cd799439041",
                                "batch": None,
                                "clinic": None,
                                "complaint": None,
                                "date": "2026-09-08",
                                "days_left": 55,
                                "diagnosis": None,
                                "documents": [],
                                "kind": "parasite",
                                "next_due": "2026-12-07",
                                "note": None,
                                "pet_id": "507f1e88bf19b6fcdb027c75",
                                "protects": None,
                                "protects_label": None,
                                "recommendations": None,
                                "status": "ok",
                                "superseded": False,
                                "target": "worms",
                                "title": "Дронтал Плюс",
                                "vet": None,
                            }
                        ],
                        "visit": [],
                        "procedure": [],
                    },
                    "record_counts": {"vaccination": 0, "parasite": 1, "visit": 0, "procedure": 0},
                    "overdue_records": [],
                    "medications": [],
                    "past_courses": [],
                    "past_courses_total": 0,
                    "vaccinations": [
                        {
                            "id": "507f1f77bcf86cd799439031",
                            "title": "Паспорт, прививки 2025",
                            "expires_at": "2027-04-21",
                            "status": "valid",
                            "days_left": 190,
                            "note": None,
                        }
                    ],
                    "documents": [],
                    "generated_at": "2026-10-13",
                    "can_edit": True,
                },
                "expires_at": "2026-10-18T07:52:00.123456Z",
            }
        }
    )


class VaccineGroupItem(BaseModel):
    key: str
    label: str
    detail: str = Field("", description="Что входит, если название не говорит само")
    species: List[str]
    model_config = ConfigDict(
        json_schema_extra={"example": {"key": "rabies", "label": "Бешенство", "species": ["dog", "cat"], "detail": ""}}
    )


class VaccineProductItem(BaseModel):
    name: str
    species: List[str]
    protects: str
    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Нобивак Rabies", "protects": "rabies", "species": ["dog", "cat"]}}
    )


class VaccineCatalogResponse(BaseModel):
    groups: List[VaccineGroupItem]
    products: List[VaccineProductItem]
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "groups": [{"key": "rabies", "label": "Бешенство", "species": ["dog", "cat"], "detail": ""}],
                "products": [{"name": "Нобивак Rabies", "protects": "rabies", "species": ["dog", "cat"]}],
            }
        }
    )
