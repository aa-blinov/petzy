"""A pet request that is refused after its photo arrived leaves no file behind (QA B-08)."""

import io
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from web import storage


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def _files() -> list:
    return [o for o in storage.list_objects("") if o]


def _tomorrow() -> str:
    # The schema allows a day ahead for a phone east of UTC, and the handler's own check refuses it.
    return (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)).strftime("%Y-%m-%d")


@pytest.mark.health
def test_a_refused_birth_date_on_create_stores_no_photo(client, mock_db, regular_user_token, s3_storage):
    before = len(_files())
    response = client.post(
        "/api/pets",
        data={
            "name": "Тоша",
            "species": "Кот",
            "birth_date": _tomorrow(),
            "photo_file": (io.BytesIO(_png()), "a.png", "image/png"),
        },
        headers={"Authorization": f"Bearer {regular_user_token}"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert len(_files()) == before
    assert mock_db["pets"].count_documents({"name": "Тоша"}) == 0


@pytest.mark.health
def test_a_refused_birth_date_on_update_stores_no_photo(client, mock_db, regular_user_token, test_pet, s3_storage):
    before = len(_files())
    response = client.put(
        f"/api/pets/{test_pet['_id']}",
        data={"birth_date": _tomorrow(), "photo_file": (io.BytesIO(_png()), "a.png", "image/png")},
        headers={"Authorization": f"Bearer {regular_user_token}"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert len(_files()) == before
