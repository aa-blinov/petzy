"""A deleted record is a tombstone for 30 days.

A device that was offline when a record was deleted on another device still has the record. A plain delete tells it
nothing; a tombstone does. So the record stays in the stand, marked with the moment it was deleted, and it leaves every
ordinary read at once: the lists, the timeline, the record itself, the charts, the types in use, the card, the baseline
of the anomaly check. The database removes a tombstone 30 days after its deletion.
"""

from datetime import datetime

import pytest
from bson import ObjectId

from web.medical_card import _weight
from web.trend_alerts import detect_anomaly

WEIGHT = {"type": "weight", "date": "2026-10-01", "fields": {"weight": 12.4}, "comment": "", "tz": "Asia/Almaty"}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, pet_id, time="09:00", **overrides):
    body = {**WEIGHT, "pet_id": str(pet_id), "time": time, **overrides}
    response = client.post("/api/events", json=body, headers=_auth(token))
    assert response.status_code == 201, response.get_json()
    return response.get_json()["id"]


def _ids(client, token, url):
    return [item["_id"] for item in client.get(url, headers=_auth(token)).get_json()["items"]]


@pytest.mark.health_records
class TestDeletingKeepsATombstone:
    def test_the_record_is_kept_marked_with_the_moment_it_was_deleted(
        self, client, mock_db, regular_user_token, test_pet
    ):
        record = _create(client, regular_user_token, test_pet["_id"])

        response = client.delete(f"/api/events/{record}", headers=_auth(regular_user_token))

        assert response.status_code == 200
        stored = mock_db["events"].find_one({"_id": ObjectId(record)})
        assert stored["is_deleted"] is True
        assert isinstance(stored["deleted_at"], datetime)

    def test_the_lists_the_timeline_and_the_record_itself_leave_it_out(
        self, client, mock_db, regular_user_token, test_pet
    ):
        pet = str(test_pet["_id"])
        keep = _create(client, regular_user_token, pet, time="09:00")
        gone = _create(client, regular_user_token, pet, time="09:01")
        client.delete(f"/api/events/{gone}", headers=_auth(regular_user_token))

        listed = client.get(f"/api/events?pet_id={pet}", headers=_auth(regular_user_token)).get_json()
        timeline = _ids(client, regular_user_token, f"/api/history/timeline?pet_id={pet}")

        assert [item["_id"] for item in listed["items"]] == [keep]
        assert listed["total"] == 1
        assert timeline == [keep]
        assert client.get(f"/api/events/{gone}", headers=_auth(regular_user_token)).status_code == 404
        # An edit of a record that is gone is told so (409), apart from a record that never was (404).
        edited = client.put(f"/api/events/{gone}", json={"comment": "x"}, headers=_auth(regular_user_token))
        assert (edited.status_code, edited.get_json()["code"]) == (409, "record_deleted")
        assert client.delete(f"/api/events/{gone}", headers=_auth(regular_user_token)).status_code == 404

    def test_the_types_in_use_and_the_chart_leave_it_out(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        record = _create(client, regular_user_token, pet)
        assert (
            "weight"
            in client.get(f"/api/events/used-types?pet_id={pet}", headers=_auth(regular_user_token)).get_json()["types"]
        )
        client.delete(f"/api/events/{record}", headers=_auth(regular_user_token))

        types = client.get(f"/api/events/used-types?pet_id={pet}", headers=_auth(regular_user_token)).get_json()[
            "types"
        ]
        chart = client.get(
            f"/api/stats/health?pet_id={pet}&type=weight&days=365", headers=_auth(regular_user_token)
        ).get_json()

        assert "weight" not in types
        assert chart["data"] == []

    def test_the_medical_card_leaves_its_weight_out(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        record = _create(client, regular_user_token, pet)
        assert _weight(pet) is not None
        client.delete(f"/api/events/{record}", headers=_auth(regular_user_token))

        assert _weight(pet) is None

    def test_the_anomaly_baseline_leaves_deleted_readings_out(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        for day in range(3):
            mock_db["events"].insert_one(
                {
                    "pet_id": pet,
                    "type": "weight",
                    "date_time": datetime(2026, 9, 1 + day, 9, 0),
                    "fields": {"weight": 10.0},
                    "comment": "",
                    "username": "testuser",
                }
            )
        for day in range(3):
            mock_db["events"].insert_one(
                {
                    "pet_id": pet,
                    "type": "weight",
                    "date_time": datetime(2026, 9, 10 + day, 9, 0),
                    "fields": {"weight": 100.0},
                    "comment": "",
                    "username": "testuser",
                    "is_deleted": True,
                    "deleted_at": datetime(2026, 9, 20),
                }
            )

        anomaly = detect_anomaly(mock_db, pet, "weight", "weight", 50.0)

        assert anomaly is not None


@pytest.mark.health_records
class TestWhatComesBackAfterADelete:
    def test_the_same_record_made_again_after_its_deletion_is_written(
        self, client, mock_db, regular_user_token, test_pet
    ):
        pet = str(test_pet["_id"])
        first = _create(client, regular_user_token, pet)
        client.delete(f"/api/events/{first}", headers=_auth(regular_user_token))

        again = client.post(
            "/api/events", json={**WEIGHT, "pet_id": pet, "time": "09:00"}, headers=_auth(regular_user_token)
        )

        assert again.status_code == 201
        assert again.get_json()["id"] != first

    def test_a_repeat_of_a_named_record_does_not_bring_it_back(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        record = _create(client, regular_user_token, pet, local_id="n9")
        client.delete("/api/events/local/n9", headers=_auth(regular_user_token))

        repeat = client.post(
            "/api/events",
            json={**WEIGHT, "pet_id": pet, "time": "09:00", "local_id": "n9"},
            headers=_auth(regular_user_token),
        )

        assert repeat.status_code == 409
        assert repeat.get_json()["code"] == "record_deleted"
        assert len(list(mock_db["events"].find({"local_id": "n9"}))) == 1
        assert client.get(f"/api/events/{record}", headers=_auth(regular_user_token)).status_code == 404

    def test_a_device_reads_the_tombstones_with_with_deleted(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        keep = _create(client, regular_user_token, pet, time="09:00")
        gone = _create(client, regular_user_token, pet, time="09:01")
        client.delete(f"/api/events/{gone}", headers=_auth(regular_user_token))

        listed = client.get(f"/api/events?pet_id={pet}&with_deleted=1", headers=_auth(regular_user_token)).get_json()
        by_id = {item["_id"]: item for item in listed["items"]}
        timeline = client.get(
            f"/api/history/timeline?pet_id={pet}&with_deleted=1", headers=_auth(regular_user_token)
        ).get_json()["items"]

        assert set(by_id) == {keep, gone}
        assert by_id[gone]["is_deleted"] is True
        assert by_id[gone]["deleted_at"].endswith("Z")
        assert "is_deleted" not in by_id[keep]
        assert {item["_id"] for item in timeline} == {keep, gone}

    def test_a_pet_deleted_takes_its_tombstones_with_it(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        record = _create(client, regular_user_token, pet)
        client.delete(f"/api/events/{record}", headers=_auth(regular_user_token))

        response = client.delete(f"/api/pets/{pet}", headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert mock_db["events"].count_documents({"pet_id": pet}) == 0
