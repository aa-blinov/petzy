"""«К приёму» edited from two places: the note carries a version like the vet profile does, so a save made from an
old copy is refused instead of silently wiping what the other person wrote."""

import pytest

from web.security import create_access_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _put(client, token, pet, body):
    return client.put(f"/api/pets/{pet['_id']}/visit-prep", json=body, headers=_auth(token))


def _card(client, token, pet):
    return client.get(f"/api/pets/{pet['_id']}/medical-card", headers=_auth(token)).get_json()["card"]


BODY = {"complaint": "Кашляет по ночам", "checks": {"appetite": "changed", "cough": "changed"}}
OTHER = {"complaint": "Перестал есть совсем", "checks": {"appetite": "changed"}}


@pytest.mark.health
class TestOneSavedNote:
    def test_a_save_comes_back_with_a_version(self, client, mock_db, regular_user_token, test_pet):
        prep = _put(client, regular_user_token, test_pet, BODY).get_json()["visit_prep"]
        assert prep["version"]
        assert _card(client, regular_user_token, test_pet)["visit_prep"]["version"] == prep["version"]

    def test_every_save_has_its_own_version(self, client, mock_db, regular_user_token, test_pet):
        first = _put(client, regular_user_token, test_pet, BODY).get_json()["visit_prep"]["version"]
        second = _put(client, regular_user_token, test_pet, OTHER).get_json()["visit_prep"]["version"]
        assert first != second
        assert _card(client, regular_user_token, test_pet)["visit_prep"]["version"] == second

    def test_the_version_the_form_came_from_is_not_stored_as_such(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, {**BODY, "base_version": ""})
        stored = mock_db["pets"].find_one({"_id": test_pet["_id"]})["visit_prep"]
        assert "base_version" not in stored and stored["version"]


@pytest.mark.health
class TestTwoPeopleEditingTheNote:
    def test_a_save_from_the_current_version_goes_through(self, client, mock_db, regular_user_token, test_pet):
        version = _put(client, regular_user_token, test_pet, BODY).get_json()["visit_prep"]["version"]
        response = _put(client, regular_user_token, test_pet, {**OTHER, "base_version": version})
        assert response.status_code == 200
        assert response.get_json()["visit_prep"]["complaint"] == "Перестал есть совсем"

    def test_a_stale_copy_is_refused_and_the_other_persons_note_comes_back(
        self, client, mock_db, regular_user_token, test_pet
    ):
        opened = _put(client, regular_user_token, test_pet, BODY).get_json()["visit_prep"]["version"]
        # The other device saves first.
        assert _put(client, regular_user_token, test_pet, {**OTHER, "base_version": opened}).status_code == 200
        # The first form, still on the old version, saves its own text.
        response = _put(client, regular_user_token, test_pet, {"complaint": "Кашляет", "base_version": opened})
        assert response.status_code == 409
        body = response.get_json()
        assert body["code"] == "conflict"
        assert "другом месте" in body["error"]
        # The other person's note is in the answer, so the person can look at it and choose.
        assert body["visit_prep"]["complaint"] == "Перестал есть совсем"
        assert body["visit_prep"]["version"] != opened
        # And it is still what is stored: the refused save changed nothing.
        stored = _card(client, regular_user_token, test_pet)["visit_prep"]
        assert stored["complaint"] == "Перестал есть совсем" and stored["version"] == body["visit_prep"]["version"]

    def test_a_stale_copy_cannot_take_the_note_away_either(self, client, mock_db, regular_user_token, test_pet):
        opened = _put(client, regular_user_token, test_pet, BODY).get_json()["visit_prep"]["version"]
        _put(client, regular_user_token, test_pet, {**OTHER, "base_version": opened})
        # Emptying the form is a save too: from an old copy it is refused the same way.
        assert (
            _put(client, regular_user_token, test_pet, {"complaint": None, "base_version": opened}).status_code == 409
        )
        assert _card(client, regular_user_token, test_pet)["visit_prep"]["complaint"] == "Перестал есть совсем"

    def test_two_forms_of_a_note_that_had_no_version_yet(self, client, mock_db, regular_user_token, test_pet):
        # Both forms opened before anything was written (no version, sent as an empty string).
        assert _put(client, regular_user_token, test_pet, {**BODY, "base_version": ""}).status_code == 200
        response = _put(client, regular_user_token, test_pet, {**OTHER, "base_version": ""})
        assert response.status_code == 409
        assert response.get_json()["visit_prep"]["complaint"] == "Кашляет по ночам"

    def test_a_note_saved_before_versions_existed_takes_a_form_made_from_it(
        self, client, mock_db, regular_user_token, test_pet
    ):
        mock_db["pets"].update_one(
            {"_id": test_pet["_id"]}, {"$set": {"visit_prep": {"complaint": "Стал вялым", "checks": {}}}}
        )
        assert _put(client, regular_user_token, test_pet, {**BODY, "base_version": ""}).status_code == 200

    def test_a_client_that_sends_no_version_still_saves_as_before(self, client, mock_db, regular_user_token, test_pet):
        _put(client, regular_user_token, test_pet, BODY)
        assert _put(client, regular_user_token, test_pet, OTHER).status_code == 200

    def test_the_clearing_the_visit_form_does_still_works_without_a_version(
        self, client, mock_db, regular_user_token, test_pet
    ):
        _put(client, regular_user_token, test_pet, BODY)
        assert _put(client, regular_user_token, test_pet, {}).get_json() == {"visit_prep": None}
        assert _card(client, regular_user_token, test_pet)["visit_prep"] is None


@pytest.mark.health
class TestTheOtherPersonIsSomebodyWithAccess:
    def test_a_shared_persons_stale_save_is_refused_too(self, client, mock_db, regular_user_token, test_pet):
        mock_db["users"].insert_one({"username": "friend", "is_active": True, "password_hash": "x"})
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["friend"]}})
        opened = _put(client, regular_user_token, test_pet, BODY).get_json()["visit_prep"]["version"]
        friend = create_access_token("friend")
        assert _put(client, friend, test_pet, {**OTHER, "base_version": opened}).status_code == 200
        assert _put(client, regular_user_token, test_pet, {**BODY, "base_version": opened}).status_code == 409
        assert _card(client, friend, test_pet)["visit_prep"]["complaint"] == "Перестал есть совсем"
