"""Pictures on a signed address: they open without sign-in headers, and only for the person they were made for.

A native app shows a picture from a plain URL. The address carries its own proof, and each time it is used the stand
checks the signature, the expiry, and that the person still sees the pet. The picture size is not part of the proof.
"""

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from bson import ObjectId

import web.picture_links as picture_links

WEBP = (b"RIFF\x10\x00\x00\x00WEBPVP8 ", "image/webp")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _as_path(url):
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


def _people(mock_db, pet, *, shared_with_family=True):
    """The owner's token, the family's token, and the family's user id."""
    from web.security import create_access_token

    family = mock_db["users"].insert_one(
        {
            "username": "family",
            "password_hash": "unused",
            "full_name": "Семья",
            "email": "",
            "created_at": datetime.now(timezone.utc),
            "created_by": "admin",
            "is_active": True,
        }
    )
    if shared_with_family:
        mock_db["pets"].update_one({"_id": pet["_id"]}, {"$set": {"shared_with": ["family"]}})
    return create_access_token("family"), str(family.inserted_id)


def _with_photo(mock_db, pet, monkeypatch, ref="photos/rex.webp"):
    mock_db["pets"].update_one({"_id": pet["_id"]}, {"$set": {"photo_file_id": ref}})
    monkeypatch.setattr("web.pets.load_image_variant", lambda file_id, w, h: WEBP)


def _photo_url(client, token, pet_id):
    pets = client.get("/api/pets", headers=_auth(token)).get_json()["pets"]
    return next(p for p in pets if p["_id"] == str(pet_id))["photo_url"]


