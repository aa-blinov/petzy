"""What the API did differently from what it promised, found by checking the reference against the code.

Each test fails with the fix taken out: a comment edit moved the record to «now», logout left access tokens alive,
a short password got 422 from the «is it common» check, a pack added to a count kept while counting was off,
``preview=1`` deleted for real, a value chart could name a field the type no longer had, an unknown zone silently
stopped reminders, medication answers had no ``success`` and spoke English, a course's ``created_at`` came as an
HTTP date, and a signed-out request with a bad body was told about the body before being told to sign in.
"""

import re
from datetime import datetime, timedelta


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _event(client, token, pet_id, when, comment=""):
    response = client.post(
        f"/api/events?pet_id={pet_id}",
        json={
            "pet_id": str(pet_id),
            "type": "walk",
            "date": when.strftime("%Y-%m-%d"),
            "time": when.strftime("%H:%M"),
            "comment": comment,
            "tz": "Asia/Almaty",
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["id"]


def test_editing_only_the_comment_keeps_the_time(client, mock_db, regular_user_token, test_pet):
    when = datetime.now() - timedelta(days=2, hours=3)
    record_id = _event(client, regular_user_token, test_pet["_id"], when)

    response = client.put(f"/api/events/{record_id}", json={"comment": "ел хорошо"}, headers=_auth(regular_user_token))
    assert response.status_code == 200, response.get_json()
    stored = client.get(f"/api/events/{record_id}", headers=_auth(regular_user_token)).get_json()
    assert stored["date_time"] == when.strftime("%Y-%m-%dT%H:%M:00") + "+05:00"

    # One half sent: the other comes from the stored time.
    client.put(f"/api/events/{record_id}", json={"time": "07:15"}, headers=_auth(regular_user_token))
    stored = client.get(f"/api/events/{record_id}", headers=_auth(regular_user_token)).get_json()
    assert stored["date_time"] == when.strftime("%Y-%m-%d") + "T07:15:00+05:00"


def test_the_common_password_check_answers_a_short_password(client):
    response = client.post("/api/auth/password/common", json={"password": "1234"})
    assert response.status_code == 200, response.get_json()
    assert "common" in response.get_json()


def _course(client, token, pet_id, **extra):
    body = {
        "pet_id": str(pet_id),
        "name": "Дронтал Плюс",
        "type": "Таблетка",
        "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["10:00"]},
        **extra,
    }
    response = client.post("/api/medications", json=body, headers=_auth(token))
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def test_a_pack_after_counting_was_off_starts_the_count_again(client, mock_db, regular_user_token, test_pet):
    course_id = _course(client, regular_user_token, test_pet["_id"], inventory_enabled=True, inventory_current=10)["id"]
    off = client.put(
        f"/api/medications/{course_id}", json={"inventory_enabled": False}, headers=_auth(regular_user_token)
    )
    assert off.status_code == 200, off.get_json()

    response = client.post(
        f"/api/medications/{course_id}/restock", json={"amount": 5}, headers=_auth(regular_user_token)
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["inventory_current"] == 5


def test_medication_answers_say_success_in_russian(client, mock_db, regular_user_token, test_pet):
    created = _course(client, regular_user_token, test_pet["_id"])
    assert created["success"] is True
    assert created["message"] == "Лекарство добавлено"


def test_a_course_comes_with_created_at_in_the_lists_format(client, mock_db, regular_user_token, test_pet):
    course_id = _course(client, regular_user_token, test_pet["_id"])["id"]
    course = client.get(f"/api/medications/{course_id}", headers=_auth(regular_user_token)).get_json()["medication"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", course["created_at"]), course["created_at"]


def _climbing(client, token):
    response = client.post(
        "/api/event-types",
        json={
            "label": "Лазание",
            "icon": "paw",
            "color": "green",
            "fields": [{"name": "height", "label": "Высота (см)", "type": "number", "min": 0, "max": 100}],
            "chart": {"kind": "value", "value_field": "height"},
        },
        headers=_auth(token),
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["key"]


def test_preview_given_as_1_deletes_nothing(client, mock_db, regular_user_token):
    key = _climbing(client, regular_user_token)
    response = client.delete(f"/api/event-types/{key}?preview=1", headers=_auth(regular_user_token))
    assert response.status_code == 200
    assert response.get_json()["events_count"] == 0
    assert mock_db.event_types.find_one({"key": key}) is not None


def test_a_value_chart_is_checked_against_what_is_stored(client, mock_db, regular_user_token):
    key = _climbing(client, regular_user_token)
    chart_alone = client.put(
        f"/api/event-types/{key}",
        json={"chart": {"kind": "value", "value_field": "no_such_field"}},
        headers=_auth(regular_user_token),
    )
    assert chart_alone.status_code == 422

    fields_alone = client.put(
        f"/api/event-types/{key}",
        json={"fields": [{"name": "note", "label": "Заметка", "type": "text"}]},
        headers=_auth(regular_user_token),
    )
    assert fields_alone.status_code == 422


def test_an_unknown_push_timezone_is_refused(client, regular_user_token):
    response = client.post(
        "/api/push/subscribe",
        json={
            "endpoint": "https://fcm.googleapis.com/fcm/send/abcd1234",
            "keys": {"p256dh": "base64 public key", "auth": "base64 auth secret"},
            "timezone": "Mars/Olympus",
        },
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422


def test_a_signed_out_request_is_told_to_sign_in_before_anything_about_its_body(client):
    response = client.post("/api/events", json={"type": 5})
    assert response.status_code == 401
