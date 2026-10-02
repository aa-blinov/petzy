"""Pydantic schemas for request/response validation and OpenAPI documentation.

Naming Convention:
- All JSON fields use snake_case (e.g., pet_id, date_time, food_weight, eye_drops, tooth_brushing)
- See docs/api-naming-conventions.md for full naming rules
"""

from datetime import datetime, timedelta
from typing import Optional, List, Annotated, Any, Dict
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, StringConstraints

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
    if not allow_future and dt.date() > now.date():
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


class PasswordResetRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=1, max_length=256)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=256)
    new_password: str = Field(..., min_length=1, max_length=256)


class AccountDeleteRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=256, description="Текущий пароль")


class DeletionPet(BaseModel):
    id: str
    name: str
    new_owner: Optional[str] = Field(None, description="Кому перейдёт питомец (в transferred)")
    owner: Optional[str] = Field(None, description="Чей это питомец (в left)")


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


class EmailChangeRequest(BaseModel):
    """An empty email removes it."""

    email: str = Field(..., max_length=254)
    password: str = Field(..., min_length=1, max_length=256, description="Текущий пароль")


class EmailVerifyRequest(BaseModel):
    token: str = Field(..., min_length=1, max_length=200)


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


class PrivacyConsentRequest(BaseModel):
    version: str = Field(..., max_length=32, description="policy_version из GET /api/legal")


class LegalInfoResponse(BaseModel):
    """Facts the privacy policy page fills in; empty until the operator sets them."""

    policy_version: str
    operator: str = Field("", description="Кто обрабатывает данные")
    contact_email: str = Field("", description="Куда писать о персональных данных")
    server_location: str = Field("", description="Страна, где стоит сервер с базой данных")
    backups_kept_days: int = Field(..., description="Сколько дней живут резервные копии")


class RegistrationStatusResponse(BaseModel):
    open: bool
    mail_enabled: bool = False


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
                "message": "Login successful",
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            }
        }
    )


