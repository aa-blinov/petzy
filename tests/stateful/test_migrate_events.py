"""Tests for scripts/migrate_events.py against a mongomock database."""

from datetime import datetime, timezone

import mongomock
import pytest
from bson.int64 import Int64

from scripts.migrate_events import migrate
from web.builtin_event_types import BUILTIN_EVENT_TYPES, seed_builtin_event_types


@pytest.fixture
def legacy_db():
    """A standalone mongomock database seeded with old-style documents —
    deliberately not the shared `mock_db` fixture, since this exercises the
    migration script's own db-parameter wiring rather than the app."""
    db = mongomock.MongoClient()["migrate_test"]
    # Records of pets that still exist; migration skips the others.
    db.pets.insert_many([{"_id": "507f1f77bcf86cd799439011"}, {"_id": "p1"}])
    return db


def test_migrate_seeds_builtin_types(legacy_db):
    counts = migrate(legacy_db)
    assert counts == {
        name: 0
        for name in [
            "asthma_attacks",
            "defecations",
            "litter_changes",
            "weights",
            "feedings",
            "eye_drops",
            "tooth_brushing",
            "ear_cleaning",
        ]
    }
    keys = {d["key"] for d in legacy_db.event_types.find({})}
    assert keys == {t["key"] for t in BUILTIN_EVENT_TYPES}


def test_migrate_moves_legacy_documents(legacy_db):
    pet_id = "507f1f77bcf86cd799439011"
    now = datetime.now(timezone.utc)

    legacy_db.asthma_attacks.insert_one(
        {
            "pet_id": pet_id,
            "date_time": now,
            "duration": "5 минут",
            "reason": "Стресс",
            "inhalation": True,
            "comment": "c",
            "username": "u",
        }
    )
    legacy_db.defecations.insert_one(
        {
            "pet_id": pet_id,
            "date_time": now,
            "stool_type": "Обычный",
            "color": "Коричневый",
            "food": "",
            "comment": "",
            "username": "u",
        }
    )
    legacy_db.weights.insert_one(
        {
            "pet_id": pet_id,
            "date_time": now,
            "weight": 4.5,
            "food": "",
            "comment": "",
            "username": "u",
        }
    )

    counts = migrate(legacy_db)
    assert counts["asthma_attacks"] == 1
    assert counts["defecations"] == 1
    assert counts["weights"] == 1
    assert counts["litter_changes"] == 0

    events = list(legacy_db.events.find({}))
    assert len(events) == 3

    asthma_event = next(e for e in events if e["type"] == "asthma")
    # "5 минут" is no duration option: kept in the comment, not guessed.
    assert "duration" not in asthma_event["fields"]
    assert asthma_event["comment"] == "c\nДлительность: 5 минут"
    assert asthma_event["fields"]["inhalation"] == "true"
    assert asthma_event["fields"]["reason"] == "Стресс"
    assert asthma_event["pet_id"] == pet_id
    weight_event = next(e for e in events if e["type"] == "weight")
    assert weight_event["fields"] == {"weight": 4.5}

    # Legacy collections are left untouched.
    assert legacy_db.asthma_attacks.count_documents({}) == 1


def test_migrate_dry_run_writes_nothing(legacy_db):
    legacy_db.weights.insert_one(
        {
            "pet_id": "p1",
            "date_time": datetime.now(timezone.utc),
            "weight": 4.5,
            "food": "",
            "comment": "",
            "username": "u",
        }
    )

    counts = migrate(legacy_db, dry_run=True)
    assert counts["weights"] == 1
    assert legacy_db.events.count_documents({}) == 0
    # Registry seeding is not part of the dry-run guard — it's idempotent
    # metadata, not data — so builtin types are still created.
    assert legacy_db.event_types.count_documents({}) == len(BUILTIN_EVENT_TYPES)


def test_migrate_is_idempotent(legacy_db):
    legacy_db.weights.insert_one(
        {
            "pet_id": "p1",
            "date_time": datetime.now(timezone.utc),
            "weight": 4.5,
            "food": "",
            "comment": "",
            "username": "u",
        }
    )

    migrate(legacy_db)
    counts_second_run = migrate(legacy_db)

    assert counts_second_run["weights"] == 0
    assert legacy_db.events.count_documents({}) == 1


