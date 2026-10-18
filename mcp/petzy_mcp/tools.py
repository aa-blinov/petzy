"""Инструменты MCP: что спрашивается у API Petzy и что из ответа уходит модели.

Здесь нет ни MCP, ни HTTP: функции получают PetzyClient и аргументы инструмента. Аргументы проверяются до первого
запроса, ответы сжимаются до того, что нужно для работы. Ошибка это PetzyError с текстом для модели.

Ни один инструмент не меняет и не удаляет записи: в API уходят только чтения и POST новой записи.
"""

import json
import re
from datetime import datetime
from typing import Any

from .client import BAD_RESPONSE, PetzyClient, PetzyError

PET_ID = re.compile(r"[0-9a-fA-F]{24}")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
TIME = re.compile(r"[0-9]{2}:[0-9]{2}")

TYPE_MAX_LENGTH = 60  # EventCreate.type
COMMENT_MAX_LENGTH = 500  # EventCreate.comment
TZ_MAX_LENGTH = 64  # EventCreate.tz
HISTORY_LIMIT_MIN = 1
HISTORY_LIMIT_MAX = 100
HISTORY_LIMIT_DEFAULT = 20
MEDICAL_CARD_MAX_CHARS = 30_000

BAD_PET_ID = "Номер питомца выглядит неверно. Возьмите его из ответа list_pets"
BAD_TYPE = "Укажите ключ типа записи из list_event_types"
BAD_DATE = "Дата должна быть в формате ГГГГ-ММ-ДД, например 2026-10-16"
BAD_TIME = "Время должно быть в формате ЧЧ:ММ, например 09:30"
BAD_FIELDS = "Поля записи передаются словарём «имя поля: значение»"
BAD_COMMENT = f"Комментарий не длиннее {COMMENT_MAX_LENGTH} символов"
BAD_TZ = "Часовой пояс передаётся строкой, например Europe/Moscow"
BAD_LIMIT = f"Сколько записей показать: число от {HISTORY_LIMIT_MIN} до {HISTORY_LIMIT_MAX}"
UNCONFIRMED = (
    "Petzy не подтвердил сохранение записи. Проверьте через get_history, появилась ли она, прежде чем добавлять ещё раз"
)

# Что из записи дневника нужно модели. Логин того, кто записал, адрес питомца и служебные поля не уходят.
HISTORY_KEYS = (
    "record_type",
    "date_time",
    "fields",
    "comment",
    "medication_name",
    "dose_taken",
    "dose_unit",
    "skipped",
)
# Разделы медкарты, которые нужны интерфейсу, а не разговору о здоровье.
CARD_SKIPPED_SECTIONS = ("can_edit",)


async def list_pets(api: PetzyClient) -> dict[str, Any]:
    response = await api.get("/api/pets")
    pets = _objects(response, "pets")
    return {"pets": [{"id": pet.get("_id"), "name": pet.get("name"), "species": pet.get("species")} for pet in pets]}


async def list_event_types(api: PetzyClient) -> dict[str, Any]:
    response = await api.get("/api/event-types")
    return {"event_types": [_event_type(item) for item in _objects(response, "event_types")]}


async def add_event(
    api: PetzyClient,
    *,
    pet_id: Any,
    type: Any,
    date: Any,
    time: Any,
    fields: Any,
    comment: Any = "",
    tz: Any,
) -> dict[str, Any]:
    pet_id = _pet_id(pet_id)
    key = _type_key(type)
    date = _date(date)
    time = _time(time)
    values = _fields(fields)
    note = _comment(comment)
    body: dict[str, Any] = {
        "pet_id": pet_id,
        "type": key,
        "date": date,
        "time": time,
        "fields": values,
        "comment": note,
    }
    body["tz"] = _tz(tz)
    response = await api.post("/api/events", body)
    record_id = response.get("id") if isinstance(response, dict) else None
    if not isinstance(record_id, str) or not record_id:
        raise PetzyError(UNCONFIRMED)
    # Сервер отвечает только id: остальное здесь показано так, как было отправлено.
    return {"id": record_id, "type": key, "date": date, "time": time, "fields": values, "comment": note}


async def get_history(api: PetzyClient, *, pet_id: Any, limit: Any = HISTORY_LIMIT_DEFAULT) -> dict[str, Any]:
    pet_id = _pet_id(pet_id)
    size = _limit(limit)
    response = await api.get("/api/history/timeline", params={"pet_id": pet_id, "page": 1, "page_size": size})
    items = [_history_item(item) for item in _objects(response, "items")]
    return {"items": items, "total": response.get("total")}


