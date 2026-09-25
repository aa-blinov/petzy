"""Object storage: users can't reach each other's files; scan uploads; upkeep.

Every test runs against moto's in-memory bucket (conftest.s3_storage).
"""

import io
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

import bcrypt
import pytest
from bson import ObjectId

from web import storage
from web.security import create_access_token

BUCKET = "petzy-test"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _keys(s3, prefix=""):
    return {o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", [])}


def _zip_bytes(size=64):
    return b"PK\x03\x04" + b"\0" * (size - 4)


@pytest.fixture
def other_user(mock_db):
    user = {
        "username": "stranger",
        "password_hash": bcrypt.hashpw(b"stranger123", bcrypt.gensalt()).decode(),
        "full_name": "Stranger",
        "created_at": datetime.now(timezone.utc),
        "is_active": True,
    }
    mock_db["users"].insert_one(user)
    return user


@pytest.fixture
def other_token(other_user):
    return create_access_token(other_user["username"])


@pytest.fixture
def pet_with_files(client, mock_db, regular_user_token, test_pet, s3_storage):
    """testuser's pet with a photo and a PDF document, both in storage."""
    pet_id = str(test_pet["_id"])
    photo = io.BytesIO()
    from PIL import Image

    Image.new("RGB", (300, 300), (10, 120, 200)).save(photo, format="PNG")
    photo.seek(0)
    response = client.put(
        f"/api/pets/{pet_id}",
        data={"name": "Test Cat", "photo_file": (photo, "cat.png", "image/png")},
        headers=_auth(regular_user_token),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    response = client.post(
        "/api/documents",
        data={
            "pet_id": pet_id,
            "category": "other",
            "title": "Анализ крови",
            "file": (io.BytesIO(b"%PDF-1.4 test"), "blood.pdf", "application/pdf"),
        },
        headers=_auth(regular_user_token),
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.get_json()
    return {"pet_id": pet_id, "document_id": response.get_json()["id"]}


def _start_scan(client, token, pet_id, filename="mri.zip", size=64):
    return client.post(
        "/api/documents/scans",
        json={"pet_id": pet_id, "filename": filename, "size": size},
        headers=_auth(token),
    )


def _upload_scan(client, token, mock_db, s3, pet_id, body=None, filename="mri.zip", size=None):
    body = _zip_bytes() if body is None else body
    slot = _start_scan(client, token, pet_id, filename, len(body) if size is None else size)
    assert slot.status_code == 201, slot.get_json()
    upload_id = slot.get_json()["upload_id"]
    key = mock_db["document_uploads"].find_one({"_id": upload_id})["key"]
    s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType=slot.get_json()["content_type"])
    return upload_id, key


def _complete(client, token, upload_id, title="МРТ головы"):
    return client.post(f"/api/documents/scans/{upload_id}/complete", json={"title": title}, headers=_auth(token))


class TestKeysAreNamespacedByOwner:
    def test_every_file_of_a_pet_sits_under_its_owners_prefix(self, mock_db, regular_user, pet_with_files, s3_storage):
        owner_id = str(mock_db["users"].find_one({"username": "testuser"})["_id"])
        prefix = f"users/{owner_id}/pets/{pet_with_files['pet_id']}/"

        keys = _keys(s3_storage)

        assert keys and all(k.startswith(prefix) for k in keys)
        assert any("/photos/" in k for k in keys) and any("/documents/" in k for k in keys)

    def test_the_prefix_uses_the_user_id_not_the_username(self, mock_db, regular_user):
        key = storage.new_key(mock_db, "testuser", "p1", "photos", ".webp")

        assert "testuser" not in key
        assert key.startswith(f"users/{mock_db['users'].find_one({'username': 'testuser'})['_id']}/pets/p1/photos/")

    def test_two_users_never_share_a_prefix(self, mock_db, regular_user, other_user):
        assert storage.pet_prefix(mock_db, "testuser", "p1") != storage.pet_prefix(mock_db, "stranger", "p1")

    def test_an_extension_cannot_escape_the_prefix(self, mock_db, regular_user):
        key = storage.new_key(mock_db, "testuser", "../../x", "scans", "/../../evil")

        assert ".." not in key
        assert key.count("/") == 5  # users/<id>/pets/<pet>/scans/<name>

    def test_a_key_prefix_namespaces_every_key(self, mock_db, regular_user, monkeypatch):
        monkeypatch.setenv("S3_PREFIX", "dev")

        key = storage.new_key(mock_db, "testuser", "p1", "scans", ".zip")

        assert key.startswith("dev/users/")
        assert storage.pet_prefix(mock_db, "testuser", "p1").startswith("dev/users/")
        assert storage.thumb_key(key, 96, None).startswith("dev/users/")

    def test_production_keys_have_no_prefix(self, mock_db, regular_user):
        assert storage.new_key(mock_db, "testuser", "p1", "photos", ".webp").startswith("users/")

    def test_responses_never_carry_a_key(self, client, regular_user_token, pet_with_files):
        pet = client.get(f"/api/pets/{pet_with_files['pet_id']}", headers=_auth(regular_user_token))
        docs = client.get(f"/api/documents?pet_id={pet_with_files['pet_id']}", headers=_auth(regular_user_token))
        photo = client.get(f"/api/pets/{pet_with_files['pet_id']}/photo", headers=_auth(regular_user_token))
        doc_file = client.get(f"/api/documents/{pet_with_files['document_id']}/file", headers=_auth(regular_user_token))

        for body in (pet.get_data(as_text=True), docs.get_data(as_text=True)):
            assert "users/" not in body
            assert "file_id" not in body
        for response in (photo, doc_file):
            assert response.status_code == 200
            assert "users/" not in (response.headers.get("ETag") or "")


class TestOtherUsersCannotReachTheFiles:
    def test_pet_photo(self, client, other_token, pet_with_files):
        response = client.get(f"/api/pets/{pet_with_files['pet_id']}/photo", headers=_auth(other_token))
        assert response.status_code in (403, 404)

    def test_document_file_and_record(self, client, other_token, pet_with_files):
        doc_id = pet_with_files["document_id"]
        for url in (f"/api/documents/{doc_id}/file", f"/api/documents/{doc_id}"):
            response = client.get(url, headers=_auth(other_token))
            assert response.status_code in (403, 404)
            assert b"PDF" not in response.data

    def test_document_list(self, client, other_token, pet_with_files):
        response = client.get(f"/api/documents?pet_id={pet_with_files['pet_id']}", headers=_auth(other_token))
        assert response.status_code in (403, 404)

    def test_deleting_someone_elses_document(self, client, other_token, pet_with_files, s3_storage):
        before = _keys(s3_storage)

        response = client.delete(f"/api/documents/{pet_with_files['document_id']}", headers=_auth(other_token))

        assert response.status_code in (403, 404)
        assert _keys(s3_storage) == before

    def test_uploading_into_someone_elses_pet(self, client, other_token, pet_with_files, s3_storage):
        before = _keys(s3_storage)

        document = client.post(
            "/api/documents",
            data={
                "pet_id": pet_with_files["pet_id"],
                "category": "other",
                "title": "x",
                "file": (io.BytesIO(b"%PDF-1.4"), "x.pdf", "application/pdf"),
            },
            headers=_auth(other_token),
            content_type="multipart/form-data",
        )
        scan = _start_scan(client, other_token, pet_with_files["pet_id"])

        assert document.status_code in (403, 404)
        assert scan.status_code in (403, 404)
        assert _keys(s3_storage) == before

    def test_downloading_someone_elses_scan(
        self, client, mock_db, regular_user_token, other_token, test_pet, s3_storage
    ):
        upload_id, _ = _upload_scan(client, regular_user_token, mock_db, s3_storage, str(test_pet["_id"]))
        doc_id = _complete(client, regular_user_token, upload_id).get_json()["id"]

        response = client.get(f"/api/documents/{doc_id}/file", headers=_auth(other_token))

        assert response.status_code in (403, 404)
        assert "Location" not in response.headers

    def test_completing_someone_elses_upload_slot(
        self, client, mock_db, regular_user_token, other_token, test_pet, s3_storage
    ):
        upload_id, key = _upload_scan(client, regular_user_token, mock_db, s3_storage, str(test_pet["_id"]))

        response = _complete(client, other_token, upload_id)

        assert response.status_code == 404
        assert mock_db["documents"].count_documents({"file_id": key}) == 0
        assert key in _keys(s3_storage)

    def test_access_ends_when_a_pet_is_unshared(
        self, client, mock_db, regular_user_token, other_token, test_pet, s3_storage
    ):
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["stranger"]}})
        upload_id, _ = _upload_scan(client, other_token, mock_db, s3_storage, str(test_pet["_id"]))
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": []}})

        response = _complete(client, other_token, upload_id)

        assert response.status_code in (403, 404)

    def test_a_shared_user_uploads_under_the_owners_prefix(
        self, client, mock_db, regular_user, other_token, test_pet, s3_storage
    ):
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["stranger"]}})

        _, key = _upload_scan(client, other_token, mock_db, s3_storage, str(test_pet["_id"]))

        assert key.startswith(storage.pet_prefix(mock_db, "testuser", test_pet["_id"]))


