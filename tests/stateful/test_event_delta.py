"""What changed since a moment: a device that keeps its own copy asks only for the changes.

``since`` gives the live records and the tombstones whose last change is at or after that moment, oldest change first.
A record's last change is its ``updated_at``, and a deletion counts as a change too. The device keeps the moment up to
which it has everything, and reads on with the ``next_cursor`` of each answer (as ``after``) until there is none.
"""

from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

WEIGHT = {"type": "weight", "date": "2026-10-01", "fields": {"weight": 12.4}, "comment": ""}
FIRST_MOMENT = datetime(2026, 10, 5, 10, 0, 0)
SECOND_MOMENT = datetime(2026, 10, 6, 10, 0, 0)
OLD_MOMENT = datetime(2026, 9, 1, 8, 0, 0)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, pet_id, time):
    body = {**WEIGHT, "pet_id": str(pet_id), "time": time}
    response = client.post("/api/events", json=body, headers=_auth(token))
    assert response.status_code == 201, response.get_json()
    return response.get_json()["id"]


def _set_changed(mock_db, record_id, moment):
    mock_db["events"].update_one({"_id": ObjectId(record_id)}, {"$set": {"updated_at": moment}})


def _stamp(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _read_delta(client, token, url):
    """Every change from the first answer on, read as a device reads it: page by page, on by ``after``."""
    items, cursor = [], None
    while True:
        target = url + (f"&after={cursor}" if cursor else "")
        body = client.get(target, headers=_auth(token)).get_json()
        items += body["items"]
        cursor = body["next_cursor"]
        if cursor is None:
            return items


@pytest.mark.health_records
class TestWhatChangedSince:
    def _records(self, client, mock_db, token, test_pet):
        """Four records: two changed at the first moment, one changed at the second and then deleted, one old."""
        pet = str(test_pet["_id"])
        first = _create(client, token, pet, "09:00")
        second = _create(client, token, pet, "09:01")
        third = _create(client, token, pet, "09:02")
        old = _create(client, token, pet, "09:03")
        _set_changed(mock_db, first, FIRST_MOMENT)
        _set_changed(mock_db, third, FIRST_MOMENT)
        _set_changed(mock_db, second, SECOND_MOMENT)
        _set_changed(mock_db, old, OLD_MOMENT)
        client.delete(f"/api/events/{second}", headers=_auth(token))
        return pet, first, second, third, old

    def test_the_changes_from_the_moment_on_come_oldest_first(self, client, mock_db, regular_user_token, test_pet):
        pet, first, second, third, old = self._records(client, mock_db, regular_user_token, test_pet)

        body = client.get(
            f"/api/events?pet_id={pet}&since={_stamp(FIRST_MOMENT)}", headers=_auth(regular_user_token)
        ).get_json()

        ids = [item["_id"] for item in body["items"]]
        assert ids == sorted([first, third], key=ObjectId) + [second]
        assert old not in ids

    def test_a_later_moment_gives_only_the_deletion_that_came_after(
        self, client, mock_db, regular_user_token, test_pet
    ):
        pet, first, second, third, old = self._records(client, mock_db, regular_user_token, test_pet)

        body = client.get(
            f"/api/events?pet_id={pet}&since={_stamp(SECOND_MOMENT)}", headers=_auth(regular_user_token)
        ).get_json()

        assert [item["_id"] for item in body["items"]] == [second]
        assert body["items"][0]["is_deleted"] is True
        assert body["items"][0]["deleted_at"].endswith("Z")

    def test_the_device_reads_each_change_once_by_the_after_cursor(self, client, mock_db, regular_user_token, test_pet):
        pet, first, second, third, old = self._records(client, mock_db, regular_user_token, test_pet)

        items = _read_delta(
            client, regular_user_token, f"/api/events?pet_id={pet}&since={_stamp(FIRST_MOMENT)}&page_size=1"
        )

        assert [item["_id"] for item in items] == sorted([first, third], key=ObjectId) + [second]

    def test_a_deletion_is_a_change_of_its_own(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        record = _create(client, regular_user_token, pet, "09:00")
        just_before = datetime.now(timezone.utc) - timedelta(minutes=1)
        client.delete(f"/api/events/{record}", headers=_auth(regular_user_token))

        body = client.get(
            f"/api/events?pet_id={pet}&since={just_before.strftime('%Y-%m-%dT%H:%M:%S.000Z')}",
            headers=_auth(regular_user_token),
        ).get_json()

        assert [item["_id"] for item in body["items"]] == [record]
        assert body["items"][0]["is_deleted"] is True

    def test_the_moment_and_the_cursor_are_checked(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])

        not_a_moment = client.get(f"/api/events?pet_id={pet}&since=вчера", headers=_auth(regular_user_token))
        after_alone = client.get(
            f"/api/events?pet_id={pet}&after=2026-10-05T10:00:00,{ObjectId()}", headers=_auth(regular_user_token)
        )
        both = client.get(
            f"/api/events?pet_id={pet}&since={_stamp(FIRST_MOMENT)}&before=2026-10-05T10:00:00,{ObjectId()}",
            headers=_auth(regular_user_token),
        )

        assert not_a_moment.status_code == 422
        assert after_alone.status_code == 422
        assert both.status_code == 422
