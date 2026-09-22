"""Stateful tests for pet deletion's cascading cleanup.

These assert on what's left in the database *after* a multi-collection
operation, including under partial failure — the interesting case for
the fallback (non-transactional) cascade delete that mongomock always
takes, since it can't emulate `start_session()`. That fallback branch
already accepts that a single collection can fail mid-cascade (it
tracks `failed_collections` and carries on) — this pins down that the
pet and the other, unrelated collections still end up correctly
cleaned, and the request doesn't come back as an error for a partial
failure it already chose to tolerate.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from bson import ObjectId

import web.app as app


@pytest.mark.pets
class TestPetDeletionStateConsistency:
    def test_delete_pet_removes_its_events(self, client, mock_db, regular_user_token, test_pet):
        """A pet's events (the unified events collection, not the retired
        per-type collections) must not survive its own deletion.

        Regression test: `collections_to_clean` didn't list `events` at
        all until this was added, so every event ever logged for a
        deleted pet — feeding, weight, custom types, everything — stayed
        in the database forever, orphaned under a pet_id nothing could
        reach anymore.
        """
        pet_id = str(test_pet["_id"])
        mock_db["events"].insert_many(
            [
                {
                    "pet_id": pet_id,
                    "type": "feeding",
                    "date_time": datetime.now(timezone.utc),
                    "fields": {},
                    "comment": "",
                    "username": "testuser",
                }
                for _ in range(3)
            ]
        )
        assert mock_db["events"].count_documents({"pet_id": pet_id}) == 3

        response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        assert mock_db["events"].count_documents({"pet_id": pet_id}) == 0

    def test_delete_pet_partial_collection_failure_still_deletes_pet_and_rest(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """One collection's delete_many raising mid-cascade (mongomock
        always takes the fallback branch, which is also what a real
        standalone, non-replica-set MongoDB takes — the same topology
        the current docker-compose deployment runs) must not stop the
        pet itself, or the other collections, from being cleaned up.
        """
        pet_id = str(test_pet["_id"])
        med_id = ObjectId()
        mock_db["medications"].insert_one(
            {
                "_id": med_id,
                "pet_id": pet_id,
                "name": "Test Med",
                "owner": "testuser",
            }
        )
        mock_db["medication_intakes"].insert_one(
            {
                "medication_id": str(med_id),
                "pet_id": pet_id,
                "dose_taken": 1.0,
                "date_time": datetime.now(timezone.utc),
                "username": "testuser",
            }
        )
        mock_db["events"].insert_one(
            {
                "pet_id": pet_id,
                "type": "feeding",
                "date_time": datetime.now(timezone.utc),
                "fields": {},
                "comment": "",
                "username": "testuser",
            }
        )

        real_delete_many = mock_db["medications"].delete_many

        def flaky_delete_many(query, *args, **kwargs):
            if query.get("pet_id") == pet_id:
                raise RuntimeError("simulated transient failure deleting medications")
            return real_delete_many(query, *args, **kwargs)

        with patch.object(app.db.medications, "delete_many", side_effect=flaky_delete_many):
            response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        # The endpoint tolerates a partial cascade failure by design
        # (it logs `failed_collections` and continues) rather than
        # leaving the pet undeleted because one unrelated cleanup step
        # broke.
        assert response.status_code == 200
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}) is None

        # The collection that failed keeps its orphaned row...
        assert mock_db["medications"].count_documents({"pet_id": pet_id}) == 1
        # ...but everything else still got cleaned up despite that.
        assert mock_db["medication_intakes"].count_documents({"pet_id": pet_id}) == 0
        assert mock_db["events"].count_documents({"pet_id": pet_id}) == 0
