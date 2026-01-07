"""Pydantic schemas for request/response validation and OpenAPI documentation.

Naming Convention:
- All JSON fields use snake_case (e.g., pet_id, date_time, food_weight, eye_drops, tooth_brushing)
- See docs/api-naming-conventions.md for full naming rules
"""

from datetime import datetime, timedelta
from typing import Optional, List, Annotated
from pydantic import BaseModel, Field, field_validator, ConfigDict, StringConstraints

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
                "order": ["weight", "defecation", "feeding", "eye_drops", "asthma", "litter", "ear_cleaning", "tooth_brushing"],
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
                "birth_date": "2020-03-15",
                "gender": "Мужской",
                "photo_url": "",
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
                "birth_date": "2020-03-15",
                "gender": "Мужской",
            }
        }
    )


class PetResponse(BaseModel):
    """Pet response model."""

    _id: str
    name: str
    breed: str
    species: Optional[str] = None
    birth_date: Optional[str] = None
    gender: str
    is_neutered: Optional[bool] = None
    health_notes: Optional[str] = None
    photo_url: Optional[str] = None
    photo_file_id: Optional[str] = None
    tiles_settings: Optional[TilesSettings] = None
    owner: str
    shared_with: List[str]
    created_at: str
    created_by: str
    current_user_is_owner: bool

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "Мурзик",
                "breed": "Британская короткошерстная",
                "birth_date": "2020-03-15",
                "gender": "Мужской",
                "photo_url": "",
                "owner": "admin",
                "shared_with": [],
                "created_at": "2024-01-15 14:30",
                "created_by": "admin",
                "current_user_is_owner": True,
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
# Asthma Schemas
# ============================================================================


class AsthmaAttackCreate(HealthRecordBase):
    """Asthma attack creation request model."""

    duration: Optional[str] = Field(None, max_length=50, description="Длительность приступа")
    reason: Optional[str] = Field(None, max_length=200, description="Причина приступа")
    inhalation: Optional[bool] = Field(None, description="Была ли проведена ингаляция")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "duration": "5 минут",
                "reason": "Стресс",
                "inhalation": True,
                "comment": "Приступ был легким",
            }
        }
    )


class AsthmaAttackUpdate(HealthRecordUpdateBase):
    """Asthma attack update request model."""

    duration: Optional[str] = Field(None, max_length=50)
    reason: Optional[str] = Field(None, max_length=200)
    inhalation: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "time": "14:30",
                "duration": "5 минут",
                "reason": "Стресс",
                "inhalation": True,
                "comment": "Приступ был легким",
            }
        }
    )


class AsthmaAttackItem(BaseModel):
    """Asthma attack item in list response."""

    _id: str
    pet_id: str
    date_time: str
    username: str
    duration: Optional[str] = None
    reason: Optional[str] = None
    inhalation: Optional[bool] = None  # Boolean value (true/false) as stored in DB
    comment: Optional[str] = None


class AsthmaAttackListResponse(PaginatedResponse):
    """List of asthma attacks response with pagination."""

    attacks: List[AsthmaAttackItem]


# ============================================================================
# Defecation Schemas
# ============================================================================


class DefecationCreate(HealthRecordBase):
    """Defecation creation request model."""

    stool_type: Optional[str] = Field(None, max_length=50, description="Тип стула")
    color: Optional[str] = Field(None, max_length=50, description="Цвет стула")
    food: Optional[str] = Field(None, max_length=200, description="Корм")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "stool_type": "Нормальный",
                "color": "Коричневый",
                "food": "Сухой корм",
                "comment": "Все в порядке",
            }
        }
    )


class DefecationUpdate(HealthRecordUpdateBase):
    """Defecation update request model."""

    stool_type: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=50)
    food: Optional[str] = Field(None, max_length=200)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "time": "14:30",
                "stool_type": "Нормальный",
                "color": "Коричневый",
                "food": "Сухой корм",
                "comment": "Все в порядке",
            }
        }
    )


class DefecationItem(BaseModel):
    """Defecation item in list response."""

    _id: str
    pet_id: str
    date_time: str
    username: str
    stool_type: Optional[str] = None
    color: Optional[str] = None
    food: Optional[str] = None
    comment: Optional[str] = None


class DefecationListResponse(PaginatedResponse):
    """List of defecations response with pagination."""

    defecations: List[DefecationItem]


# ============================================================================
# Litter Change Schemas
# ============================================================================


class LitterChangeCreate(HealthRecordBase):
    """Litter change creation request model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "comment": "Полная замена наполнителя",
            }
        }
    )


class LitterChangeUpdate(HealthRecordUpdateBase):
    """Litter change update request model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "time": "14:30",
                "comment": "Полная замена наполнителя",
            }
        }
    )


class LitterChangeItem(BaseModel):
    """Litter change item in list response."""

    _id: str
    pet_id: str
    date_time: str
    username: str
    comment: Optional[str] = None


class LitterChangeListResponse(PaginatedResponse):
    """List of litter changes response with pagination."""

    litter_changes: List[LitterChangeItem]


# ============================================================================
# Weight Schemas
# ============================================================================


