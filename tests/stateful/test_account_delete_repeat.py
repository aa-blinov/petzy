"""The same DELETE twice: the second one is the same request, not a mistake.

A first attempt that reached the server and lost its answer leaves a person
pressing the button again. There is no account left to check the password
against, so the repeat answers as the first one did instead of «неверный
пароль».
"""

from datetime import datetime, timezone

from bson import ObjectId

from web.security import create_access_token
from tests.conftest import password_hash_for

PASSWORD = "user123"  # conftest's regular_user

# Deleting is limited to ten an hour per address, and the whole file shares
# 127.0.0.1: each test asks from its own address, as separate phones would.
_addresses = iter(range(1, 400))


def _auth(token):
    return {"Authorization": f"Bearer {token}", "X-Forwarded-For": f"198.51.100.{next(_addresses)}"}


def _delete(client, token, password=PASSWORD):
    return client.delete("/api/me/account", json={"password": password}, headers=_auth(token))


def _other_household(mock_db):
    """Someone else's account, pet and records: a repeat must not touch them."""
    mock_db["users"].insert_one(
        {
            "username": "anna",
            "password_hash": password_hash_for(b"anna-secret"),
            "is_active": True,
            "email": "anna@example.com",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
        }
    )
    pet_id = str(
        mock_db["pets"]
        .insert_one(
            {
                "name": "Барсик",
                "species": "cat",
                "owner": "anna",
                "shared_with": [],
                "created_at": datetime.now(timezone.utc),
                "created_by": "anna",
            }
        )
        .inserted_id
    )
    mock_db["events"].insert_one(
        {
            "pet_id": pet_id,
            "type": "weight",
            "date_time": datetime.now(timezone.utc),
            "fields": {"weight": 4.0},
            "username": "anna",
        }
    )
    return pet_id


def test_the_second_delete_answers_as_the_first(client, mock_db, regular_user_token):
    first = _delete(client, regular_user_token)
    assert first.status_code == 200
    assert first.get_json()["message"] == "Аккаунт удалён"

    second = _delete(client, regular_user_token)
    assert second.status_code == 200, second.get_json()
    assert second.get_json() == first.get_json()
    cookies = " ".join(second.headers.getlist("Set-Cookie"))
    assert "access_token=;" in cookies and "refresh_token=;" in cookies


def test_the_repeat_does_not_ask_for_the_password_again(client, mock_db, regular_user_token):
    """No account is left to check a password against, so any password the
    person remembers types in answers the same way."""
    _delete(client, regular_user_token)
    response = _delete(client, regular_user_token, "something-else-entirely")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["message"] == "Аккаунт удалён"


def test_the_repeat_leaves_everyone_else_alone(client, mock_db, regular_user_token):
    annas_pet = _other_household(mock_db)
    _delete(client, regular_user_token)

    assert _delete(client, regular_user_token).status_code == 200

    assert mock_db["users"].find_one({"username": "anna"})
    assert mock_db["pets"].find_one({"_id": ObjectId(annas_pet)})
    assert mock_db["events"].count_documents({"pet_id": annas_pet}) == 1
    assert mock_db["pets"].find_one({"_id": ObjectId(annas_pet)})["shared_with"] == []


def test_nothing_of_the_account_is_kept_but_the_login(client, mock_db, regular_user_token):
    """Only «this login is gone» is remembered: a login list has no hashes,
    no names and no addresses in it."""
    _delete(client, regular_user_token)
    row = mock_db["deleted_accounts"].find_one({"username": "testuser"})
    assert row is not None
    assert row["deleted_at"] is not None
    assert set(row) == {"_id", "username", "deleted_at"}


def test_a_wrong_password_before_any_delete_still_changes_nothing(client, mock_db, regular_user_token):
    _other_household(mock_db)
    response = _delete(client, regular_user_token, "wrong")
    assert response.status_code == 422
    assert response.get_json()["code"] == "account_wrong_password"
    assert mock_db["users"].find_one({"username": "testuser"})
    assert mock_db["deleted_accounts"].count_documents({}) == 0


def test_the_login_registered_again_is_a_new_account(client, mock_db, regular_user_token):
    """«testuser» is free again: the next owner of the login is asked for the
    password as any other account would be."""
    _delete(client, regular_user_token)
    mock_db["users"].insert_one(
        {
            "username": "testuser",
            "password_hash": password_hash_for(b"new-owner-pass"),
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
    )
    token = create_access_token("testuser")
    assert _delete(client, token, "wrong").get_json()["code"] == "account_wrong_password"
    assert mock_db["users"].find_one({"username": "testuser"})
    assert _delete(client, token, "new-owner-pass").status_code == 200


def test_deleting_twice_over_is_still_one_row(client, mock_db, regular_user_token):
    _delete(client, regular_user_token)
    _delete(client, regular_user_token)
    _delete(client, regular_user_token)
    assert mock_db["deleted_accounts"].count_documents({"username": "testuser"}) == 1
