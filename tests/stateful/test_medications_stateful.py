"""Stateful tests for medication courses.

Unlike a plain request/response contract check, these assert on how
*persisted state* evolves across a sequence of operations — specifically
the inventory-decrement compensation and optimistic-concurrency retry
logic in `log_intake`, which only ever runs when something else already
went wrong (a lost update race, or the intake insert itself failing).
Both paths are exercised here by mocking the specific PyMongo call that
needs to misbehave, since mongomock has no way to simulate a genuine
concurrent write: the same mock stands in for the second phone in the two
races below (one slot closed twice, one pack entered twice).
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from bson import ObjectId

import web.app as app
from web.db import ensure_indexes


@pytest.fixture
def indexed(mock_db):
    """The database with the indexes the app declares, so a unique one really bites."""
    with patch("web.db.db", mock_db):
        ensure_indexes()
    return mock_db


@pytest.mark.medications
class TestMedicationInventoryStateConsistency:
    """Inventory must never end up decremented for an intake that doesn't exist."""

    def test_log_intake_conflict_exhausts_retries_leaves_inventory_untouched(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """All 3 optimistic-lock retries losing the race returns 409 and
        touches neither the inventory nor the intake collection.

        `update_one`'s filter includes the last-read `inventory_current`
        as an optimistic-lock condition; a concurrent writer changing it
        first makes `matched_count == 0`. Forcing that on every attempt
        (impossible to trigger with mongomock's single-threaded writes)
        simulates sustained contention.
        """
        med_id = ObjectId()
        mock_db["medications"].insert_one(
            {
                "_id": med_id,
                "pet_id": str(test_pet["_id"]),
                "name": "Antibiotic",
                "inventory_enabled": True,
                "inventory_current": 9.0,
                "owner": "testuser",
            }
        )

        now = datetime.now(timezone.utc)
        log_data = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "dose_taken": 1.0,
            "tz": "Asia/Almaty",
        }

        never_matches = MagicMock(matched_count=0)
        with patch.object(app.db.medications, "update_one", return_value=never_matches):
            response = client.post(
                f"/api/medications/{med_id}/log",
                json=log_data,
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 409
        data = response.get_json()
        assert "error" in data

        # Inventory must read back exactly as it started — the mocked
        # update_one never actually wrote anything, but this pins down
        # that the code path never falls through to a write it shouldn't.
        med = mock_db["medications"].find_one({"_id": med_id})
        assert med["inventory_current"] == 9.0
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(med_id)}) == 0

    def test_log_intake_restores_inventory_when_intake_insert_fails(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """If the intake insert fails after inventory was already
        decremented, the decrement must be compensated back — otherwise
        stock silently vanishes for a dose that was never recorded.
        """
        med_id = ObjectId()
        mock_db["medications"].insert_one(
            {
                "_id": med_id,
                "pet_id": str(test_pet["_id"]),
                "name": "Antibiotic",
                "inventory_enabled": True,
                "inventory_current": 9.0,
                "owner": "testuser",
            }
        )

        now = datetime.now(timezone.utc)
        log_data = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "dose_taken": 1.0,
            "tz": "Asia/Almaty",
        }

        with patch.object(app.db.medication_intakes, "insert_one", side_effect=RuntimeError("simulated write failure")):
            response = client.post(
                f"/api/medications/{med_id}/log",
                json=log_data,
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        # The failure isn't swallowed into a false "success" — the
        # outer handler turns the re-raised exception into a 500.
        assert response.status_code == 500

        # But the compensation still has to have happened: inventory
        # back to its pre-decrement value, and no orphaned intake.
        med = mock_db["medications"].find_one({"_id": med_id})
        assert med["inventory_current"] == 9.0
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(med_id)}) == 0

    def test_log_intake_succeeds_normally_without_mocks(self, client, mock_db, regular_user_token, test_pet):
        """Control case: with nothing mocked, a normal intake decrements
        inventory by exactly the dose and is recorded once. Anchors the
        two failure-path tests above against a working baseline.
        """
        med_id = ObjectId()
        mock_db["medications"].insert_one(
            {
                "_id": med_id,
                "pet_id": str(test_pet["_id"]),
                "name": "Antibiotic",
                "inventory_enabled": True,
                "inventory_current": 9.0,
                "owner": "testuser",
            }
        )

        now = datetime.now(timezone.utc)
        log_data = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "dose_taken": 1.0,
            "tz": "Asia/Almaty",
        }

        response = client.post(
            f"/api/medications/{med_id}/log",
            json=log_data,
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        med = mock_db["medications"].find_one({"_id": med_id})
        assert med["inventory_current"] == 8.0
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(med_id)}) == 1


