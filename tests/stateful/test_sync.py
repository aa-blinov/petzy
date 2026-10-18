"""The offline feed (GET /api/sync): what changed, and what is gone, for a device's copy.

The writes go through the API where the payload is known, so each stamp and each gone record is checked where it is
made. Paging, windows and resets are checked on rows written straight into the database, one case per row.
"""

import re
from bson import ObjectId
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch


BASE = datetime(2026, 10, 1, 12, 0, 0)  # naive UTC, as the database keeps moments
UTC_TO_THE_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _iso(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sync(client, token, **query):
    response = client.get("/api/sync", query_string=query, headers=_auth(token))
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def _everything(client, token, since=None, page_size=200):
    """The whole feed, page after page, as a device follows it."""
    items, after = [], None
    while True:
        query = {"page_size": page_size}
        if since:
            query["since"] = since
        if after:
            query["after"] = after
        body = _sync(client, token, **query)
        items.extend(body["items"])
        if not body["has_more"]:
            return items
        after = body["next_cursor"]


def _markers(items, kind=None):
    return {(i["kind"], i["id"], i["deleted"]) for i in items if kind is None or i["kind"] == kind}


def _record(mock_db, pet_id, moment, collection="medical_records", **extra):
    row = {"pet_id": pet_id, "username": "vera", "created_at": moment, "updated_at": moment, **extra}
    if collection == "medical_records":
        row.setdefault("kind", "visit")
    return str(mock_db[collection].insert_one(row).inserted_id)


def _share(client, owner_token, pet_id, username, invitee_token):
    assert (
        client.post(f"/api/pets/{pet_id}/share", json={"username": username}, headers=_auth(owner_token)).status_code
        == 200
    )
    assert client.post(f"/api/pets/{pet_id}/invite/accept", headers=_auth(invitee_token)).status_code == 200


def _medication_body(pet_id):
    return {
        "pet_id": str(pet_id),
        "name": "Синулокс",
        "type": "Таблетка",
        "default_dose": 1,
        "dose_unit": "таб",
        "schedule": {"days": list(range(7)), "times": ["08:00"]},
    }


class TestMarkers:
    def test_a_new_pet_is_a_marker_for_its_owner_only(self, client, regular_user_token, admin_token):
        pet = client.post("/api/pets", json={"name": "Тиша"}, headers=_auth(regular_user_token)).get_json()
        pet_id = pet["_id"] if "_id" in pet else pet["pet"]["_id"]

        owners = _markers(_everything(client, regular_user_token), "pet")
        others = _markers(_everything(client, admin_token), "pet")

        assert ("pet", pet_id, False) in owners
        assert ("pet", pet_id, False) not in others

    def test_a_change_made_through_the_api_is_stamped_and_sent(self, client, mock_db, regular_user_token, test_pet):
        before = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=2)

        assert (
            client.put(
                f"/api/pets/{test_pet['_id']}", json={"name": "Мурзик"}, headers=_auth(regular_user_token)
            ).status_code
            == 200
        )

        stored = mock_db["pets"].find_one({"_id": test_pet["_id"]})
        assert stored["updated_at"] >= before
        items = _everything(client, regular_user_token, since=_iso(before))
        marker = next(i for i in items if i["kind"] == "pet" and i["id"] == str(test_pet["_id"]))
        assert UTC_TO_THE_SECOND.match(marker["updated_at"]) and marker["deleted"] is False

    def test_a_medical_record_that_is_deleted_comes_as_a_deletion(self, client, regular_user_token, test_pet):
        created = client.post(
            "/api/medical-records",
            json={"pet_id": str(test_pet["_id"]), "kind": "visit", "title": "Осмотр", "date": date.today().isoformat()},
            headers=_auth(regular_user_token),
        )
        assert created.status_code == 201, created.get_json()
        record_id = created.get_json()["id"]
        assert ("medical_record", record_id, False) in _markers(_everything(client, regular_user_token))

        assert client.delete(f"/api/medical-records/{record_id}", headers=_auth(regular_user_token)).status_code == 200

        markers = _markers(_everything(client, regular_user_token), "medical_record")
        assert ("medical_record", record_id, True) in markers
        assert ("medical_record", record_id, False) not in markers

    def test_deleting_a_course_sends_its_intakes_as_deletions_too(self, client, mock_db, regular_user_token, test_pet):
        course = client.post(
            "/api/medications", json=_medication_body(test_pet["_id"]), headers=_auth(regular_user_token)
        ).get_json()
        medication_id = course["id"]
        assert (
            client.post(
                f"/api/medications/{medication_id}/log",
                json={"date": date.today().isoformat(), "time": "08:05", "dose_taken": 1.0},
                headers=_auth(regular_user_token),
            ).status_code
            == 201
        )
        intake_id = str(mock_db["medication_intakes"].find_one({"medication_id": medication_id})["_id"])

        assert client.delete(f"/api/medications/{medication_id}", headers=_auth(regular_user_token)).status_code == 200

        markers = _markers(_everything(client, regular_user_token))
        assert ("medication", medication_id, True) in markers
        assert ("medication_intake", intake_id, True) in markers

    def test_a_pet_taken_off_a_viewer_is_a_deletion_for_that_viewer_only(
        self, client, regular_user_token, admin_token, test_pet
    ):
        pet_id = str(test_pet["_id"])
        _share(client, regular_user_token, pet_id, "admin", admin_token)
        assert ("pet", pet_id, False) in _markers(_everything(client, admin_token), "pet")

        assert client.delete(f"/api/pets/{pet_id}/share/admin", headers=_auth(regular_user_token)).status_code == 200

        assert ("pet", pet_id, True) in _markers(_everything(client, admin_token), "pet")
        owner_view = _markers(_everything(client, regular_user_token), "pet")
        assert ("pet", pet_id, False) in owner_view
        assert ("pet", pet_id, True) not in owner_view

    def test_deleting_a_pet_sends_its_marker_and_nothing_under_it(
        self, client, regular_user_token, admin_token, test_pet
    ):
        pet_id = str(test_pet["_id"])
        _share(client, regular_user_token, pet_id, "admin", admin_token)
        created = client.post(
            "/api/medical-records",
            json={"pet_id": pet_id, "kind": "visit", "title": "Осмотр", "date": date.today().isoformat()},
            headers=_auth(regular_user_token),
        )
        assert created.status_code == 201, created.get_json()
        record_id = created.get_json()["id"]

        assert client.delete(f"/api/pets/{pet_id}", headers=_auth(regular_user_token)).status_code == 200

        for token in (regular_user_token, admin_token):
            items = _everything(client, token)
            assert ("pet", pet_id, True) in _markers(items, "pet")
            # The device takes what it had under the pet off with the pet: the feed sends nothing for those records.
            assert not [i for i in items if i["id"] == record_id]


