"""Stateless tests for pet photo handling.

Each test here checks one call's output against its input — no test
depends on, or asserts on, state left behind by another. The first
group exercises `optimize_image` directly as a pure function (a real
Pillow image in, a real WebP out); the second checks that the pet
endpoints call GridFS (mocked, per the existing `app.fs` test pattern)
with the arguments the feature promises, without caring about anything
persisted across requests.
"""

import io

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage
from bson import ObjectId

from web.helpers import optimize_image


def _make_image_file(size=(100, 100), mode="RGB", color=(200, 50, 50), fmt="PNG", filename="photo.png"):
    """Build a Werkzeug FileStorage wrapping a real in-memory image."""
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, format=fmt)
    buf.seek(0)
    return FileStorage(stream=buf, filename=filename, content_type=f"image/{fmt.lower()}")


class TestOptimizeImageStateless:
    """optimize_image is a pure function: same input, same output, no I/O beyond the passed-in stream."""

    def test_converts_to_webp(self):
        file_storage = _make_image_file(size=(50, 50), mode="RGB")

        result = optimize_image(file_storage)

        assert result is not None
        output, content_type = result
        assert content_type == "image/webp"
        img = Image.open(output)
        assert img.format == "WEBP"
        assert img.size == (50, 50)

    def test_converts_rgba_transparency_to_white_background(self):
        # A fully transparent pixel should composite onto white, not
        # black or leftover garbage — the code special-cases RGBA/LA/P
        # specifically to avoid that.
        file_storage = _make_image_file(size=(10, 10), mode="RGBA", color=(0, 0, 0, 0), fmt="PNG")

        result = optimize_image(file_storage)

        assert result is not None
        output, _ = result
        img = Image.open(output).convert("RGB")
        # WebP lossy encoding won't reproduce (255,255,255) exactly;
        # "close to white" is the meaningful assertion here.
        r, g, b = img.getpixel((5, 5))
        assert r > 240 and g > 240 and b > 240

    def test_resizes_oversized_image(self):
        file_storage = _make_image_file(size=(3000, 1500), mode="RGB")

        result = optimize_image(file_storage, max_width=1920, max_height=1920)

        assert result is not None
        output, _ = result
        img = Image.open(output)
        assert img.width <= 1920
        assert img.height <= 1920
        # Aspect ratio (2:1) preserved by thumbnail()'s scaling.
        assert abs(img.width / img.height - 2.0) < 0.05

    def test_leaves_small_image_unresized(self):
        file_storage = _make_image_file(size=(200, 100), mode="RGB")

        result = optimize_image(file_storage, max_width=1920, max_height=1920)

        assert result is not None
        output, _ = result
        img = Image.open(output)
        assert img.size == (200, 100)

    def test_returns_none_on_invalid_input(self):
        garbage = FileStorage(stream=io.BytesIO(b"not an image"), filename="broken.png")

        result = optimize_image(garbage)

        assert result is None


@pytest.mark.pets
class TestPetPhotoEndpointStateless:
    """Each test checks one request's effect on GridFS calls in isolation."""

    def _photo_bytes(self):
        buf = io.BytesIO()
        Image.new("RGB", (20, 20), (10, 20, 30)).save(buf, format="PNG")
        buf.seek(0)
        return buf

    def test_create_pet_with_photo_stores_webp_via_gridfs(self, client, mock_db, regular_user_token):
        from web.app import fs
        from unittest.mock import patch

        with patch.object(fs, "put", return_value=ObjectId()) as mock_put:
            response = client.post(
                "/api/pets",
                data={
                    "name": "Photo Cat",
                    "photo_file": (self._photo_bytes(), "cat.png"),
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["pet"]["photo_file_id"]
        assert data["pet"]["photo_url"]

        mock_put.assert_called_once()
        _, kwargs = mock_put.call_args
        assert kwargs["filename"].endswith(".webp")
        assert kwargs["content_type"] == "image/webp"

    def test_update_pet_replacing_photo_deletes_old_from_gridfs(self, client, mock_db, regular_user_token, test_pet):
        from web.app import fs
        from unittest.mock import patch

        old_photo_id = ObjectId()
        mock_db["pets"].update_one(
            {"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(old_photo_id)}}
        )

        with patch.object(fs, "delete") as mock_delete, patch.object(fs, "put", return_value=ObjectId()) as mock_put:
            response = client.put(
                f"/api/pets/{test_pet['_id']}",
                data={
                    "name": test_pet["name"],
                    "photo_file": (self._photo_bytes(), "new.png"),
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        mock_delete.assert_called_once_with(old_photo_id)
        mock_put.assert_called_once()

    def test_update_pet_remove_photo_clears_it_and_deletes_from_gridfs(
        self, client, mock_db, regular_user_token, test_pet
    ):
        from web.app import fs
        from unittest.mock import patch

        old_photo_id = ObjectId()
        mock_db["pets"].update_one(
            {"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(old_photo_id)}}
        )

        with patch.object(fs, "delete") as mock_delete:
            response = client.put(
                f"/api/pets/{test_pet['_id']}",
                data={"name": test_pet["name"], "remove_photo": "true"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        mock_delete.assert_called_once_with(old_photo_id)
        pet = mock_db["pets"].find_one({"_id": test_pet["_id"]})
        assert not pet.get("photo_file_id")

    def test_optimization_failure_falls_back_to_original_file(self, client, mock_db, regular_user_token):
        from web.app import fs
        from unittest.mock import patch

        with patch("web.pets.optimize_image", return_value=None), \
             patch.object(fs, "put", return_value=ObjectId()) as mock_put:
            response = client.post(
                "/api/pets",
                data={
                    "name": "Fallback Cat",
                    "photo_file": (self._photo_bytes(), "original.png"),
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 201
        mock_put.assert_called_once()
        _, kwargs = mock_put.call_args
        assert kwargs["filename"] == "original.png"
        assert kwargs["content_type"] == "image/png"