class TestScanUpload:
    def test_storage_status(self, client, regular_user_token):
        response = client.get("/api/documents/storage", headers=_auth(regular_user_token))
        assert response.get_json() == {"scans_enabled": True, "max_scan_bytes": 500 * 1024 * 1024}

    def test_the_signed_url_binds_key_type_and_size(self, client, mock_db, regular_user_token, test_pet):
        response = _start_scan(client, regular_user_token, str(test_pet["_id"]), "КТ грудной клетки.7z", 1234)

        body = response.get_json()
        assert response.status_code == 201
        assert body["content_type"] == "application/x-7z-compressed"
        url = urlparse(body["upload_url"])
        key = mock_db["document_uploads"].find_one({"_id": body["upload_id"]})["key"]
        assert url.path.endswith(key) and key.endswith(".7z")
        signed = parse_qs(url.query)["X-Amz-SignedHeaders"][0].split(";")
        assert {"content-length", "content-type"} <= set(signed)

    def test_upload_becomes_a_document(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        body = _zip_bytes(4096)
        upload_id, key = _upload_scan(
            client, regular_user_token, mock_db, s3_storage, str(test_pet["_id"]), body, filename="МРТ.zip"
        )

        response = _complete(client, regular_user_token, upload_id)

        assert response.status_code == 201
        document = mock_db["documents"].find_one({"_id": ObjectId(response.get_json()["id"])})
        assert document["scan"] is True
        assert document["file_id"] == key
        assert document["file_size"] == 4096
        assert document["category"] == "imaging"
        assert document["original_filename"] == "МРТ.zip"
        assert mock_db["document_uploads"].count_documents({}) == 0

    def test_download_is_a_short_lived_signed_redirect(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        upload_id, key = _upload_scan(
            client,
            regular_user_token,
            mock_db,
            s3_storage,
            str(test_pet["_id"]),
            filename="КТ.tar.gz",
            body=b"\x1f\x8b" + b"\0" * 30,
        )
        doc_id = _complete(client, regular_user_token, upload_id).get_json()["id"]

        response = client.get(f"/api/documents/{doc_id}/file", headers=_auth(regular_user_token))

        assert response.status_code == 302
        assert response.headers["Cache-Control"] == "private, no-store"
        location = urlparse(response.headers["Location"])
        query = parse_qs(location.query)
        assert location.path.endswith(key)
        assert int(query["X-Amz-Expires"][0]) <= 600
        assert "attachment" in query["response-content-disposition"][0]

    def test_download_link_as_json(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        upload_id, key = _upload_scan(client, regular_user_token, mock_db, s3_storage, str(test_pet["_id"]))
        doc_id = _complete(client, regular_user_token, upload_id).get_json()["id"]

        response = client.get(f"/api/documents/{doc_id}/download", headers=_auth(regular_user_token))

        body = response.get_json()
        assert response.status_code == 200
        assert response.headers["Cache-Control"] == "private, no-store"
        assert urlparse(body["url"]).path.endswith(key)
        assert body["expires_in"] == 600

    def test_download_link_errors_come_back_as_json(
        self, client, mock_db, regular_user_token, other_token, test_pet, s3_storage
    ):
        upload_id, _ = _upload_scan(client, regular_user_token, mock_db, s3_storage, str(test_pet["_id"]))
        doc_id = _complete(client, regular_user_token, upload_id).get_json()["id"]

        stranger = client.get(f"/api/documents/{doc_id}/download", headers=_auth(other_token))
        anonymous = client.get(f"/api/documents/{doc_id}/download")

        assert stranger.status_code in (403, 404) and "url" not in stranger.get_json()
        assert anonymous.status_code == 401

    def test_download_link_for_an_ordinary_document(self, client, regular_user_token, pet_with_files):
        doc_id = pet_with_files["document_id"]

        body = client.get(f"/api/documents/{doc_id}/download", headers=_auth(regular_user_token)).get_json()

        assert body == {"url": f"/api/documents/{doc_id}/file", "expires_in": None}

    @pytest.mark.parametrize("filename", ["scan.exe", "scan.pdf", "archive", "scan.zip.exe"])
    def test_unsupported_types_are_refused(self, client, regular_user_token, test_pet, filename):
        response = _start_scan(client, regular_user_token, str(test_pet["_id"]), filename)
        assert response.status_code == 422
        assert response.get_json()["code"] == "scan_unsupported_type"

    def test_more_than_500_mb_is_refused(self, client, regular_user_token, test_pet, mock_db):
        response = _start_scan(client, regular_user_token, str(test_pet["_id"]), size=500 * 1024 * 1024 + 1)

        assert response.status_code == 422
        assert response.get_json()["code"] == "scan_too_large"
        assert mock_db["document_uploads"].count_documents({}) == 0

    def test_confirming_before_the_file_arrived_keeps_the_slot(self, client, mock_db, regular_user_token, test_pet):
        upload_id = _start_scan(client, regular_user_token, str(test_pet["_id"])).get_json()["upload_id"]

        response = _complete(client, regular_user_token, upload_id)

        assert response.get_json()["code"] == "scan_upload_incomplete"
        assert mock_db["document_uploads"].count_documents({"_id": upload_id}) == 1
        assert mock_db["documents"].count_documents({}) == 0

    def test_a_file_of_another_size_is_not_accepted(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        upload_id, _ = _upload_scan(
            client, regular_user_token, mock_db, s3_storage, str(test_pet["_id"]), _zip_bytes(64), size=100
        )

        response = _complete(client, regular_user_token, upload_id)

        assert response.get_json()["code"] == "scan_upload_incomplete"
        assert mock_db["documents"].count_documents({}) == 0

    def test_content_that_is_not_the_claimed_archive_is_discarded(
        self, client, mock_db, regular_user_token, test_pet, s3_storage
    ):
        upload_id, key = _upload_scan(
            client, regular_user_token, mock_db, s3_storage, str(test_pet["_id"]), b"MZ\x90\x00" + b"\0" * 60
        )

        response = _complete(client, regular_user_token, upload_id)

        assert response.get_json()["code"] == "scan_content_mismatch"
        assert key not in _keys(s3_storage)
        assert mock_db["document_uploads"].count_documents({}) == 0
        assert mock_db["documents"].count_documents({}) == 0

    def test_a_scan_stays_in_its_category(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        upload_id, _ = _upload_scan(client, regular_user_token, mock_db, s3_storage, str(test_pet["_id"]))
        doc_id = _complete(client, regular_user_token, upload_id).get_json()["id"]

        moved = client.put(f"/api/documents/{doc_id}", json={"category": "other"}, headers=_auth(regular_user_token))
        renamed = client.put(f"/api/documents/{doc_id}", json={"title": "КТ"}, headers=_auth(regular_user_token))

        assert moved.status_code == 422 and moved.get_json()["code"] == "scan_category_fixed"
        assert renamed.status_code == 200
        assert mock_db["documents"].find_one({"_id": ObjectId(doc_id)})["category"] == "imaging"

    def test_deleting_the_document_removes_the_archive(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        upload_id, key = _upload_scan(client, regular_user_token, mock_db, s3_storage, str(test_pet["_id"]))
        doc_id = _complete(client, regular_user_token, upload_id).get_json()["id"]

        response = client.delete(f"/api/documents/{doc_id}", headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert key not in _keys(s3_storage)


class TestFileFormats:
    @pytest.mark.parametrize(
        ("filename", "ext", "family"),
        [
            ("a.ZIP", ".zip", "zip"),
            ("a.tar.gz", ".tar.gz", "gzip"),
            ("a.tgz", ".tgz", "gzip"),
            ("a.gz", ".gz", "gzip"),
            ("a.7z", ".7z", "7z"),
            ("a.rar", ".rar", "rar"),
            ("a.tar", ".tar", "tar"),
            ("IM0001.dcm", ".dcm", "dicom"),
            ("disk.iso", ".iso", "iso"),
        ],
    )
    def test_accepted_extensions(self, filename, ext, family):
        found_ext, _, found_family = storage.scan_format(filename)
        assert (found_ext, found_family) == (ext, family)

    @pytest.mark.parametrize(
        ("head", "family"),
        [
            (b"PK\x03\x04", "zip"),
            (b"7z\xbc\xaf\x27\x1c", "7z"),
            (b"Rar!\x1a\x07\x01\x00", "rar"),
            (b"\x1f\x8b\x08", "gzip"),
            (b"\0" * 257 + b"ustar", "tar"),
            (b"\0" * 128 + b"DICM", "dicom"),
            (b"\0" * 32769 + b"CD001", "iso"),
        ],
    )
    def test_signatures(self, head, family):
        assert storage.matches_family(head, family)
        assert not storage.matches_family(b"\0" * 40000, family)


class TestDeletingRemovesEveryVersion:
    def test_delete_object(self, s3_storage):
        s3_storage.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
        key = "users/u1/pets/p1/documents/a.pdf"
        for body in (b"one", b"two"):
            s3_storage.put_object(Bucket=BUCKET, Key=key, Body=body)

        storage.delete_object(key)

        versions = s3_storage.list_object_versions(Bucket=BUCKET, Prefix=key)
        assert not versions.get("Versions") and not versions.get("DeleteMarkers")

    def test_delete_prefix_leaves_neighbours(self, s3_storage):
        s3_storage.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
        for key in ("users/u1/pets/p1/a", "users/u1/pets/p1/b", "users/u1/pets/p10/c"):
            s3_storage.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        assert storage.delete_prefix("users/u1/pets/p1/") == 2

        remaining = s3_storage.list_object_versions(Bucket=BUCKET).get("Versions", [])
        assert [v["Key"] for v in remaining] == ["users/u1/pets/p10/c"]

    def test_deleting_a_pet_clears_its_whole_prefix(
        self, client, mock_db, regular_user_token, test_pet, pet_with_files, s3_storage
    ):
        _start_scan(client, regular_user_token, pet_with_files["pet_id"])  # an unconfirmed slot
        prefix = storage.pet_prefix(mock_db, "testuser", pet_with_files["pet_id"])
        s3_storage.put_object(Bucket=BUCKET, Key=f"{prefix}scans/orphan.zip", Body=b"x")

        response = client.delete(f"/api/pets/{pet_with_files['pet_id']}", headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert _keys(s3_storage) == set()
        assert mock_db["document_uploads"].count_documents({}) == 0


class TestUpkeep:
    def test_abandoned_upload_slots_are_swept(self, mock_db, s3_storage):
        now = datetime.now(timezone.utc)
        for slot_id, age in (("old", timedelta(hours=7)), ("fresh", timedelta(minutes=5))):
            key = f"users/u1/pets/p1/scans/{slot_id}.zip"
            s3_storage.put_object(Bucket=BUCKET, Key=key, Body=b"x")
            mock_db["document_uploads"].insert_one({"_id": slot_id, "key": key, "created_at": now - age})

        assert storage.cleanup_abandoned_uploads(mock_db, now) == 1

        assert [s["_id"] for s in mock_db["document_uploads"].find()] == ["fresh"]
        assert _keys(s3_storage) == {"users/u1/pets/p1/scans/fresh.zip"}

    def test_bucket_cors_is_set_once(self, s3_storage):
        assert storage.ensure_bucket_cors()
        rules = s3_storage.get_bucket_cors(Bucket=BUCKET)["CORSRules"]
        assert "https://petzy.duckdns.org" in rules[0]["AllowedOrigins"]
        assert set(rules[0]["AllowedMethods"]) == {"PUT", "GET", "HEAD"}

        client = storage._client()
        original = client.put_bucket_cors
        client.put_bucket_cors = MagicMock(side_effect=original)
        try:
            assert storage.ensure_bucket_cors()
            client.put_bucket_cors.assert_not_called()
        finally:
            client.put_bucket_cors = original


class _FakeGridFile:
    def __init__(self, data, content_type, filename):
        self._data, self.content_type, self.filename = data, content_type, filename

    def read(self):
        return self._data


class TestMigrationFromGridFS:
    def test_moves_files_under_the_owner_prefix_and_deletes_them_from_gridfs(
        self, mock_db, regular_user, test_pet, s3_storage
    ):
        from scripts.migrate_files_to_s3 import migrate

        photo_id, doc_id, missing_id = ObjectId(), ObjectId(), ObjectId()
        files = {
            photo_id: _FakeGridFile(b"RIFFphoto", "image/webp", "cat.webp"),
            doc_id: _FakeGridFile(b"%PDF-1.4", "application/pdf", "Анализ.pdf"),
        }
        fs = MagicMock()
        fs.get.side_effect = lambda oid: files[oid]
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_id)}})
        pet_id = str(test_pet["_id"])
        mock_db["documents"].insert_many(
            [
                {"pet_id": pet_id, "username": "testuser", "file_id": str(doc_id)},
                {"pet_id": pet_id, "username": "testuser", "file_id": str(missing_id)},
                {"pet_id": pet_id, "username": "testuser", "file_id": "users/x/pets/y/documents/done.pdf"},
            ]
        )
        mock_db["image_thumbnails"].insert_one({"_id": "t"})

        stats = migrate(mock_db, fs, storage)

        assert stats["photos"] == 1 and stats["documents"] == 1 and stats["missing"] == 1
        prefix = storage.pet_prefix(mock_db, "testuser", pet_id)
        photo_key = mock_db["pets"].find_one({"_id": test_pet["_id"]})["photo_file_id"]
        doc_key = mock_db["documents"].find_one({"file_id": {"$regex": "^users/.*/documents/.*\\.pdf$"}})["file_id"]
        assert photo_key.startswith(prefix + "photos/") and photo_key.endswith(".webp")
        assert doc_key.startswith(prefix + "documents/")
        assert _keys(s3_storage) == {photo_key, doc_key}
        assert {c.args[0] for c in fs.delete.call_args_list} == {photo_id, doc_id}
        assert mock_db["image_thumbnails"].count_documents({}) == 0
        # The missing file's record is left for a person to look at.
        assert mock_db["documents"].count_documents({"file_id": str(missing_id)}) == 1

    def test_dry_run_changes_nothing(self, mock_db, test_pet, s3_storage):
        from scripts.migrate_files_to_s3 import migrate

        photo_id = ObjectId()
        fs = MagicMock()
        fs.get.return_value = _FakeGridFile(b"x", "image/webp", "a.webp")
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_id)}})

        stats = migrate(mock_db, fs, storage, dry_run=True)

        assert stats["pending"] == 1
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]})["photo_file_id"] == str(photo_id)
        assert _keys(s3_storage) == set()
        fs.delete.assert_not_called()