class TestTheFeed:
    def test_pages_follow_the_cursor_and_nothing_repeats_or_is_lost(
        self, client, mock_db, regular_user, regular_user_token, test_pet
    ):
        pet_oid = test_pet["_id"]
        for minute in range(5):
            _record(mock_db, pet_oid, BASE + timedelta(minutes=minute))
        # Several changes in the same moment, of two kinds: the cursor must go past all of them.
        _record(mock_db, pet_oid, BASE + timedelta(minutes=10))
        _record(mock_db, pet_oid, BASE + timedelta(minutes=10))
        mock_db["events"].insert_one(
            {
                "pet_id": pet_oid,
                "username": "vera",
                "type": "feeding",
                "date_time": BASE + timedelta(minutes=10),
                "created_at": BASE + timedelta(minutes=10),
                "updated_at": BASE + timedelta(minutes=10),
            }
        )

        items = _everything(client, regular_user_token, since=_iso(BASE - timedelta(days=1)), page_size=2)

        keys = [(i["kind"], i["id"]) for i in items if i["kind"] in ("medical_record", "event")]
        assert len(keys) == 8
        assert len(set(keys)) == 8

    def test_a_change_before_since_is_not_sent(self, client, mock_db, regular_user_token, test_pet):
        pet_oid = test_pet["_id"]
        old = _record(mock_db, pet_oid, BASE - timedelta(days=2))
        new = _record(mock_db, pet_oid, BASE)

        items = _everything(client, regular_user_token, since=_iso(BASE - timedelta(days=1)))

        ids = {i["id"] for i in items if i["kind"] == "medical_record"}
        assert new in ids and old not in ids

    def test_a_tombstone_of_an_event_is_a_deletion(self, client, mock_db, regular_user_token, test_pet):
        event_id = str(
            mock_db["events"]
            .insert_one(
                {
                    "pet_id": test_pet["_id"],
                    "username": "vera",
                    "type": "feeding",
                    "date_time": BASE,
                    "created_at": BASE,
                    "updated_at": BASE,
                    "is_deleted": True,
                    "deleted_at": BASE,
                }
            )
            .inserted_id
        )

        assert ("event", event_id, True) in _markers(
            _everything(client, regular_user_token, since=_iso(BASE - timedelta(days=1)))
        )

    def test_a_device_away_longer_than_gone_records_are_kept_is_reset(self, client, regular_user_token):
        stale = _iso(datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=40))

        body = _sync(client, regular_user_token, since=stale)

        assert body["reset"] is True and body["items"] == [] and body["has_more"] is False

    def test_a_first_sync_without_since_is_not_a_reset(self, client, regular_user_token):
        assert _sync(client, regular_user_token)["reset"] is False

    def test_bad_arguments_are_refused(self, client, regular_user_token):
        for query in ({"since": "когда-нибудь"}, {"after": "0,pet,x"}, {"page_size": 0}, {"page_size": 501}):
            response = client.get("/api/sync", query_string=query, headers=_auth(regular_user_token))
            assert response.status_code == 422, query


