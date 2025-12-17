"""Pydantic schemas for request/response validation and OpenAPI documentation."""

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

    error: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Описание ошибки",
            }
        }
    )


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

    isAdmin: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "isAdmin": True,
            }
        }
    )


# ============================================================================
# User Schemas
# ============================================================================


class UserCreate(BaseModel):
    """User creation request model."""

    username: str = Field(..., min_length=3, max_length=50, description="Имя пользователя")
    password: str = Field(..., min_length=6, max_length=100, description="Пароль")
    full_name: Optional[str] = Field(None, max_length=100, description="Полное имя")
    email: Optional[str] = Field(None, max_length=100, description="Email")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "newuser",
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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Иван Петров",
                "email": "ivan.new@example.com",
                "is_active": True,
            }
        }
    )


class UserResponse(BaseModel):
    """User response model (without password_hash)."""

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


# ============================================================================
# Pet Schemas
# ============================================================================


class PetCreate(BaseModel):
    """Pet creation request model."""

    name: str = Field(..., min_length=1, max_length=100, description="Имя питомца")
    breed: Optional[str] = Field(None, max_length=100, description="Порода")
    birth_date: Optional[str] = Field(None, description="Дата рождения в формате YYYY-MM-DD")
    gender: Optional[str] = Field(None, max_length=20, description="Пол")
    photo_url: Optional[str] = Field(None, description="URL фотографии")

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
    birth_date: Optional[str] = Field(None, description="Дата рождения в формате YYYY-MM-DD")
    gender: Optional[str] = Field(None, max_length=20)
    photo_url: Optional[str] = None

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

    id: str = Field(alias="_id")
    name: str
    breed: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    owner: str
    photo_url: Optional[str] = None
    current_user_is_owner: bool
    created_at: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "Мурзик",
                "breed": "Британская короткошерстная",
                "birth_date": "2020-03-15",
                "gender": "Мужской",
                "owner": "admin",
                "photo_url": "/api/pets/507f1f77bcf86cd799439011/photo",
                "current_user_is_owner": True,
                "created_at": "2024-01-15 14:30",
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
    """Pet share request model."""

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
    """Base model for health records with common fields."""

    pet_id: Optional[ObjectIdString] = Field(None, description="ID питомца (может быть в query params)")
    date: Optional[str] = Field(None, description="Дата в формате YYYY-MM-DD")
    time: Optional[str] = Field(None, description="Время в формате HH:MM")
    comment: Optional[str] = Field(None, max_length=1000, description="Комментарий")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        """Validate date format and logic (up to 1 day in future)."""
        return validate_date_logic(v, allow_future=True, max_future_days=1)

    @field_validator("time")
    @classmethod
    def validate_time(cls, v):
        """Validate time format."""
        if v:
            try:
                datetime.strptime(v, "%H:%M")
            except ValueError:
                raise ValueError("Неверный формат времени. Используйте HH:MM")
        return v


class HealthRecordUpdateBase(BaseModel):
    """Base model for health record updates with common fields."""

    date: Optional[str] = None
    time: Optional[str] = None
    comment: Optional[str] = Field(None, max_length=1000)

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        """Validate date format and logic (up to 1 day in future)."""
        return validate_date_logic(v, allow_future=True, max_future_days=1)

    @field_validator("time")
    @classmethod
    def validate_time(cls, v):
        """Validate time format."""
        if v:
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
    reason: Optional[str] = Field(None, max_length=200, description="Причина")
    inhalation: bool = Field(False, description="Использование ингалятора")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "duration": "5 минут",
                "reason": "Стресс",
                "inhalation": True,
                "comment": "Приступ был несильным",
            }
        }
    )


class AsthmaAttackUpdate(HealthRecordUpdateBase):
    """Asthma attack update request model."""

    duration: Optional[str] = Field(None, max_length=50)
    reason: Optional[str] = Field(None, max_length=200)
    inhalation: bool = False


class AsthmaAttackItem(BaseModel):
    """Asthma attack item in list response."""

    id: str = Field(alias="_id")
    pet_id: str
    date_time: str
    duration: Optional[str] = None
    reason: Optional[str] = None
    inhalation: str  # "Да" or "Нет"
    comment: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class AsthmaAttackListResponse(BaseModel):
    """List of asthma attacks response."""

    attacks: List[AsthmaAttackItem]


# ============================================================================
# Defecation Schemas
# ============================================================================


class DefecationCreate(HealthRecordBase):
    """Defecation creation request model."""

    stool_type: Optional[str] = Field(None, max_length=50, description="Тип стула")
    color: str = Field("Коричневый", max_length=50, description="Цвет")
    food: Optional[str] = Field(None, max_length=200, description="Еда")

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
    color: str = Field("Коричневый", max_length=50)
    food: Optional[str] = Field(None, max_length=200)


