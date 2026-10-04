"""A user deletes their own account: shared pets go on, the rest goes.

Runs against moto's in-memory bucket (conftest.s3_storage).
"""

import io
from datetime import datetime, timezone

import bcrypt
import pytest
from bson import ObjectId

from web.security import create_access_token

BUCKET = "petzy-test"
PASSWORD = "user123"  # conftest's regular_user


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _keys(s3, prefix=""):
    return {o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", [])}


def _user_folder(mock_db, username):
    return f"users/{mock_db['users'].find_one({'username': username})['_id']}/"


def _add_user(mock_db, username, active=True):
    mock_db["users"].insert_one(
        {
            "username": username,
            "password_hash": bcrypt.hashpw(b"secret-pass", bcrypt.gensalt()).decode(),
            "is_active": active,
            "email": f"{username}@example.com",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return create_access_token(username)


def _add_pet(mock_db, owner, name, shared_with=(), invites=()):
    return str(
        mock_db["pets"]
        .insert_one(
            {
                "name": name,
                "species": "cat",
                "owner": owner,
                "shared_with": list(shared_with),
                "share_invites": list(invites),
                "created_at": datetime.now(timezone.utc),
                "created_by": owner,
            }
        )
        .inserted_id
    )


def _add_files(client, token, pet_id, name):
    from PIL import Image

    photo = io.BytesIO()
    Image.new("RGB", (200, 200), (10, 120, 200)).save(photo, format="PNG")
    photo.seek(0)
    response = client.put(
        f"/api/pets/{pet_id}",
        data={"name": name, "photo_file": (photo, "cat.png", "image/png")},
        headers=_auth(token),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_json()
    response = client.post(
        "/api/documents",
        data={
            "pet_id": pet_id,
            "category": "other",
            "title": "Анализ крови",
            "file": (io.BytesIO(b"%PDF-1.4 test"), "blood.pdf", "application/pdf"),
        },
        headers=_auth(token),
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["id"]


def _event(mock_db, pet_id, username, type_="weight"):
    mock_db["events"].insert_one(
        {"pet_id": pet_id, "type": type_, "date_time": datetime.now(timezone.utc), "fields": {}, "username": username}
    )


def _delete(client, token, password=PASSWORD):
    return client.delete("/api/me/account", json={"password": password}, headers=_auth(token))


@pytest.fixture
def household(client, mock_db, regular_user, regular_user_token):
    """testuser owns a pet shared with anna (with files) and one nobody else
    has; anna owns a pet shared with testuser; boris invited testuser."""
    anna = _add_user(mock_db, "anna")
    _add_user(mock_db, "boris")
    shared = _add_pet(mock_db, "testuser", "Мурзик", shared_with=["anna"], invites=["boris"])
    solo = _add_pet(mock_db, "testuser", "Рекс")
    annas = _add_pet(mock_db, "anna", "Барсик", shared_with=["testuser"])
    borises = _add_pet(mock_db, "boris", "Шарик", invites=["testuser"])
    document_id = _add_files(client, regular_user_token, shared, "Мурзик")
    _add_files(client, regular_user_token, solo, "Рекс")
    return {
        "anna": anna,
        "shared": shared,
        "solo": solo,
        "annas": annas,
        "borises": borises,
        "document_id": document_id,
    }


def test_the_preview_says_what_happens_to_each_pet(client, household, regular_user_token):
    response = client.get("/api/me/account/deletion", headers=_auth(regular_user_token))
    assert response.status_code == 200
    body = response.get_json()
    assert body["can_delete"] is True
    assert [(p["name"], p["new_owner"]) for p in body["transferred"]] == [("Мурзик", "anna")]
    assert [p["name"] for p in body["deleted"]] == ["Рекс"]
    assert [(p["name"], p["owner"]) for p in body["left"]] == [("Барсик", "anna")]


def test_a_wrong_password_changes_nothing(client, mock_db, household, regular_user_token):
    assert _delete(client, regular_user_token, "wrong").status_code == 422
    assert mock_db["users"].find_one({"username": "testuser"})
    assert mock_db["pets"].count_documents({"owner": "testuser"}) == 2


def test_the_admin_account_cannot_be_deleted(client, mock_db, admin_token):
    assert client.get("/api/me/account/deletion", headers=_auth(admin_token)).get_json()["can_delete"] is False
    response = client.delete("/api/me/account", json={"password": "anything"}, headers=_auth(admin_token))
    assert response.status_code == 422
    assert response.get_json()["code"] == "account_admin_undeletable"
    assert mock_db["users"].find_one({"username": "admin"})


def test_deleting_the_account(client, mock_db, s3_storage, household, regular_user_token):
    old_folder = _user_folder(mock_db, "testuser")
    anna_folder = _user_folder(mock_db, "anna")
    shared, solo, annas = household["shared"], household["solo"], household["annas"]
    _event(mock_db, shared, "testuser")
    _event(mock_db, solo, "testuser")
    _event(mock_db, annas, "testuser")
    _event(mock_db, annas, "anna")
    mock_db["event_types"].insert_many(
        [
            {"key": "custom_walk", "label": "Прогулка", "icon": "x", "color": "#000", "created_by": "testuser"},
            {"key": "unused", "label": "Лишнее", "icon": "x", "color": "#000", "created_by": "testuser"},
        ]
    )
    _event(mock_db, shared, "testuser", type_="custom_walk")
    mock_db["push_subscriptions"].insert_one({"username": "testuser", "endpoint": "https://push.example/1"})

    response = _delete(client, regular_user_token)
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["message"] == "Аккаунт удалён"
    cookies = " ".join(response.headers.getlist("Set-Cookie"))
    assert "access_token=;" in cookies and "refresh_token=;" in cookies

    # The account and everything personal is gone; its token stops working.
    assert mock_db["users"].find_one({"username": "testuser"}) is None
    assert mock_db["push_subscriptions"].count_documents({"username": "testuser"}) == 0
    assert mock_db["refresh_tokens"].count_documents({"username": "testuser"}) == 0
    assert client.get("/api/pets", headers=_auth(regular_user_token)).status_code == 401

    # The pet nobody else had is deleted with its records.
    assert mock_db["pets"].find_one({"_id": ObjectId(solo)}) is None
    assert mock_db["events"].count_documents({"pet_id": solo}) == 0
    assert mock_db["documents"].count_documents({"pet_id": solo}) == 0

    # The shared pet is anna's now, files moved into her folder.
    pet = mock_db["pets"].find_one({"_id": ObjectId(shared)})
    assert pet["owner"] == "anna" and pet["shared_with"] == [] and pet["share_invites"] == ["boris"]
    assert "created_by" not in pet
    assert pet["photo_file_id"].startswith(f"{anna_folder}pets/{shared}/")
    document = mock_db["documents"].find_one({"_id": ObjectId(household["document_id"])})
    assert document["file_id"].startswith(f"{anna_folder}pets/{shared}/")
    anna = household["anna"]
    assert client.get(f"/api/pets/{shared}/photo", headers=_auth(anna)).status_code == 200
    file_response = client.get(f"/api/documents/{household['document_id']}/file", headers=_auth(anna))
    assert file_response.status_code in (200, 302), file_response.get_json()
    assert _keys(s3_storage, old_folder) == set()

    # What testuser wrote stays, without their name; anna's own records keep hers.
    assert mock_db["events"].count_documents({"username": "testuser"}) == 0
    assert mock_db["documents"].count_documents({"username": "testuser"}) == 0
    assert mock_db["events"].count_documents({"pet_id": annas, "username": ""}) == 1
    assert mock_db["events"].count_documents({"pet_id": annas, "username": "anna"}) == 1

    # No more access to others' pets, no invitations left.
    assert "testuser" not in mock_db["pets"].find_one({"_id": ObjectId(annas)})["shared_with"]
    assert "testuser" not in mock_db["pets"].find_one({"_id": ObjectId(household["borises"])})["share_invites"]

    # A record type still in use goes to the pet's new owner; an unused one goes.
    assert mock_db["event_types"].find_one({"key": "custom_walk"})["created_by"] == "anna"
    assert mock_db["event_types"].find_one({"key": "unused"}) is None


def test_the_letters(client, mock_db, household, regular_user_token, monkeypatch):
    from web import mail

    monkeypatch.setenv("MAIL_OUTBOX", "memory")
    mail.OUTBOX.clear()
    mock_db["users"].update_one({"username": "testuser"}, {"$set": {"email_verified": True}})
    assert _delete(client, regular_user_token).status_code == 200
    by_address = {letter["to"]: letter for letter in mail.OUTBOX}
    assert "удалён" in by_address["test@example.com"]["subject"]
    assert "«Мурзик»" in by_address["anna@example.com"]["text"]


def test_the_heir_is_someone_who_can_still_sign_in(client, mock_db, regular_user, regular_user_token):
    _add_user(mock_db, "blocked", active=False)
    _add_user(mock_db, "vera")
    pet = _add_pet(mock_db, "testuser", "Мурзик", shared_with=["ghost", "blocked", "vera"])
    assert _delete(client, regular_user_token).status_code == 200
    assert mock_db["pets"].find_one({"_id": ObjectId(pet)})["owner"] == "vera"
    assert mock_db["pets"].find_one({"_id": ObjectId(pet)})["shared_with"] == ["ghost", "blocked"]


def test_the_login_registered_again_sees_nothing_of_the_old_account(client, mock_db, household, regular_user_token):
    assert _delete(client, regular_user_token).status_code == 200
    mock_db["users"].insert_one({"username": "testuser", "password_hash": "x", "is_active": True})
    token = create_access_token("testuser")
    assert client.get("/api/pets", headers=_auth(token)).get_json()["pets"] == []
    assert client.get("/api/pets/invites", headers=_auth(token)).get_json()["invites"] == []


def test_a_file_store_failure_leaves_the_account_as_it_was(client, mock_db, household, regular_user_token, monkeypatch):
    from web import storage

    def broken(*_args, **_kwargs):
        raise RuntimeError("store is down")

    monkeypatch.setattr(storage, "copy_object", broken)
    response = _delete(client, regular_user_token)
    assert response.status_code == 500
    assert response.get_json()["code"] == "account_delete_failed"
    assert mock_db["users"].find_one({"username": "testuser"})
    assert mock_db["pets"].count_documents({"owner": "testuser"}) == 2