class WeightRecordCreate(HealthRecordBase):
    """Weight record creation request model."""

    weight: Optional[float] = Field(None, gt=0, description="Вес в килограммах")
    food: Optional[str] = Field(None, max_length=200, description="Корм")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "weight": 4.5,
                "food": "Сухой корм",
                "comment": "Вес в норме",
            }
        }
    )


class WeightRecordUpdate(HealthRecordUpdateBase):
    """Weight record update request model."""

    weight: Optional[float] = Field(None, gt=0)
    food: Optional[str] = Field(None, max_length=200)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "time": "14:30",
                "weight": 4.5,
                "food": "Сухой корм",
                "comment": "Вес в норме",
            }
        }
    )


class WeightRecordItem(BaseModel):
    """Weight record item in list response."""

    _id: str
    pet_id: str
    date_time: str
    username: str
    weight: Optional[float] = None
    food: Optional[str] = None
    comment: Optional[str] = None


class WeightRecordListResponse(PaginatedResponse):
    """List of weight records response with pagination."""

    weights: List[WeightRecordItem]


# ============================================================================
# Feeding Schemas
# ============================================================================


class FeedingCreate(HealthRecordBase):
    """Feeding creation request model."""

    food_weight: Optional[float] = Field(None, gt=0, description="Вес корма в граммах")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "food_weight": 50.0,
                "comment": "Обычная порция",
            }
        }
    )


class FeedingUpdate(HealthRecordUpdateBase):
    """Feeding update request model."""

    food_weight: Optional[float] = Field(None, gt=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "time": "14:30",
                "food_weight": 50.0,
                "comment": "Обычная порция",
            }
        }
    )


class FeedingItem(BaseModel):
    """Feeding item in list response."""

    _id: str
    pet_id: str
    date_time: str
    username: str
    food_weight: Optional[float] = None
    comment: Optional[str] = None


class FeedingListResponse(PaginatedResponse):
    """List of feedings response with pagination."""

    feedings: List[FeedingItem]


# ============================================================================
# Eye Drops Schemas
# ============================================================================


class EyeDropsCreate(HealthRecordBase):
    """Eye drops creation request model."""

    drops_type: Optional[str] = Field(None, max_length=50, description="Тип капель")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "drops_type": "Обычные",
                "comment": "Закапано в оба глаза",
            }
        }
    )


class EyeDropsUpdate(HealthRecordUpdateBase):
    """Eye drops update request model."""

    drops_type: Optional[str] = Field(None, max_length=50)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "time": "14:30",
                "drops_type": "Обычные",
                "comment": "Закапано в оба глаза",
            }
        }
    )


class EyeDropsItem(BaseModel):
    """Eye drops item in list response."""

    _id: str
    pet_id: str
    date_time: str
    username: str
    drops_type: Optional[str] = None
    comment: Optional[str] = None


class EyeDropsListResponse(PaginatedResponse):
    """List of eye drops records response with pagination."""

    eye_drops: List[EyeDropsItem]


# ============================================================================
# Tooth Brushing Schemas
# ============================================================================


class ToothBrushingCreate(HealthRecordBase):
    """Tooth brushing creation request model."""

    brushing_type: Optional[str] = Field(None, max_length=50, description="Способ чистки")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "brushing_type": "Щетка",
                "comment": "Чистка верхних зубов",
            }
        }
    )


class ToothBrushingUpdate(HealthRecordUpdateBase):
    """Tooth brushing update request model."""

    brushing_type: Optional[str] = Field(None, max_length=50)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "time": "14:30",
                "brushing_type": "Щетка",
                "comment": "Чистка верхних зубов",
            }
        }
    )


class ToothBrushingItem(BaseModel):
    """Tooth brushing item in list response."""

    _id: str
    pet_id: str
    date_time: str
    username: str
    brushing_type: Optional[str] = None
    comment: Optional[str] = None


class ToothBrushingListResponse(PaginatedResponse):
    """List of tooth brushing records response with pagination."""

    tooth_brushing: List[ToothBrushingItem]


# ============================================================================
# Ear Cleaning Schemas
# ============================================================================

class EarCleaningCreate(HealthRecordBase):
    """Ear cleaning creation request model."""

    cleaning_type: Optional[str] = Field(None, max_length=50, description="Способ чистки")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "cleaning_type": "Салфетка/Марля",
                "comment": "Чистка левого уха",
            }
        }
    )


class EarCleaningUpdate(HealthRecordUpdateBase):
    """Ear cleaning update request model."""

    cleaning_type: Optional[str] = Field(None, max_length=50)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2024-01-15",
                "time": "14:30",
                "cleaning_type": "Салфетка/Марля",
                "comment": "Чистка левого уха",
            }
        }
    )


class EarCleaningItem(BaseModel):
    """Ear cleaning item in list response."""

    _id: str
    pet_id: str
    date_time: str
    username: str
    cleaning_type: Optional[str] = None
    comment: Optional[str] = None


class EarCleaningListResponse(PaginatedResponse):
    """List of ear cleaning records response with pagination."""

    ear_cleaning: List[EarCleaningItem]


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
