"""A picture address that is broken, too old, or made for nobody opens nothing.

The address of a picture carries its own proof: who it was made for, when it stops working and a
signature over the file it opens. A broken address must be refused the same way every time, and it
must be refused before the file is even looked for.
"""

import web.picture_links as picture_links
from bson import ObjectId
from datetime import datetime, timezone
from web.app import app as flask_app

WEBP = (b"RIFF\x10\x00\x00\x00WEBPVP8 ", "image/webp")


def _user_id(mock_db, username="testuser"):
    return str(mock_db["users"].find_one({"username": username})["_id"])


def _expiry():
    now = picture_links._now()
    return picture_links._expiry(now)


def _address(user_id, exp=None, sig="a-signature"):
    return f"uid={user_id}&exp={exp if exp is not None else _expiry()}&sig={sig}"


def _picture_document(mock_db, pet, title):
    return (
        mock_db["documents"]
        .insert_one(
            {
                "pet_id": str(pet["_id"]),
                "username": "testuser",
                "category": "other",
                "title": title,
                "original_filename": f"{title}.jpg",
                "content_type": "image/jpeg",
                "file_id": f"docs/{title}.jpg",
                "file_size": 2048,
                "created_at": datetime.now(timezone.utc),
            }
        )
        .inserted_id
    )


def test_an_address_with_a_broken_person_id_is_refused(client, mock_db, regular_user_token, test_pet):
    response = client.get(f"/api/pets/{test_pet['_id']}/photo?{_address('not-an-id')}")

    assert response.status_code == 401
    assert response.get_json()["code"] == "picture_link_invalid"


def test_an_address_without_a_readable_time_is_refused(client, mock_db, regular_user_token, test_pet):
    response = client.get(f"/api/pets/{test_pet['_id']}/photo?{_address(_user_id(mock_db), exp='abc')}")

    assert response.status_code == 401
    assert response.get_json()["code"] == "picture_link_invalid"


def test_the_address_of_a_pet_without_a_photo_says_the_photo_is_not_there(
    client, mock_db, regular_user_token, test_pet
):
    response = client.get(f"/api/pets/{test_pet['_id']}/photo?{_address(_user_id(mock_db))}")

    assert response.status_code == 404
    assert response.get_json()["code"] == "photo_not_found"


def test_the_address_of_a_document_that_is_not_there_says_the_record_is_not_there(client, mock_db, regular_user_token):
    response = client.get(f"/api/documents/{ObjectId()}/file?{_address(_user_id(mock_db))}")

    assert response.status_code == 404
    assert response.get_json()["code"] == "record_not_found"


def test_two_pictures_in_one_list_are_for_the_same_person(client, mock_db, regular_user_token, test_pet, monkeypatch):
    """The person is looked up once for the whole answer: both pictures are for the same person."""
    monkeypatch.setattr("web.documents.load_image_variant", lambda file_id, w, h, ctype: WEBP)
    _picture_document(mock_db, test_pet, "one")
    _picture_document(mock_db, test_pet, "two")

    listed = client.get(
        f"/api/documents?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
    )
    urls = [d["file_url"] for d in listed.get_json()["documents"]]

    assert len(urls) == 2
    assert all(url for url in urls)
    assert len({url.split("uid=")[1].split("&")[0] for url in urls}) == 1


def test_a_picture_address_is_only_made_for_somebody_who_is_there():
    """Nobody is asking, so there is no address: a picture is only ever given to someone."""
    with flask_app.test_request_context("/"):
        assert picture_links.signed_picture_url("/api/pets/1/photo", "pet-photo", "1", "v") is None
