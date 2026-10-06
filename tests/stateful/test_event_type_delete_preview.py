"""Asking «delete the type?» once, with the number of its records in the question.

And: a save of a type keeps the bounds a record is checked against. A form that has no inputs for them sends them
absent, and a plain overwrite dropped them, so renaming a built-in type turned a weight capped at 100 into any float.
"""

from datetime import datetime, timezone

import pytest


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def walker(client, mock_db, regular_user_token):
    response = client.post(
        "/api/event-types",
        json={
            "label": "Лазание",
            "icon": "paw",
            "color": "green",
            "fields": [{"name": "height", "label": "Высота (см)", "type": "number", "min": 0, "max": 100, "step": 0.5}],
        },
        headers=_auth(regular_user_token),
    )
    return response.get_json()["key"]


def _record(client, token, pet_id, type_key):
    now = datetime.now(timezone.utc)
    return client.post(
        f"/api/events?pet_id={pet_id}",
        json={
            "pet_id": str(pet_id),
            "type": type_key,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "fields": {"height": 40},
        },
        headers=_auth(token),
    )


def test_preview_says_how_many_records_there_are(client, walker, regular_user_token, test_pet):
    assert _record(client, regular_user_token, test_pet["_id"], walker).status_code == 201

    response = client.delete(f"/api/event-types/{walker}?preview=true", headers=_auth(regular_user_token))

    assert response.status_code == 200
    assert response.get_json()["events_count"] == 1


def test_preview_deletes_nothing(client, mock_db, walker, regular_user_token, test_pet):
    _record(client, regular_user_token, test_pet["_id"], walker)

    client.delete(f"/api/event-types/{walker}?preview=true", headers=_auth(regular_user_token))

    assert mock_db["event_types"].find_one({"key": walker}) is not None
    assert mock_db["events"].count_documents({"type": walker}) == 1


def test_a_type_without_records_previews_zero(client, walker, regular_user_token):
    response = client.delete(f"/api/event-types/{walker}?preview=true", headers=_auth(regular_user_token))

    assert response.get_json()["events_count"] == 0


def test_preview_keeps_the_same_refusals_as_the_delete(client, regular_user_token):
    # A built-in type is nobody's to delete, and the preview says so instead of counting its records.
    response = client.delete("/api/event-types/weight?preview=true", headers=_auth(regular_user_token))

    assert response.status_code == 422
    assert response.get_json()["code"] == "event_type_builtin_immutable"


def test_a_save_keeps_the_bounds_it_was_given(client, mock_db, walker, regular_user_token):
    response = client.put(
        f"/api/event-types/{walker}",
        # What the type form sends: no bounds, only a new label for the field.
        json={
            "fields": [
                {"name": "height", "label": "Высота (см)", "type": "number", "required": True},
            ]
        },
        headers=_auth(regular_user_token),
    )

    assert response.status_code == 200, response.get_json()
    saved = mock_db["event_types"].find_one({"key": walker})["fields"][0]
    assert (saved["min"], saved["max"], saved["step"]) == (0.0, 100.0, 0.5)


def test_a_save_keeps_the_anomaly_threshold_too(client, mock_db, regular_user_token):
    mock_db["event_types"].insert_one(
        {
            "key": "portion",
            "label": "Порция",
            "icon": "bone",
            "color": "brown",
            "is_builtin": False,
            "created_by": "testuser",
            "fields": [
                {
                    "name": "grams",
                    "label": "Вес (г)",
                    "type": "number",
                    "required": True,
                    "min": 0.0,
                    "max": None,
                    "step": 1.0,
                    "deviation_threshold": 0.35,
                }
            ],
            "chart": {"kind": "count"},
        }
    )

    client.put(
        "/api/event-types/portion",
        json={"label": "Порция еды", "fields": [{"name": "grams", "label": "Вес порции (г)", "type": "number"}]},
        headers=_auth(regular_user_token),
    )

    saved = mock_db["event_types"].find_one({"key": "portion"})["fields"][0]
    assert saved["deviation_threshold"] == 0.35
    assert saved["step"] == 1.0


def test_a_bound_given_explicitly_wins_over_the_stored_one(client, mock_db, walker, regular_user_token):
    client.put(
        f"/api/event-types/{walker}",
        json={"fields": [{"name": "height", "label": "Высота (см)", "type": "number", "max": 250}]},
        headers=_auth(regular_user_token),
    )

    saved = mock_db["event_types"].find_one({"key": walker})["fields"][0]
    assert saved["max"] == 250.0


def test_a_new_number_field_is_not_given_a_bounds_of_a_similar_name(client, mock_db, walker, regular_user_token):
    client.put(
        f"/api/event-types/{walker}",
        json={
            "fields": [
                {"name": "height", "label": "Высота (см)", "type": "number"},
                {"name": "height_cm", "label": "Высота в см", "type": "number"},
            ]
        },
        headers=_auth(regular_user_token),
    )

    by_name = {f["name"]: f for f in mock_db["event_types"].find_one({"key": walker})["fields"]}
    assert by_name["height"]["max"] == 100.0
    assert by_name["height_cm"].get("max") is None
