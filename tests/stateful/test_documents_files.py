"""A document's own zone («Добавлен <дата>» reads the same for everyone),
replacing the file of a document, and taking back a file whose upload the
user stopped.

One record = one file: a replaced file keeps the document, its id and what
the medical card has attached to it, and only the file behind it changes.
"""

import io
from datetime import datetime
from unittest.mock import patch

import pytest
from bson import ObjectId

UPLOAD_ID = "0123456789abcdef0123456789abcdef"


def _pdf(text: str = "%PDF-1.4 one") -> bytes:
    return text.encode()


def _png() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def _create(client, token, pet_id, **form):
    data = {"pet_id": str(pet_id), "category": "other", "title": "Справка", **form}
    return client.post(
        "/api/documents",
        data=data,
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _stored_keys(s3):
    return {o["Key"] for o in s3.list_objects_v2(Bucket="petzy-test").get("Contents", [])}


@pytest.mark.documents
class TestDocumentZone:
    def test_create_keeps_the_zone_the_file_was_added_in(self, client, mock_db, regular_user_token, test_pet):
        """The zone is stored and handed back, so the list can read the time
        on the clock of the document rather than of the phone."""
        response = _create(
            client,
            regular_user_token,
            test_pet["_id"],
            tz="Asia/Almaty",
            file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf"),
        )

        assert response.status_code == 201
        doc_id = response.get_json()["id"]
        assert mock_db["documents"].find_one({"_id": ObjectId(doc_id)})["tz"] == "Asia/Almaty"

        detail = client.get(f"/api/documents/{doc_id}", headers=_auth(regular_user_token))
        assert detail.get_json()["document"]["tz"] == "Asia/Almaty"

        listed = client.get(f"/api/documents?pet_id={test_pet['_id']}", headers=_auth(regular_user_token)).get_json()[
            "documents"
        ]
        assert listed[0]["tz"] == "Asia/Almaty"

    def test_create_drops_a_name_that_is_not_a_zone(self, client, mock_db, regular_user_token, test_pet):
        """Not every client can name a zone, and a made-up one must not be
        stored as if it were one: the time then stays on the reader's clock,
        which is all that is known."""
        response = _create(
            client,
            regular_user_token,
            test_pet["_id"],
            tz="Not/AZone",
            file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf"),
        )

        assert response.status_code == 201
        doc_id = response.get_json()["id"]
        assert "tz" not in mock_db["documents"].find_one({"_id": ObjectId(doc_id)})
        detail = client.get(f"/api/documents/{doc_id}", headers=_auth(regular_user_token))
        assert detail.get_json()["document"]["tz"] is None

    def test_a_document_without_a_zone_says_none(self, client, mock_db, regular_user_token, test_pet):
        """Documents added before the field have no zone at all."""
        _create(client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf"))
        doc_id = next(iter(mock_db["documents"].find({}, {"_id": 1})))["_id"]
        detail = client.get(f"/api/documents/{doc_id}", headers=_auth(regular_user_token))
        assert detail.get_json()["document"]["tz"] is None


@pytest.mark.documents
class TestReplaceDocumentFile:
    def test_replace_swaps_the_file_and_keeps_the_document(
        self, client, mock_db, regular_user_token, test_pet, s3_storage
    ):
        created = _create(
            client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "старое.pdf", "application/pdf")
        )
        doc_id = created.get_json()["id"]
        old = mock_db["documents"].find_one({"_id": ObjectId(doc_id)})
        # Something in the medical card points at this document: replacing the
        # file must not detach it.
        mock_db["medical_records"].insert_one(
            {"pet_id": str(test_pet["_id"]), "kind": "vaccination", "title": "Прививка", "document_ids": [doc_id]}
        )

        response = client.put(
            f"/api/documents/{doc_id}/file",
            data={"file": (io.BytesIO(_png()), "новое.png", "image/png")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        updated = mock_db["documents"].find_one({"_id": ObjectId(doc_id)})
        assert str(updated["_id"]) == doc_id
        assert updated["file_id"] != old["file_id"]
        assert updated["original_filename"] == "новое.png"
        assert updated["content_type"] == "image/webp"  # a PNG is converted, as at creation
        assert updated["title"] == "Справка"  # the description is not the file's business
        # The old file is gone once the new one is in place; the new one is there.
        assert old["file_id"] not in _stored_keys(s3_storage)
        stored = s3_storage.get_object(Bucket="petzy-test", Key=updated["file_id"])
        assert stored["Body"].read()[:4] == b"RIFF"
        # Still the same document to the medical card.
        detail = client.get(f"/api/documents/{doc_id}", headers=_auth(regular_user_token)).get_json()["document"]
        assert detail["medical_record_kinds"] == ["vaccination"]

    def test_replacing_a_scan_leaves_an_ordinary_file(self, client, mock_db, regular_user_token, test_pet):
        """An archive is downloaded through a signed link and never previewed;
        a photo put in its place has to be served like any other photo."""
        created = _create(
            client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "снимки.zip", "application/pdf")
        )
        doc_id = created.get_json()["id"]
        mock_db["documents"].update_one({"_id": ObjectId(doc_id)}, {"$set": {"scan": True, "category": "imaging"}})

        response = client.put(
            f"/api/documents/{doc_id}/file",
            data={"file": (io.BytesIO(_pdf("%PDF-1.4 two")), "снимок.pdf", "application/pdf")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )

        assert response.status_code == 200
        assert "scan" not in mock_db["documents"].find_one({"_id": ObjectId(doc_id)})

    def test_a_refused_file_leaves_the_old_one(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        """Nothing is stored and nothing is changed until the new file has
        passed every check the creation path makes."""
        created = _create(
            client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "старое.pdf", "application/pdf")
        )
        doc_id = created.get_json()["id"]
        before = mock_db["documents"].find_one({"_id": ObjectId(doc_id)})

        refused = client.put(
            f"/api/documents/{doc_id}/file",
            data={"file": (io.BytesIO(b"hello"), "notes.txt", "text/plain")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )
        assert refused.status_code == 422
        assert refused.get_json()["code"] == "document_unsupported_type"

        mismatched = client.put(
            f"/api/documents/{doc_id}/file",
            data={"file": (io.BytesIO(b"not a pdf"), "подделка.pdf", "application/pdf")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )
        assert mismatched.status_code == 422
        assert mismatched.get_json()["code"] == "document_content_mismatch"

        after = mock_db["documents"].find_one({"_id": ObjectId(doc_id)})
        assert after["file_id"] == before["file_id"]
        assert after["original_filename"] == "старое.pdf"
        assert before["file_id"] in _stored_keys(s3_storage)

    def test_too_large_a_file_is_refused(self, client, regular_user_token, test_pet):
        from web import documents as documents_module

        created = _create(
            client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "старое.pdf", "application/pdf")
        )
        doc_id = created.get_json()["id"]

        with patch.object(documents_module, "MAX_DOCUMENT_SIZE_BYTES", 5):
            response = client.put(
                f"/api/documents/{doc_id}/file",
                data={"file": (io.BytesIO(b"%PDF-1.4 too big"), "big.pdf", "application/pdf")},
                headers=_auth(regular_user_token),
                content_type="multipart/form-data",
            )

        assert response.status_code == 422
        assert response.get_json()["code"] == "document_file_too_large"

    def test_the_replaced_file_is_credited_against_the_quota(self, client, mock_db, regular_user_token, test_pet):
        """A replacement isn't counted twice: the owner's bucket is already
        full of the file being replaced."""
        from web import documents as documents_module

        created = _create(
            client,
            regular_user_token,
            test_pet["_id"],
            file=(io.BytesIO(_pdf("%PDF-1.4 " + "x" * 100)), "старое.pdf", "application/pdf"),
        )
        doc_id = created.get_json()["id"]
        used = documents_module.storage_used_bytes("testuser")

        with patch.object(documents_module, "STORAGE_QUOTA_BYTES", used + 10):
            response = client.put(
                f"/api/documents/{doc_id}/file",
                data={"file": (io.BytesIO(_pdf("%PDF-1.4 " + "y" * 110)), "новое.pdf", "application/pdf")},
                headers=_auth(regular_user_token),
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        assert mock_db["documents"].find_one({"_id": ObjectId(doc_id)})["file_size"] == used + 10

    def test_replace_requires_record_access(self, client, regular_user_token, admin_pet):
        doc_id = str(ObjectId())
        response = client.put(
            f"/api/documents/{doc_id}/file",
            data={"file": (io.BytesIO(_pdf()), "a.pdf", "application/pdf")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )
        assert response.status_code == 404

    def test_replace_without_a_file(self, client, regular_user_token, test_pet):
        created = _create(
            client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "старое.pdf", "application/pdf")
        )
        response = client.put(
            f"/api/documents/{created.get_json()['id']}/file",
            data={},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )
        assert response.status_code == 422
        assert response.get_json()["code"] == "document_file_required"

    def test_a_failure_to_delete_the_old_file_still_succeeds(
        self, client, mock_db, regular_user_token, test_pet, s3_storage
    ):
        """The document already points at the new file: a storage hiccup with
        the old one must not fail the request and leave the two out of step."""
        created = _create(
            client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "старое.pdf", "application/pdf")
        )
        doc_id = created.get_json()["id"]

        with patch("web.documents.delete_stored_file", side_effect=RuntimeError("bucket grumpy")) as deleter:
            response = client.put(
                f"/api/documents/{doc_id}/file",
                data={"file": (io.BytesIO(_pdf("%PDF-1.4 two")), "новое.pdf", "application/pdf")},
                headers=_auth(regular_user_token),
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        assert deleter.call_count == 1
        assert mock_db["documents"].find_one({"_id": ObjectId(doc_id)})["original_filename"] == "новое.pdf"


@pytest.mark.documents
class TestCancelDocumentUpload:
    def test_a_stopped_upload_leaves_nothing_behind(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        """The request was cut, but the server may have stored the file and
        answered before the answer arrived: the document goes with its file."""
        created = _create(
            client,
            regular_user_token,
            test_pet["_id"],
            upload_id=UPLOAD_ID,
            file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf"),
        )
        doc_id = created.get_json()["id"]
        file_id = mock_db["documents"].find_one({"_id": ObjectId(doc_id)})["file_id"]
        assert file_id in _stored_keys(s3_storage)

        response = client.post(f"/api/documents/uploads/{UPLOAD_ID}/cancel", headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert mock_db["documents"].find_one({"_id": ObjectId(doc_id)}) is None
        assert file_id not in _stored_keys(s3_storage)

    def test_cancelling_takes_the_document_out_of_the_medical_card(self, client, mock_db, regular_user_token, test_pet):
        created = _create(
            client,
            regular_user_token,
            test_pet["_id"],
            upload_id=UPLOAD_ID,
            file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf"),
        )
        doc_id = created.get_json()["id"]
        mock_db["medical_records"].insert_one(
            {"pet_id": str(test_pet["_id"]), "kind": "vaccination", "title": "Прививка", "document_ids": [doc_id]}
        )

        client.post(f"/api/documents/uploads/{UPLOAD_ID}/cancel", headers=_auth(regular_user_token))

        record = mock_db["medical_records"].find_one({"pet_id": str(test_pet["_id"])})
        assert record["document_ids"] == []

    def test_cancelling_an_unknown_upload_is_only_an_answer(self, client, mock_db, regular_user_token, test_pet):
        """The common case: the request never arrived, so there is nothing to
        take back — and that is not an error either."""
        _create(client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf"))

        response = client.post(f"/api/documents/uploads/{UPLOAD_ID}/cancel", headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert mock_db["documents"].count_documents({}) == 1

    def test_an_upload_id_of_another_shape_touches_nothing(self, client, mock_db, regular_user_token, test_pet):
        _create(client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf"))

        response = client.post("/api/documents/uploads/not-an-upload-id/cancel", headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert mock_db["documents"].count_documents({}) == 1

    def test_one_person_cannot_cancel_another_person_s_upload(
        self, client, mock_db, admin_token, test_pet, regular_user_token
    ):
        created = _create(
            client,
            regular_user_token,
            test_pet["_id"],
            upload_id=UPLOAD_ID,
            file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf"),
        )
        doc_id = created.get_json()["id"]

        client.post(f"/api/documents/uploads/{UPLOAD_ID}/cancel", headers=_auth(admin_token))

        assert mock_db["documents"].find_one({"_id": ObjectId(doc_id)}) is not None

    def test_a_document_without_an_upload_id_is_not_cancelable(self, client, mock_db, regular_user_token, test_pet):
        """Replacing a file writes no upload id: stopping that upload must
        never take the document away."""
        created = _create(
            client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf")
        )
        doc_id = created.get_json()["id"]

        client.post(f"/api/documents/uploads/{UPLOAD_ID}/cancel", headers=_auth(regular_user_token))

        assert mock_db["documents"].find_one({"_id": ObjectId(doc_id)}) is not None

    def test_created_at_stays_the_moment_the_document_was_added(self, client, mock_db, regular_user_token, test_pet):
        """A replaced file is not a new document: the list's «Добавлен» keeps
        pointing at when the file arrived the first time."""
        created = _create(
            client, regular_user_token, test_pet["_id"], file=(io.BytesIO(_pdf()), "a.pdf", "application/pdf")
        )
        doc_id = created.get_json()["id"]
        before = mock_db["documents"].find_one({"_id": ObjectId(doc_id)})["created_at"]

        client.put(
            f"/api/documents/{doc_id}/file",
            data={"file": (io.BytesIO(_pdf("%PDF-1.4 two")), "b.pdf", "application/pdf")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )

        after = mock_db["documents"].find_one({"_id": ObjectId(doc_id)})["created_at"]
        assert isinstance(after, datetime)
        assert after == before
