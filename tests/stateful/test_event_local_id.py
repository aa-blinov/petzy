"""An event the device names itself: the same name sent again is the record that is already there.

A native client writes offline and sends later. When the answer to a send is lost it sends the same record again, and
without a name that is a second entry in the diary. With ``local_id`` the stand keeps one record per name, and the
device can change or remove the record by its name before it has the record's id.
"""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

import web.events as events

WEIGHT = {
    "type": "weight",
    "date": "2026-10-01",
    "time": "09:00",
    "fields": {"weight": 12.4},
    "comment": "",
    "tz": "Asia/Almaty",
}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, pet_id, **overrides):
    body = {**WEIGHT, "pet_id": str(pet_id), **overrides}
    return client.post("/api/events", json=body, headers=_auth(token))


def _named(mock_db, local_id):
    return list(mock_db["events"].find({"local_id": local_id}))


@pytest.fixture
def second_pet(mock_db, regular_user):
    """Another pet of the same owner: the same person may give a record's name for either pet."""
    result = mock_db["pets"].insert_one(
        {
            "name": "Второй",
            "owner": regular_user["username"],
            "shared_with": [],
            "created_by": regular_user["username"],
            "created_at": datetime.now(timezone.utc),
        }
    )
    return result.inserted_id


@pytest.fixture
def stranger_token(mock_db):
    """A signed-in person with no access to the test pet."""
    from web.security import create_access_token

    mock_db["users"].insert_one(
        {
            "username": "stranger",
            "password_hash": "unused",
            "full_name": "Посторонний",
            "email": "",
            "created_at": datetime.now(timezone.utc),
            "created_by": "admin",
            "is_active": True,
        }
    )
    return create_access_token("stranger")


