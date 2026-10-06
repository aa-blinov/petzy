"""The link to a card is a copy, but the person who made it may be the owner opening it on their own phone to
show it to a vet. Then the page names the pet and the way back into the app is offered; with no session there is
no id and no way in."""

import pytest

from web.security import create_access_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make(client, token, pet, days=7):
    return client.post(f"/api/pets/{pet['_id']}/medical-card/shares", json={"days": days}, headers=_auth(token))


def _open(client, share_token, headers=None):
    return client.get(f"/api/shared/medical-card/{share_token}", headers=headers or {})


@pytest.mark.health
class TestTheWayBackIntoTheApp:
    def test_the_owner_opening_their_own_link_is_told_which_pet_it_is(
        self, client, mock_db, regular_user_token, test_pet
    ):
        share = _make(client, regular_user_token, test_pet).get_json()["token"]
        body = _open(client, share, _auth(regular_user_token)).get_json()
        assert body["pet_id"] == str(test_pet["_id"])

    def test_someone_the_pet_is_shared_with_gets_it_too(self, client, mock_db, regular_user_token, test_pet):
        mock_db["users"].insert_one({"username": "friend", "is_active": True, "password_hash": "x"})
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["friend"]}})
        share = _make(client, regular_user_token, test_pet).get_json()["token"]
        assert _open(client, share, _auth(create_access_token("friend"))).get_json()["pet_id"] == str(test_pet["_id"])

    def test_a_vet_with_no_account_gets_no_pet_and_no_way_in(self, client, mock_db, regular_user_token, test_pet):
        share = _make(client, regular_user_token, test_pet).get_json()["token"]
        body = _open(client, share).get_json()
        assert "pet_id" not in body
        assert body["card"]["can_edit"] is False

    def test_a_signed_in_stranger_gets_no_pet(self, client, mock_db, regular_user_token, test_pet):
        mock_db["users"].insert_one({"username": "stranger", "is_active": True, "password_hash": "x"})
        share = _make(client, regular_user_token, test_pet).get_json()["token"]
        assert "pet_id" not in _open(client, share, _auth(create_access_token("stranger"))).get_json()

    def test_a_disabled_account_gets_no_pet(self, client, mock_db, regular_user_token, test_pet):
        mock_db["users"].insert_one({"username": "off", "is_active": False, "password_hash": "x"})
        share = _make(client, regular_user_token, test_pet).get_json()["token"]
        assert "pet_id" not in _open(client, share, _auth(create_access_token("off"))).get_json()

    def test_a_broken_token_gets_no_pet_and_the_card_still_opens(self, client, mock_db, regular_user_token, test_pet):
        share = _make(client, regular_user_token, test_pet).get_json()["token"]
        response = _open(client, share, _auth("not-a-token"))
        assert response.status_code == 200
        assert "pet_id" not in response.get_json()

    def test_the_card_is_the_same_copy_either_way(self, client, mock_db, regular_user_token, test_pet):
        share = _make(client, regular_user_token, test_pet).get_json()["token"]
        signed_in = _open(client, share, _auth(regular_user_token)).get_json()
        as_vet = _open(client, share).get_json()
        assert signed_in["card"] == as_vet["card"] == as_vet["card"]

    def test_the_private_headers_stay_the_same_with_a_session(self, client, mock_db, regular_user_token, test_pet):
        share = _make(client, regular_user_token, test_pet).get_json()["token"]
        response = _open(client, share, _auth(regular_user_token))
        assert response.headers["Cache-Control"] == "private, no-store"
        assert "noindex" in response.headers["X-Robots-Tag"]
        assert response.headers["Referrer-Policy"] == "no-referrer"
