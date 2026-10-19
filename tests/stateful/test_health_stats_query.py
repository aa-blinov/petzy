"""The health chart asks the database only for what a point is made of.

``GET /api/stats/health`` walks every record of a type in the window and makes a point of each. The record's own clock,
its zone and the one field the chart reads are all a point needs; the comment and the fields it does not read used to
ride along with every record of the window, out of the database and into the process, only to be dropped.

The records are written straight into the database (the chart only reads), and what the route asked the database for is
noted while the request runs.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _argument(args, kwargs, position, name):
    return args[position] if len(args) > position else kwargs.get(name)


@contextmanager
def _asked_for(mock_db):
    """Every find the request makes on ``events`` and ``medication_intakes``, with the projection it asked for."""
    asked = []
    originals = {name: getattr(mock_db[name], "find") for name in ("events", "medication_intakes")}

    def spy(name):
        original = originals[name]

        def find(*args, **kwargs):
            # pymongo takes the filter and the projection both ways round; the route uses the positional one.
            asked.append((name, _argument(args, kwargs, 0, "filter"), _argument(args, kwargs, 1, "projection")))
            return original(*args, **kwargs)

        return find

    for name in originals:
        setattr(mock_db[name], "find", spy(name))
    try:
        yield asked
    finally:
        for name, original in originals.items():
            setattr(mock_db[name], "find", original)


def _stats(client, token, pet_id, type_key, days=30):
    response = client.get(f"/api/stats/health?pet_id={pet_id}&type={type_key}&days={days}", headers=_auth(token))
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]


@pytest.fixture
def walk_type(mock_db):
    """A type charted by value, as the settings screen makes one."""
    key = "custom_walk"
    mock_db["event_types"].insert_one(
        {
            "key": key,
            "label": "Прогулка",
            "icon": "paw",
            "color": "green",
            "is_builtin": False,
            "created_by": "testuser",
            "fields": [
                {"name": "minutes", "label": "Минуты", "type": "number", "min": 0, "max": 600},
                {"name": "mood", "label": "Настроение", "type": "text"},
            ],
            "chart": {"kind": "value", "value_field": "minutes", "value_label": "Минуты"},
        }
    )
    return key


def _record(mock_db, pet_id, type_key, moment, **fields):
    mock_db["events"].insert_one(
        {
            "pet_id": str(pet_id),
            "type": type_key,
            "date_time": moment,
            "tz": "Asia/Almaty",
            "fields": fields,
            "comment": "Долгая прогулка вдоль реки",
            "username": "testuser",
            "created_at": moment,
            "updated_at": moment,
        }
    )


def test_a_value_chart_reads_the_charted_field_only(client, mock_db, regular_user_token, test_pet, walk_type):
    _record(mock_db, test_pet["_id"], walk_type, datetime.now(timezone.utc), minutes=40, mood="весело")

    with _asked_for(mock_db) as asked:
        data = _stats(client, regular_user_token, test_pet["_id"], walk_type)

    assert data[0]["value"] == 40
    events = [entry for entry in asked if entry[0] == "events"]
    assert events, "the chart read no records of the type at all"
    assert events[0][2] == {"_id": 0, "date_time": 1, "tz": 1, "fields.minutes": 1}


def test_a_counted_type_reads_no_fields_at_all(client, mock_db, regular_user_token, test_pet):
    _record(mock_db, test_pet["_id"], "defecation", datetime.now(timezone.utc), litter_type="наполнитель")

    with _asked_for(mock_db) as asked:
        data = _stats(client, regular_user_token, test_pet["_id"], "defecation")

    assert [point["value"] for point in data] == [1]
    assert asked[0][2] == {"_id": 0, "date_time": 1, "tz": 1}


def test_doses_read_only_the_clock_and_the_zone(client, mock_db, regular_user_token, test_pet):
    now = datetime.now(timezone.utc)
    mock_db["medication_intakes"].insert_many(
        [
            {
                "medication_id": "65f000000000000000000001",
                "pet_id": str(test_pet["_id"]),
                "date_time": now,
                "tz": "Asia/Almaty",
                "dose_taken": 1.0,
                "comment": "с едой",
                "username": "testuser",
            },
            {
                "medication_id": "65f000000000000000000001",
                "pet_id": str(test_pet["_id"]),
                "date_time": now - timedelta(minutes=5),
                "tz": "Asia/Almaty",
                "skipped": True,
                "username": "testuser",
            },
        ]
    )

    with _asked_for(mock_db) as asked:
        data = _stats(client, regular_user_token, test_pet["_id"], "medications")

    assert [point["value"] for point in data] == [1]
    assert asked[0][2] == {"_id": 0, "date_time": 1, "tz": 1}


def test_the_points_are_the_records_of_the_window_oldest_first(
    client, mock_db, regular_user_token, test_pet, walk_type
):
    now = datetime.now(timezone.utc)
    _record(mock_db, test_pet["_id"], walk_type, now - timedelta(days=2), minutes=20)
    _record(mock_db, test_pet["_id"], walk_type, now - timedelta(hours=1), minutes=30)
    _record(mock_db, test_pet["_id"], walk_type, now - timedelta(days=40), minutes=99)
    _record(mock_db, test_pet["_id"], "feeding", now - timedelta(hours=2), food_weight=0.2)

    data = _stats(client, regular_user_token, test_pet["_id"], walk_type)

    assert [point["value"] for point in data] == [20, 30]
    assert data[0]["date"] < data[1]["date"]
    assert data[0]["date"].startswith((now - timedelta(days=2)).strftime("%Y-%m-%d"))


def test_a_record_without_the_charted_field_is_a_zero_point(client, mock_db, regular_user_token, test_pet, walk_type):
    _record(mock_db, test_pet["_id"], walk_type, datetime.now(timezone.utc), mood="весело")

    data = _stats(client, regular_user_token, test_pet["_id"], walk_type)

    assert data[0]["value"] == 0
