"""``updated_at``: when a record last changed, on the stand's clock, so that a device can tell its copy is out of date.

A device that was offline cannot judge from its own clock whether the stand changed a record meanwhile: the two
clocks differ. The stand stamps the moment of every save in UTC, and the answer gives it to the second. A record saved before the field
existed reports its creation as the last change it had.
"""

import re
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
WEIGHT = {"type": "weight", "date": "2026-10-01", "time": "09:00", "fields": {"weight": 12.4}, "comment": ""}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, pet_id, **overrides):
    body = {**WEIGHT, "pet_id": str(pet_id), **overrides}
    response = client.post("/api/events", json=body, headers=_auth(token))
    assert response.status_code == 201, response.get_json()
    return response.get_json()["id"]


def _instant(stamp):
    """The answer's ``updated_at`` read back as a UTC instant without a zone, as the database returns them."""
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).replace(tzinfo=None)


def _utc_naive_to_the_second(moment):
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment.replace(microsecond=0)


@pytest.mark.health_records
class TestUpdatedAt:
    def test_a_new_record_is_last_changed_when_it_was_made(self, client, mock_db, regular_user_token, test_pet):
        record_id = _create(client, regular_user_token, test_pet["_id"])
        stored = mock_db["events"].find_one({"_id": ObjectId(record_id)})

        item = client.get(f"/api/events/{record_id}", headers=_auth(regular_user_token)).get_json()

        assert STAMP.match(item["updated_at"])
        assert _instant(item["updated_at"]) == _utc_naive_to_the_second(stored["created_at"])
        assert stored["updated_at"] == stored["created_at"]

    def test_a_change_moves_it_forward_and_leaves_the_creation_alone(
        self, client, mock_db, regular_user_token, test_pet
    ):
        record_id = _create(client, regular_user_token, test_pet["_id"])
        long_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_db["events"].update_one({"_id": ObjectId(record_id)}, {"$set": {"updated_at": long_ago}})
        created_before = mock_db["events"].find_one({"_id": ObjectId(record_id)})["created_at"]

        response = client.put(
            f"/api/events/{record_id}", json={"comment": "после прогулки"}, headers=_auth(regular_user_token)
        )

        assert response.status_code == 200
        stored = mock_db["events"].find_one({"_id": ObjectId(record_id)})
        assert _utc_naive_to_the_second(stored["updated_at"]) > _utc_naive_to_the_second(long_ago)
        assert stored["created_at"] == created_before
        item = client.get(f"/api/events/{record_id}", headers=_auth(regular_user_token)).get_json()
        assert _instant(item["updated_at"]) > _utc_naive_to_the_second(long_ago)

    def test_a_save_that_changes_nothing_is_still_a_save(self, client, mock_db, regular_user_token, test_pet):
        """Every save is stamped, as the field says. A device that finds a stamp it does not know re-reads the record,
        which costs one request; a change that went unstamped would cost the record."""
        record_id = _create(client, regular_user_token, test_pet["_id"])
        long_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        mock_db["events"].update_one({"_id": ObjectId(record_id)}, {"$set": {"updated_at": long_ago}})

        response = client.put(f"/api/events/{record_id}", json={}, headers=_auth(regular_user_token))

        assert response.status_code == 200
        stored = mock_db["events"].find_one({"_id": ObjectId(record_id)})
        assert _utc_naive_to_the_second(stored["updated_at"]) > _utc_naive_to_the_second(long_ago)

    def test_a_repeat_of_a_named_record_is_not_a_save(self, client, mock_db, regular_user_token, test_pet):
        record_id = _create(client, regular_user_token, test_pet["_id"], local_id="r1")
        stamp_before = mock_db["events"].find_one({"_id": ObjectId(record_id)})["updated_at"]

        again = client.post(
            "/api/events",
            json={**WEIGHT, "pet_id": str(test_pet["_id"]), "local_id": "r1"},
            headers=_auth(regular_user_token),
        )

        assert again.status_code == 200
        assert mock_db["events"].find_one({"_id": ObjectId(record_id)})["updated_at"] == stamp_before

    def test_a_record_saved_before_the_field_reports_its_creation(self, client, mock_db, regular_user_token, test_pet):
        created = datetime(2026, 9, 1, 8, 30, 15, 250000)
        result = mock_db["events"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date_time": created,
                "fields": {"weight": 4.0},
                "comment": "",
                "username": "testuser",
                "created_at": created,
            }
        )

        item = client.get(f"/api/events/{result.inserted_id}", headers=_auth(regular_user_token)).get_json()

        assert item["updated_at"] == "2026-09-01T08:30:15Z"

    def test_the_list_and_the_timeline_carry_it_too(self, client, mock_db, regular_user_token, test_pet):
        _create(client, regular_user_token, test_pet["_id"])
        pet = str(test_pet["_id"])

        listed = client.get(f"/api/events?pet_id={pet}", headers=_auth(regular_user_token)).get_json()["items"][0]
        timeline = client.get(f"/api/history/timeline?pet_id={pet}", headers=_auth(regular_user_token))

        assert STAMP.match(listed["updated_at"])
        assert STAMP.match(timeline.get_json()["items"][0]["updated_at"])