async def get_medical_card(api: PetzyClient, *, pet_id: Any) -> dict[str, Any]:
    pet_id = _pet_id(pet_id)
    response = await api.get(f"/api/pets/{pet_id}/medical-card")
    card = response.get("card") if isinstance(response, dict) else None
    if not isinstance(card, dict):
        raise PetzyError(BAD_RESPONSE)
    sections: dict[str, Any] = {}
    for name, value in card.items():
        if name in CARD_SKIPPED_SECTIONS:
            continue
        compact = _compact(value)
        if compact is not None and compact != "":
            sections[name] = compact
    kept, left_out = _within_limit(sections, MEDICAL_CARD_MAX_CHARS)
    result: dict[str, Any] = {"card": kept, "truncated": bool(left_out)}
    if left_out:
        result["note"] = "ответ обрезан: не поместились разделы " + ", ".join(left_out)
    return result


def _objects(response: Any, key: str) -> list[dict[str, Any]]:
    items = response.get(key) if isinstance(response, dict) else None
    if not isinstance(items, list):
        raise PetzyError(BAD_RESPONSE)
    return [item for item in items if isinstance(item, dict)]


def _event_type(item: dict[str, Any]) -> dict[str, Any]:
    fields = item.get("fields")
    return {
        "key": item.get("key"),
        "label": item.get("label"),
        "fields": [_field(field) for field in fields if isinstance(field, dict)] if isinstance(fields, list) else [],
    }


def _field(field: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "name": field.get("name"),
        "label": field.get("label"),
        "type": field.get("type"),
        "required": bool(field.get("required")),
    }
    for key in ("min", "max", "step"):
        if field.get(key) is not None:
            out[key] = field[key]
    options = field.get("options")
    if isinstance(options, list):
        out["options"] = [{"value": o.get("value"), "text": o.get("text")} for o in options if isinstance(o, dict)]
    return out


def _history_item(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"id": item.get("_id")}
    for key in HISTORY_KEYS:
        value = item.get(key)
        if value is None or value == "" or value == {} or value is False:
            continue
        if key == "date_time" and isinstance(value, str) and len(value) >= 16 and value[10] == "T":
            # The clock as typed, the form this tool has always shown; the zone is not part of the answer.
            value = f"{value[:10]} {value[11:16]}"
        out[key] = value
    return out


def _compact(value: Any) -> Any:
    """Без null и пустых строк. Нули, false и пустые списки остаются: «аллергий нет» тоже ответ."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            compact = _compact(item)
            if compact is not None and compact != "":
                out[key] = compact
        return out
    if isinstance(value, list):
        compact_items = [_compact(item) for item in value]
        return [item for item in compact_items if item is not None and item != ""]
    return value


def _within_limit(sections: dict[str, Any], limit: int) -> tuple[dict[str, Any], list[str]]:
    """Разделы целиком, пока они помещаются. Что не поместилось, назвать по имени, а не обрезать посреди JSON."""
    kept: dict[str, Any] = {}
    used = 0
    for name, value in sections.items():
        size = len(json.dumps({name: value}, ensure_ascii=False, separators=(",", ":")))
        if used + size > limit:
            return kept, [left for left in sections if left not in kept]
        kept[name] = value
        used += size
    return kept, []


def _pet_id(value: Any) -> str:
    if not isinstance(value, str) or not PET_ID.fullmatch(value):
        raise PetzyError(BAD_PET_ID)
    return value


def _type_key(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > TYPE_MAX_LENGTH:
        raise PetzyError(BAD_TYPE)
    return value.strip()


def _date(value: Any) -> str:
    if not isinstance(value, str) or not DATE.fullmatch(value):
        raise PetzyError(BAD_DATE)
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise PetzyError(BAD_DATE) from None
    return value


def _time(value: Any) -> str:
    if not isinstance(value, str) or not TIME.fullmatch(value):
        raise PetzyError(BAD_TIME)
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        raise PetzyError(BAD_TIME) from None
    return value


def _fields(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(name, str) for name in value):
        raise PetzyError(BAD_FIELDS)
    return value


def _comment(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > COMMENT_MAX_LENGTH:
        raise PetzyError(BAD_COMMENT)
    return value


def _tz(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > TZ_MAX_LENGTH:
        raise PetzyError(BAD_TZ)
    return value


def _limit(value: Any) -> int:
    # bool is an int in Python, but true is not a number of records.
    if isinstance(value, bool) or not isinstance(value, int) or not HISTORY_LIMIT_MIN <= value <= HISTORY_LIMIT_MAX:
        raise PetzyError(BAD_LIMIT)
    return value
