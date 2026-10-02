"""Which scheduled doses are handled: an intake belongs to a slot, a dose marked twice is asked about,
and a dose forgotten at night is still offered after midnight.

The behaviours below are the failures found in the audit: adding an early time to the schedule turned a dose already
given into a missed one, a dose given late for the morning closed the evening slot, two people marking the same
morning both went through, and at 00:10 the evening dose of yesterday closed this morning's.
"""

from datetime import datetime

import pytest
from bson import ObjectId

from web.dose_slots import closed_slots, open_slots


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def at(hour, minute=0, day=2):
    return datetime(2026, 10, day, hour, minute)


def made(hour, minute=0, **extra):
    return {"date_time": at(hour, minute), **extra}


class TestWhichSlotAnIntakeCloses:
    def test_an_early_time_added_to_the_schedule_does_not_turn_a_given_dose_into_a_missed_one(self):
        # 08:05 was the 08:00 dose. A 06:00 slot added afterwards stays open, 08:00 stays closed.
        assert open_slots(["06:00", "08:00"], [made(8, 5)]) == ["06:00"]

    def test_a_dose_given_between_slots_closes_the_nearer(self):
        assert open_slots(["08:00", "20:00"], [made(14, 30)]) == ["08:00"]
        assert open_slots(["08:00", "20:00"], [made(11, 0)]) == ["20:00"]

    def test_a_dose_marked_for_a_slot_closes_that_slot_whenever_it_was_given(self):
        assert open_slots(["08:00", "20:00"], [made(14, 30, slot_date="2026-10-02", slot_time="08:00")]) == ["20:00"]

    def test_every_intake_closes_one_slot_and_a_surplus_closes_nothing_more(self):
        assert open_slots(["08:00", "20:00"], [made(8, 0), made(8, 1)]) == []
        assert open_slots(["08:00"], [made(8, 0), made(8, 1), made(8, 2)]) == []

    def test_a_skip_is_an_intake_too(self):
        assert open_slots(["08:00", "20:00"], [made(8, 0, skipped=True)]) == ["20:00"]

    def test_two_loose_doses_close_their_own_slots_in_the_order_they_happened(self):
        assert closed_slots(["08:00", "12:00", "20:00"], [made(19, 40), made(8, 20)]) == {"08:00", "20:00"}

    def test_an_explicit_slot_the_schedule_no_longer_has_is_treated_as_a_loose_dose(self):
        assert open_slots(["08:00", "20:00"], [made(8, 10, slot_date="2026-10-02", slot_time="07:00")]) == ["20:00"]


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
            "created_at": datetime(2026, 9, 1),
        }
    )
    return med_id


def _log(client, token, med_id, when, **extra):
    return client.post(
        f"/api/medications/{med_id}/log",
        json={"date": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"), **extra},
        headers=_auth(token),
    )


def _upcoming(client, token, pet, now):
    response = client.get(
        f"/api/medications/upcoming?pet_id={pet['_id']}&client_datetime={now.strftime('%Y-%m-%dT%H:%M:00')}",
        headers=_auth(token),
    )
    assert response.status_code == 200
    return [(d["date"], d["time"], d["carried_over"]) for d in response.get_json()["doses"]]


@pytest.mark.medications
class TestTheSameDoseMarkedTwice:
    def test_a_second_mark_close_in_time_is_refused_with_who_and_when(
        self, client, mock_db, regular_user_token, course
    ):
        assert _log(client, regular_user_token, course, at(10, 51)).status_code == 201
        second = _log(client, regular_user_token, course, at(10, 59))
        assert second.status_code == 409
        body = second.get_json()
        assert body["code"] == "duplicate_intake"
        assert body["existing"] == {"date": "2026-10-02", "time": "10:51", "username": "testuser", "own": True}
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(course)}) == 1
        assert mock_db["medications"].find_one({"_id": course})["inventory_current"] == 9.0

    def test_another_person_is_named_as_another_person(self, client, mock_db, regular_user_token, course):
        mock_db["medication_intakes"].insert_one(
            {"medication_id": str(course), "date_time": at(10, 51), "dose_taken": 1.0, "username": "anna"}
        )
        body = _log(client, regular_user_token, course, at(10, 55)).get_json()
        assert body["existing"]["username"] == "anna" and body["existing"]["own"] is False

    def test_force_records_it_anyway(self, client, mock_db, regular_user_token, course):
        _log(client, regular_user_token, course, at(10, 51))
        assert _log(client, regular_user_token, course, at(10, 59), force=True).status_code == 201
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(course)}) == 2

    def test_doses_far_apart_are_two_doses(self, client, regular_user_token, course):
        assert _log(client, regular_user_token, course, at(8, 0)).status_code == 201
        assert _log(client, regular_user_token, course, at(20, 0)).status_code == 201

    def test_a_skip_is_not_a_dose_and_is_not_asked_about(self, client, regular_user_token, course):
        _log(client, regular_user_token, course, at(10, 51))
        assert _log(client, regular_user_token, course, at(10, 55), skipped=True).status_code == 201

    def test_a_course_with_no_schedule_can_be_given_again_at_once(self, client, mock_db, regular_user_token, test_pet):
        prn = ObjectId()
        mock_db["medications"].insert_one(
            {"_id": prn, "pet_id": str(test_pet["_id"]), "name": "При боли", "default_dose": 1.0, "is_active": True}
        )
        assert _log(client, regular_user_token, prn, at(10, 51)).status_code == 201
        assert _log(client, regular_user_token, prn, at(10, 55)).status_code == 201

    def test_the_slot_a_dose_was_for_is_kept(self, client, mock_db, regular_user_token, course):
        _log(client, regular_user_token, course, at(14, 30), slot_date="2026-10-02", slot_time="08:00")
        stored = mock_db["medication_intakes"].find_one({"medication_id": str(course)})
        assert (stored["slot_date"], stored["slot_time"]) == ("2026-10-02", "08:00")