class AuthRefreshResponse(BaseModel):
    """Access token refresh response."""

    success: bool = True
    access_token: str
    refresh_token: Optional[str] = Field(
        None,
        description="Новый refresh-токен (только нативному клиенту). Старый после этого работает ещё 30 секунд",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
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
    is a string comparison, so no collection is touched.
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


class FormDefaults(BaseModel):
    """What a new record's form starts with, per type: {"defecation": {"food": "…"}}.

    Stored on the account so every device of the user shares it (it used
    to be in each browser's localStorage)."""

    form_defaults: Dict[str, Dict[str, str]] = Field(default_factory=dict)

    @field_validator("form_defaults")
    @classmethod
    def _bounded(cls, value: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        if len(value) > 50 or any(len(fields) > 30 for fields in value.values()):
            raise ValueError("Слишком много значений по умолчанию")
        for form, fields in value.items():
            if len(form) > 50 or any(len(k) > 50 or len(v) > 300 for k, v in fields.items()):
                raise ValueError("Слишком длинное значение по умолчанию")
        return value


class UserSearchResponse(BaseModel):
    """List of usernames for autocomplete."""

    users: List[UserSearchItem]


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


class UserListResponse(BaseModel):
    """List of users response."""

    users: List[UserResponse]


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


class UserPublicProfile(BaseModel):
    """The subset of a user's profile visible to a co-owner they share a
    pet with — not the full admin UserResponse (no email, no is_active)."""

    username: str
    full_name: Optional[str] = None
    created_at: str
    shared_pets: List[str] = Field(default_factory=list, description="Имена питомцев, доступных обоим")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "user2",
                "full_name": "Мария Петрова",
                "created_at": "2024-01-15 14:30",
                "shared_pets": ["Рекс"],
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


class Clinic(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="Клиника")
    vet: Optional[str] = Field(None, max_length=100, description="Врач")
    phone: Optional[str] = Field(None, max_length=30, description="Телефон")

    @field_validator("name", "vet", "phone", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)


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


class ClinicEntry(BaseModel):
    """One clinic the pet is taken to, with the doctors seen there."""

    name: Optional[str] = Field(None, max_length=100, description="Название клиники")
    phone: Optional[str] = Field(None, max_length=30, description="Телефон")
    doctors: List[Doctor] = Field(default_factory=list, max_length=10)

    @field_validator("name", "phone", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        return _blank_to_none(v)


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


class MedicalProfileOut(MedicalProfile):
    updated_at: Optional[str] = None
    version: Optional[str] = Field(None, description="Версия профиля: меняется при каждом сохранении")


class PetCreate(BaseModel):
    """Pet creation request model."""

    name: str = Field(..., min_length=1, max_length=100, description="Имя питомца")
    breed: Optional[str] = Field(None, max_length=100, description="Порода")
    species: Optional[str] = Field(None, max_length=50, description="Вид животного (кот, собака и т.д.)")
    birth_date: Optional[str] = Field(None, description="Дата рождения в формате YYYY-MM-DD")
    gender: Optional[str] = Field(None, max_length=20, description="Пол")
    is_neutered: Optional[bool] = Field(None, description="Кастрирован/Стерилизована")
    health_notes: Optional[str] = Field(None, max_length=1000, description="Особенности здоровья, аллергии")
    tiles_settings: Optional[TilesSettings] = Field(None, description="Настройки тайлов дневника")

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
                "species": "Кот",
                "birth_date": "2020-03-15",
                "gender": "Мужской",
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
    gender: Optional[str] = Field(None, max_length=20)
    is_neutered: Optional[bool] = None
    health_notes: Optional[str] = Field(None, max_length=1000)
    remove_photo: Optional[bool] = Field(None, description="True, если нужно удалить текущую фотографию")
    tiles_settings: Optional[TilesSettings] = Field(None, description="Настройки тайлов дневника")

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
                "species": "Кот",
                "birth_date": "2020-03-15",
                "gender": "Мужской",
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

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "Мурзик",
                "breed": "Британская короткошерстная",
                "species": "Кот",
                "birth_date": "2020-03-15",
                "gender": "Мужской",
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


class PetInviteListResponse(BaseModel):
    invites: List[PetInviteItem]


class PetResponseWrapper(BaseModel):
    """Wrapper for pet response (matches current API structure)."""

    pet: PetResponse


class PetCreatedResponse(SuccessResponse):
    """POST /api/pets: the new pet comes back whole."""

    pet: PetResponse


class PetListResponse(BaseModel):
    """List of pets response."""

    pets: List[PetResponse]


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
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    # How far a new reading may drift from this field's own rolling average
    # before it's pushed as a trend anomaly (see web/trend_alerts.py) — e.g.
    # 0.15 for 15%. A stable field (weight) and a naturally noisy one (a
    # feeding portion) don't belong under the same fixed sensitivity, so
    # this is per-field rather than one constant for every numeric type.
    # None means "use the module default".
    deviation_threshold: Optional[float] = Field(None, gt=0, lt=1)

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
    icon: str = Field(..., min_length=1, max_length=50, description="Ключ иконки")
    color: str = Field(..., min_length=1, max_length=20, description="Цвет плитки")
    fields: List[EventTypeField] = Field(default_factory=list)
    chart: EventChartConfig = Field(default_factory=EventChartConfig)

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v):
        return _validate_field_names(v)

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
    icon: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, min_length=1, max_length=20)
    fields: Optional[List[EventTypeField]] = None
    chart: Optional[EventChartConfig] = None

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, v):
        return v if v is None else _validate_field_names(v)


class EventTypeItem(BaseModel):
    """An event type as returned by the API."""

    key: str
    label: str
    icon: str
    color: str
    is_builtin: bool
    created_by: Optional[str] = None
    fields: List[EventTypeField]
    chart: EventChartConfig


class EventTypeListResponse(BaseModel):
    """List of event types."""

    event_types: List[EventTypeItem]


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


class EventListResponse(PaginatedResponse):
    """List of events with pagination."""

    items: List[EventItem]


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


