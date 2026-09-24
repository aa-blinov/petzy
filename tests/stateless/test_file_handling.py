"""Uploaded images and documents: how they're stored, resized and served."""

import io
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from PIL import Image
from werkzeug.datastructures import FileStorage

from web.documents import content_disposition
from web.helpers import (
    PRIVATE_IMMUTABLE_CACHE,
    delete_stored_file,
    optimize_image,
    resize_image_bytes,
    snap_thumbnail_size,
)


def _png_bytes(size=(40, 20), color=(200, 50, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _webp_bytes(size=(40, 20), mode="RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, (200, 50, 50, 255)[: len(mode)]).save(buf, format="WEBP", quality=85)
    return buf.getvalue()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestImageProcessing:
    def test_exif_orientation_is_applied_before_reencoding(self):
        # A phone photo stored landscape with an "rotate 90°" EXIF tag must
        # come out portrait: the WebP re-encode drops EXIF, so the rotation
        # has to be baked into the pixels first.
        buf = io.BytesIO()
        img = Image.new("RGB", (200, 100), (10, 120, 200))
        exif = img.getexif()
        exif[0x0112] = 6  # Orientation: rotate 90° CW
        img.save(buf, format="JPEG", exif=exif.tobytes())
        buf.seek(0)

        output, _ = optimize_image(FileStorage(stream=buf, filename="p.jpg", content_type="image/jpeg"))

        assert Image.open(output).size == (100, 200)

    def test_heic_is_converted_to_webp(self):
        pillow_heif = pytest.importorskip("pillow_heif")
        buf = io.BytesIO()
        try:
            pillow_heif.from_pillow(Image.new("RGB", (64, 32), (0, 200, 0))).save(buf, quality=60)
        except Exception as e:  # pragma: no cover - encoder missing in this build
            pytest.skip(f"HEIC encoder unavailable: {e}")
        buf.seek(0)

        result = optimize_image(FileStorage(stream=buf, filename="IMG_0001.HEIC", content_type="image/heic"))

        assert result is not None
        output, content_type = result
        assert content_type == "image/webp"
        assert Image.open(output).size == (64, 32)

    @pytest.mark.parametrize("mode", ["RGB", "RGBA"])
    def test_ready_webp_is_stored_without_a_second_lossy_pass(self, mode):
        # The crop modal exports WebP already; re-encoding it would only
        # compress the same photo twice.
        data = _webp_bytes((300, 300), mode)
        output, content_type = optimize_image(FileStorage(stream=io.BytesIO(data), filename="p.webp"))

        assert content_type == "image/webp"
        assert output.getvalue() == data

    def test_oversized_webp_is_still_downscaled(self):
        data = _webp_bytes((2400, 1200))
        output, _ = optimize_image(FileStorage(stream=io.BytesIO(data), filename="p.webp"))

        assert output.getvalue() != data
        assert Image.open(output).size == (1920, 960)

    def test_thumbnail_sizes_snap_up_to_a_bucket(self):
        assert snap_thumbnail_size(None) is None
        assert snap_thumbnail_size(96) == 96
        assert snap_thumbnail_size(97) == 128
        assert snap_thumbnail_size(1) == 20
        assert snap_thumbnail_size(4000) is None  # bigger than any bucket: the original

    def test_resize_returns_none_when_no_size_or_image_already_small(self):
        data = _png_bytes((40, 20))
        assert resize_image_bytes(data, None, None) is None
        assert resize_image_bytes(data, 400, None) is None

    def test_resize_downscales_keeping_aspect_ratio(self):
        out = resize_image_bytes(_png_bytes((400, 200)), 100, None)

        img = Image.open(io.BytesIO(out))
        assert img.format == "WEBP"
        assert img.size == (100, 50)


class TestContentDisposition:
    def test_cyrillic_name_is_encodable_and_keeps_the_real_name(self):
        value = content_disposition("inline", "Прививка от бешенства.jpg", "image/webp")

        value.encode("latin-1")  # a header that can't be encoded fails the whole download
        assert "filename*=UTF-8''%D0%9F" in value
        assert value.endswith(".webp")  # stored as WebP, not the uploaded .jpg
        assert 'filename="document.webp"' in value  # ASCII fallback

    def test_quotes_cannot_break_the_header(self):
        value = content_disposition("attachment", 'my "scan".pdf', "application/pdf")
        assert 'filename="my scan.pdf"' in value


@pytest.mark.documents
class TestServingFiles:
    def _document(self, mock_db, pet_id, content_type="image/png", name="справка.png"):
        doc = {
            "pet_id": pet_id,
            "username": "testuser",
            "category": "other",
            "title": "Doc",
            "note": "",
            "file_id": str(ObjectId()),
            "original_filename": name,
            "content_type": content_type,
            "file_size": 123,
            "created_at": datetime.now(timezone.utc),
        }
        doc["_id"] = mock_db["documents"].insert_one(doc).inserted_id
        return doc

    def test_document_download_with_cyrillic_name_and_private_cache(
        self, client, mock_db, regular_user_token, test_pet
    ):
        from web.app import fs

        doc = self._document(mock_db, str(test_pet["_id"]))
        with patch.object(fs, "get", return_value=MagicMock(read=MagicMock(return_value=_png_bytes()))):
            response = client.get(f"/api/documents/{doc['_id']}/file", headers=_auth(regular_user_token))

        assert response.status_code == 200
        response.headers["Content-Disposition"].encode("latin-1")
        assert response.headers["Cache-Control"] == PRIVATE_IMMUTABLE_CACHE

    def test_document_revalidation_returns_304_without_reading_the_file(
        self, client, mock_db, regular_user_token, test_pet
    ):
        from web.app import fs

        doc = self._document(mock_db, str(test_pet["_id"]))
        with patch.object(fs, "get") as mock_get:
            response = client.get(
                f"/api/documents/{doc['_id']}/file?w=192",
                headers={**_auth(regular_user_token), "If-None-Match": f'"{doc["file_id"]}_192_None"'},
            )

        assert response.status_code == 304
        mock_get.assert_not_called()

    def test_pet_photo_thumbnail_is_resized_and_revalidates(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        photo_id = str(ObjectId())
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": photo_id}})
        stored = MagicMock(read=MagicMock(return_value=_png_bytes((1000, 1000))), content_type="image/webp")

        with patch.object(fs, "get", return_value=stored):
            response = client.get(f"/api/pets/{test_pet['_id']}/photo?v=abc&w=40", headers=_auth(regular_user_token))
        assert response.status_code == 200
        assert Image.open(io.BytesIO(response.data)).size == (40, 40)
        assert response.headers["Cache-Control"] == PRIVATE_IMMUTABLE_CACHE

        with patch.object(fs, "get") as mock_get:
            again = client.get(
                f"/api/pets/{test_pet['_id']}/photo?v=abc&w=40",
                headers={**_auth(regular_user_token), "If-None-Match": response.headers["ETag"]},
            )
        assert again.status_code == 304
        mock_get.assert_not_called()


@pytest.mark.pets
class TestThumbnailCache:
    def _pet_with_photo(self, mock_db, test_pet):
        photo_id = str(ObjectId())
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": photo_id}})
        return photo_id

    def test_second_request_is_served_from_the_cache(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        photo_id = self._pet_with_photo(mock_db, test_pet)
        stored = MagicMock(read=MagicMock(return_value=_png_bytes((1000, 1000))), content_type="image/webp")
        url = f"/api/pets/{test_pet['_id']}/photo?w=90"

        with patch.object(fs, "get", return_value=stored):
            first = client.get(url, headers=_auth(regular_user_token))
        with patch.object(fs, "get") as mock_get:
            second = client.get(url, headers=_auth(regular_user_token))

        mock_get.assert_not_called()
        assert second.data == first.data
        assert Image.open(io.BytesIO(second.data)).size == (96, 96)  # 90 snapped up to 96
        assert mock_db["image_thumbnails"].count_documents({"source_file_id": photo_id}) == 1

    def test_nearby_sizes_share_one_cached_variant(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        photo_id = self._pet_with_photo(mock_db, test_pet)
        stored = MagicMock(read=MagicMock(return_value=_png_bytes((1000, 1000))), content_type="image/webp")

        with patch.object(fs, "get", return_value=stored):
            for width in (81, 90, 96):
                client.get(f"/api/pets/{test_pet['_id']}/photo?w={width}", headers=_auth(regular_user_token))

        assert mock_db["image_thumbnails"].count_documents({"source_file_id": photo_id}) == 1

    def test_small_original_is_not_cached(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        self._pet_with_photo(mock_db, test_pet)
        stored = MagicMock(read=MagicMock(return_value=_png_bytes((30, 30))), content_type="image/png")

        with patch.object(fs, "get", return_value=stored):
            response = client.get(f"/api/pets/{test_pet['_id']}/photo?w=96", headers=_auth(regular_user_token))

        assert response.data == _png_bytes((30, 30))
        assert mock_db["image_thumbnails"].count_documents({}) == 0

    def test_deleting_a_file_drops_its_thumbnails(self, mock_db):
        from web.app import fs

        keep, gone = str(ObjectId()), str(ObjectId())
        mock_db["image_thumbnails"].insert_many(
            [{"_id": f"{keep}_96_None", "source_file_id": keep}, {"_id": f"{gone}_96_None", "source_file_id": gone}]
        )

        with patch.object(fs, "delete") as mock_delete:
            delete_stored_file(gone)

        mock_delete.assert_called_once_with(ObjectId(gone))
        assert [t["source_file_id"] for t in mock_db["image_thumbnails"].find()] == [keep]

    def test_replacing_a_photo_drops_the_old_thumbnails(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        old_id = self._pet_with_photo(mock_db, test_pet)
        mock_db["image_thumbnails"].insert_one({"_id": f"{old_id}_96_None", "source_file_id": old_id})

        with patch.object(fs, "delete"):
            client.put(f"/api/pets/{test_pet['_id']}", json={"remove_photo": True}, headers=_auth(regular_user_token))

        assert mock_db["image_thumbnails"].count_documents({}) == 0


class TestNoOrphanedFiles:
    def test_json_remove_photo_deletes_the_stored_file(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs

        old_id = ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(old_id)}})

        with patch.object(fs, "delete") as mock_delete:
            response = client.put(
                f"/api/pets/{test_pet['_id']}", json={"remove_photo": True}, headers=_auth(regular_user_token)
            )

        assert response.status_code == 200
        mock_delete.assert_called_once_with(old_id)
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]})["photo_file_id"] is None

    def test_replacing_a_photo_deletes_the_old_file_only_after_saving(
        self, client, mock_db, regular_user_token, test_pet
    ):
        from web.app import fs

        old_id, new_id = ObjectId(), ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(old_id)}})
        calls = []

        def fake_delete(file_id):
            # By the time the old file goes, the pet must already point at the new one.
            calls.append((file_id, mock_db["pets"].find_one({"_id": test_pet["_id"]})["photo_file_id"]))

        with patch.object(fs, "put", return_value=new_id), patch.object(fs, "delete", side_effect=fake_delete):
            response = client.put(
                f"/api/pets/{test_pet['_id']}",
                data={"name": "Test Cat", "photo_file": (io.BytesIO(_png_bytes()), "cat.png", "image/png")},
                headers=_auth(regular_user_token),
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        assert calls == [(old_id, str(new_id))]


@pytest.mark.documents
def test_oversized_upload_gets_a_json_413(client, regular_user_token, test_pet):
    response = client.post(
        "/api/documents",
        data={
            "pet_id": str(test_pet["_id"]),
            "category": "other",
            "title": "Huge",
            "file": (io.BytesIO(b"0" * (17 * 1024 * 1024)), "huge.pdf", "application/pdf"),
        },
        headers=_auth(regular_user_token),
        content_type="multipart/form-data",
    )

    assert response.status_code == 413
    assert response.get_json()["code"] == "request_too_large"
