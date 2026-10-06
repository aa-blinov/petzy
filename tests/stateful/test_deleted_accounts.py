"""The `deleted_accounts` collection: what it is for, what it is not.

It remembers that a login is gone so that the same DELETE asked twice answers
the same way. It must not become a list of the people who once had an account,
and no cleanup of a pet or an account may take it away.
"""

from datetime import datetime, timezone

from mongomock import MongoClient
from unittest.mock import patch

from web.account_deletion import PERSONAL_COLLECTIONS, was_deleted
from web.db import ensure_indexes
from web.security import create_access_token


def _patched_db():
    mock_db = MongoClient()["deleted_accounts_test"]
    return patch("web.db.db", mock_db), mock_db


def test_the_login_index_is_there():
    """web/db.py declares it on the login; the flag the decision asks for
    ({'unique': True}) isn't on that line yet — see the report."""
    cm, mock_db = _patched_db()
    with cm:
        ensure_indexes()
    info = mock_db["deleted_accounts"].index_information()
    assert "deleted_accounts_username" in info, list(info)
    assert [("username", 1)] == [tuple(k) for k in info["deleted_accounts_username"]["key"]]


def test_a_deleted_login_is_remembered_but_a_living_one_is_not(client, mock_db, regular_user, regular_user_token):
    assert was_deleted("testuser") is False
    client.delete(
        "/api/me/account", json={"password": "user123"}, headers={"Authorization": f"Bearer {regular_user_token}"}
    )
    assert was_deleted("testuser") is True
    # A login that exists again belongs to the next person: no memory of the
    # old account, and the request goes the ordinary way.
    mock_db["users"].insert_one({"username": "testuser", "password_hash": "x", "is_active": True})
    assert was_deleted("testuser") is False
    assert (
        client.delete(
            "/api/me/account",
            json={"password": "x"},
            headers={"Authorization": f"Bearer {create_access_token('testuser')}"},
        ).get_json()["code"]
        == "account_wrong_password"
    )


def test_deleting_a_pet_leaves_the_remembered_logins_alone(client, mock_db, regular_user_token, test_pet):
    mock_db["deleted_accounts"].insert_one({"username": "someone-else", "deleted_at": datetime.now(timezone.utc)})
    client.delete(f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"})
    assert mock_db["deleted_accounts"].count_documents({"username": "someone-else"}) == 1


def test_the_collection_is_not_one_of_the_cleaned_ones():
    """It holds no data of the account, so it is deliberately absent from the
    list an account deletion sweeps."""
    assert "deleted_accounts" not in PERSONAL_COLLECTIONS
    from web.account_deletion import AUTHORED_COLLECTIONS

    assert "deleted_accounts" not in AUTHORED_COLLECTIONS
