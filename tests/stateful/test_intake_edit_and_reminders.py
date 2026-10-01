"""What the dose reminders do when an intake is moved in time or taken back.

The rule behind all of it (web.medications.compute_taken_counts): a day's schedule is consumed by a plain COUNT of the
intakes of that day, in order, whatever their clock times. So moving an intake inside its day changes nothing for the
reminders, moving it to another day takes a slot from one day and gives it to the other, and deleting it gives the slot
back (and the stock it took).

A fixed scenario as in test_send_medication_reminders: Tuesday 2024-01-02, slots 08:00 and 20:00, an owner subscribed
from UTC+5 (03:00 UTC is 08:00 there).
"""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from scripts.send_medication_reminders import find_due_medication_reminders

MORNING_UTC = datetime(2024, 1, 2, 3, 0, 30, tzinfo=timezone.utc)  # 08:00:30 local
EVENING_UTC = datetime(2024, 1, 2, 15, 0, 30, tzinfo=timezone.utc)  # 20:00:30 local
EVERY_DAY = [0, 1, 2, 3, 4, 5, 6]


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
            "default_dose": 1.0,
            "is_active": True,
            "schedule": {"days": EVERY_DAY, "times": ["08:00", "20:00"]},
            "inventory_enabled": True,
            "inventory_current": 10.0,
        }
    )
    mock_db["push_subscriptions"].insert_one(
        {
            "username": "testuser",
            "endpoint": "https://push.example/e",
            "keys": {"p256dh": "a", "auth": "b"},
            "timezone": "Etc/GMT-5",
        }
    )
    return med_id


def _intake(mock_db, med_id, test_pet, local, **extra):
    """An intake as the app stores it: the local wall clock, naive."""
    inserted = mock_db["medication_intakes"].insert_one(
        {
            "medication_id": str(med_id),
            "pet_id": str(test_pet["_id"]),
            "date_time": local,
            "dose_taken": 1.0,
            "inventory_deducted": 1.0,
            "username": "testuser",
            **extra,
        }
    )
    return str(inserted.inserted_id)


def _due(mock_db, now_utc):
    return [(d["date"], d["time"]) for d in find_due_medication_reminders(mock_db, now_utc)]


def _move(client, token, intake_id, local):
    return client.put(
        f"/api/medications/intakes/{intake_id}",
        json={"date": local.strftime("%Y-%m-%d"), "time": local.strftime("%H:%M")},
        headers=_auth(token),
    )


@pytest.mark.medications
class TestMovingAnIntake:
    def test_the_slot_stays_given_when_the_time_moves_inside_the_day(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        intake = _intake(mock_db, course, test_pet, datetime(2024, 1, 2, 7, 55))
        assert _due(mock_db, MORNING_UTC) == []
        assert _move(client, regular_user_token, intake, datetime(2024, 1, 2, 7, 40)).status_code == 200
        assert _due(mock_db, MORNING_UTC) == []

    def test_moving_it_late_in_the_day_does_not_hide_the_evening_dose(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        """One dose is given. When it is said to have been given at 21:00 it is still the day's first: the 20:00 dose is
        still owed, and the reminder for it comes."""
        intake = _intake(mock_db, course, test_pet, datetime(2024, 1, 2, 7, 55))
        _move(client, regular_user_token, intake, datetime(2024, 1, 2, 21, 0))
        assert _due(mock_db, MORNING_UTC) == []
        assert _due(mock_db, EVENING_UTC) == [("2024-01-02", "20:00")]

    def test_moving_it_to_another_day_gives_the_slot_back_to_the_day_it_left(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        intake = _intake(mock_db, course, test_pet, datetime(2024, 1, 2, 7, 55))
        assert _due(mock_db, MORNING_UTC) == []
        _move(client, regular_user_token, intake, datetime(2024, 1, 1, 20, 5))
        assert _due(mock_db, MORNING_UTC) == [("2024-01-02", "08:00")]

    def test_moving_it_takes_nothing_more_from_the_stock(self, client, mock_db, regular_user_token, test_pet, course):
        intake = _intake(mock_db, course, test_pet, datetime(2024, 1, 2, 7, 55))
        _move(client, regular_user_token, intake, datetime(2024, 1, 1, 20, 5))
        assert mock_db["medications"].find_one({"_id": course})["inventory_current"] == 10.0


@pytest.mark.medications
class TestTakingAnIntakeBack:
    def test_deleting_a_mistaken_intake_brings_the_reminder_back(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        intake = _intake(mock_db, course, test_pet, datetime(2024, 1, 2, 7, 55))
        assert _due(mock_db, MORNING_UTC) == []
        assert client.delete(f"/api/medications/intakes/{intake}", headers=_auth(regular_user_token)).status_code == 200
        assert _due(mock_db, MORNING_UTC) == [("2024-01-02", "08:00")]

    def test_deleting_it_gives_back_exactly_what_it_took_from_the_stock(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        mock_db["medications"].update_one({"_id": course}, {"$set": {"inventory_current": 0.0}})
        intake = _intake(mock_db, course, test_pet, datetime(2024, 1, 2, 7, 55), dose_taken=1.0, inventory_deducted=0.5)
        client.delete(f"/api/medications/intakes/{intake}", headers=_auth(regular_user_token))
        assert mock_db["medications"].find_one({"_id": course})["inventory_current"] == 0.5

    def test_a_skip_taken_back_gives_the_slot_back_and_nothing_to_the_stock(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        intake = _intake(
            mock_db, course, test_pet, datetime(2024, 1, 2, 7, 55), skipped=True, dose_taken=0.0, inventory_deducted=0.0
        )
        assert _due(mock_db, MORNING_UTC) == []
        client.delete(f"/api/medications/intakes/{intake}", headers=_auth(regular_user_token))
        assert _due(mock_db, MORNING_UTC) == [("2024-01-02", "08:00")]
        assert mock_db["medications"].find_one({"_id": course})["inventory_current"] == 10.0

    def test_a_reminder_already_pushed_is_not_pushed_again_when_the_intake_is_taken_back(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        """The push went at 08:00; the dose was marked at 08:10 by mistake and taken back at 08:20. The dose is due again
        (the widget says so), but the same slot is not announced twice."""
        mock_db["medication_reminders_sent"].insert_one(
            {"medication_id": str(course), "date": "2024-01-02", "time": "08:00"}
        )
        intake = _intake(mock_db, course, test_pet, datetime(2024, 1, 2, 8, 10))
        client.delete(f"/api/medications/intakes/{intake}", headers=_auth(regular_user_token))
        assert _due(mock_db, MORNING_UTC) == []
