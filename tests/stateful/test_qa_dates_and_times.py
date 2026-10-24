"""Dates and times travel as strict YYYY-MM-DD and HH:MM, and half of a moment is refused rather than guessed (QA B-02, B-03)."""

from datetime import datetime, timedelta

import pytest
from bson import ObjectId

from web.schemas import validate_date_logic


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("value", ["2026-1-5", "2026-9-1", "2026-01-5", "２０２６-01-05", " 2026-01-05", "2026-01-05 "])
def test_a_date_that_is_not_zero_padded_is_refused(value):
    with pytest.raises(ValueError):
        validate_date_logic(value)


def test_a_date_compares_as_text_after_validation():
    nine = validate_date_logic("2026-09-01")
    ten = validate_date_logic("2026-10-01")
    assert nine < ten


def test_a_medication_course_date_is_refused_unpadded(client, mock_db, regular_user_token, test_pet):
    response = client.post(
        "/api/medications",
        json={
            "pet_id": str(test_pet["_id"]),
            "name": "Тест",
            "type": "Таблетка",
            "schedule": {"days": [0], "times": ["08:00"]},
            "started_on": "2026-9-1",
        },
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422


def test_an_event_time_that_is_not_padded_is_refused(client, mock_db, regular_user_token, test_pet):
    response = client.post(
        "/api/events",
        json={
            "pet_id": str(test_pet["_id"]),
            "type": "weight",
            "date": datetime.now().strftime("%Y-%m-%d"),
            "time": "8:5",
            "fields": {"weight": 12.4},
            "tz": "Asia/Almaty",
        },
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422


@pytest.fixture
def course(mock_db, test_pet):
    med_id = ObjectId()
    mock_db["medications"].insert_one(
        {
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Габапентин",
            "type": "Таблетка",
            "default_dose": 1.0,
            "is_active": True,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
            "created_at": datetime.now(),
        }
    )
    return med_id


def test_moving_an_intake_with_an_empty_time_is_refused_and_does_not_move_it(
    client, mock_db, regular_user_token, course
):
    now = datetime.now().replace(second=0, microsecond=0)
    when = now - timedelta(hours=2)
    intake_id = client.post(
        f"/api/medications/{course}/log",
        json={"date": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"), "tz": "Asia/Almaty"},
        headers=_auth(regular_user_token),
    ).get_json()["id"]
    day = when.strftime("%Y-%m-%d")
    for body in ({"date": day, "time": ""}, {"date": "", "time": "10:00"}, {"date": "", "time": ""}):
        response = client.put(
            f"/api/medications/intakes/{intake_id}",
            json={**body, "tz": "Asia/Almaty"},
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 422
    assert mock_db["medication_intakes"].find_one({"_id": ObjectId(intake_id)})["date_time"] == when


def test_a_dose_logged_without_a_clock_time_is_now_to_the_minute(client, mock_db, regular_user_token, course):
    response = client.post(
        f"/api/medications/{course}/log",
        json={"date": "", "time": "", "tz": "Asia/Almaty"},
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 201
    taken = mock_db["medication_intakes"].find_one({})["date_time"]
    assert taken.second == 0 and taken.microsecond == 0


def test_a_date_without_a_time_does_not_become_now(client, mock_db, regular_user_token, course):
    response = client.post(
        f"/api/medications/{course}/log",
        json={"date": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"), "time": "", "tz": "Asia/Almaty"},
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 422
    assert mock_db["medication_intakes"].count_documents({}) == 0
