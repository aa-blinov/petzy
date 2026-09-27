"""A dose skipped on purpose, and an intake moved to when it was really given."""

from datetime import datetime, timedelta

import pytest
from bson import ObjectId


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


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
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00", "20:00"]},
            "inventory_enabled": True,
            "inventory_current": 10.0,
            "created_at": datetime.now(),
        }
    )
    return med_id


def _log(client, token, med_id, when, **extra):
    return client.post(
        f"/api/medications/{med_id}/log",
        json={"date": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"), **extra},
        headers=_auth(token),
    )


@pytest.mark.medications
class TestSkip:
    def test_a_skip_takes_nothing_from_the_stock(self, client, mock_db, regular_user_token, course):
        response = _log(client, regular_user_token, course, datetime.now(), skipped=True)
        assert response.status_code == 201
        assert mock_db["medications"].find_one({"_id": course})["inventory_current"] == 10.0
        intake = mock_db["medication_intakes"].find_one({"medication_id": str(course)})
        assert intake["skipped"] is True
        assert intake["dose_taken"] == 0
        assert intake["inventory_deducted"] == 0

    def test_a_skip_handles_the_slot_but_is_not_the_last_dose(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        now = datetime.now()
        _log(client, regular_user_token, course, now - timedelta(minutes=5))
        _log(client, regular_user_token, course, now, skipped=True)

        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date={now.strftime('%Y-%m-%d')}",
            headers=_auth(regular_user_token),
        )
        med = response.get_json()["medications"][0]
        assert med["intakes_today"] == 2
        assert med["last_taken_at"] == (now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M")

    def test_both_slots_handled_leaves_nothing_due_today(self, client, regular_user_token, test_pet, course):
        now = datetime.now()
        _log(client, regular_user_token, course, now, skipped=True)
        _log(client, regular_user_token, course, now, skipped=True)
        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime={now.strftime('%Y-%m-%dT%H:%M')}:00",
            headers=_auth(regular_user_token),
        )
        today = now.strftime("%Y-%m-%d")
        assert [d for d in response.get_json()["doses"] if d["date"] == today] == []

    def test_a_skip_is_not_counted_in_stats(self, client, regular_user_token, test_pet, course):
        now = datetime.now()
        _log(client, regular_user_token, course, now)
        _log(client, regular_user_token, course, now, skipped=True)
        response = client.get(
            f"/api/stats/health?pet_id={test_pet['_id']}&type=medications&days=7",
            headers=_auth(regular_user_token),
        )
        assert len(response.get_json()["data"]) == 1

    def test_the_feed_shows_the_skip(self, client, regular_user_token, test_pet, course):
        _log(client, regular_user_token, course, datetime.now(), skipped=True)
        response = client.get(
            f"/api/history/timeline?pet_id={test_pet['_id']}",
            headers=_auth(regular_user_token),
        )
        items = response.get_json()["items"]
        assert items[0]["record_type"] == "medications"
        assert items[0]["skipped"] is True

    def test_deleting_a_skip_gives_nothing_back(self, client, mock_db, regular_user_token, course):
        intake_id = _log(client, regular_user_token, course, datetime.now(), skipped=True).get_json()["id"]
        response = client.delete(f"/api/medications/intakes/{intake_id}", headers=_auth(regular_user_token))
        assert response.status_code == 200
        assert mock_db["medications"].find_one({"_id": course})["inventory_current"] == 10.0


@pytest.mark.medications
class TestIntakeTime:
    def test_an_intake_moves_to_the_time_it_was_given(self, client, mock_db, regular_user_token, course):
        now = datetime.now().replace(second=0, microsecond=0)
        intake_id = _log(client, regular_user_token, course, now).get_json()["id"]
        given = now - timedelta(hours=3)
        response = client.put(
            f"/api/medications/intakes/{intake_id}",
            json={"date": given.strftime("%Y-%m-%d"), "time": given.strftime("%H:%M")},
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 200
        intake = mock_db["medication_intakes"].find_one({"_id": ObjectId(intake_id)})
        assert intake["date_time"] == given
        # Only the time: the stock it took stays taken.
        assert intake["dose_taken"] == 1.0
        assert mock_db["medications"].find_one({"_id": course})["inventory_current"] == 9.0

    def test_a_bad_time_is_refused(self, client, regular_user_token, course):
        intake_id = _log(client, regular_user_token, course, datetime.now()).get_json()["id"]
        response = client.put(
            f"/api/medications/intakes/{intake_id}",
            json={"date": "2026-02-30", "time": "25:00"},
            headers=_auth(regular_user_token),
        )
        assert response.status_code in (400, 422)

    def test_a_stranger_cannot_move_it(self, client, mock_db, regular_user_token, course):
        from web.security import create_access_token

        intake_id = _log(client, regular_user_token, course, datetime.now()).get_json()["id"]
        mock_db["users"].insert_one({"username": "stranger", "is_active": True, "password_hash": "x"})
        response = client.put(
            f"/api/medications/intakes/{intake_id}",
            json={"date": "2026-01-01", "time": "08:00"},
            headers=_auth(create_access_token("stranger")),
        )
        assert response.status_code in (403, 404)


@pytest.mark.medications
def test_upcoming_doses_are_in_time_order_across_courses(client, mock_db, regular_user_token, test_pet, course):
    mock_db["medications"].insert_one(
        {
            "pet_id": str(test_pet["_id"]),
            "name": "Омега",
            "type": "Капсула",
            "is_active": True,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["07:00"]},
            "inventory_enabled": False,
        }
    )
    day = datetime.now().strftime("%Y-%m-%d")
    response = client.get(
        f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime={day}T06:00:00",
        headers=_auth(regular_user_token),
    )
    times = [d["time"] for d in response.get_json()["doses"] if d["date"] == day]
    assert times == ["07:00", "08:00", "20:00"]