@pytest.mark.health_records
class TestCreatingWithAName:
    def test_the_record_keeps_its_name_and_the_answer_says_so(self, client, mock_db, regular_user_token, test_pet):
        response = _create(client, regular_user_token, test_pet["_id"], local_id="a1b2")

        assert response.status_code == 201
        body = response.get_json()
        assert body["local_id"] == "a1b2"
        [stored] = _named(mock_db, "a1b2")
        assert str(stored["_id"]) == body["id"]

    def test_the_same_name_sent_again_is_the_record_already_there(self, client, mock_db, regular_user_token, test_pet):
        first = _create(client, regular_user_token, test_pet["_id"], local_id="a1b2")
        again = _create(client, regular_user_token, test_pet["_id"], local_id="a1b2")

        assert again.status_code == 200
        assert again.get_json()["id"] == first.get_json()["id"]
        assert len(_named(mock_db, "a1b2")) == 1

    def test_the_repeat_is_not_refused_by_the_guard_for_unnamed_repeats(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """Without a name the same record within 5 minutes is refused (409 duplicate_event). With a name the repeat is
        the answer the device needs, not a refusal."""
        assert _create(client, regular_user_token, test_pet["_id"], local_id="a1b2").status_code == 201

        again = _create(client, regular_user_token, test_pet["_id"], local_id="a1b2")

        assert again.status_code == 200
        assert again.get_json().get("code") != "duplicate_event"

    def test_a_name_of_another_pets_record_is_refused(self, client, mock_db, regular_user_token, test_pet, second_pet):
        assert _create(client, regular_user_token, test_pet["_id"], local_id="a1b2").status_code == 201

        other = _create(client, regular_user_token, second_pet, local_id="a1b2")

        assert other.status_code == 409
        assert other.get_json()["code"] == "local_id_taken"
        assert len(_named(mock_db, "a1b2")) == 1

    def test_a_name_of_another_type_is_refused(self, client, mock_db, regular_user_token, test_pet):
        assert _create(client, regular_user_token, test_pet["_id"], local_id="a1b2").status_code == 201

        other = _create(client, regular_user_token, test_pet["_id"], type="walk", fields={}, local_id="a1b2")

        assert other.status_code == 409
        assert other.get_json()["code"] == "local_id_taken"

    def test_the_name_is_stored_without_the_spaces_around_it(self, client, mock_db, regular_user_token, test_pet):
        response = _create(client, regular_user_token, test_pet["_id"], local_id="  a1b2  ")

        assert response.status_code == 201
        assert response.get_json()["local_id"] == "a1b2"

    def test_a_blank_name_is_refused(self, client, regular_user_token, test_pet):
        assert _create(client, regular_user_token, test_pet["_id"], local_id="   ").status_code == 422

    def test_a_name_longer_than_64_characters_is_refused(self, client, regular_user_token, test_pet):
        assert _create(client, regular_user_token, test_pet["_id"], local_id="x" * 65).status_code == 422

    def test_a_record_without_a_name_stays_out_of_the_names(self, client, mock_db, regular_user_token, test_pet):
        response = _create(client, regular_user_token, test_pet["_id"], time="10:00")

        assert response.status_code == 201
        assert "local_id" not in response.get_json()
        assert "local_id" not in mock_db["events"].find_one({"_id": ObjectId(response.get_json()["id"])})

    def test_two_sends_at_once_give_the_record_the_first_one_wrote(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        """Both sends pass the look-up before either writes; the unique index refuses the second write, and the answer
        is the record the first one wrote."""
        mock_db["events"].create_index([("local_id", 1)], unique=True, sparse=True)
        first = _create(client, regular_user_token, test_pet["_id"], local_id="a1b2")
        original = events._record_with_local_id
        looked_up = []

        def miss_the_first_time(local_id):
            looked_up.append(local_id)
            return None if len(looked_up) == 1 else original(local_id)

        monkeypatch.setattr(events, "_record_with_local_id", miss_the_first_time)

        second = _create(client, regular_user_token, test_pet["_id"], local_id="a1b2")

        assert second.status_code == 200
        assert second.get_json()["id"] == first.get_json()["id"]
        assert len(_named(mock_db, "a1b2")) == 1


@pytest.mark.health_records
class TestChangingAndRemovingByName:
    def test_an_update_by_name_changes_the_record_it_names(self, client, mock_db, regular_user_token, test_pet):
        created = _create(client, regular_user_token, test_pet["_id"], local_id="n1").get_json()["id"]

        response = client.put("/api/events/local/n1", json={"comment": "ел хорошо"}, headers=_auth(regular_user_token))

        assert response.status_code == 200
        [stored] = _named(mock_db, "n1")
        assert stored["comment"] == "ел хорошо"
        assert str(stored["_id"]) == created
        assert stored["local_id"] == "n1"

    def test_a_delete_by_name_removes_the_record(self, client, mock_db, regular_user_token, test_pet):
        _create(client, regular_user_token, test_pet["_id"], local_id="n1")

        response = client.delete("/api/events/local/n1", headers=_auth(regular_user_token))

        assert response.status_code == 200
        # Marked, not erased: the name stays with the tombstone, and no ordinary read finds the record.
        [stored] = _named(mock_db, "n1")
        assert stored["is_deleted"] is True

    def test_an_unknown_name_is_not_found(self, client, regular_user_token):
        put = client.put("/api/events/local/nothing", json={"comment": "x"}, headers=_auth(regular_user_token))
        delete = client.delete("/api/events/local/nothing", headers=_auth(regular_user_token))

        assert put.status_code == 404
        assert put.get_json()["code"] == "record_not_found"
        assert delete.status_code == 404
        assert delete.get_json()["code"] == "record_not_found"

    def test_someone_elses_record_answers_as_if_it_were_missing(
        self, client, mock_db, regular_user_token, test_pet, stranger_token
    ):
        _create(client, regular_user_token, test_pet["_id"], local_id="n1", comment="своя")

        put = client.put("/api/events/local/n1", json={"comment": "чужая"}, headers=_auth(stranger_token))
        delete = client.delete("/api/events/local/n1", headers=_auth(stranger_token))

        assert put.status_code == 404
        assert put.get_json()["code"] == "record_not_found"
        assert delete.status_code == 404
        [stored] = _named(mock_db, "n1")
        assert stored["comment"] == "своя"

    def test_the_record_still_changes_by_its_id(self, client, mock_db, regular_user_token, test_pet):
        created = _create(client, regular_user_token, test_pet["_id"], local_id="n1").get_json()["id"]

        response = client.put(
            f"/api/events/{created}", json={"comment": "по номеру"}, headers=_auth(regular_user_token)
        )

        assert response.status_code == 200
        assert mock_db["events"].find_one({"local_id": "n1"})["comment"] == "по номеру"