@pytest.mark.medications
class TestWhatTheWidgetOffers:
    def test_the_slot_a_late_dose_was_for_is_the_one_that_closes(self, client, regular_user_token, test_pet, course):
        now = at(14, 40)
        assert [d[:2] for d in _upcoming(client, regular_user_token, test_pet, now)][:2] == [
            ("2026-10-02", "08:00"),
            ("2026-10-02", "20:00"),
        ]
        _log(client, regular_user_token, course, now, slot_date="2026-10-02", slot_time="08:00")
        assert [d[:2] for d in _upcoming(client, regular_user_token, test_pet, now)] == [("2026-10-02", "20:00")]

    def test_a_schedule_edited_after_a_dose_does_not_ask_for_it_again(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        _log(client, regular_user_token, course, at(8, 5))
        mock_db["medications"].update_one({"_id": course}, {"$set": {"schedule.times": ["06:00", "08:00", "20:00"]}})
        offered = [d[:2] for d in _upcoming(client, regular_user_token, test_pet, at(8, 30))]
        assert ("2026-10-02", "08:00") not in offered
        assert ("2026-10-02", "06:00") in offered

    def test_yesterdays_evening_dose_is_still_offered_after_midnight(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        mock_db["medications"].update_one({"_id": course}, {"$set": {"schedule.times": ["08:00", "23:30"]}})
        offered = _upcoming(client, regular_user_token, test_pet, at(0, 10, day=3))
        assert offered[0] == ("2026-10-02", "23:30", True)
        assert ("2026-10-03", "08:00", False) in offered

    def test_giving_it_closes_yesterdays_slot_and_not_this_mornings(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        mock_db["medications"].update_one({"_id": course}, {"$set": {"schedule.times": ["08:00", "23:30"]}})
        now = at(0, 10, day=3)
        assert (
            _log(client, regular_user_token, course, now, slot_date="2026-10-02", slot_time="23:30").status_code == 201
        )
        offered = _upcoming(client, regular_user_token, test_pet, now)
        assert all(not carried for _, _, carried in offered)
        assert ("2026-10-03", "08:00", False) in offered

    def test_it_is_not_carried_over_for_ever(self, client, mock_db, regular_user_token, test_pet, course):
        mock_db["medications"].update_one({"_id": course}, {"$set": {"schedule.times": ["08:00", "23:30"]}})
        offered = _upcoming(client, regular_user_token, test_pet, at(6, 0, day=3))
        assert all(not carried for _, _, carried in offered)

    def test_a_dose_marked_yesterday_is_not_carried(self, client, mock_db, regular_user_token, test_pet, course):
        mock_db["medications"].update_one({"_id": course}, {"$set": {"schedule.times": ["08:00", "23:30"]}})
        _log(client, regular_user_token, course, at(23, 40))
        assert all(not c for _, _, c in _upcoming(client, regular_user_token, test_pet, at(0, 10, day=3)))


@pytest.mark.medications
class TestTheCourseList:
    def test_it_says_which_slots_are_still_open_today(self, client, mock_db, regular_user_token, test_pet, course):
        _log(client, regular_user_token, course, at(14, 30), slot_date="2026-10-02", slot_time="08:00")
        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2026-10-02", headers=_auth(regular_user_token)
        )
        med = response.get_json()["medications"][0]
        assert med["scheduled_today"] is True
        assert med["open_slots_today"] == ["20:00"]

    def test_a_course_not_scheduled_today_has_no_open_slots(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        # 2026-10-02 is a Friday (weekday 4).
        mock_db["medications"].update_one({"_id": course}, {"$set": {"schedule.days": [0, 1]}})
        med = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2026-10-02", headers=_auth(regular_user_token)
        ).get_json()["medications"][0]
        assert med["scheduled_today"] is False and med["open_slots_today"] == []

    def test_a_finished_course_has_nothing_scheduled_today(self, client, mock_db, regular_user_token, test_pet, course):
        mock_db["medications"].update_one({"_id": course}, {"$set": {"is_active": False, "ended_on": "2026-10-02"}})
        med = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2026-10-02", headers=_auth(regular_user_token)
        ).get_json()["medications"][0]
        assert med["scheduled_today"] is False and med["open_slots_today"] == []

    def test_the_last_mark_carries_the_zone_of_its_clock(self, client, mock_db, regular_user_token, test_pet, course):
        mock_db["medication_intakes"].insert_one(
            {
                "medication_id": str(course),
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2026, 10, 2, 8, 5),
                "dose_taken": 1,
                "username": "testuser",
                "tz": "Europe/Moscow",
            }
        )
        med = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2026-10-02", headers=_auth(regular_user_token)
        ).get_json()["medications"][0]
        assert med["last_taken_at"] == "2026-10-02 08:05" and med["last_taken_tz"] == "Europe/Moscow"

    def test_every_slot_closed_leaves_none_open(self, client, regular_user_token, test_pet, course):
        _log(client, regular_user_token, course, at(8, 5))
        _log(client, regular_user_token, course, at(20, 5))
        med = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2026-10-02", headers=_auth(regular_user_token)
        ).get_json()["medications"][0]
        assert med["open_slots_today"] == []


