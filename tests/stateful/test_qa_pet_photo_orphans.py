"""A pet request that is refused after its photo arrived leaves no file behind (QA B-08)."""

import io
from datetime import datetime

import pytest
from PIL import Image

from web import storage


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), (1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def _files() -> list:
    return [o for o in storage.list_objects("") if o]


NOW = datetime(2026, 6, 10, 12, 0)
TOMORROW = "2026-06-11"


@pytest.fixture
def fixed_entry_clock(monkeypatch):
    """The clock the handler judges a typed date against is fixed, so that «tomorrow» is tomorrow at any hour of any zone.

    The schema reads the real clock, which is months later, and lets the date pass as a past one; the handler's own check,
    on the fixed one, refuses it as a future one: the order this module is about (the photo is stored only after the date)."""
    monkeypatch.setattr("web.helpers._entry_now", lambda tz_name: NOW)


@pytest.mark.health
def test_a_refused_birth_date_on_create_stores_no_photo(
    client, mock_db, regular_user_token, s3_storage, fixed_entry_clock
):
    before = len(_files())
    response = client.post(
        "/api/pets",
        data={
            "name": "Тоша",
            "species": "Кот",
            "birth_date": TOMORROW,
            "photo_file": (io.BytesIO(_png()), "a.png", "image/png"),
        },
        headers={"Authorization": f"Bearer {regular_user_token}"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert len(_files()) == before
    assert mock_db["pets"].count_documents({"name": "Тоша"}) == 0


@pytest.mark.health
def test_a_refused_birth_date_on_update_stores_no_photo(
    client, mock_db, regular_user_token, test_pet, s3_storage, fixed_entry_clock
):
    before = len(_files())
    response = client.put(
        f"/api/pets/{test_pet['_id']}",
        data={"birth_date": TOMORROW, "photo_file": (io.BytesIO(_png()), "a.png", "image/png")},
        headers={"Authorization": f"Bearer {regular_user_token}"},
        content_type="multipart/form-data",
    )
    assert response.status_code == 422
    assert len(_files()) == before
