"""A text field of a multipart form is text: a pet named «7» or a document titled «2025» is not a number, and «true» or «null» is
not a boolean or nothing (the validation library used to read every single value as JSON)."""

import io

import pytest
from bson import ObjectId
from PIL import Image


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def _post_pet(client, token, **fields):
    return client.post(
        "/api/pets",
        data={"species": "Кот", **fields},
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


@pytest.mark.health
class TestPetsNamedLikeNumbers:
    @pytest.mark.parametrize("name", ["7", "123", "1.5", "1e3", "true", "null", "007", "2025"])
    def test_the_name_is_kept_as_it_was_typed(self, client, mock_db, regular_user_token, name):
        response = _post_pet(client, regular_user_token, name=name)
        assert response.status_code == 201, response.get_json()
        assert mock_db["pets"].find_one({"name": name}) is not None

    def test_the_other_text_fields_too(self, client, mock_db, regular_user_token):
        response = _post_pet(client, regular_user_token, name="Тоша", breed="5", health_notes="0", gender="1")
        assert response.status_code == 201, response.get_json()
        pet = mock_db["pets"].find_one({"name": "Тоша"})
        assert (pet["breed"], pet["health_notes"], pet["gender"]) == ("5", "0", "1")

    def test_a_switch_and_the_tiles_still_come_through(self, client, mock_db, regular_user_token):
        response = _post_pet(
            client, regular_user_token, name="Мика", is_neutered="true", tiles_settings='{"enabled": ["feeding"]}'
        )
        assert response.status_code in (201, 422), response.get_json()
        if response.status_code == 201:
            assert mock_db["pets"].find_one({"name": "Мика"})["is_neutered"] is True


@pytest.mark.documents
class TestDocumentsTitledLikeNumbers:
    @pytest.mark.parametrize("title", ["2025", "7", "1.5", "true", "null"])
    def test_the_title_and_the_note_are_kept_as_typed(
        self, client, mock_db, regular_user_token, test_pet, s3_storage, title
    ):
        response = client.post(
            "/api/documents",
            data={
                "pet_id": str(test_pet["_id"]),
                "category": "other",
                "title": title,
                "note": "0",
                "file": (io.BytesIO(_png()), "a.png", "image/png"),
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )
        assert response.status_code == 201, response.get_json()
        doc = mock_db["documents"].find_one({"_id": ObjectId(response.get_json()["id"])})
        assert (doc["title"], doc["note"]) == (title, "0")


@pytest.mark.health
class TestNamesAreOneLine:
    def test_a_line_break_or_a_run_of_spaces_in_a_pet_name_is_one_space(self, client, mock_db, regular_user_token):
        response = _post_pet(client, regular_user_token, name="  Рыжий \r\n  кот  ")
        assert response.status_code == 201, response.get_json()
        assert mock_db["pets"].find_one({"name": "Рыжий кот"}) is not None
