"""Pydantic schemas for request/response validation and OpenAPI documentation.

Naming Convention:
- All JSON fields use snake_case (e.g., pet_id, date_time, food_weight, eye_drops, tooth_brushing)
- See docs/api-naming-conventions.md for full naming rules
"""

from datetime import datetime, timedelta
from typing import Optional, List, Annotated, Any
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
    access_token: str
    refresh_token: str

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

    _id: str
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


class PetCreate(BaseModel):
    """Pet creation request model."""

    name: str = Field(..., min_length=1, max_length=100, description="Имя питомца")
    breed: Optional[str] = Field(None, max_length=100, description="Порода")
    species: Optional[str] = Field(None, max_length=50, description="Вид животного (кот, собака и т.д.)")
    birth_date: Optional[str] = Field(None, description="Дата рождения в формате YYYY-MM-DD")
    gender: Optional[str] = Field(None, max_length=20, description="Пол")
    is_neutered: Optional[bool] = Field(None, description="Кастрирован/Стерилизована")
    health_notes: Optional[str] = Field(None, max_length=1000, description="Особенности здоровья, аллергии")
    photo_url: Optional[str] = Field(None, description="URL фотографии")
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
                "photo_url": "https://example.com/photo.jpg",
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
    photo_url: Optional[str] = None
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
                "photo_url": "https://example.com/photo.jpg",
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

    _id: str
    name: str
    breed: Optional[str] = None
    species: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    is_neutered: Optional[bool] = None
    health_notes: Optional[str] = None
    photo_url: Optional[str] = None
    photo_file_id: Optional[str] = None
    tiles_settings: Optional[TilesSettings] = None
    owner: str
    shared_with: Optional[List[str]] = None
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
                "photo_file_id": "507f1f77bcf86cd799439012",
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


class PetResponseWrapper(BaseModel):
    """Wrapper for pet response (matches current API structure)."""

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


class EventItem(BaseModel):
    """An event as returned by the API."""

    _id: str
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

    type: Optional[str] = Field(None, description="Фильтр по ключу типа события (опустить — все типы)")


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
    default_dose: float = Field(1.0, description="Default amount to subtract from inventory")
    schedule: MedicationSchedule
    inventory_enabled: bool = False
    inventory_total: Optional[float] = None
    inventory_current: Optional[float] = None
    inventory_warning_threshold: Optional[float] = None
    is_active: bool = True
    comment: Optional[str] = None


class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    form_factor: Optional[str] = None
    strength: Optional[str] = None
    dosage: Optional[str] = None
    unit: Optional[str] = None
    dose_unit: Optional[str] = None
    default_dose: Optional[float] = None
    schedule: Optional[MedicationSchedule] = None
    inventory_enabled: Optional[bool] = None
    inventory_total: Optional[float] = None
    inventory_current: Optional[float] = None
    inventory_warning_threshold: Optional[float] = None
    is_active: Optional[bool] = None
    comment: Optional[str] = None


class MedicationItem(BaseModel):
    _id: str
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
    is_active: bool
    comment: Optional[str] = None
    last_taken_at: Optional[str] = None
    intakes_today: int = 0


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


class MedicationIntakeItem(BaseModel):
    _id: str
    medication_id: str
    pet_id: str
    date_time: str
    dose_taken: float
    username: str
    comment: Optional[str] = None


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


class DocumentUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    note: Optional[str] = Field(None, max_length=500)


class DocumentListQuery(PetIdPaginationQuery):
    category: Optional[str] = Field(None, description="Фильтр по категории (опустить — все)")


class DocumentItem(BaseModel):
    id: str = Field(alias="_id")
    pet_id: str
    username: str
    category: str
    title: str
    note: Optional[str] = None
    original_filename: str
    content_type: str
    file_size: int
    created_at: str

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
    _id: str
    record_type: str = Field(..., description="Тип записи (feeding, weight, asthma, и т.д.)")
    pet_id: str
    date_time: str
    username: str

    # Allows additional dynamic fields from different record types
    model_config = ConfigDict(extra="allow")


class TimelineResponse(PaginatedResponse):
    items: List[dict]  # Use dict to allow flexibility of various record types
