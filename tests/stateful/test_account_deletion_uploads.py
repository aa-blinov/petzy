"""An unfinished scan upload must not outlive the account that started it.

A slot in `document_uploads` is a file still being uploaded: the upload link
belongs to whoever started it, and it stops working the moment the account is
gone. Left behind, the row kept counting against the *pet owner's* storage
quota (web/documents.py sums pending slots) and pointed at a stored object
nobody could finish.

Slots of a pet that is deleted or handed over were already cleaned; this is
about the pet that stays: somebody else's pet the user had access to.
"""

from datetime import datetime, timezone

import pytest

from tests.conftest import password_hash_for
from web.security import create_access_token


@pytest.fixture
def regular_user(mock_db):
    mock_db["users"].insert_one(
        {
            "username": "testuser",
            "password_hash": password_hash_for(b"user123"),
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
    )


@pytest.fixture
def token(regular_user):
    return create_access_token("testuser")


def _auth(jwt):
    return {"Authorization": f"Bearer {jwt}"}


def _other_user(mock_db, username):
    mock_db["users"].insert_one(
        {
            "username": username,
            "password_hash": password_hash_for(b"secret-pass"),
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
    )


def _pet(mock_db, owner, name, shared_with=()):
    return str(
        mock_db["pets"]
        .insert_one(
            {
                "name": name,
                "species": "cat",
                "owner": owner,
                "shared_with": list(shared_with),
                "created_at": datetime.now(timezone.utc),
                "created_by": owner,
            }
        )
        .inserted_id
    )


def _slot(mock_db, username, pet_id, name):
    mock_db["document_uploads"].insert_one(
        {
            "_id": f"slot-{username}-{name}",
            "key": f"users/x/pets/{pet_id}/scans/{name}.pdf",
            "pet_id": pet_id,
            "username": username,
            "filename": "анализ.pdf",
            "size": 1000,
            "created_at": datetime.now(timezone.utc),
        }
    )


def _delete_account(client, token):
    return client.delete("/api/me/account", json={"password": "user123"}, headers=_auth(token))


def test_the_slot_of_a_scan_somebody_elses_pet_is_gone(client, mock_db, token):
    _other_user(mock_db, "anna")
    annas_pet = _pet(mock_db, "anna", "Барсик", shared_with=["testuser"])
    _slot(mock_db, "testuser", annas_pet, "mine")

    assert _delete_account(client, token).status_code == 200
    assert mock_db["document_uploads"].count_documents({"username": "testuser"}) == 0
    # The pet and its owner are untouched: only the dead user's slot went.
    assert mock_db["pets"].find_one({"name": "Барсик"})
    assert mock_db["users"].find_one({"username": "anna"})


def test_another_users_slot_on_the_same_pet_stays(client, mock_db, token):
    """The pet belongs to someone else, so its owner's own upload is not
    this account's to delete."""
    _other_user(mock_db, "anna")
    annas_pet = _pet(mock_db, "anna", "Барсик", shared_with=["testuser"])
    _slot(mock_db, "testuser", annas_pet, "mine")
    _slot(mock_db, "anna", annas_pet, "hers")

    assert _delete_account(client, token).status_code == 200
    remaining = list(mock_db["document_uploads"].find({"pet_id": annas_pet}, {"username": 1}))
    assert [slot["username"] for slot in remaining] == ["anna"]


def test_the_slot_of_a_deleted_pet_is_gone_too(client, mock_db, token):
    """The pet purge has always cleaned these; this says so out loud, since
    the account list and the pet list are two separate places to remember."""
    own_pet = _pet(mock_db, "testuser", "Рекс")
    _slot(mock_db, "testuser", own_pet, "mine")

    assert _delete_account(client, token).status_code == 200
    assert mock_db["document_uploads"].count_documents({}) == 0


def test_a_pet_deleted_on_its_own_takes_its_slot_with_it(client, mock_db, token):
    """Not account deletion: deleting one pet clears that pet's slots, so a
    file that can never be finished stops counting against a quota."""
    own_pet = _pet(mock_db, "testuser", "Рекс")
    _slot(mock_db, "testuser", own_pet, "mine")
    other = _pet(mock_db, "testuser", "Мурзик")
    _slot(mock_db, "testuser", other, "other")

    assert client.delete(f"/api/pets/{own_pet}", headers=_auth(token)).status_code == 200
    remaining = list(mock_db["document_uploads"].find({}, {"pet_id": 1}))
    assert [slot["pet_id"] for slot in remaining] == [other]