class TestRecordsSavedBeforeTheFeed:
    def test_a_record_without_a_change_moment_gets_its_creation_and_reaches_the_feed(
        self, client, mock_db, regular_user_token, test_pet
    ):
        from web.db import backfill_updated_at

        created = datetime(2026, 9, 1, 8, 30, 15)
        legacy = (
            mock_db["medications"]
            .insert_one({"pet_id": test_pet["_id"], "username": "vera", "name": "Старый курс", "created_at": created})
            .inserted_id
        )
        fresh = _record(mock_db, test_pet["_id"], BASE)

        with patch("web.db.db", mock_db):
            # The pet of the fixture is a record of the same kind, and gets the field too.
            assert backfill_updated_at() >= 1

        assert mock_db["medications"].find_one({"_id": legacy})["updated_at"] == created
        assert mock_db["medical_records"].find_one({"_id": ObjectId(fresh)})["updated_at"] == BASE
        assert ("medication", str(legacy), False) in _markers(_everything(client, regular_user_token))


class TestAccountDeletion:
    def test_deleting_an_account_takes_its_name_out_of_the_gone_records(
        self, client, mock_db, regular_user, regular_user_token, test_pet
    ):
        from tests.conftest import password_hash_for
        from web.security import create_access_token

        mock_db["users"].insert_one(
            {
                "username": "anna",
                "password_hash": password_hash_for(b"secret-pass"),
                "is_active": True,
                "created_at": BASE,
            }
        )
        anna_token = create_access_token("anna")
        pet_id = str(test_pet["_id"])
        _share(client, regular_user_token, pet_id, "anna", anna_token)
        assert client.delete(f"/api/pets/{pet_id}", headers=_auth(regular_user_token)).status_code == 200
        entry = mock_db["sync_deletions"].find_one({"kind": "pet", "entity_id": test_pet["_id"]})
        assert set(entry["viewers"]) == {regular_user["username"], "anna"}

        response = client.delete("/api/me/account", json={"password": "secret-pass"}, headers=_auth(anna_token))

        assert response.status_code == 200, response.get_json()
        entry = mock_db["sync_deletions"].find_one({"kind": "pet", "entity_id": test_pet["_id"]})
        assert entry["viewers"] == [regular_user["username"]]