@pytest.mark.medications
class TestAnOverdueDoseIsShownOnTheTab:
    """The tab and the pet switcher say a dose is overdue: unmarked, and more than an hour after its time."""

    def _alerts(self, client, token, pet, now):
        # The endpoint reads the zone's clock; the function behind it takes the moment, which is what is tested.
        from web.medications import has_overdue_dose
        import web.app as app

        return has_overdue_dose(app.db, str(pet["_id"]), now)

    def test_a_dose_more_than_an_hour_late_is_overdue_a_minute_late_is_not(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        assert self._alerts(client, regular_user_token, test_pet, at(8, 1)) is False
        assert self._alerts(client, regular_user_token, test_pet, at(9, 5)) is True

    def test_marked_it_is_not(self, client, mock_db, regular_user_token, test_pet, course):
        _log(client, regular_user_token, course, at(8, 10), slot_date="2026-10-02", slot_time="08:00")
        assert self._alerts(client, regular_user_token, test_pet, at(9, 30)) is False
        assert self._alerts(client, regular_user_token, test_pet, at(21, 30)) is True  # the 20:00 one

    def test_a_finished_course_and_a_day_off_are_not(self, client, mock_db, regular_user_token, test_pet, course):
        mock_db["medications"].update_one({"_id": course}, {"$set": {"schedule.days": [0, 1]}})  # 2026-10-02 is Friday
        assert self._alerts(client, regular_user_token, test_pet, at(12, 0)) is False
        mock_db["medications"].update_one(
            {"_id": course}, {"$set": {"schedule.days": [0, 1, 2, 3, 4, 5, 6], "is_active": False}}
        )
        assert self._alerts(client, regular_user_token, test_pet, at(12, 0)) is False

    def test_last_evenings_dose_counts_for_a_few_hours_after_midnight_only(
        self, client, mock_db, regular_user_token, test_pet, course
    ):
        mock_db["medications"].update_one({"_id": course}, {"$set": {"schedule.times": ["23:30"]}})
        assert self._alerts(client, regular_user_token, test_pet, at(0, 40, day=3)) is True
        assert self._alerts(client, regular_user_token, test_pet, at(8, 0, day=3)) is False

    def test_the_endpoint_carries_it(self, client, mock_db, regular_user_token, test_pet, course):
        # Any real clock: a course with a time that is certainly past an hour ago today only when it is late in the day,
        # so the answer is checked for its shape, and the function above for its logic.
        response = client.get(f"/api/pets/{test_pet['_id']}/medical-card/alerts", headers=_auth(regular_user_token))
        assert set(response.get_json()["alerts"]) == {"vaccination", "parasite", "medication"}
