"""«По необходимости» as a stored sign of its own, not read out of an empty schedule.

A course with the sign may keep days and times (they show in the card), and
nothing is due or reminded about it. A course written before the sign came
kept its mode in the schedule: no times meant «по необходимости». Those are
read that way still, so no old course loses its doses.
"""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from web.medications import is_as_needed


def _insert_course(mock_db, pet_id, name, times, days, as_needed=..., owner="testuser"):
    doc = {
        "name": name,
        "type": "Таблетка",
        "pet_id": pet_id,
        "schedule": {"days": days, "times": times},
        "is_active": True,
        "inventory_enabled": False,
        "created_at": datetime.now(timezone.utc),
        "owner": owner,
    }
    if as_needed is not ...:
        doc["as_needed"] = as_needed
    return mock_db["medications"].insert_one(doc).inserted_id


@pytest.mark.medications
class TestAsNeededSign:
    def test_course_stores_and_returns_the_sign(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        med_id = _insert_course(mock_db, pet_id, "По расписанию", ["08:00"], [0, 1, 2, 3, 4, 5, 6], as_needed=False)

        response = client.put(
            f"/api/medications/{med_id}",
            json={"as_needed": True, "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]}},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        # The schedule came along and stayed.
        stored = mock_db["medications"].find_one({"_id": med_id})
        assert stored["as_needed"] is True
        assert stored["schedule"]["times"] == ["08:00"]

        listing = client.get(
            f"/api/medications?pet_id={pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        item = listing.get_json()["medications"][0]
        assert item["as_needed"] is True

    def test_sign_alone_keeps_the_course_out_of_today(self, client, mock_db, regular_user_token, test_pet):
        """The sign decides, so a course «по необходимости» with a schedule is not due today."""
        pet_id = str(test_pet["_id"])
        _insert_course(mock_db, pet_id, "По необходимости", ["08:00"], [0, 1, 2, 3, 4, 5, 6], as_needed=True)

        response = client.get(
            f"/api/medications?pet_id={pet_id}&client_date=2026-01-05",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        item = response.get_json()["medications"][0]
        assert item["as_needed"] is True
        assert item["scheduled_today"] is False
        assert item.get("open_slots_today") in (None, [])

    def test_sign_alone_keeps_the_course_out_of_upcoming(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        _insert_course(mock_db, pet_id, "По необходимости", ["08:00"], [0, 1, 2, 3, 4, 5, 6], as_needed=True)

        response = client.get(
            f"/api/medications/upcoming?pet_id={pet_id}&client_datetime=2026-01-05T07:00:00",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        assert response.get_json()["doses"] == []

    def test_course_without_the_sign_reads_as_needed_from_its_empty_schedule(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """A course written before the sign keeps its doses and is not due today."""
        pet_id = str(test_pet["_id"])
        _insert_course(mock_db, pet_id, "Старый", [], [])

        response = client.get(
            f"/api/medications?pet_id={pet_id}&client_date=2026-01-05",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        item = response.get_json()["medications"][0]
        assert item["as_needed"] is True
        assert item["scheduled_today"] is False

    def test_old_course_with_times_stays_due(self, client, mock_db, regular_user_token, test_pet):
        """The other half of the old rule: times meant a schedule, and its doses stay."""
        pet_id = str(test_pet["_id"])
        _insert_course(mock_db, pet_id, "Старый по расписанию", ["08:00"], [0, 1, 2, 3, 4, 5, 6])

        response = client.get(
            f"/api/medications?pet_id={pet_id}&client_date=2026-01-05",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        item = response.get_json()["medications"][0]
        assert item["as_needed"] is False
        assert item["scheduled_today"] is True

    def test_intake_can_be_marked_twice_in_needed_mode(self, client, mock_db, regular_user_token, test_pet):
        """A course «по необходимости» is given when it is given: no «already marked» question."""
        pet_id = str(test_pet["_id"])
        med_id = _insert_course(mock_db, pet_id, "По необходимости", ["08:00"], [0, 1, 2, 3, 4, 5, 6], as_needed=True)

        for _ in range(2):
            response = client.post(
                f"/api/medications/{med_id}/log",
                json={"date": "2026-01-05", "time": "09:00"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
            assert response.status_code == 201, response.get_json()


@pytest.mark.usefixtures("client")
class TestACourseFromAnOlderClient:
    """An installed app of the previous version does not send the flag at all.

    Its as-needed course has no times and says nothing about the mode. If the
    server stored «not as needed» for it, the course would turn into a schedule
    with no time in it: no way to give a dose by hand, and the card would say
    «В выбранные дни» with nothing after it.
    """

    def _create(self, client, headers, pet_id, times: list[str]):
        return client.post(
            "/api/medications",
            json={
                "pet_id": str(pet_id),
                "name": "Курс без признака",
                "type": "Таблетка",
                "default_dose": 1,
                "dose_unit": "таб",
                "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": times},
                "is_active": True,
            },
            headers=headers,
        )

    def test_a_course_without_times_stays_as_needed(self, client, regular_user_token, test_pet, mock_db):
        response = self._create(client, {"Authorization": f"Bearer {regular_user_token}"}, test_pet["_id"], [])
        assert response.status_code == 201
        stored = mock_db["medications"].find_one({"_id": ObjectId(response.get_json()["id"])})
        assert "as_needed" not in stored, stored
        assert is_as_needed(stored) is True

    def test_a_course_with_times_stays_scheduled(self, client, regular_user_token, test_pet, mock_db):
        response = self._create(client, {"Authorization": f"Bearer {regular_user_token}"}, test_pet["_id"], ["08:00"])
        stored = mock_db["medications"].find_one({"_id": ObjectId(response.get_json()["id"])})
        assert "as_needed" not in stored
        assert is_as_needed(stored) is False

    def test_the_flag_the_client_did_send_is_stored_as_given(self, client, regular_user_token, test_pet, mock_db):
        response = client.post(
            "/api/medications",
            json={
                "pet_id": str(test_pet["_id"]),
                "name": "Курс с признаком",
                "type": "Таблетка",
                "default_dose": 1,
                "dose_unit": "таб",
                "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
                "as_needed": True,
                "is_active": True,
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        stored = mock_db["medications"].find_one({"_id": ObjectId(response.get_json()["id"])})
        assert stored["as_needed"] is True
        # Расписание при этом остаётся в курсе: режим и расписание теперь независимы.
        assert stored["schedule"]["times"] == ["08:00"]
        assert is_as_needed(stored) is True
