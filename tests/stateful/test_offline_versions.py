"""An edit from an offline queue says which version of the record it was made from.

``base_version`` is the ``updated_at`` the device last read. A record that changed since is not overwritten: the stand
answers 409 ``conflict`` with the record as it is now, and the device compares the fields itself. Without the field the
edit is applied, as before. An edit of a record that is gone is 409 ``record_deleted``, not the 404 of a record that
never was.
"""

from datetime import datetime

import pytest
from bson import ObjectId

TZ = "Asia/Almaty"
LATER = datetime(2031, 1, 1, 12, 0, 0)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class Kind:
    """What differs between the four sections: how to make a record, read it, change it, and where it is stored."""

    def __init__(self, name, collection):
        self.name, self.collection = name, collection

    def __repr__(self):
        return self.name


def _make(client, token, kind, pet):
    pet_id = str(pet["_id"])
    if kind.name == "events":
        body = {
            "pet_id": pet_id,
            "type": "weight",
            "date": "2026-10-01",
            "time": "09:00",
            "fields": {"weight": 12.4},
            "comment": "",
            "tz": TZ,
        }
        return client.post("/api/events", json=body, headers=_auth(token)).get_json()["id"]
    if kind.name == "medications":
        body = {
            "pet_id": pet_id,
            "name": "Дронтал",
            "type": "Таблетка",
            "schedule": {"days": [0], "times": ["08:00"]},
        }
        return client.post("/api/medications", json=body, headers=_auth(token)).get_json()["id"]
    if kind.name == "medical_records":
        body = {"pet_id": pet_id, "kind": "visit", "date": "2026-09-23", "title": "Осмотр"}
        return client.post("/api/medical-records", json=body, headers=_auth(token)).get_json()["id"]
    return pet_id


def _read(client, token, kind, record_id):
    headers = _auth(token)
    if kind.name == "events":
        return client.get(f"/api/events/{record_id}", headers=headers).get_json()
    if kind.name == "medications":
        return client.get(f"/api/medications/{record_id}", headers=headers).get_json()["medication"]
    if kind.name == "medical_records":
        return client.get(f"/api/medical-records/{record_id}", headers=headers).get_json()["record"]
    return client.get(f"/api/pets/{record_id}", headers=headers).get_json()["pet"]


URLS = {
    "events": "/api/events/{}",
    "medications": "/api/medications/{}",
    "medical_records": "/api/medical-records/{}",
    "pets": "/api/pets/{}",
}
LOCAL_URLS = {
    "events": "/api/events/local/{}",
    "medications": "/api/medications/local/{}",
    "medical_records": "/api/medical-records/local/{}",
    "pets": "/api/pets/local/{}",
}
# A change that is valid for each section, and the field that shows it was applied.
CHANGES = {
    "events": ({"comment": "правка"}, "comment"),
    "medications": ({"name": "Новое имя"}, "name"),
    "medical_records": ({"date": "2026-09-23", "title": "Новое имя"}, "title"),
    "pets": ({"name": "Новое имя"}, "name"),
}


@pytest.fixture(params=["events", "medications", "medical_records", "pets"], ids=str)
def kind(request):
    return Kind(request.param, request.param)


@pytest.fixture
def made(client, regular_user_token, test_pet, kind):
    """A record of the section, and the version of it the device read."""
    record_id = _make(client, regular_user_token, kind, test_pet)
    return record_id, _read(client, regular_user_token, kind, record_id)["updated_at"]


def _stored(mock_db, kind, record_id):
    return mock_db[kind.collection].find_one({"_id": ObjectId(record_id)})


def _changed_elsewhere(mock_db, kind, record_id):
    """Someone else saved the record: its version moves."""
    mock_db[kind.collection].update_one({"_id": ObjectId(record_id)}, {"$set": {"updated_at": LATER}})


