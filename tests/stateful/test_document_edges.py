"""A document at its edges: a file that cannot be stored, a scan that cannot be reserved, a name
without an extension and a date that was written as text.

These are the answers a person gets when something outside the document goes wrong: the storage is
not set up, the bucket says no, the file was never there. None of them may take the document away:
the record stays, and the person can try again.
"""

import io
from datetime import datetime, timezone

import pytest
from PIL import Image

from web import storage
from web.documents import content_disposition

UPLOAD_ID = "0123456789abcdef0123456789abcdef"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def _webp():
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (1, 2, 3)).save(buf, format="WEBP")
    return buf.getvalue()


def _document(mock_db, pet, **fields):
    document = {
        "pet_id": str(pet["_id"]),
        "username": "testuser",
        "category": "other",
        "title": "Справка",
        "original_filename": "a.jpg",
        "content_type": "image/jpeg",
        "file_id": "users/a/pets/1/documents/a.jpg",
        "file_size": 2048,
        "created_at": datetime.now(timezone.utc),
        **fields,
    }
    if document.get("created_at") is None:
        document.pop("created_at")
    return mock_db["documents"].insert_one(document).inserted_id


@pytest.mark.documents
class TestDocumentEdges:
    def test_a_webp_picture_is_accepted_as_itself(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/documents",
            data={
                "pet_id": str(test_pet["_id"]),
                "category": "other",
                "title": "Снимок",
                "file": (io.BytesIO(_webp()), "scan.webp", "image/webp"),
            },
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        document = mock_db["documents"].find_one({"title": "Снимок"})
        assert document["content_type"] == "image/webp"

    def test_a_type_the_server_does_not_know_is_not_a_picture(self):
        """The check of the first bytes knows the types it accepts: anything else is not a picture."""
        from web.documents import _starts_like

        assert _starts_like(b"PK\x03\x04", "application/zip") is False

    def test_the_files_of_an_owner_without_pets_take_no_room(self, client, mock_db, test_pet):
        """Only the files of the owner's own pets are counted against the owner's place."""
        from web.documents import storage_used_bytes

        _document(mock_db, test_pet, file_size=100)

        assert storage_used_bytes("testuser") == 100
        assert storage_used_bytes("nobody") == 0

    def test_the_administrator_has_no_quota(self, client, mock_db):
        from web.documents import _over_quota

        assert _over_quota("admin", 10**12) is False

    def test_a_document_whose_date_was_written_as_text_shows_it_as_it_was_written(
        self, client, mock_db, regular_user_token, test_pet
    ):
        _document(mock_db, test_pet, created_at="2020-01-02T03:04:05")

        listed = client.get(f"/api/documents?pet_id={test_pet['_id']}", headers=_auth(regular_user_token)).get_json()

        assert listed["documents"][0]["created_at"] == "2020-01-02T03:04:05"

    def test_a_document_without_a_date_says_nothing_about_it(self, client, mock_db, regular_user_token, test_pet):
        # A row written before the field existed: the answer needs a date, and there is none.
        _document(mock_db, test_pet, created_at=None)

        listed = client.get(f"/api/documents?pet_id={test_pet['_id']}", headers=_auth(regular_user_token)).get_json()

        assert listed["documents"][0]["created_at"] == ""

    def test_a_document_cannot_be_stored_when_the_storage_is_not_set_up(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        def refuse(*args, **kwargs):
            raise storage.StorageNotConfigured("no storage")

        monkeypatch.setattr("web.documents.store_file", refuse)

        response = client.post(
            "/api/documents",
            data={
                "pet_id": str(test_pet["_id"]),
                "category": "other",
                "title": "Справка",
                "file": (io.BytesIO(_png()), "a.png", "image/png"),
            },
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )

        assert response.status_code == 503
        assert response.get_json()["code"] == "storage_not_configured"
        assert mock_db["documents"].count_documents({}) == 0

    def test_a_file_cannot_be_put_behind_a_document_when_the_storage_is_not_set_up(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        document = _document(mock_db, test_pet)

        def refuse(*args, **kwargs):
            raise storage.StorageNotConfigured("no storage")

        monkeypatch.setattr("web.documents.store_file", refuse)

        response = client.put(
            f"/api/documents/{document}/file",
            data={"file": (io.BytesIO(_png()), "b.png", "image/png")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )

        assert response.status_code == 503
        assert response.get_json()["code"] == "storage_not_configured"

    def test_a_failure_while_the_file_is_put_behind_a_document_answers_with_the_general_error(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        document = _document(mock_db, test_pet)

        def refuse(*args, **kwargs):
            raise RuntimeError("something went wrong")

        monkeypatch.setattr("web.documents.store_file", refuse)

        response = client.put(
            f"/api/documents/{document}/file",
            data={"file": (io.BytesIO(_png()), "b.png", "image/png")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"

    def test_a_file_that_cannot_be_removed_does_not_stop_the_cancellation(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        _document(mock_db, test_pet, upload_id=UPLOAD_ID)

        def refuse(*args, **kwargs):
            raise RuntimeError("the bucket says no")

        monkeypatch.setattr("web.documents.delete_stored_file", refuse)

        response = client.post(f"/api/documents/uploads/{UPLOAD_ID}/cancel", headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert mock_db["documents"].count_documents({}) == 0

    def test_a_cancellation_that_fails_answers_with_the_general_error(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        _document(mock_db, test_pet, upload_id=UPLOAD_ID)

        def refuse(*args, **kwargs):
            raise RuntimeError("something went wrong")

        monkeypatch.setattr(mock_db["documents"], "delete_one", refuse)

        response = client.post(f"/api/documents/uploads/{UPLOAD_ID}/cancel", headers=_auth(regular_user_token))

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"


@pytest.mark.documents
class TestScanEdges:
    def test_a_scan_cannot_be_reserved_when_the_storage_is_not_set_up(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        monkeypatch.setattr(storage, "storage_configured", lambda: False)

        response = client.post(
            "/api/documents/scans",
            json={"pet_id": str(test_pet["_id"]), "filename": "kt.zip", "size": 1000},
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 503
        assert response.get_json()["code"] == "storage_not_configured"

    def test_a_slot_that_cannot_be_made_answers_with_the_general_error(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        def refuse(*args, **kwargs):
            raise RuntimeError("something went wrong")

        monkeypatch.setattr(storage, "new_key", refuse)

        response = client.post(
            "/api/documents/scans",
            json={"pet_id": str(test_pet["_id"]), "filename": "kt.zip", "size": 1000},
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"

    def test_a_scan_cannot_be_confirmed_when_the_storage_is_not_set_up(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        monkeypatch.setattr(storage, "storage_configured", lambda: False)

        response = client.post(
            "/api/documents/scans/some-upload-id/complete",
            json={"title": "КТ"},
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 503
        assert response.get_json()["code"] == "storage_not_configured"

    def test_the_bucket_failing_while_the_upload_is_confirmed_answers_with_the_general_error(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        mock_db["document_uploads"].insert_one(
            {
                "_id": "the-upload",
                "key": "users/a/pets/1/scans/kt.zip",
                "pet_id": str(test_pet["_id"]),
                "username": "testuser",
                "filename": "kt.zip",
                "size": 1000,
                "content_type": "application/zip",
                "family": "zip",
                "created_at": datetime.now(timezone.utc),
            }
        )

        def refuse(*args, **kwargs):
            raise RuntimeError("the bucket says no")

        monkeypatch.setattr(storage, "object_size", refuse)

        response = client.post(
            "/api/documents/scans/the-upload/complete",
            json={"title": "КТ"},
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"
        # The slot stays: the upload can be confirmed again.
        assert mock_db["document_uploads"].count_documents({}) == 1

    def test_a_scan_cannot_be_downloaded_when_the_storage_is_not_set_up(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        document = _document(mock_db, test_pet, scan=True, content_type="application/zip")
        monkeypatch.setattr(storage, "storage_configured", lambda: False)

        response = client.get(f"/api/documents/{document}/download", headers=_auth(regular_user_token))

        assert response.status_code == 503
        assert response.get_json()["code"] == "storage_not_configured"

    def test_a_scan_cannot_be_served_when_the_storage_is_not_set_up(
        self, client, mock_db, regular_user_token, test_pet, monkeypatch
    ):
        document = _document(mock_db, test_pet, scan=True, content_type="application/zip")
        monkeypatch.setattr(storage, "storage_configured", lambda: False)

        response = client.get(f"/api/documents/{document}/file", headers=_auth(regular_user_token))

        assert response.status_code == 503
        assert response.get_json()["code"] == "storage_not_configured"


def test_a_name_without_an_extension_gets_the_extension_of_what_is_stored():
    """A file called «снимок» is served as «снимок.jpg»: the name in the header says what it is."""
    disposition = content_disposition("inline", "снимок", "image/jpeg")

    assert "filename*=UTF-8''%D1%81%D0%BD%D0%B8%D0%BC%D0%BE%D0%BA.jpg" in disposition