class TestLocalRunsShareTheBucketUnderDev:
    def test_start_clears_only_dev(self, s3_storage, monkeypatch):
        from scripts import dev_local

        for key in ("dev/users/u1/pets/p1/photos/a.jpg", "users/u1/pets/p1/photos/prod.webp", "healthcheck/x"):
            s3_storage.put_object(Bucket=BUCKET, Key=key, Body=b"x")
        monkeypatch.setenv("S3_PREFIX", "")  # restored (removed) after the test
        monkeypatch.delenv("DEV_STORAGE", raising=False)
        monkeypatch.setattr(dev_local, "_read_dotenv", lambda path: {})

        dev_local._start_local_storage()

        assert storage.key_prefix() == "dev/"
        assert _keys(s3_storage) == {"users/u1/pets/p1/photos/prod.webp", "healthcheck/x"}

    def test_refuses_to_clear_anything_else(self, monkeypatch):
        from scripts import dev_local

        monkeypatch.setattr(dev_local, "DEV_STORAGE_PREFIX", "")
        monkeypatch.setenv("S3_PREFIX", "")
        monkeypatch.setattr(dev_local, "_read_dotenv", lambda path: {})
        monkeypatch.delenv("DEV_STORAGE", raising=False)
        cleared = MagicMock()
        monkeypatch.setattr(storage, "delete_prefix", cleared)

        with pytest.raises(RuntimeError):
            dev_local._start_local_storage()
        cleared.assert_not_called()

    def test_dotenv_values_do_not_override_the_environment(self, tmp_path, monkeypatch):
        from scripts import dev_local

        env = tmp_path / ".env"
        env.write_text('# comment\nS3_BUCKET="from-file"\nS3_REGION=eu\n\nBROKEN\n')

        assert dev_local._read_dotenv(str(env)) == {"S3_BUCKET": "from-file", "S3_REGION": "eu"}