@pytest.mark.health_records
class TestTheVersionAnEditIsMadeFrom:
    def test_the_reading_says_the_version_as_text_in_the_projects_format(self, made):
        _, version = made

        assert isinstance(version, str)
        assert datetime.strptime(version, "%Y-%m-%dT%H:%M:%SZ")

    def test_an_edit_from_the_current_version_is_applied(self, client, mock_db, regular_user_token, kind, made):
        record_id, version = made
        change, field = CHANGES[kind.name]

        response = client.put(
            URLS[kind.name].format(record_id),
            json={**change, "base_version": version},
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 200
        assert _stored(mock_db, kind, record_id)[field] == change[field]

    def test_an_edit_without_a_version_is_applied_as_before(self, client, mock_db, regular_user_token, kind, made):
        record_id, _ = made
        _changed_elsewhere(mock_db, kind, record_id)
        change, field = CHANGES[kind.name]

        response = client.put(URLS[kind.name].format(record_id), json=change, headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert _stored(mock_db, kind, record_id)[field] == change[field]

    def test_an_edit_from_an_old_version_is_refused_with_the_record_as_it_is_now(
        self, client, mock_db, regular_user_token, kind, made
    ):
        record_id, version = made
        _changed_elsewhere(mock_db, kind, record_id)
        before = _stored(mock_db, kind, record_id)
        change, field = CHANGES[kind.name]

        response = client.put(
            URLS[kind.name].format(record_id),
            json={**change, "base_version": version},
            headers=_auth(regular_user_token),
        )

        assert (response.status_code, response.get_json()["code"]) == (409, "conflict")
        current = response.get_json()["record"]
        assert str(current["_id"]) == record_id
        assert current["updated_at"] == "2031-01-01T12:00:00Z"
        assert _stored(mock_db, kind, record_id) == before

    def test_the_refusal_is_the_same_by_the_name_the_device_gave(self, client, mock_db, regular_user_token, kind, made):
        record_id, version = made
        mock_db[kind.collection].update_one({"_id": ObjectId(record_id)}, {"$set": {"local_id": "n1"}})
        _changed_elsewhere(mock_db, kind, record_id)
        change, _ = CHANGES[kind.name]

        response = client.put(
            LOCAL_URLS[kind.name].format("n1"),
            json={**change, "base_version": version},
            headers=_auth(regular_user_token),
        )

        assert (response.status_code, response.get_json()["code"]) == (409, "conflict")
        assert str(response.get_json()["record"]["_id"]) == record_id

    def test_a_save_that_lost_the_race_is_refused_too(
        self, client, mock_db, regular_user_token, kind, made, monkeypatch
    ):
        """The version is checked and then written: someone saving in between must not be overwritten."""
        import web.offline as offline

        record_id, version = made
        change, _ = CHANGES[kind.name]
        real_is_stale = offline.is_stale

        def stale_after_the_check(base_version, record):
            answer = real_is_stale(base_version, record)
            # The other person saves right after the check has passed.
            _changed_elsewhere(mock_db, kind, record_id)
            return answer

        for module in ("web.events", "web.medications", "web.medical_records", "web.pets"):
            monkeypatch.setattr(f"{module}.is_stale", stale_after_the_check)

        response = client.put(
            URLS[kind.name].format(record_id),
            json={**change, "base_version": version},
            headers=_auth(regular_user_token),
        )

        assert (response.status_code, response.get_json()["code"]) == (409, "conflict")
        assert _stored(mock_db, kind, record_id)["updated_at"] == LATER

    def test_a_record_without_updated_at_has_its_creation_as_the_version(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """A pet saved before the field existed: the version is its creation, and an edit from it goes through."""
        pet = client.get(f"/api/pets/{test_pet['_id']}", headers=_auth(regular_user_token)).get_json()["pet"]
        assert "updated_at" not in mock_db["pets"].find_one({"_id": test_pet["_id"]})

        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            json={"name": "Новое", "base_version": pet["updated_at"]},
            headers=_auth(regular_user_token),
        )

        assert pet["updated_at"] == pet["created_at"]
        assert response.status_code == 200


@pytest.mark.health_records
class TestAnEditOfARecordThatIsGone:
    def test_it_is_told_the_record_is_deleted(self, client, mock_db, regular_user_token, kind, made):
        record_id, version = made
        client.delete(URLS[kind.name].format(record_id), headers=_auth(regular_user_token))
        change, _ = CHANGES[kind.name]

        for body in (change, {**change, "base_version": version}):
            response = client.put(URLS[kind.name].format(record_id), json=body, headers=_auth(regular_user_token))

            assert (response.status_code, response.get_json()["code"]) == (409, "record_deleted")

    def test_a_record_that_never_was_is_not_found(self, client, regular_user_token, kind):
        change, _ = CHANGES[kind.name]

        response = client.put(URLS[kind.name].format(str(ObjectId())), json=change, headers=_auth(regular_user_token))

        assert (response.status_code, response.get_json()["code"]) == (
            404,
            "record_not_found" if kind.name != "pets" else "pet_not_found",
        )


@pytest.mark.health_records
def test_a_pets_photo_is_not_stored_by_an_edit_that_is_refused(
    client, mock_db, regular_user_token, test_pet, s3_storage
):
    import io

    from PIL import Image

    pet = client.get(f"/api/pets/{test_pet['_id']}", headers=_auth(regular_user_token)).get_json()["pet"]
    mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"updated_at": LATER}})
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buffer, "PNG")
    buffer.seek(0)

    response = client.put(
        f"/api/pets/{test_pet['_id']}",
        data={"name": "Новое", "base_version": pet["updated_at"], "photo_file": (buffer, "cat.png")},
        headers=_auth(regular_user_token),
        content_type="multipart/form-data",
    )

    assert response.status_code == 409
    stored = mock_db["pets"].find_one({"_id": test_pet["_id"]})
    assert stored["name"] == "Test Cat"
    assert not stored.get("photo_file_id")
