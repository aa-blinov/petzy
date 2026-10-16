"""Stateful tests for pet deletion's cascading cleanup.

These assert on what is left in the database after a pet is deleted, and on what a
failed delete leaves behind. mongomock has no sessions, so the non-transactional branch
always runs here, which is also what a standalone MongoDB without a replica set gets:
there the order of the deletes is the only guarantee. The pet document goes last, a
collection that cannot be cleared fails the request, and the pet stays so that the
same DELETE can finish the job.
"""

import logging

import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from bson import ObjectId

import web.app as app

# Every collection `purge_pet` clears for a pet (`collections_to_clean` in web/pets.py). Written out here on
# purpose: taking one out of the code must fail a test, not quietly shrink the list the test looks at.
PET_COLLECTIONS = (
    "asthma_attacks",
    "defecations",
    "weights",
    "feedings",
    "litter_changes",
    "eye_drops",
    "ear_cleaning",
    "tooth_brushing",
    "events",
    "medication_intakes",
    "medications",
    "documents",
    "medical_records",
    "medical_shares",
    "document_uploads",
)

DELETE_FAILED_TEXT = "Не удалось удалить питомца, попробуйте ещё раз"


def _seed_pet_records(mock_db, pet: dict) -> None:
    """One row in each collection of PET_COLLECTIONS, all of them the pet's."""
    pet_id = str(pet["_id"])
    owner = pet["owner"]
    now = datetime.now(timezone.utc)
    medication_id = ObjectId()
    mock_db["medications"].insert_one({"_id": medication_id, "pet_id": pet_id, "name": "Test Med", "owner": owner})
    mock_db["medication_intakes"].insert_one(
        {"medication_id": str(medication_id), "pet_id": pet_id, "dose_taken": 1.0, "date_time": now, "username": owner}
    )
    mock_db["events"].insert_one(
        {"pet_id": pet_id, "type": "feeding", "date_time": now, "fields": {}, "comment": "", "username": owner}
    )
    mock_db["documents"].insert_one({"pet_id": pet_id, "title": "Анализ крови", "username": owner, "created_at": now})
    mock_db["medical_records"].insert_one(
        {"pet_id": pet_id, "kind": "vaccination", "title": "Прививка", "date": now, "username": owner}
    )
    mock_db["medical_shares"].insert_one(
        {"pet_id": pet_id, "token_hash": "a" * 64, "created_at": now, "purge_at": now, "username": owner}
    )
    mock_db["document_uploads"].insert_one({"pet_id": pet_id, "username": owner, "created_at": now})
    for name in (
        "asthma_attacks",
        "defecations",
        "weights",
        "feedings",
        "litter_changes",
        "eye_drops",
        "ear_cleaning",
        "tooth_brushing",
    ):
        mock_db[name].insert_one({"pet_id": pet_id, "username": owner, "created_at": now})


def _rows_left(mock_db, pet_id: str) -> dict:
    """How many rows with this pet's id each collection in PET_COLLECTIONS still holds."""
    return {name: mock_db[name].count_documents({"pet_id": pet_id}) for name in PET_COLLECTIONS}


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

    def test_delete_pet_clears_every_collection_it_owns(self, client, mock_db, regular_user_token, test_pet):
        """After a successful DELETE no row with the pet's id is left in any collection the purge clears.

        Covers what a pet accumulates: records and their history, medication courses with their intakes,
        documents, the medical card (records and share links), and scans still uploading.
        """
        pet_id = str(test_pet["_id"])
        _seed_pet_records(mock_db, test_pet)
        assert _rows_left(mock_db, pet_id) == {name: 1 for name in PET_COLLECTIONS}

        response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}) is None
        assert _rows_left(mock_db, pet_id) == {name: 0 for name in PET_COLLECTIONS}

    def test_a_collection_that_fails_is_an_error_and_the_pet_stays(
        self, client, mock_db, regular_user_token, test_pet, caplog
    ):
        """A collection that cannot be cleared answers pet_delete_failed, and the pet document stays.

        The fallback used to log the failure, remove the pet anyway and answer 200, which left the rows
        of the other collections without a pet to reach them. The log names the collection and the error.
        """
        pet_id = str(test_pet["_id"])
        _seed_pet_records(mock_db, test_pet)
        failure = RuntimeError("simulated medications failure")

        caplog.set_level(logging.ERROR, logger=app.logger.name)
        with patch.object(app.db.medications, "delete_many", side_effect=failure):
            response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 503
        body = response.get_json()
        assert body["code"] == "pet_delete_failed"
        assert body["error"] == DELETE_FAILED_TEXT
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}) is not None
        logged = " ".join(record.getMessage() for record in caplog.records)
        assert "medications" in logged
        assert "simulated medications failure" in logged

    def test_the_pet_document_goes_last(self, client, mock_db, regular_user_token, test_pet):
        """When the pet document is removed, nothing that belongs to the pet is left in any collection.

        Removing the pet first would orphan every record the moment a later delete failed.
        """
        pet_id = str(test_pet["_id"])
        _seed_pet_records(mock_db, test_pet)
        real_delete_one = mock_db["pets"].delete_one
        rows_when_pet_goes = {}

        def watched_delete_one(query, *args, **kwargs):
            rows_when_pet_goes.update(_rows_left(mock_db, pet_id))
            return real_delete_one(query, *args, **kwargs)

        with patch.object(app.db.pets, "delete_one", side_effect=watched_delete_one):
            response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        assert rows_when_pet_goes == {name: 0 for name in PET_COLLECTIONS}

    def test_a_failed_pet_delete_is_an_error_too(self, client, mock_db, regular_user_token, test_pet):
        """The last step failing answers the same way: the pet is still there, and nothing is reported as done."""
        pet_id = str(test_pet["_id"])

        with patch.object(app.db.pets, "delete_one", side_effect=RuntimeError("simulated pet failure")):
            response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 503
        assert response.get_json()["code"] == "pet_delete_failed"
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}) is not None

    def test_a_repeated_delete_after_a_failure_finishes_the_job(self, client, mock_db, regular_user_token, test_pet):
        """The request that failed is repeated as it is, and it removes everything the pet had."""
        pet_id = str(test_pet["_id"])
        _seed_pet_records(mock_db, test_pet)
        headers = {"Authorization": f"Bearer {regular_user_token}"}
        failure = RuntimeError("simulated medications failure")

        with patch.object(app.db.medications, "delete_many", side_effect=failure):
            failed = client.delete(f"/api/pets/{pet_id}", headers=headers)
        assert failed.status_code == 503
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}) is not None

        finished = client.delete(f"/api/pets/{pet_id}", headers=headers)
        assert finished.status_code == 200
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}) is None
        assert _rows_left(mock_db, pet_id) == {name: 0 for name in PET_COLLECTIONS}
