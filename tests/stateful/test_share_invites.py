"""Sharing is an invitation the other person accepts, and they can leave."""

from datetime import datetime, timezone

import pytest

from web.security import create_access_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def anna(mock_db):
    mock_db["users"].insert_one(
        {"username": "anna", "password_hash": "x", "is_active": True, "created_at": datetime.now(timezone.utc)}
    )
    return create_access_token("anna")


def _invite(client, owner_token, pet_id, username="anna"):
    return client.post(f"/api/pets/{pet_id}/share", json={"username": username}, headers=_auth(owner_token))


def _pet_ids(client, token):
    return [p["_id"] for p in client.get("/api/pets", headers=_auth(token)).get_json()["pets"]]


def test_an_invited_user_sees_nothing_until_they_accept(client, regular_user_token, test_pet, anna):
    pet_id = str(test_pet["_id"])
    assert _invite(client, regular_user_token, pet_id).status_code == 200
    assert pet_id not in _pet_ids(client, anna)
    assert client.get(f"/api/history/timeline?pet_id={pet_id}", headers=_auth(anna)).status_code in (403, 404)

    invites = client.get("/api/pets/invites", headers=_auth(anna)).get_json()["invites"]
    assert [(i["pet_id"], i["owner"]) for i in invites] == [(pet_id, "testuser")]

    assert client.post(f"/api/pets/{pet_id}/invite/accept", headers=_auth(anna)).status_code == 200
    assert pet_id in _pet_ids(client, anna)
    assert client.get("/api/pets/invites", headers=_auth(anna)).get_json()["invites"] == []


def test_a_declined_invite_gives_no_access(client, mock_db, regular_user_token, test_pet, anna):
    pet_id = str(test_pet["_id"])
    _invite(client, regular_user_token, pet_id)
    assert client.post(f"/api/pets/{pet_id}/invite/decline", headers=_auth(anna)).status_code == 200
    pet = mock_db["pets"].find_one({"_id": test_pet["_id"]})
    assert "anna" not in pet.get("shared_with", []) and "anna" not in pet.get("share_invites", [])


def test_nobody_accepts_an_invite_that_is_not_theirs(client, regular_user_token, test_pet, anna, mock_db):
    pet_id = str(test_pet["_id"])
    # No invite for anna at all.
    assert client.post(f"/api/pets/{pet_id}/invite/accept", headers=_auth(anna)).status_code == 404
    assert "anna" not in mock_db["pets"].find_one({"_id": test_pet["_id"]}).get("shared_with", [])


def test_the_owner_can_take_an_invite_back(client, mock_db, regular_user_token, test_pet, anna):
    pet_id = str(test_pet["_id"])
    _invite(client, regular_user_token, pet_id)
    assert client.delete(f"/api/pets/{pet_id}/share/anna", headers=_auth(regular_user_token)).status_code == 200
    assert client.post(f"/api/pets/{pet_id}/invite/accept", headers=_auth(anna)).status_code == 404


def test_a_member_can_leave(client, regular_user_token, test_pet, anna):
    pet_id = str(test_pet["_id"])
    _invite(client, regular_user_token, pet_id)
    client.post(f"/api/pets/{pet_id}/invite/accept", headers=_auth(anna))
    assert client.post(f"/api/pets/{pet_id}/leave", headers=_auth(anna)).status_code == 200
    assert pet_id not in _pet_ids(client, anna)
    # The owner can't "leave" their own pet this way.
    assert client.post(f"/api/pets/{pet_id}/leave", headers=_auth(regular_user_token)).status_code == 404


def test_only_the_owner_sees_who_is_invited(client, mock_db, regular_user_token, test_pet, anna):
    pet_id = str(test_pet["_id"])
    mock_db["users"].insert_one({"username": "boris", "password_hash": "x", "is_active": True})
    _invite(client, regular_user_token, pet_id)
    client.post(f"/api/pets/{pet_id}/invite/accept", headers=_auth(anna))
    _invite(client, regular_user_token, pet_id, "boris")
    owner_view = next(p for p in client.get("/api/pets", headers=_auth(regular_user_token)).get_json()["pets"])
    assert owner_view["share_invites"] == ["boris"]
    anna_view = next(p for p in client.get("/api/pets", headers=_auth(anna)).get_json()["pets"])
    assert "share_invites" not in anna_view or not anna_view["share_invites"]


def test_an_invite_does_not_put_you_in_the_senders_circle(client, regular_user_token, test_pet, anna, mock_db):
    """Before accepting, the invited user's custom types stay invisible to the sender."""
    mock_db["event_types"].insert_one(
        {
            "key": "anna_walk",
            "label": "Прогулка Анны",
            "icon": "paw",
            "color": "blue",
            "fields": [],
            "is_builtin": False,
            "created_by": "anna",
        }
    )
    _invite(client, regular_user_token, str(test_pet["_id"]))
    keys = [
        t["key"] for t in client.get("/api/event-types", headers=_auth(regular_user_token)).get_json()["event_types"]
    ]
    assert "anna_walk" not in keys
