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


# What fills the tray; the first is what every change made before the field existed is taken to have been.
LITTER_TYPES = ("Комкующийся", "Впитывающий", "Силикагелевый", "Древесный", "Другой")


def _pick(name: str, label: str, *options: str) -> dict[str, Any]:
    return {"name": name, "label": label, "type": "select", "required": True, "options": _opts(*options)}


BUILTIN_EVENT_TYPES: list[dict[str, Any]] = [
    {
        "key": "feeding",
        "label": "Кормление",
        "icon": "utensils",
        "color": "brown",
        "fields": [
            {
                "name": "food_weight",
                "label": "Вес корма (г)",
                "type": "number",
                "required": True,
                "options": None,
                "min": 0,
                "step": 0.1,
                # A feeding portion swings meal-to-meal far more than a
                # pet's own weight does — the module-wide 15% default (right
                # for `weight`, below) would false-positive on ordinary
                # portion variation, so this field gets a wider band.
                "deviation_threshold": 0.35,
            },
        ],
        "chart": {"kind": "value", "value_field": "food_weight", "value_label": "Вес порции (г)"},
    },
    {
        "key": "weight",
        "label": "Вес",
        "icon": "scale",
        "color": "orange",
        "fields": [
            {
                "name": "weight",
                "label": "Вес (кг)",
                "type": "number",
                "required": True,
                "options": None,
                "min": 0,
                # The legacy app capped this at 20 — clearly sized for cats
                # and small dogs only, since it would reject a real
                # Labrador/Retriever-sized dog (25-40kg is normal). 100
                # comfortably covers every realistic dog breed while still
                # catching a fat-fingered extra digit.
                "max": 100,
                "step": 0.01,
            },
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
                "name": "duration",
                "label": "Длительность",
                "type": "select",
                "required": True,
                "options": _opts("Короткий", "Длительный"),
            },
            {
                "name": "inhalation",
                "label": "Ингаляция",
                "type": "select",
                "required": True,
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
                "name": "stool_type",
                "label": "Тип стула",
                "type": "select",
                "required": True,
                "options": _opts("Обычный", "Твердый", "Жидкий"),
            },
            {
                "name": "color",
                "label": "Цвет стула",
                "type": "select",
                "required": True,
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
        "fields": [_pick("litter_type", "Наполнитель", *LITTER_TYPES)],
        "chart": {"kind": "count", "value_field": None, "value_label": None},
    },
    {
        "key": "eye_drops",
        "label": "Закапывание глаз",
        "icon": "eye",
        "color": "teal",
        "fields": [
            {
                "name": "drops_type",
                "label": "Тип капель",
                "type": "select",
                "required": True,
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
                "name": "brushing_type",
                "label": "Способ чистки",
                "type": "select",
                "required": True,
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
                "name": "cleaning_type",
                "label": "Способ чистки",
                "type": "select",
                "required": True,
                "options": _opts("Салфетка/Марля", "Капли"),
            },
        ],
        "chart": {"kind": "count", "value_field": None, "value_label": None},
    },
]


def _count_type(
    key: str, label: str, icon: str, color: str, category: str, fields: list | None = None
) -> dict[str, Any]:
    """A type that is simply counted (it happened, with at most a note or a detail)."""
    return {
        "key": key,
        "label": label,
        "icon": icon,
        "color": color,
        "category": category,
        "fields": fields or [],
        "chart": {"kind": "count", "value_field": None, "value_label": None},
    }


def _number(name: str, label: str, low: float, high: float, step: float, required: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "type": "number",
        "required": required,
        "options": None,
        "min": low,
        "max": high,
        "step": step,
    }


def _valued(base: dict[str, Any], field: str, label: str) -> dict[str, Any]:
    """The same type, charted by one of its numbers instead of counted."""
    return {**base, "chart": {"kind": "value", "value_field": field, "value_label": label}}


# The catalogue beyond the original eight: what is useful to write down, grouped by `category`. A new pet gets only a few of
# them (utils/species.ts says which, by species); the rest are one tap away in the pet's events.
_CATALOG_TYPES: list[dict[str, Any]] = [
    # Food and water
    _count_type(
        "treat",
        "Лакомство",
        "gift",
        "pink",
        "food",
        [{"name": "treat", "label": "Что дали", "type": "text", "required": False, "options": None}],
    ),
    _valued(
        _count_type(
            "water_intake", "Питьё", "droplet", "cyan", "food", [_number("amount_ml", "Выпито (мл)", 0, 5000, 1, True)]
        ),
        "amount_ml",
        "Выпито (мл)",
    ),
    _count_type(
        "appetite",
        "Аппетит",
        "smile",
        "orange",
        "food",
        [_pick("level", "Какой", "Хороший", "Сниженный", "Отказывается от еды")],
    ),
    # Excretion
    _count_type(
        "urination",
        "Мочеиспускание",
        "droplet",
        "yellow",
        "excretion",
        [_pick("kind", "Какое", "Обычное", "Частое", "Редкое", "С трудом", "С кровью")],
    ),
    _count_type(
        "vomiting",
        "Рвота",
        "wind",
        "red",
        "excretion",
        [_pick("kind", "Что вышло", "Пена", "Корм", "Желчь", "Шерсть", "Другое")],
    ),
    # Health
    _valued(
        _count_type(
            "temperature",
            "Температура",
            "thermometer",
            "red",
            "health",
            [_number("temp_c", "Температура (°C)", 30, 45, 0.1, True)],
        ),
        "temp_c",
        "Температура (°C)",
    ),
    _count_type(
        "mood",
        "Самочувствие",
        "heart",
        "green",
        "health",
        [_pick("state", "Каков", "Бодрый", "Вялый", "Возбуждённый", "Прячется")],
    ),
    _count_type("cough", "Кашель или чихание", "wind", "orange", "health"),
    _count_type("seizure", "Судороги", "zap", "red", "health", [_number("minutes", "Длительность (мин)", 0, 120, 0.5)]),
    _count_type("itching", "Зуд", "paw", "orange", "health"),
    _count_type("limping", "Хромота", "bone", "brown", "health"),
    # Care
    _count_type("bathing", "Купание", "droplet", "teal", "care"),
    _count_type("brushing", "Расчёсывание", "star", "purple", "care"),
    _count_type("nail_trim", "Стрижка когтей", "paw", "gray", "care"),
    # Activity
    _valued(
        _count_type(
            "walk", "Прогулка", "sun", "green", "activity", [_number("minutes", "Длительность (мин)", 1, 720, 1)]
        ),
        "minutes",
        "Длительность (мин)",
    ),
    _valued(
        _count_type("play", "Игра", "zap", "blue", "activity", [_number("minutes", "Длительность (мин)", 1, 720, 1)]),
        "minutes",
        "Длительность (мин)",
    ),
    _count_type(
        "out_of_cage", "Выпуск из клетки", "sun", "yellow", "activity", [_number("minutes", "Сколько (мин)", 1, 720, 1)]
    ),
    _count_type(
        "training",
        "Дрессировка",
        "star",
        "yellow",
        "activity",
        [{"name": "skill", "label": "Что отрабатывали", "type": "text", "required": False, "options": None}],
    ),
    # The place a pet lives in
    _count_type("cage_cleaning", "Уборка клетки или террариума", "shovel", "brown", "habitat"),
    _count_type(
        "water_test",
        "Параметры воды",
        "thermometer",
        "teal",
        "habitat",
        [
            _number("ph", "pH", 0, 14, 0.1, True),
            _number("ammonia", "Аммоний или аммиак (мг/л)", 0, 10, 0.01),
            _number("nitrite", "Нитриты (мг/л)", 0, 10, 0.01),
            _number("nitrate", "Нитраты (мг/л)", 0, 500, 1),
            _number("water_temp_c", "Температура воды (°C)", 0, 45, 0.1),
        ],
    ),
    _count_type(
        "terrarium_climate",
        "Климат террариума",
        "thermometer",
        "orange",
        "habitat",
        [
            _number("warm_zone_c", "Тёплая зона (°C)", 0, 60, 0.5, True),
            _number("cool_zone_c", "Холодная зона (°C)", 0, 60, 0.5),
            _number("humidity", "Влажность (%)", 0, 100, 1),
        ],
    ),
    _count_type(
        "water_change", "Подмена воды", "droplet", "blue", "habitat", [_number("percent", "Подменено (%)", 1, 100, 1)]
    ),
    _count_type("filter_cleaning", "Чистка фильтра", "droplet", "gray", "habitat"),
    _count_type("uv_lamp", "Замена УФ-лампы", "sun", "yellow", "habitat"),
    _count_type("misting", "Опрыскивание", "droplet", "teal", "habitat"),
    _count_type("shedding", "Линька", "paw", "brown", "habitat"),
]

BUILTIN_EVENT_TYPES.extend(_CATALOG_TYPES)

# Where each of the original eight belongs; the rest say it themselves.
_ORIGINAL_CATEGORY = {
    "feeding": "food",
    "weight": "health",
    "asthma": "health",
    "defecation": "excretion",
    "litter": "excretion",
    "eye_drops": "care",
    "tooth_brushing": "care",
    "ear_cleaning": "care",
}
for _spec in BUILTIN_EVENT_TYPES:
    _spec.setdefault("category", _ORIGINAL_CATEGORY.get(_spec["key"]))


# Bounds that hold whatever an older install stored for the field: a weight of 0 kg draws a false point on the chart
# and a pet card, 99999 g is a slip of the finger. (event type key, field name) -> (lowest, highest).
HARD_BOUNDS: dict[tuple[str, str], tuple[float, float]] = {
    ("weight", "weight"): (0.01, 100),
    ("feeding", "food_weight"): (0.1, 5000),
    ("temperature", "temp_c"): (30, 45),
}

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


# The order a pet's «+» tiles take until someone reorders them: most
# frequent first. By name put «Астма» first and «Кормление» in the middle.
ORIGINAL_TYPE_ORDER = [
    "feeding",
    "weight",
    "defecation",
    "litter",
    "eye_drops",
    "tooth_brushing",
    "ear_cleaning",
    "asthma",
]
# The original eight first, then the catalogue as it is written (by category).
BUILTIN_TYPE_ORDER = ORIGINAL_TYPE_ORDER + [spec["key"] for spec in _CATALOG_TYPES]

# What every pet got before, alphabetical by the old names. A pet still
# carrying exactly this was never reordered by hand.
_OLD_DEFAULT_TILE_ORDER = [
    "weight",
    "defecation",
    "feeding",
    "eye_drops",
    "asthma",
    "litter",
    "ear_cleaning",
    "tooth_brushing",
]


def reorder_default_tiles(db) -> int:
    """Move pets still on the old alphabetical tile order to BUILTIN_TYPE_ORDER."""
    result = db.pets.update_many(
        {"tiles_settings.order": _OLD_DEFAULT_TILE_ORDER},
        {"$set": {"tiles_settings.order": ORIGINAL_TYPE_ORDER}},
    )
    return result.modified_count


def seed_builtin_event_types(db) -> int:
    """Insert any builtin event type missing from ``db.event_types``.

    Idempotent: existing documents (matched by ``key``) are left untouched
    beyond the numeric-bounds backfill below, so re-running after a user
    has edited a builtin type's label/icon/color doesn't clobber their
    change.

    Returns the number of documents inserted.
    """
    from datetime import datetime, timezone

    inserted = 0
    for spec in BUILTIN_EVENT_TYPES:
        existing = db.event_types.find_one({"key": spec["key"]})
        if not existing:
            db.event_types.insert_one(
                {
                    **spec,
                    "is_builtin": True,
                    "created_by": None,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            inserted += 1
            continue
        _backfill_numeric_bounds(db, existing, spec)
        _rename_old_defaults(db, existing)
        _add_missing_fields(db, existing, spec)
        if spec.get("category") and not existing.get("category"):
            db.event_types.update_one({"_id": existing["_id"]}, {"$set": {"category": spec["category"]}})
    return inserted


# Fields a built-in type got after it was first released: an install that already has the type is given the field, once. (The
# rest of a stored type is left to whoever edited it.)
_ADDED_FIELDS = {("litter", "litter_type")}


def _add_missing_fields(db, existing: dict, spec: dict) -> None:
    stored = existing.get("fields", [])
    names = {f["name"] for f in stored}
    added = [
        f for f in spec.get("fields", []) if (existing["key"], f["name"]) in _ADDED_FIELDS and f["name"] not in names
    ]
    if added:
        db.event_types.update_one({"_id": existing["_id"]}, {"$set": {"fields": [*stored, *added]}})


def backfill_litter_type(db) -> int:
    """Every change of the tray written before the filling was asked for is taken to have the first of the options."""
    result = db.events.update_many(
        {"type": "litter", "fields.litter_type": {"$exists": False}}, {"$set": {"fields.litter_type": LITTER_TYPES[0]}}
    )
    return result.modified_count


# Names a builtin type shipped with and later replaced. A stored type still
# carrying the old default gets the new one; a name someone chose stays.
# Feeding was «Дневная порция» on the tile and form while the feed card said
# «Кормление», and its portion had no unit.
_OLD_DEFAULT_LABELS = {
    "feeding": ("Дневная порция", "Кормление"),
    "cage_cleaning": ("Уборка клетки", "Уборка клетки или террариума"),
}
_OLD_DEFAULT_FIELD_LABELS = {("feeding", "food_weight"): ("Вес корма", "Вес корма (г)")}


def _rename_old_defaults(db, existing: dict) -> None:
    updates: dict = {}
    old_new = _OLD_DEFAULT_LABELS.get(existing["key"])
    if old_new and existing.get("label") == old_new[0]:
        updates["label"] = old_new[1]
    fields = existing.get("fields", [])
    renamed = False
    for field in fields:
        field_old_new = _OLD_DEFAULT_FIELD_LABELS.get((existing["key"], field.get("name")))
        if field_old_new and field.get("label") == field_old_new[0]:
            field["label"] = field_old_new[1]
            renamed = True
    if renamed:
        updates["fields"] = fields
    if updates:
        db.event_types.update_one({"_id": existing["_id"]}, {"$set": updates})


def _backfill_numeric_bounds(db, existing: dict, spec: dict) -> None:
    """Fill in a numeric field's ``min``/``max``/``step``/``deviation_threshold``
    on an already-seeded builtin type, e.g. an install running from before
    those existed.

    Only adds keys a field doesn't have at all yet — a field the user has
    since customized (including deliberately clearing a bound) keeps
    whatever it already has, matching the "don't clobber an edit" contract
    of the insert path above.
    """
    existing_fields = {f["name"]: f for f in existing.get("fields", [])}
    changed = False
    for spec_field in spec.get("fields", []):
        stored_field = existing_fields.get(spec_field["name"])
        if not stored_field:
            continue
        for bound in ("min", "max", "step", "deviation_threshold"):
            if bound in spec_field and bound not in stored_field:
                stored_field[bound] = spec_field[bound]
                changed = True
    if changed:
        db.event_types.update_one({"_id": existing["_id"]}, {"$set": {"fields": list(existing_fields.values())}})
