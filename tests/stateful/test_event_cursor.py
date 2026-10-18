"""A feed read from a cursor: every record once, however records are written while it is being read.

The web app reads a page by number, which is right for a screen. But a record written between two pages shifts the
second one by a record, so one record shows twice and one is skipped. A device that reads the whole diary goes by the
cursor that the previous answer named, so the pages do not move. Records at the same time are ordered by their id, so
that order does not change between two reads either.
"""

from urllib.parse import quote

import pytest
from bson import ObjectId

WEIGHT = {"type": "weight", "date": "2026-10-01", "fields": {"weight": 12.4}, "comment": ""}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, pet_id, time, comment=""):
    body = {**WEIGHT, "pet_id": str(pet_id), "time": time, "comment": comment}
    response = client.post("/api/events", json=body, headers=_auth(token))
    assert response.status_code == 201, response.get_json()
    return response.get_json()["id"]


def _page(client, token, url, cursor=None):
    target = url + (f"&before={quote(cursor)}" if cursor else "")
    response = client.get(target, headers=_auth(token))
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def _read_on(client, token, url, cursor=None):
    """The ids from a cursor to the end of the feed, read the way a device reads: page by page, on by cursor."""
    seen = []
    while True:
        body = _page(client, token, url, cursor)
        seen += [item["_id"] for item in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            return seen


@pytest.mark.health_records
class TestReadingEventsFromACursor:
    def test_a_device_reads_every_record_once_newest_first(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        made = [_create(client, regular_user_token, pet, f"09:0{i}") for i in range(5)]

        seen = _read_on(client, regular_user_token, f"/api/events?pet_id={pet}&page_size=2")

        assert seen == list(reversed(made))

    def test_a_record_written_between_pages_moves_no_page(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        made = [_create(client, regular_user_token, pet, f"09:0{i}") for i in range(5)]
        url = f"/api/events?pet_id={pet}&page_size=2"
        first = _page(client, regular_user_token, url)
        _create(client, regular_user_token, pet, "10:30")

        rest = _read_on(client, regular_user_token, url, first["next_cursor"])

        assert [item["_id"] for item in first["items"]] + rest == list(reversed(made))

    def test_a_record_written_below_the_cursor_is_read_once(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        made = [_create(client, regular_user_token, pet, f"09:0{i}") for i in range(5)]
        url = f"/api/events?pet_id={pet}&page_size=2"
        first = _page(client, regular_user_token, url)
        older = _create(client, regular_user_token, pet, "08:00")

        rest = _read_on(client, regular_user_token, url, first["next_cursor"])

        assert rest.count(older) == 1
        assert sorted(rest + [item["_id"] for item in first["items"]]) == sorted(made + [older])

    def test_records_at_the_same_time_are_each_read_once(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        made = [_create(client, regular_user_token, pet, "11:00", comment=f"запись {i}") for i in range(3)]

        seen = _read_on(client, regular_user_token, f"/api/events?pet_id={pet}&page_size=1")

        assert sorted(seen) == sorted(made)
        assert len(seen) == len(set(seen))

    def test_the_last_page_has_no_cursor(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        _create(client, regular_user_token, pet, "09:00")
        _create(client, regular_user_token, pet, "09:01")

        full = _page(client, regular_user_token, f"/api/events?pet_id={pet}&page_size=2")
        more = _page(client, regular_user_token, f"/api/events?pet_id={pet}&page_size=1")

        assert full["next_cursor"] is None
        assert more["next_cursor"] is not None

    def test_a_cursor_that_is_not_one_is_refused(self, client, regular_user_token, test_pet):
        pet = str(test_pet["_id"])

        response = client.get(f"/api/events?pet_id={pet}&before=вчера", headers=_auth(regular_user_token))

        assert response.status_code == 422

    def test_the_page_by_number_still_answers_as_before(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        made = [_create(client, regular_user_token, pet, f"09:0{i}") for i in range(4)]

        body = _page(client, regular_user_token, f"/api/events?pet_id={pet}&page=2&page_size=2")

        assert [item["_id"] for item in body["items"]] == list(reversed(made))[2:]
        assert body["total"] == 4
        assert body["page"] == 2


@pytest.mark.health_records
class TestReadingTheTimelineFromACursor:
    def test_events_and_doses_are_each_read_once_across_pages(self, client, mock_db, regular_user_token, test_pet):
        pet = str(test_pet["_id"])
        made = [_create(client, regular_user_token, pet, f"09:0{i}") for i in range(3)]
        same_minute = mock_db["events"].find_one({"_id": ObjectId(made[1])})["date_time"]
        dose = mock_db["medication_intakes"].insert_one(
            {
                "pet_id": pet,
                "medication_id": str(ObjectId()),
                "date_time": same_minute,
                "dose_taken": 1.0,
                "skipped": False,
                "username": "testuser",
            }
        )
        url = f"/api/history/timeline?pet_id={pet}&page_size=2"

        seen = _read_on(client, regular_user_token, url)

        assert len(seen) == 4
        assert len(set(seen)) == 4
        assert str(dose.inserted_id) in seen
        assert set(made) <= set(seen)
