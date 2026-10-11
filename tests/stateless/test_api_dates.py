"""Every date that leaves the API is in the project's format.

A datetime handed to jsonify without strftime goes out as a web-server date,
«Sat, 03 Oct 2026 07:52:49 GMT». Pets, documents and users always formatted
their created_at; records, medication courses, intakes and the timeline left
it raw, so the same field spoke two formats depending on the endpoint, and
next to a date_time in «YYYY-MM-DD HH:MM» it looked like someone else's idea.

The value is UTC and carries no zone marker, as it always has. That is a
separate question from the shape, and this test is about the shape.
"""

import re
from datetime import datetime, timezone

import pytest
from bson import ObjectId

PROJECT_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")


def dates_in(body, where=""):
    """Every date-shaped string in an answer, with where it was found."""
    if isinstance(body, dict):
        for key, value in body.items():
            yield from dates_in(value, f"{where}.{key}")
    elif isinstance(body, list):
        for i, item in enumerate(body):
            yield from dates_in(item, f"{where}[{i}]")
    elif isinstance(body, str) and not PROJECT_DATE.match(body) and re.match(r"^[A-Z][a-z]{2}, \d{2} ", body):
        yield where, body


@pytest.mark.parametrize("date_field", ["created_at", "date_time"])
def test_an_event_speaks_the_project_dates(client, mock_db, regular_user_token, test_pet, date_field):
    mock_db["events"].insert_one(
        {
            "_id": ObjectId(),
            "pet_id": str(test_pet["_id"]),
            "type": "weight",
            "date_time": datetime(2026, 10, 4, 8, 2),
            "created_at": datetime(2026, 10, 4, 8, 2),
            "username": "user1",
            "comment": "",
            "fields": {"weight": 29.3},
        }
    )
    response = client.get(
        f"/api/events?pet_id={test_pet['_id']}",
        headers={"Authorization": f"Bearer {regular_user_token}"},
    )
    assert response.status_code == 200
    item = response.get_json()["items"][0]
    assert PROJECT_DATE.match(item[date_field]), f"{date_field} is {item[date_field]!r}"


def test_a_course_and_an_intake_speak_the_project_dates(client, mock_db, regular_user_token, test_pet):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    mock_db["medications"].insert_one(
        {
            "_id": ObjectId(),
            "pet_id": str(test_pet["_id"]),
            "name": "Test Course",
            "type": "Таблетка",
            "schedule": {"days": [0], "times": ["08:00"]},
            "is_active": True,
            "inventory_enabled": False,
            "created_at": now,
        }
    )
    mock_db["medication_intakes"].insert_one(
        {
            "_id": ObjectId(),
            "pet_id": str(test_pet["_id"]),
            "medication_id": str(mock_db["medications"].find_one({})["_id"]),
            "date_time": now,
            "created_at": now,
            "dose_taken": 1,
            "username": "user1",
        }
    )
    headers = {"Authorization": f"Bearer {regular_user_token}"}

    courses = client.get(f"/api/medications?pet_id={test_pet['_id']}", headers=headers)
    intakes = client.get(f"/api/medications/intakes?pet_id={test_pet['_id']}", headers=headers)
    timeline = client.get(f"/api/history/timeline?pet_id={test_pet['_id']}", headers=headers)
    assert courses.status_code == 200 and intakes.status_code == 200 and timeline.status_code == 200

    wrong = []
    for name, answer in (("courses", courses), ("intakes", intakes), ("timeline", timeline)):
        for where, value in dates_in(answer.get_json()):
            wrong.append(f"{name}{where} is {value!r}")
    assert not wrong, wrong


def test_pets_and_documents_kept_speaking_them(client, regular_user_token, test_pet):
    """The other half of the rule: they already did, and must go on doing it."""
    headers = {"Authorization": f"Bearer {regular_user_token}"}
    pets = client.get("/api/pets", headers=headers)
    assert pets.status_code == 200
    for where, value in dates_in(pets.get_json()):
        assert False, f"pets{where} is {value!r}"
