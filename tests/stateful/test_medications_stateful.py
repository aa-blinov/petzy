"""Stateful tests for medication intake logging.

Unlike a plain request/response contract check, these assert on how
*persisted state* evolves across a sequence of operations — specifically
the inventory-decrement compensation and optimistic-concurrency retry
logic in `log_intake`, which only ever runs when something else already
went wrong (a lost update race, or the intake insert itself failing).
Both paths are exercised here by mocking the specific PyMongo call that
needs to misbehave, since mongomock has no way to simulate a genuine
concurrent write.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from bson import ObjectId

import web.app as app


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