class ExportQuery(PetIdQuery):
    """Query of a data export: the pet, and the user's time zone."""

    tz: Optional[str] = Field(
        None,
        max_length=64,
        description="IANA-имя часового пояса пользователя (Asia/Almaty): по нему считается время в имени файла",
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


class HealthStatsQuery(PetIdQuery):
    """Query parameters for statistics."""

    type: str = Field(..., description="Тип записи (feeding, asthma, weight и т.д.)")
    days: Optional[int] = Field(30, description="Количество дней")


class HealthStatsItem(BaseModel):
    """Simplified health record item for charts."""

    date: str
    value: Any


class HealthStatsResponse(BaseModel):
    """Statistics response for charts."""

    data: List[HealthStatsItem]


# ============================================================================
# Medication Schemas
# ============================================================================


class MedicationSchedule(BaseModel):
    days: List[int] = Field(..., description="Дни недели (0-6, где 0 - Пн, 6 - Вс)")
    times: List[str] = Field(..., description="Время приема (HH:mm)")


def _course_date(v: Optional[str]) -> Optional[str]:
    """A course date: empty (clears it), or a real YYYY-MM-DD within a year ahead and fifty back."""
    if v is None or v == "":
        return v
    return validate_date_logic(v, allow_future=True, max_future_days=366)


COURSE_FIELDS_NOTE = "YYYY-MM-DD; пустая строка убирает дату"


class MedicationListQuery(PetIdQuery):
    """Query parameters for listing medications with timezone support."""

    client_date: Optional[str] = Field(None, description="Client local date (YYYY-MM-DD)")


class UpcomingDosesQuery(PetIdQuery):
    """Query parameters for upcoming doses with timezone support."""

    client_datetime: Optional[str] = Field(None, description="Client local datetime (ISO format)")


class MedicationCreate(PetIdQuery):
    name: str = Field(..., max_length=100)
    type: str = Field(..., max_length=50, description="Ингаляция, Таблетка, Капли и т.д.")
    form_factor: Optional[str] = Field(None, max_length=20, description="tablet, liquid, injection, other")
    strength: Optional[str] = Field(None, max_length=50, description="50 mg, 5 mg/ml")
    dosage: Optional[str] = Field(None, max_length=50, description="Legacy dosage string")
    unit: Optional[str] = Field(None, max_length=20, description="Legacy unit string")
    dose_unit: Optional[str] = Field(None, max_length=20, description="tablet, ml, etc")
    default_dose: float = Field(1.0, ge=0, le=10_000, description="Default amount to subtract from inventory")
    schedule: MedicationSchedule
    inventory_enabled: bool = False
    inventory_total: Optional[float] = Field(None, ge=0, le=1_000_000)
    inventory_current: Optional[float] = Field(None, ge=0, le=1_000_000)
    inventory_warning_threshold: Optional[float] = Field(None, ge=0, le=1_000_000)
    inventory_warning_days: Optional[float] = Field(
        None, ge=0, le=60, description="Предупредить, когда запаса останется на столько дней"
    )
    is_active: bool = True
    comment: Optional[str] = Field(None, max_length=500)
    started_on: Optional[str] = Field(None, description="Начало курса, " + COURSE_FIELDS_NOTE)
    ended_on: Optional[str] = Field(None, description="Окончание курса, " + COURSE_FIELDS_NOTE)
    purpose: Optional[str] = Field(None, max_length=200, description="От чего или для чего назначен")
    prescribed_by: Optional[str] = Field(None, max_length=100, description="Кто назначил (врач, клиника)")

    @field_validator("started_on", "ended_on")
    @classmethod
    def validate_course_dates(cls, v):
        return _course_date(v) or None

    @model_validator(mode="after")
    def validate_course_order(self):
        if self.started_on and self.ended_on and self.ended_on < self.started_on:
            raise ValueError("Окончание курса раньше его начала")
        return self


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
    default_dose: Optional[float] = Field(None, ge=0, le=10_000)
    schedule: Optional[MedicationSchedule] = None
    inventory_enabled: Optional[bool] = None
    inventory_total: Optional[float] = Field(None, ge=0, le=1_000_000)
    inventory_current: Optional[float] = Field(None, ge=0, le=1_000_000)
    inventory_warning_threshold: Optional[float] = Field(None, ge=0, le=1_000_000)
    inventory_warning_days: Optional[float] = Field(None, ge=0, le=60)
    is_active: Optional[bool] = None
    comment: Optional[str] = Field(None, max_length=500)
    # A date or text is cleared with an empty string (None means «not sent»).
    started_on: Optional[str] = Field(None, description="Начало курса, " + COURSE_FIELDS_NOTE)
    ended_on: Optional[str] = Field(None, description="Окончание курса, " + COURSE_FIELDS_NOTE)
    purpose: Optional[str] = Field(None, max_length=200)
    prescribed_by: Optional[str] = Field(None, max_length=100)

    @field_validator("started_on", "ended_on")
    @classmethod
    def validate_course_dates(cls, v):
        return _course_date(v)

    @model_validator(mode="after")
    def validate_course_order(self):
        if self.started_on and self.ended_on and self.ended_on < self.started_on:
            raise ValueError("Окончание курса раньше его начала")
        return self


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
    intakes_today: int = 0
    scheduled_today: Optional[bool] = Field(None, description="Сегодня по расписанию есть приёмы (день недели и курс)")
    open_slots_today: Optional[List[str]] = Field(
        None, description="Сегодняшние приёмы по расписанию, которые ещё ничем не закрыты, по времени"
    )
    username: Optional[str] = None


class MedicationRestock(BaseModel):
    """Add a bought pack (or any amount) to the stock."""

    amount: float = Field(..., gt=0, le=100000, description="Сколько добавить к остатку")


class MedicationListResponse(BaseModel):
    medications: List[MedicationItem]


class MedicationDetailResponse(BaseModel):
    """Wrapper for the single-medication GET response."""

    medication: MedicationItem


class MedicationIntakeCreate(BaseModel):
    date: str
    time: str
    dose_taken: Optional[float] = None  # Uses default_dose if not provided
    comment: Optional[str] = None
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


class MedicationIntakeUpdate(BaseModel):
    date: str
    time: str
    tz: Optional[str] = Field(
        None,
        max_length=64,
        description="IANA-имя часового пояса, в котором введено время (Asia/Almaty): по нему выгрузка показывает время на часах выгружающего",
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


class MedicationIntakeListResponse(PaginatedResponse):
    intakes: List[MedicationIntakeItem]


class UpcomingDoseItem(BaseModel):
    medication_id: str
    name: str
    type: str = "pill"
    time: str
    date: str
    is_overdue: bool
    inventory_warning: bool
    carried_over: bool = Field(False, description="Приём со вчерашнего вечера, который ещё не отмечен")


class UpcomingDosesResponse(BaseModel):
    doses: List[UpcomingDoseItem]


# ============================================================================
# Document Schemas
# ============================================================================
# `category` is a plain str, not a Literal/enum — matches EventListQuery.type
# below, which is likewise unrestricted at the schema level. The allowed set
# (vaccination/lab_result/insurance/other) is enforced by the frontend's own
# fixed picker, not here.


class DocumentCreate(PetIdQuery):
    category: str = Field(..., description="Категория документа")
    title: str = Field(..., min_length=1, max_length=100)
    note: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[str] = Field(
        None, description="Срок действия (YYYY-MM-DD) для прививок, страховки и т.п., необязателен"
    )

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


class ScanUploadRequest(PetIdQuery):
    """Ask for a slot to upload a scan archive straight to object storage."""

    filename: str = Field(..., min_length=1, max_length=255, description="Имя файла с расширением")
    size: int = Field(..., gt=0, description="Размер файла в байтах")


class ScanUploadSlot(BaseModel):
    upload_id: str
    upload_url: str = Field(..., description="Куда отправить файл методом PUT")
    content_type: str = Field(..., description="Заголовок Content-Type для PUT")
    max_bytes: int


class ScanUploadComplete(BaseModel):
    """Turn an uploaded scan into a document."""

    title: str = Field(..., min_length=1, max_length=100)
    note: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[str] = Field(None, description="Срок действия (YYYY-MM-DD)")

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v):
        return validate_date_logic(v, allow_future=True, max_future_days=3650)


class StorageStatus(BaseModel):
    scans_enabled: bool
    max_scan_bytes: int


class DownloadLink(BaseModel):
    url: str = Field(..., description="Куда перейти, чтобы скачать файл")
    expires_in: Optional[int] = Field(None, description="Сколько секунд ссылка действует (для снимков)")


class DocumentUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    note: Optional[str] = Field(None, max_length=500)
    expires_at: Optional[str] = Field(None, description="Срок действия (YYYY-MM-DD)")

    @field_validator("expires_at")
    @classmethod
    def validate_expires_at(cls, v):
        return validate_date_logic(v, allow_future=True, max_future_days=3650)


class DocumentListQuery(PetIdPaginationQuery):
    category: Optional[str] = Field(None, description="Фильтр по категории (без него все)")


class DocumentItem(BaseModel):
    id: str = Field(alias="_id")
    pet_id: str
    username: str
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

    model_config = ConfigDict(populate_by_name=True)


class DocumentListResponse(PaginatedResponse):
    documents: List[DocumentItem]


class DocumentDetailResponse(BaseModel):
    document: DocumentItem


# ============================================================================
# Push Notification Schemas
# ============================================================================


class PushSubscriptionKeys(BaseModel):
    """The two keys the browser's PushManager returns alongside an
    endpoint — required by the Web Push encryption scheme (RFC 8291)."""

    p256dh: str
    auth: str


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
    timezone: str = Field(..., min_length=1, max_length=64, description="IANA-имя часового пояса (напр. Asia/Almaty)")

    _check_endpoint = field_validator("endpoint")(_validate_push_endpoint)


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=1)