@pytest.mark.health_records
class TestPetPhotoAddress:
    def test_the_address_is_absolute_signed_and_opens_without_headers(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        _with_photo(mock_db, test_pet, monkeypatch)
        url = _photo_url(client, regular_user_token, test_pet["_id"])

        query = parse_qs(urlsplit(url).query)
        response = client.get(_as_path(url))

        assert url.startswith("https://") or url.startswith("http://")
        assert {"uid", "exp", "sig"} <= set(query)
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/webp"

    def test_a_changed_signature_is_refused(self, client, mock_db, regular_user_token, test_pet, monkeypatch):
        _with_photo(mock_db, test_pet, monkeypatch)
        url = _photo_url(client, regular_user_token, test_pet["_id"])
        forged = url[:-4] + ("AAAA" if not url.endswith("AAAA") else "BBBB")

        response = client.get(_as_path(forged))

        assert response.status_code == 401
        assert response.get_json()["code"] == "picture_link_invalid"

    def test_an_address_without_the_person_or_with_a_strange_signature_is_refused(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        _with_photo(mock_db, test_pet, monkeypatch)
        url = _photo_url(client, regular_user_token, test_pet["_id"])
        without_person = url.replace("uid=" + parse_qs(urlsplit(url).query)["uid"][0] + "&", "")
        strange_signature = url.split("sig=")[0] + "sig=подпись"

        assert client.get(_as_path(without_person)).status_code == 401
        assert client.get(_as_path(strange_signature)).status_code == 401

    def test_someone_elses_user_id_is_refused(self, client, mock_db, regular_user_token, test_pet, monkeypatch):
        _with_photo(mock_db, test_pet, monkeypatch)
        url = _photo_url(client, regular_user_token, test_pet["_id"])
        stranger = str(ObjectId())
        swapped = url.replace(parse_qs(urlsplit(url).query)["uid"][0], stranger)

        assert client.get(_as_path(swapped)).status_code == 401

    def test_an_expired_address_is_refused(self, client, mock_db, regular_user_token, test_pet, monkeypatch):
        _with_photo(mock_db, test_pet, monkeypatch)
        url = _photo_url(client, regular_user_token, test_pet["_id"])
        much_later = picture_links._now() + 3 * picture_links.HOUR
        monkeypatch.setattr(picture_links, "_now", lambda: much_later)

        response = client.get(_as_path(url))

        assert response.status_code == 401
        assert response.get_json()["code"] == "picture_link_invalid"

    def test_an_address_that_lasts_longer_than_two_hours_is_refused(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        _with_photo(mock_db, test_pet, monkeypatch)
        user_id = str(mock_db["users"].find_one({"username": "testuser"})["_id"])
        now = picture_links._now()
        too_long = now + 3 * picture_links.HOUR
        sig = picture_links._signature(
            "pet-photo", str(test_pet["_id"]), picture_links.storage.file_version("photos/rex.webp"), user_id, too_long
        )
        url = f"/api/pets/{test_pet['_id']}/photo?uid={user_id}&exp={too_long}&sig={sig}"

        assert client.get(url).status_code == 401

    def test_the_address_is_stable_within_the_hour_and_lasts_one_to_two_hours(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        _with_photo(mock_db, test_pet, monkeypatch)
        first = parse_qs(urlsplit(_photo_url(client, regular_user_token, test_pet["_id"])).query)
        second = parse_qs(urlsplit(_photo_url(client, regular_user_token, test_pet["_id"])).query)
        exp = int(first["exp"][0])
        now = picture_links._now()

        assert first["sig"] == second["sig"]
        assert exp % picture_links.HOUR == 0
        assert picture_links.HOUR < exp - now <= 2 * picture_links.HOUR

    def test_a_new_photo_makes_the_old_address_invalid(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        _with_photo(mock_db, test_pet, monkeypatch)
        old = _photo_url(client, regular_user_token, test_pet["_id"])
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": "photos/new.webp"}})

        assert client.get(_as_path(old)).status_code == 401

    def test_taking_the_sharing_away_ends_the_address_at_once(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        _with_photo(mock_db, test_pet, monkeypatch)
        family_token, _ = _people(mock_db, test_pet)
        family_url = _photo_url(client, family_token, test_pet["_id"])
        assert client.get(_as_path(family_url)).status_code == 200

        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": []}})

        assert client.get(_as_path(family_url)).status_code == 404

    def test_a_deactivated_person_ends_the_address(self, client, mock_db, regular_user_token, test_pet, monkeypatch):
        _with_photo(mock_db, test_pet, monkeypatch)
        family_token, _ = _people(mock_db, test_pet)
        family_url = _photo_url(client, family_token, test_pet["_id"])

        mock_db["users"].update_one({"username": "family"}, {"$set": {"is_active": False}})

        assert client.get(_as_path(family_url)).status_code == 401

    def test_the_size_is_not_part_of_the_proof(self, client, mock_db, regular_user_token, test_pet, monkeypatch):
        _with_photo(mock_db, test_pet, monkeypatch)
        url = _photo_url(client, regular_user_token, test_pet["_id"])

        assert client.get(_as_path(url) + "&w=300").status_code == 200

    def test_without_an_address_and_without_a_session_the_picture_is_refused(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        _with_photo(mock_db, test_pet, monkeypatch)

        assert client.get(f"/api/pets/{test_pet['_id']}/photo").status_code == 401

    def test_the_session_still_opens_it_as_before(self, client, mock_db, regular_user_token, test_pet, monkeypatch):
        _with_photo(mock_db, test_pet, monkeypatch)

        response = client.get(f"/api/pets/{test_pet['_id']}/photo", headers=_auth(regular_user_token))

        assert response.status_code == 200


@pytest.mark.health_records
class TestDocumentPictureAddress:
    def _document(self, mock_db, pet, *, content_type, scan=False):
        return (
            mock_db["documents"]
            .insert_one(
                {
                    "pet_id": str(pet["_id"]),
                    "username": "testuser",
                    "category": "other",
                    "title": "Выписка",
                    "original_filename": "scan.jpg",
                    "content_type": content_type,
                    "file_id": "docs/one.jpg",
                    "file_size": 2048,
                    "scan": scan,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            .inserted_id
        )

    def test_a_document_picture_has_an_address_that_opens_without_headers(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        monkeypatch.setattr("web.documents.load_image_variant", lambda file_id, w, h, ctype: WEBP)
        document = self._document(mock_db, test_pet, content_type="image/jpeg")

        listed = client.get(f"/api/documents?pet_id={test_pet['_id']}", headers=_auth(regular_user_token)).get_json()
        url = next(d for d in listed["documents"] if d["_id"] == str(document))["file_url"]
        response = client.get(_as_path(url))

        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/webp"

    def test_a_pdf_and_a_scan_get_no_picture_address(self, client, mock_db, regular_user_token, test_pet):
        pdf = self._document(mock_db, test_pet, content_type="application/pdf")
        scan = self._document(mock_db, test_pet, content_type="image/jpeg", scan=True)

        listed = client.get(f"/api/documents?pet_id={test_pet['_id']}", headers=_auth(regular_user_token)).get_json()
        urls = {d["_id"]: d["file_url"] for d in listed["documents"]}

        assert urls[str(pdf)] is None
        assert urls[str(scan)] is None

    def test_taking_the_sharing_away_ends_a_document_picture_address(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        monkeypatch.setattr("web.documents.load_image_variant", lambda file_id, w, h, ctype: WEBP)
        document = self._document(mock_db, test_pet, content_type="image/jpeg")
        family_token, _ = _people(mock_db, test_pet)
        listed = client.get(f"/api/documents?pet_id={test_pet['_id']}", headers=_auth(family_token)).get_json()
        url = next(d for d in listed["documents"] if d["_id"] == str(document))["file_url"]
        assert client.get(_as_path(url)).status_code == 200

        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": []}})

        assert client.get(_as_path(url)).status_code == 404
