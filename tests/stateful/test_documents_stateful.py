"""Tests for pet document attachments (vaccination certs, lab results,
insurance papers, photos) — upload, list/filter, metadata update, delete,
and file serving, plus their cascade-delete on pet removal.
"""

import io
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from bson import ObjectId
from PIL import Image


def _stored(s3, key: str) -> tuple[bytes, str]:
    """The object behind a record's file_id, straight from the (moto) bucket."""
    obj = s3.get_object(Bucket="petzy-test", Key=key)
    return obj["Body"].read(), obj["ContentType"]


def _owner_prefix(mock_db, username: str, pet_id) -> str:
    user_id = mock_db["users"].find_one({"username": username})["_id"]
    return f"users/{user_id}/pets/{pet_id}/"


def _make_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.documents
class TestCreateDocument:
    def test_create_document_with_image_success(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        response = client.post(
            "/api/documents",
            data={
                "pet_id": str(test_pet["_id"]),
                "category": "vaccination",
                "title": "Прививка от бешенства",
                "file": (io.BytesIO(_make_png_bytes()), "cert.png", "image/png"),
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        data = response.get_json()
        assert "id" in data

        doc = mock_db["documents"].find_one({"_id": ObjectId(data["id"])})
        # Stored in the bucket under the pet owner's own prefix.
        assert doc["file_id"].startswith(_owner_prefix(mock_db, "testuser", test_pet["_id"]) + "documents/")
        stored, stored_type = _stored(s3_storage, doc["file_id"])
        assert stored_type == "image/webp" and stored[:4] == b"RIFF"
        assert doc["category"] == "vaccination"
        assert doc["title"] == "Прививка от бешенства"
        assert doc["content_type"] == "image/webp"  # real PNG -> optimize_image succeeds
        assert doc["original_filename"] == "cert.png"
        assert doc["pet_id"] == str(test_pet["_id"])
        assert doc["username"] == "testuser"

    def test_create_document_with_pdf_success(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        response = client.post(
            "/api/documents",
            data={
                "pet_id": str(test_pet["_id"]),
                "category": "lab_result",
                "title": "Анализ крови",
                "note": "Плановый",
                "file": (io.BytesIO(b"%PDF-1.4 fake"), "blood.pdf", "application/pdf"),
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        data = response.get_json()
        doc = mock_db["documents"].find_one({"_id": ObjectId(data["id"])})
        assert _stored(s3_storage, doc["file_id"]) == (b"%PDF-1.4 fake", "application/pdf")
        assert doc["file_id"].endswith(".pdf")
        assert doc["content_type"] == "application/pdf"
        assert doc["note"] == "Плановый"

    def test_create_document_with_expiry_date(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        with patch.object(fs, "put", return_value=ObjectId()):
            response = client.post(
                "/api/documents",
                data={
                    "pet_id": str(test_pet["_id"]),
                    "category": "vaccination",
                    "title": "Прививка от бешенства",
                    "expires_at": "2027-05-01",
                    "file": (io.BytesIO(_make_png_bytes()), "cert.png", "image/png"),
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 201
        data = response.get_json()
        doc = mock_db["documents"].find_one({"_id": ObjectId(data["id"])})
        assert doc["expires_at"] == "2027-05-01"

        get_response = client.get(
            f"/api/documents/{data['id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert get_response.get_json()["document"]["expires_at"] == "2027-05-01"

    def test_create_document_rejects_malformed_expiry_date(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/documents",
            data={
                "pet_id": str(test_pet["_id"]),
                "category": "vaccination",
                "title": "Прививка",
                "expires_at": "не дата",
                "file": (io.BytesIO(_make_png_bytes()), "cert.png", "image/png"),
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )
        assert response.status_code == 422

    def test_create_document_missing_file(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/documents",
            data={"pet_id": str(test_pet["_id"]), "category": "other", "title": "Без файла"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 422
        assert response.get_json()["code"] == "document_file_required"

    def test_create_document_unsupported_type(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/documents",
            data={
                "pet_id": str(test_pet["_id"]),
                "category": "other",
                "title": "Текстовый файл",
                "file": (io.BytesIO(b"hello"), "notes.txt", "text/plain"),
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 422
        assert response.get_json()["code"] == "document_unsupported_type"

    def test_create_document_file_too_large(self, client, mock_db, regular_user_token, test_pet):
        from web import documents as documents_module

        too_big = b"0" * 10
        with patch.object(documents_module, "MAX_DOCUMENT_SIZE_BYTES", 5):
            response = client.post(
                "/api/documents",
                data={
                    "pet_id": str(test_pet["_id"]),
                    "category": "other",
                    "title": "Слишком большой",
                    "file": (io.BytesIO(too_big), "big.pdf", "application/pdf"),
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 422
        assert response.get_json()["code"] == "document_file_too_large"

    def test_create_document_requires_pet_access(self, client, mock_db, regular_user_token, admin_pet):
        """A pet belonging to another user is forbidden, not just any pet_id."""
        response = client.post(
            "/api/documents",
            data={
                "pet_id": str(admin_pet["_id"]),
                "category": "other",
                "title": "Чужой питомец",
                "file": (io.BytesIO(b"%PDF-1.4 fake"), "doc.pdf", "application/pdf"),
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 403

    def test_create_document_image_optimization_failure_falls_back(
        self, client, mock_db, regular_user_token, test_pet, s3_storage
    ):
        """A file declared as image/* but not actually decodable (Pillow
        can't open it) falls back to storing the raw bytes untouched,
        same tolerance as pets.create_pet's own optimize_image fallback."""
        response = client.post(
            "/api/documents",
            data={
                "pet_id": str(test_pet["_id"]),
                "category": "other",
                "title": "Не настоящее изображение",
                "file": (io.BytesIO(b"not actually a jpeg"), "fake.jpg", "image/jpeg"),
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        data = response.get_json()
        doc = mock_db["documents"].find_one({"_id": ObjectId(data["id"])})
        assert doc["content_type"] == "image/jpeg"  # unchanged — optimization was skipped
        assert doc["original_filename"] == "fake.jpg"

    def test_create_document_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        from web.app import db

        with patch.object(db.documents, "insert_one", side_effect=RuntimeError("boom")):
            response = client.post(
                "/api/documents",
                data={
                    "pet_id": str(test_pet["_id"]),
                    "category": "other",
                    "title": "Сломанная вставка",
                    "file": (io.BytesIO(b"%PDF-1.4 fake"), "doc.pdf", "application/pdf"),
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"

    def test_create_document_invalid_pet_id(self, client, mock_db, regular_user_token):
        response = client.post(
            "/api/documents",
            data={
                "pet_id": "not-an-object-id",
                "category": "other",
                "title": "Плохой pet_id",
                "file": (io.BytesIO(b"%PDF-1.4 fake"), "doc.pdf", "application/pdf"),
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 422


def _insert_document(mock_db, pet_id, category="other", title="Doc", file_id=None):
    doc = {
        "pet_id": pet_id,
        "username": "testuser",
        "category": category,
        "title": title,
        "note": "",
        "file_id": str(file_id or ObjectId()),
        "original_filename": "file.pdf",
        "content_type": "application/pdf",
        "file_size": 123,
        "created_at": datetime.now(timezone.utc),
    }
    result = mock_db["documents"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


@pytest.mark.documents
class TestListDocuments:
    def test_list_documents_pagination(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        for i in range(3):
            _insert_document(mock_db, pet_id, title=f"Doc {i}")

        response = client.get(
            f"/api/documents?pet_id={pet_id}&page=1&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["documents"]) == 2

    def test_list_documents_filter_by_category(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        _insert_document(mock_db, pet_id, category="vaccination", title="Прививка")
        _insert_document(mock_db, pet_id, category="lab_result", title="Анализ")

        response = client.get(
            f"/api/documents?pet_id={pet_id}&category=vaccination",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["documents"][0]["category"] == "vaccination"

    def test_list_documents_requires_pet_access(self, client, mock_db, regular_user_token, admin_pet):
        response = client.get(
            f"/api/documents?pet_id={admin_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 403

    def test_list_documents_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        from web.app import db

        with patch.object(db.documents, "count_documents", side_effect=RuntimeError("boom")):
            response = client.get(
                f"/api/documents?pet_id={test_pet['_id']}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"


@pytest.mark.documents
class TestGetUpdateDeleteDocument:
    def test_get_document_success(self, client, mock_db, regular_user_token, test_pet):
        doc = _insert_document(mock_db, str(test_pet["_id"]), title="Моя справка")

        response = client.get(f"/api/documents/{doc['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        assert response.get_json()["document"]["title"] == "Моя справка"

    def test_get_document_not_found(self, client, mock_db, regular_user_token):
        response = client.get(f"/api/documents/{ObjectId()}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 404

    def test_get_document_forbidden(self, client, mock_db, regular_user_token, admin_pet):
        doc = _insert_document(mock_db, str(admin_pet["_id"]))

        response = client.get(f"/api/documents/{doc['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 403

    def test_get_document_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        doc = _insert_document(mock_db, str(test_pet["_id"]))

        with patch("web.documents._serialize_document", side_effect=RuntimeError("boom")):
            response = client.get(
                f"/api/documents/{doc['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"

    def test_update_document_metadata_success(self, client, mock_db, regular_user_token, test_pet):
        doc = _insert_document(mock_db, str(test_pet["_id"]), title="Старое название")

        response = client.put(
            f"/api/documents/{doc['_id']}",
            json={"title": "Новое название", "category": "insurance"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        updated = mock_db["documents"].find_one({"_id": doc["_id"]})
        assert updated["title"] == "Новое название"
        assert updated["category"] == "insurance"

    def test_update_document_expiry_date(self, client, mock_db, regular_user_token, test_pet):
        doc = _insert_document(mock_db, str(test_pet["_id"]))

        response = client.put(
            f"/api/documents/{doc['_id']}",
            json={"expires_at": "2028-01-15"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        updated = mock_db["documents"].find_one({"_id": doc["_id"]})
        assert updated["expires_at"] == "2028-01-15"

    def test_update_document_rejects_malformed_expiry_date(self, client, mock_db, regular_user_token, test_pet):
        doc = _insert_document(mock_db, str(test_pet["_id"]))

        response = client.put(
            f"/api/documents/{doc['_id']}",
            json={"expires_at": "31-31-2028"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422

    def test_update_document_clears_expiry_date(self, client, mock_db, regular_user_token, test_pet):
        """Regression test: an earlier version sent `expires_at: data.expires_at
        || undefined` from the frontend, so clearing the field (empty string,
        falsy) turned into `undefined` and vanished from the request body
        entirely, silently leaving the old date in place."""
        doc = _insert_document(mock_db, str(test_pet["_id"]))
        mock_db["documents"].update_one({"_id": doc["_id"]}, {"$set": {"expires_at": "2028-01-15"}})

        response = client.put(
            f"/api/documents/{doc['_id']}",
            json={"expires_at": ""},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        updated = mock_db["documents"].find_one({"_id": doc["_id"]})
        assert updated["expires_at"] == ""

    def test_update_document_no_update_data(self, client, mock_db, regular_user_token, test_pet):
        doc = _insert_document(mock_db, str(test_pet["_id"]))

        response = client.put(
            f"/api/documents/{doc['_id']}",
            json={},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422
        assert response.get_json()["code"] == "validation_error_no_update_data"

    def test_update_document_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        from web.app import db

        doc = _insert_document(mock_db, str(test_pet["_id"]))

        with patch.object(db.documents, "update_one", side_effect=RuntimeError("boom")):
            response = client.put(
                f"/api/documents/{doc['_id']}",
                json={"title": "Новое"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"

    def test_delete_document_removes_gridfs_file(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        file_id = ObjectId()
        doc = _insert_document(mock_db, str(test_pet["_id"]), file_id=file_id)

        with patch.object(fs, "delete") as mock_delete:
            response = client.delete(
                f"/api/documents/{doc['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 200
        mock_delete.assert_called_once_with(file_id)
        assert mock_db["documents"].find_one({"_id": doc["_id"]}) is None

    def test_delete_document_gridfs_failure_still_succeeds(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        doc = _insert_document(mock_db, str(test_pet["_id"]))

        with patch.object(fs, "delete", side_effect=RuntimeError("gridfs unavailable")):
            response = client.delete(
                f"/api/documents/{doc['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 200
        assert mock_db["documents"].find_one({"_id": doc["_id"]}) is None

    def test_delete_document_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        from web.app import db

        doc = _insert_document(mock_db, str(test_pet["_id"]))

        with patch.object(db.documents, "delete_one", side_effect=RuntimeError("boom")):
            response = client.delete(
                f"/api/documents/{doc['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"


@pytest.mark.documents
class TestServeDocumentFile:
    def test_get_document_file_image_success(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import MagicMock

        from web.app import fs

        doc = _insert_document(mock_db, str(test_pet["_id"]))
        mock_db["documents"].update_one({"_id": doc["_id"]}, {"$set": {"content_type": "image/webp"}})

        mock_file = MagicMock()
        mock_file.read.return_value = b"fake_image_bytes"

        with patch.object(fs, "get", return_value=mock_file):
            response = client.get(
                f"/api/documents/{doc['_id']}/file", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 200
        assert response.data == b"fake_image_bytes"
        assert "inline" in response.headers.get("Content-Disposition", "")

    def test_get_document_file_image_resize(self, client, mock_db, regular_user_token, test_pet):
        """?w= on an image document thumbnails it, same as pet photos."""
        from unittest.mock import MagicMock

        from web.app import fs

        doc = _insert_document(mock_db, str(test_pet["_id"]))
        mock_db["documents"].update_one({"_id": doc["_id"]}, {"$set": {"content_type": "image/png"}})

        mock_file = MagicMock()
        mock_file.read.return_value = _make_png_bytes()

        with patch.object(fs, "get", return_value=mock_file):
            response = client.get(
                f"/api/documents/{doc['_id']}/file?w=5",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert response.content_type == "image/webp"

    def test_get_document_file_image_resize_by_height(self, client, mock_db, regular_user_token, test_pet):
        """?h= alone (no ?w=) derives width from the aspect ratio."""
        from unittest.mock import MagicMock

        from web.app import fs

        doc = _insert_document(mock_db, str(test_pet["_id"]))
        mock_db["documents"].update_one({"_id": doc["_id"]}, {"$set": {"content_type": "image/png"}})

        mock_file = MagicMock()
        mock_file.read.return_value = _make_png_bytes()

        with patch.object(fs, "get", return_value=mock_file):
            response = client.get(
                f"/api/documents/{doc['_id']}/file?h=5",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert response.content_type == "image/webp"

    def test_get_document_file_resize_failure_falls_back(self, client, mock_db, regular_user_token, test_pet):
        """A width/height request on an undecodable image just logs and
        serves the original bytes, mirroring pets.get_pet_photo."""
        from unittest.mock import MagicMock

        from web.app import fs

        doc = _insert_document(mock_db, str(test_pet["_id"]))
        mock_db["documents"].update_one({"_id": doc["_id"]}, {"$set": {"content_type": "image/png"}})

        mock_file = MagicMock()
        mock_file.read.return_value = b"not actually a png"

        with patch.object(fs, "get", return_value=mock_file):
            response = client.get(
                f"/api/documents/{doc['_id']}/file?w=5",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert response.data == b"not actually a png"

    def test_get_document_file_pdf_is_inline(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import MagicMock

        from web.app import fs

        doc = _insert_document(mock_db, str(test_pet["_id"]))  # content_type already application/pdf

        mock_file = MagicMock()
        mock_file.read.return_value = b"%PDF-1.4 fake"

        with patch.object(fs, "get", return_value=mock_file):
            response = client.get(
                f"/api/documents/{doc['_id']}/file", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        assert "inline" in response.headers.get("Content-Disposition", "")

    def test_get_document_file_forbidden(self, client, mock_db, regular_user_token, admin_pet):
        doc = _insert_document(mock_db, str(admin_pet["_id"]))

        response = client.get(
            f"/api/documents/{doc['_id']}/file", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 403

    def test_get_document_file_not_found(self, client, mock_db, regular_user_token):
        response = client.get(
            f"/api/documents/{ObjectId()}/file", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 404

    def test_get_document_file_gridfs_error(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        doc = _insert_document(mock_db, str(test_pet["_id"]))

        with patch.object(fs, "get", side_effect=Exception("gridfs error")):
            response = client.get(
                f"/api/documents/{doc['_id']}/file", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 404