class VapidPublicKeyResponse(BaseModel):
    public_key: str = Field(..., description="VAPID-ключ для PushManager.subscribe()")


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


# ============================================================================
# Medical records (vaccinations, treatments, visits, procedures)
# ============================================================================

MEDICAL_KINDS = ("vaccination", "parasite", "visit", "procedure")
PARASITE_TARGETS = ("fleas_ticks", "worms", "both")


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

    @model_validator(mode="after")
    def next_after_date(self):
        if self.next_due and self.next_due < self.date:
            raise ValueError("Повтор раньше самой записи")
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
        if self.kind != "visit":
            self.complaint = self.diagnosis = self.recommendations = None
        if self.kind == "parasite":
            if not self.target:
                raise ValueError("Укажите, от чего обработка")
        else:
            self.target = None
        return self


class MedicalRecordUpdate(MedicalRecordBody):
    """The whole record again: its pet and kind stay as they were."""


class MedicalRecordDocument(BaseModel):
    id: str
    title: str


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
    superseded: bool = Field(False, description="Есть более новая запись с тем же названием: эта осталась историей")
    clinic: Optional[str] = None
    vet: Optional[str] = None
    note: Optional[str] = None
    batch: Optional[str] = None
    target: Optional[str] = None
    complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    recommendations: Optional[str] = None
    documents: List[MedicalRecordDocument] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class MedicalRecordListQuery(PetIdQuery):
    kind: Optional[str] = Field(None, description="Только этого вида")
    tz: Optional[str] = Field(
        None, max_length=64, description="IANA-имя часового пояса пользователя: по нему считается «сегодня»"
    )


