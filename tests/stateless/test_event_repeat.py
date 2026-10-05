"""The same record sent twice is one record.

A create request whose answer never arrived says nothing about whether the record was written, so
the person presses «Создать» again. Without a guard that is a second entry in the diary about one
feeding, one dose-free weighing or one attack. The server answers the repeat with the record it
already has (409, ``duplicate_event``, the first record's id) instead of writing it again.
"""

from datetime import datetime, timedelta, timezone

import pytest

EVENT = {
    "type": "weight",
    "date": "2026-10-01",
    "time": "09:00",
    "fields": {"weight": 12.4},
    "comment": "",
}


def _create(client, token, pet_id, **overrides):
    body = {**EVENT, "pet_id": str(pet_id), **overrides}
    return client.post("/api/events", json=body, headers={"Authorization": f"Bearer {token}"})


def _records(mock_db, pet_id):
    return list(mock_db["events"].find({"pet_id": str(pet_id), "type": "weight"}))


@pytest.mark.health_records
class TestTheSameRecordTwice:
    def test_the_repeat_answers_with_the_record_that_is_already_there(
        self, client, mock_db, regular_user_token, test_pet
    ):
        first = _create(client, regular_user_token, test_pet["_id"])
        assert first.status_code == 201
        first_id = first.get_json()["id"]

        again = _create(client, regular_user_token, test_pet["_id"])
        assert again.status_code == 409
        body = again.get_json()
        assert body["code"] == "duplicate_event"
        assert body["existing"]["id"] == first_id
        assert body["existing"]["own"] is True
        assert "09:00" in body["error"]
        assert len(_records(mock_db, test_pet["_id"])) == 1

    def test_another_minute_is_another_record(self, client, mock_db, regular_user_token, test_pet):
        assert _create(client, regular_user_token, test_pet["_id"]).status_code == 201
        assert _create(client, regular_user_token, test_pet["_id"], time="09:01").status_code == 201
        assert len(_records(mock_db, test_pet["_id"])) == 2

    def test_another_value_at_the_same_minute_is_another_record(self, client, mock_db, regular_user_token, test_pet):
        assert _create(client, regular_user_token, test_pet["_id"]).status_code == 201
        assert _create(client, regular_user_token, test_pet["_id"], fields={"weight": 12.5}).status_code == 201
        assert len(_records(mock_db, test_pet["_id"])) == 2

    def test_the_same_values_written_again_later_are_not_a_repeat(self, client, mock_db, regular_user_token, test_pet):
        """The guard is about the finger landing twice, not about a pet's day: a weight written
        down at the same clock a week later is a record of its own."""
        assert _create(client, regular_user_token, test_pet["_id"]).status_code == 201
        stale = datetime.now(timezone.utc) - timedelta(minutes=30)
        mock_db["events"].update_many({}, {"$set": {"created_at": stale}})
        assert _create(client, regular_user_token, test_pet["_id"]).status_code == 201
        assert len(_records(mock_db, test_pet["_id"])) == 2

    def test_another_person_writing_the_same_thing_is_not_a_repeat(self, client, mock_db, regular_user_token, test_pet):
        """Two people of one household note the same feeding in the same minute: whatever it means,
        it is not this person's own request sent again, so nothing is refused."""
        mock_db["events"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date_time": datetime(2026, 10, 1, 9, 0),
                "fields": {"weight": 12.4},
                "comment": "",
                "username": "someone_else",
                "created_at": datetime.now(timezone.utc),
            }
        )
        assert _create(client, regular_user_token, test_pet["_id"]).status_code == 201
        assert len(_records(mock_db, test_pet["_id"])) == 2

    def test_a_record_saved_before_this_guard_is_never_a_twin(self, client, mock_db, regular_user_token, test_pet):
        mock_db["events"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date_time": datetime(2026, 10, 1, 9, 0),
                "fields": {"weight": 12.4},
                "comment": "",
                "username": "testuser",
            }
        )
        assert _create(client, regular_user_token, test_pet["_id"]).status_code == 201
        assert len(_records(mock_db, test_pet["_id"])) == 2
