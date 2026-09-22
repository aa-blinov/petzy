"""Seed data for the eight event types that used to be hand-rolled collections.

Shared by the one-time migration script (``scripts/migrate_events.py``) and
by test fixtures that need a populated ``event_types`` registry. Keys match
the old ``HEALTH_RECORD_TYPES``/``tilesConfig`` ids exactly, so a pet's
existing ``tiles_settings.order``/``visible`` (keyed by these same strings)
keeps working without touching the ``pets`` collection at all.
"""

from typing import Any


def _opts(*pairs: str) -> list[dict[str, str]]:
    """Build a select field's options from ``value`` strings (value == text)."""
    return [{"value": p, "text": p} for p in pairs]


BUILTIN_EVENT_TYPES: list[dict[str, Any]] = [
    {
        "key": "feeding",
        "label": "Дневная порция",
        "icon": "utensils",
        "color": "brown",
        "fields": [
            {"name": "food_weight", "label": "Вес корма", "type": "number", "required": True, "options": None},
        ],
        "chart": {"kind": "value", "value_field": "food_weight", "value_label": "Вес порции (г)"},
    },
    {
        "key": "weight",
        "label": "Вес",
        "icon": "scale",
        "color": "orange",
        "fields": [
            {"name": "weight", "label": "Вес (кг)", "type": "number", "required": True, "options": None},
            {"name": "food", "label": "Корм", "type": "text", "required": False, "options": None},
        ],
        "chart": {"kind": "value", "value_field": "weight", "value_label": "Вес (кг)"},
    },
    {
        "key": "asthma",
        "label": "Приступ астмы",
        "icon": "wind",
        "color": "red",
        "fields": [
            {
                "name": "duration", "label": "Длительность", "type": "select", "required": True,
                "options": _opts("Короткий", "Длительный"),
            },
            {
                "name": "inhalation", "label": "Ингаляция", "type": "select", "required": True,
                "options": [{"value": "false", "text": "Нет"}, {"value": "true", "text": "Да"}],
            },
            {"name": "reason", "label": "Причина", "type": "text", "required": True, "options": None},
        ],
        "chart": {"kind": "count", "value_field": None, "value_label": None},
    },
    {
        "key": "defecation",
        "label": "Дефекация",
        "icon": "toilet",
        "color": "green",
        "fields": [
            {
                "name": "stool_type", "label": "Тип стула", "type": "select", "required": True,
                "options": _opts("Обычный", "Твердый", "Жидкий"),
            },
            {
                "name": "color", "label": "Цвет стула", "type": "select", "required": True,
                "options": _opts("Коричневый", "Темно-коричневый", "Светло-коричневый", "Другой"),
            },
            {"name": "food", "label": "Корм", "type": "text", "required": False, "options": None},
        ],
        "chart": {"kind": "count", "value_field": None, "value_label": None},
    },
    {
        "key": "litter",
        "label": "Смена лотка",
        "icon": "shovel",
        "color": "purple",
        "fields": [],
        "chart": {"kind": "count", "value_field": None, "value_label": None},
    },
    {
        "key": "eye_drops",
        "label": "Закапывание глаз",
        "icon": "eye",
        "color": "teal",
        "fields": [
            {
                "name": "drops_type", "label": "Тип капель", "type": "select", "required": True,
                "options": _opts("Обычные", "Гелевые"),
            },
        ],
        "chart": {"kind": "count", "value_field": None, "value_label": None},
    },
    {
        "key": "tooth_brushing",
        "label": "Чистка зубов",
        "icon": "toothbrush",
        "color": "cyan",
        "fields": [
            {
                "name": "brushing_type", "label": "Способ чистки", "type": "select", "required": True,
                "options": _opts("Щетка", "Марля", "Игрушка"),
            },
        ],
        "chart": {"kind": "count", "value_field": None, "value_label": None},
    },
    {
        "key": "ear_cleaning",
        "label": "Чистка ушей",
        "icon": "ear",
        "color": "yellow",
        "fields": [
            {
                "name": "cleaning_type", "label": "Способ чистки", "type": "select", "required": True,
                "options": _opts("Салфетка/Марля", "Капли"),
            },
        ],
        "chart": {"kind": "count", "value_field": None, "value_label": None},
    },
]

# Old collection name -> event type key, and which of its fields (besides
# the shared pet_id/date_time/comment/username) move into `fields`.
LEGACY_COLLECTION_MAP: dict[str, dict[str, Any]] = {
    "asthma_attacks": {"type": "asthma", "fields": ["duration", "reason", "inhalation"]},
    "defecations": {"type": "defecation", "fields": ["stool_type", "color", "food"]},
    "litter_changes": {"type": "litter", "fields": []},
    "weights": {"type": "weight", "fields": ["weight", "food"]},
    "feedings": {"type": "feeding", "fields": ["food_weight"]},
    "eye_drops": {"type": "eye_drops", "fields": ["drops_type"]},
    "tooth_brushing": {"type": "tooth_brushing", "fields": ["brushing_type"]},
    "ear_cleaning": {"type": "ear_cleaning", "fields": ["cleaning_type"]},
}


def seed_builtin_event_types(db) -> int:
    """Insert any builtin event type missing from ``db.event_types``.

    Idempotent: existing documents (matched by ``key``) are left untouched,
    so re-running after a user has edited a builtin type's label/icon/color
    doesn't clobber their change.

    Returns the number of documents inserted.
    """
    from datetime import datetime, timezone

    inserted = 0
    for spec in BUILTIN_EVENT_TYPES:
        if db.event_types.find_one({"key": spec["key"]}):
            continue
        db.event_types.insert_one(
            {
                **spec,
                "is_builtin": True,
                "created_by": None,
                "created_at": datetime.now(timezone.utc),
            }
        )
        inserted += 1
    return inserted