class MedicalRecordResponse(BaseModel):
    record: MedicalRecordItem


class MedicalRecordListResponse(BaseModel):
    records: List[MedicalRecordItem]


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


class VisitPrepOut(VisitPrep):
    updated_at: Optional[str] = None


class VisitPrepResponse(BaseModel):
    visit_prep: Optional[VisitPrepOut] = None


class MedicalCardPet(BaseModel):
    name: str
    species: Optional[str] = Field(None, description="Вид словами: «Собака», «Кот»")
    breed: Optional[str] = None
    birth_date: Optional[str] = None
    age_text: Optional[str] = Field(None, description="Возраст словами: «5 лет», «8 месяцев»")
    gender: Optional[str] = Field(None, description="Пол словами: «Мальчик», «Девочка»")
    neutered_text: Optional[str] = Field(None, description="«кастрирован», «не стерилизована»; нет, если не указано")
    health_notes: Optional[str] = Field(None, description="Особенности здоровья и аллергии, текстом")


class MedicalCardWeightPoint(BaseModel):
    date: str
    value: float


class MedicalCardWeight(BaseModel):
    latest: MedicalCardWeightPoint
    series: List[MedicalCardWeightPoint] = Field(description="Последние замеры, от старых к новым")


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


class MedicalCardVaccination(BaseModel):
    """A vaccination certificate kept only as a document, not yet made a record."""

    id: str
    title: str
    expires_at: Optional[str] = None
    status: str = Field(description="none (срок не указан), valid, soon (скоро истекает), expired")
    days_left: Optional[int] = Field(None, description="Дней до окончания; отрицательное, если истёк")
    note: Optional[str] = None


class MedicalCardDocument(BaseModel):
    id: str
    title: str
    category: str
    added: str = Field(description="Дата добавления, YYYY-MM-DD")


class MedicalProfileResponse(BaseModel):
    profile: MedicalProfileOut


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
    medications: List[MedicalCardMedication] = Field(description="Курсы, которые идут сейчас или ещё начнутся")
    past_courses: List[MedicalCardMedication] = Field(
        description="Законченные курсы, последние сверху, не больше десяти"
    )
    past_courses_total: int = Field(description="Сколько законченных курсов всего")
    vaccinations: List[MedicalCardVaccination]
    documents: List[MedicalCardDocument]
    generated_at: str = Field(description="Дата формирования, YYYY-MM-DD, по часовому поясу пользователя")
    can_edit: bool = Field(description="Владелец ли текущий пользователь: править профиль питомца может только он")


class MedicalCardResponse(BaseModel):
    card: MedicalCardData


class MedicalAlerts(BaseModel):
    """What is overdue on the card, without the card: one cheap read for the dot on the «Медкарта» tab."""

    vaccination: bool = Field(description="Есть просроченная прививка: запись со сроком или справка с истёкшим сроком")
    parasite: bool = Field(description="Есть просроченная обработка от паразитов")


class MedicalAlertsResponse(BaseModel):
    alerts: MedicalAlerts