class DefecationItem(BaseModel):
    """Defecation item in list response."""

    id: str = Field(alias="_id")
    pet_id: str
    date_time: str
    stool_type: Optional[str] = None
    color: Optional[str] = None
    food: Optional[str] = None
    comment: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class DefecationListResponse(BaseModel):
    """List of defecations response."""

    defecations: List[DefecationItem]


# ============================================================================
# Litter Schemas
# ============================================================================


class LitterChangeCreate(HealthRecordBase):
    """Litter change creation request model."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "comment": "Лоток полностью заменен",
            }
        }
    )


class LitterChangeUpdate(HealthRecordUpdateBase):
    """Litter change update request model."""

    pass


class LitterChangeItem(BaseModel):
    """Litter change item in list response."""

    id: str = Field(alias="_id")
    pet_id: str
    date_time: str
    comment: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class LitterChangeListResponse(BaseModel):
    """List of litter changes response."""

    litter_changes: List[LitterChangeItem]


# ============================================================================
# Weight Schemas
# ============================================================================


class WeightRecordCreate(HealthRecordBase):
    """Weight record creation request model."""

    weight: Optional[str | float | int] = Field(None, description="Вес")
    food: Optional[str] = Field(None, max_length=200, description="Еда")

    model_config = ConfigDict(
        coerce_numbers_to_str=True,
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "weight": "4.5",
                "food": "Сухой корм",
                "comment": "Вес в норме",
            }
        },
    )


class WeightRecordUpdate(HealthRecordUpdateBase):
    """Weight record update request model."""

    weight: Optional[str | float | int] = None
    food: Optional[str] = Field(None, max_length=200)

    model_config = ConfigDict(coerce_numbers_to_str=True)


class WeightRecordItem(BaseModel):
    """Weight record item in list response."""

    id: str = Field(alias="_id")
    pet_id: str
    date_time: str
    weight: Optional[str | float | int] = None
    food: Optional[str] = None
    comment: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)


class WeightRecordListResponse(BaseModel):
    """List of weight records response."""

    weights: List[WeightRecordItem]


# ============================================================================
# Feeding Schemas
# ============================================================================


class FeedingCreate(HealthRecordBase):
    """Feeding creation request model."""

    food_weight: Optional[str | float | int] = Field(None, description="Вес еды")

    model_config = ConfigDict(
        coerce_numbers_to_str=True,
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "food_weight": "100 г",
                "comment": "Дневная порция",
            }
        },
    )


class FeedingUpdate(HealthRecordUpdateBase):
    """Feeding update request model."""

    food_weight: Optional[str | float | int] = None

    model_config = ConfigDict(coerce_numbers_to_str=True)


class FeedingItem(BaseModel):
    """Feeding item in list response."""

    id: str = Field(alias="_id")
    pet_id: str
    date_time: str
    food_weight: Optional[str | float | int] = None
    comment: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, coerce_numbers_to_str=True)


class FeedingListResponse(BaseModel):
    """List of feedings response."""

    feedings: List[FeedingItem]


# ============================================================================
# Eye Drops Schemas
# ============================================================================


class EyeDropsCreate(HealthRecordBase):
    """Eye drops record creation request model."""

    drops_type: str = Field("Обычные", max_length=50, description="Тип капель")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pet_id": "507f1f77bcf86cd799439011",
                "date": "2024-01-15",
                "time": "14:30",
                "drops_type": "Обычные",
                "comment": "Закапали утром",
            }
        }
    )


class EyeDropsUpdate(HealthRecordUpdateBase):
    """Eye drops record update request model."""

    drops_type: Optional[str] = Field(None, max_length=50)


class EyeDropsItem(BaseModel):
    """Eye drops record item in list response."""

    id: str = Field(alias="_id")
    pet_id: str
    date_time: str
    drops_type: str
    comment: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class EyeDropsListResponse(BaseModel):
    """List of eye drops records response."""

    eye_drops: List[EyeDropsItem] = Field(alias="eye-drops")
    
    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# Export Schemas
# ============================================================================


class PetIdQuery(BaseModel):
    """Query parameters for requests requiring pet_id."""

    pet_id: ObjectIdString = Field(..., description="ID питомца")


class ExportPathParams(BaseModel):
    """Export path parameters."""

    export_type: str = Field(..., description="Тип данных для экспорта")
    format_type: str = Field(..., description="Формат экспорта (csv, tsv, html, md)")


class ExportQueryParams(BaseModel):
    """Export query parameters."""

    pet_id: ObjectIdString = Field(..., description="ID питомца")
