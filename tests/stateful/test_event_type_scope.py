"""Custom event types belong to a household, not to the whole server."""

from datetime import datetime, timezone

import bcrypt
import pytest

from web.security import create_access_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _user(mock_db, name):
    mock_db["users"].insert_one(
        {
            "username": name,
            "password_hash": bcrypt.hashpw(b"x12345678", bcrypt.gensalt()).decode(),
            "created_at": datetime.now(timezone.utc),
            "is_active": True,
        }
    )
    return create_access_token(name)


@pytest.fixture
def stranger(mock_db):
    return _user(mock_db, "stranger")


@pytest.fixture
def family(mock_db, test_pet):
    token = _user(mock_db, "family")
    mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["family"]}})
    return token


@pytest.fixture
def walk(client, regular_user_token):
    response = client.post(
        "/api/event-types",
        json={"label": "Прогулка", "icon": "footprints", "color": "green", "fields": []},
        headers=_auth(regular_user_token),
    )
    assert response.status_code == 201
    return response.get_json()["key"]


def _keys(client, token):
    return {t["key"] for t in client.get("/api/event-types", headers=_auth(token)).get_json()["event_types"]}


def test_another_household_does_not_see_it(client, walk, stranger):
    assert walk not in _keys(client, stranger)


def test_the_author_and_their_household_see_it(client, walk, regular_user_token, family):
    assert walk in _keys(client, regular_user_token)
    assert walk in _keys(client, family)


def test_everyone_sees_the_builtins(client, stranger):
    assert {"feeding", "weight"} <= _keys(client, stranger)


def test_a_stranger_cannot_change_or_delete_it(client, mock_db, walk, stranger):
    renamed = client.put(f"/api/event-types/{walk}", json={"label": "Чужое"}, headers=_auth(stranger))
    deleted = client.delete(f"/api/event-types/{walk}", headers=_auth(stranger))

    assert renamed.status_code == 404 and deleted.status_code == 404
    assert mock_db["event_types"].find_one({"key": walk})["label"] == "Прогулка"


def test_family_sees_it_but_only_the_author_changes_it(client, mock_db, walk, family):
    renamed = client.put(f"/api/event-types/{walk}", json={"label": "Моё"}, headers=_auth(family))
    deleted = client.delete(f"/api/event-types/{walk}", headers=_auth(family))

    assert renamed.status_code == 403 and deleted.status_code == 403
    assert mock_db["event_types"].find_one({"key": walk})["label"] == "Прогулка"


def test_the_author_changes_it(client, walk, regular_user_token):
    response = client.put(
        f"/api/event-types/{walk}", json={"label": "Прогулка в парке"}, headers=_auth(regular_user_token)
    )
    assert response.status_code == 200 and response.get_json()["created_by"] == "testuser"


def test_a_record_needs_a_type_the_user_can_see(client, mock_db, walk, stranger):
    pet = mock_db["pets"].insert_one({"name": "Чужой", "owner": "stranger", "shared_with": []}).inserted_id
    now = datetime.now(timezone.utc)

    response = client.post(
        f"/api/events?pet_id={pet}",
        json={
            "pet_id": str(pet),
            "type": walk,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "fields": {},
        },
        headers=_auth(stranger),
    )

    assert response.status_code == 404


def test_family_can_log_a_record_of_it_on_the_shared_pet(client, walk, family, test_pet):
    now = datetime.now(timezone.utc)
    response = client.post(
        f"/api/events?pet_id={test_pet['_id']}",
        json={
            "pet_id": str(test_pet["_id"]),
            "type": walk,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "fields": {},
        },
        headers=_auth(family),
    )
    assert response.status_code == 201, response.get_json()