def test_migrate_seeding_does_not_clobber_edited_builtin_label(legacy_db):
    migrate(legacy_db)
    legacy_db.event_types.update_one({"key": "weight"}, {"$set": {"label": "Взвешивание"}})

    migrate(legacy_db)

    assert legacy_db.event_types.find_one({"key": "weight"})["label"] == "Взвешивание"


def test_seed_backfills_numeric_bounds_onto_a_pre_existing_builtin_type(legacy_db):
    """An install seeded before min/max/step existed on the weight field
    must pick them up on the next restart — otherwise every already-running
    deployment stays unbounded forever, bounds fixed only for brand new ones."""
    weight_spec = next(t for t in BUILTIN_EVENT_TYPES if t["key"] == "weight")
    pre_bounds_field = {k: v for k, v in weight_spec["fields"][0].items() if k not in ("min", "max", "step")}
    legacy_db.event_types.insert_one(
        {
            **weight_spec,
            "fields": [pre_bounds_field, weight_spec["fields"][1]],
            "is_builtin": True,
            "created_by": None,
        }
    )

    seed_builtin_event_types(legacy_db)

    backfilled = legacy_db.event_types.find_one({"key": "weight"})["fields"][0]
    assert backfilled["min"] == weight_spec["fields"][0]["min"]
    assert backfilled["max"] == weight_spec["fields"][0]["max"]
    assert backfilled["step"] == weight_spec["fields"][0]["step"]


def test_seed_does_not_override_a_customized_bound(legacy_db):
    """A bound the user already set (even to something other than the
    builtin default) is left alone — only a field missing the key
    entirely gets it filled in."""
    seed_builtin_event_types(legacy_db)
    legacy_db.event_types.update_one(
        {"key": "weight", "fields.name": "weight"},
        {"$set": {"fields.$.max": 50}},
    )

    seed_builtin_event_types(legacy_db)

    weight_field = legacy_db.event_types.find_one({"key": "weight"})["fields"][0]
    assert weight_field["max"] == 50


def _legacy(db, collection, **fields):
    db[collection].insert_one(
        {"pet_id": "p1", "date_time": datetime.now(timezone.utc), "comment": "", "username": "u", **fields}
    )


def _only_event(db):
    (event,) = list(db.events.find({}))
    return event


@pytest.mark.parametrize("stored", ["4.5", "4,5", 4.5, Int64(4)])
def test_numbers_become_floats(legacy_db, stored):
    _legacy(legacy_db, "weights", weight=stored)

    migrate(legacy_db)

    value = _only_event(legacy_db)["fields"]["weight"]
    assert isinstance(value, float) and value == float(str(stored).replace(",", "."))


def test_booleans_become_the_select_option_values(legacy_db):
    _legacy(legacy_db, "asthma_attacks", duration="Короткий", reason="r", inhalation=False)

    migrate(legacy_db)

    fields = _only_event(legacy_db)["fields"]
    assert fields == {"duration": "Короткий", "reason": "r", "inhalation": "false"}


def test_a_known_old_label_maps_to_its_option(legacy_db):
    _legacy(legacy_db, "defecations", stool_type="Тип 4 (Нормальный)", color="Коричневый")

    migrate(legacy_db)

    event = _only_event(legacy_db)
    assert event["fields"]["stool_type"] == "Обычный"
    assert event["comment"] == ""


def test_migrated_values_pass_the_event_engines_own_validation(legacy_db):
    from web.events import _validate_event_fields  # the check every save goes through

    _legacy(legacy_db, "asthma_attacks", duration="Короткий", reason="r", inhalation=True)
    _legacy(legacy_db, "feedings", food_weight="80")
    _legacy(legacy_db, "defecations", stool_type="Тип 4 (Нормальный)", color="Коричневый", food="корм")

    migrate(legacy_db)

    for event in legacy_db.events.find({}):
        spec = legacy_db.event_types.find_one({"key": event["type"]})["fields"]
        cleaned, error = _validate_event_fields(event["fields"], spec)
        assert error is None, (event["type"], error)
        assert cleaned == event["fields"]


def test_records_of_a_deleted_pet_are_skipped_and_left_in_place(legacy_db):
    legacy_db.feedings.insert_one(
        {"pet_id": "gone", "date_time": datetime.now(timezone.utc), "food_weight": 50, "comment": "", "username": "u"}
    )

    counts = migrate(legacy_db)

    assert counts["feedings"] == 0
    assert legacy_db.events.count_documents({}) == 0
    assert legacy_db.feedings.count_documents({}) == 1