@pytest.mark.medications
class TestOneSlotClosedByTwoPhonesAtOnce:
    """The check and the write are two moments, and the other phone's mark lands between them.

    Both requests see the slot open and both write it: the unique slot index (web/db.py) is what stops the
    second one, so it has to be the answer of the check the user already knows.
    """

    @pytest.fixture
    def course(self, indexed, test_pet):
        med_id = ObjectId()
        indexed["medications"].insert_one(
            {
                "_id": med_id,
                "pet_id": str(test_pet["_id"]),
                "name": "Antibiotic",
                "type": "Таблетка",
                "default_dose": 1.0,
                "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00", "20:00"]},
                "inventory_enabled": True,
                "inventory_current": 30.0,
                "owner": "testuser",
            }
        )
        return med_id

    def _mark(self, client, token, med_id, **extra):
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")
        return client.post(
            f"/api/medications/{med_id}/log",
            json={
                "date": day,
                "time": now.strftime("%H:%M"),
                "dose_taken": 1.0,
                "slot_date": day,
                "slot_time": "08:00",
                "tz": "Asia/Almaty",
                **extra,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

    def test_the_other_phone_mark_is_answered_not_stored_twice(self, client, indexed, regular_user_token, course):
        real_insert = indexed["medication_intakes"].insert_one

        def other_phone_first(doc):
            real_insert({**doc, "username": "anna"})
            return real_insert(doc)

        with patch.object(app.db.medication_intakes, "insert_one", side_effect=other_phone_first):
            response = self._mark(client, regular_user_token, course)

        assert response.status_code == 409
        answer = response.get_json()
        assert answer["code"] == "duplicate_intake"
        assert answer["existing"] == {
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "time": "08:00",
            "username": "anna",
            "own": False,
            "slot": True,
        }
        assert indexed["medication_intakes"].count_documents({"medication_id": str(course)}) == 1
        # The dose the refused mark had already taken went back to the shelf.
        assert indexed["medications"].find_one({"_id": course})["inventory_current"] == 30.0

    def test_a_slot_written_a_second_time_on_purpose_is_still_written(
        self, client, indexed, regular_user_token, course
    ):
        # ``force``: the person was shown who marked that slot and said to record it anyway. The index
        # leaves those marks out, or the answer would be a 409 to someone who already said yes.
        assert self._mark(client, regular_user_token, course).status_code == 201
        assert self._mark(client, regular_user_token, course, force=True).status_code == 201
        assert indexed["medication_intakes"].count_documents({"medication_id": str(course)}) == 2
        assert indexed["medications"].find_one({"_id": course})["inventory_current"] == 28.0

    def test_moving_a_mark_lets_its_slot_be_marked_again(self, client, indexed, regular_user_token, course):
        """Correcting the time of a mark gives the slot back.

        Moved to the evening the mark no longer names a slot, so it closes the one nearest its new
        time, the evening dose. The morning is free again and has to be markable. Had the slot key
        stayed on the document, the unique index would keep 08:00 closed by a mark that no longer
        points at it, and the answer would be «уже отмечен» about nothing.
        """
        assert self._mark(client, regular_user_token, course).status_code == 201
        intake_id = indexed["medication_intakes"].find_one({"medication_id": str(course)})["_id"]
        moved = client.put(
            f"/api/medications/intakes/{intake_id}",
            json={"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "time": "19:00", "tz": "UTC"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert moved.status_code == 200
        assert self._mark(client, regular_user_token, course).status_code == 201

    def test_a_slot_the_course_no_longer_has_is_still_the_same_dose(self, client, indexed, regular_user_token, course):
        """The evening dose was taken off the schedule while a stale copy of it was still on a screen.

        The check answers from the times the course has now, so it says nothing about 20:00. The
        index still knows the slot is closed, and a 500 would be a worse answer than «уже отмечен».
        """
        real_insert = indexed["medication_intakes"].insert_one

        def other_phone_first(doc):
            real_insert({**doc, "username": "anna"})
            return real_insert(doc)

        indexed["medications"].update_one({"_id": course}, {"$set": {"schedule.times": ["08:00"]}})
        with patch.object(app.db.medication_intakes, "insert_one", side_effect=other_phone_first):
            response = self._mark(client, regular_user_token, course, slot_time="20:00")

        assert response.status_code == 409
        answer = response.get_json()
        assert answer["code"] == "duplicate_intake"
        assert answer["existing"]["username"] == "anna"
        assert answer["existing"]["time"] == "20:00"
        assert answer["existing"]["slot"] is True
        assert indexed["medication_intakes"].count_documents({"medication_id": str(course)}) == 1


@pytest.mark.medications
class TestTwoPacksEnteredAtOnce:
    """The first pack of a course starts its count, and the second one must not replace it with its own."""

    def test_a_pack_that_lands_next_to_another_one_is_added_to_it(self, client, mock_db, regular_user_token, test_pet):
        med_id = ObjectId()
        mock_db["medications"].insert_one(
            {
                "_id": med_id,
                "pet_id": str(test_pet["_id"]),
                "name": "Antibiotic",
                "type": "Таблетка",
                "default_dose": 1.0,
                "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
                # As a course comes out of the form: counting is off until a pack is entered.
                "inventory_enabled": False,
                "inventory_current": None,
                "owner": "testuser",
            }
        )
        real_update = mock_db["medications"].update_one
        raced = []

        def other_phone_first(filter, update, **kwargs):
            if not raced:
                raced.append(True)
                # The other phone's pack reaches the database between our reading and our writing.
                real_update({"_id": med_id}, {"$set": {"inventory_current": 30.0, "inventory_enabled": True}})
            return real_update(filter, update, **kwargs)

        with patch.object(app.db.medications, "update_one", side_effect=other_phone_first):
            response = client.post(
                f"/api/medications/{med_id}/restock",
                json={"amount": 30},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert response.get_json()["inventory_current"] == 60.0
        assert mock_db["medications"].find_one({"_id": med_id})["inventory_current"] == 60.0

    def test_packs_entered_one_after_another_are_all_counted(self, client, mock_db, regular_user_token, test_pet):
        med_id = ObjectId()
        mock_db["medications"].insert_one(
            {
                "_id": med_id,
                "pet_id": str(test_pet["_id"]),
                "name": "Antibiotic",
                "type": "Таблетка",
                "default_dose": 1.0,
                "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
                "inventory_enabled": False,
                "inventory_current": None,
                "owner": "testuser",
            }
        )
        headers = {"Authorization": f"Bearer {regular_user_token}"}

        first = client.post(f"/api/medications/{med_id}/restock", json={"amount": 30}, headers=headers)
        second = client.post(f"/api/medications/{med_id}/restock", json={"amount": 30}, headers=headers)

        assert first.get_json()["inventory_current"] == 30.0
        assert second.get_json()["inventory_current"] == 60.0
        assert mock_db["medications"].find_one({"_id": med_id})["inventory_current"] == 60.0


@pytest.mark.medications
class TestWhatOneCourseSaysAboutItself:
    """The form reads ``course_status`` to offer «Возобновить курс»; without it a finished course
    offers «Завершить курс» instead (frontend/src/pages/MedicationForm.tsx)."""

    @pytest.mark.parametrize(
        ("stored", "expected"),
        [({}, "active"), ({"is_active": False}, "ended"), ({"ended_on": "2020-01-01"}, "ended")],
    )
    def test_the_detail_answer_carries_the_course_status(
        self, client, mock_db, regular_user_token, test_pet, stored, expected
    ):
        med_id = ObjectId()
        mock_db["medications"].insert_one(
            {
                "_id": med_id,
                "pet_id": str(test_pet["_id"]),
                "name": "Antibiotic",
                "type": "Таблетка",
                "default_dose": 1.0,
                "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
                "inventory_enabled": False,
                "is_active": True,
                "owner": "testuser",
                **stored,
            }
        )

        response = client.get(
            f"/api/medications/{med_id}?tz=Asia/Almaty",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.get_json()["medication"]["course_status"] == expected
