"""A picture the browser cannot draw (a phone's HEIC) comes back as a WebP to look at, and nothing is stored."""

import io

import pytest
from PIL import Image


def _image(fmt: str) -> bytes:
    if fmt == "HEIF":
        import pillow_heif

        pillow_heif.register_heif_opener()
    buf = io.BytesIO()
    Image.new("RGB", (3000, 2000), (196, 106, 63)).save(buf, format=fmt)
    return buf.getvalue()


def _post(client, token, data: bytes, name: str, ctype: str):
    return client.post(
        "/api/images/preview",
        data={"file": (io.BytesIO(data), name, ctype)},
        headers={"Authorization": f"Bearer {token}"},
        content_type="multipart/form-data",
    )


@pytest.mark.documents
class TestImagePreview:
    def test_a_heic_comes_back_as_a_webp_within_the_size_to_look_at(self, client, mock_db, regular_user_token):
        response = _post(client, regular_user_token, _image("HEIF"), "IMG_1.heic", "image/heic")
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/webp" and response.headers["Cache-Control"] == "no-store"
        out = Image.open(io.BytesIO(response.data))
        assert out.format == "WEBP" and max(out.size) <= 1600

    def test_a_jpeg_comes_back_too(self, client, mock_db, regular_user_token):
        response = _post(client, regular_user_token, _image("JPEG"), "a.jpg", "image/jpeg")
        assert response.status_code == 200 and response.data[:4] == b"RIFF"

    def test_it_asks_for_a_sign_in(self, client, mock_db):
        response = client.post(
            "/api/images/preview",
            data={"file": (io.BytesIO(b"x"), "a.heic", "image/heic")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 401

    @pytest.mark.parametrize(
        "data, name, ctype",
        [
            (b"not a picture at all", "a.heic", "image/heic"),
            (b"%PDF-1.4 x", "a.pdf", "application/pdf"),
            (b"<svg></svg>", "a.svg", "image/svg+xml"),
        ],
    )
    def test_what_is_not_a_picture_is_refused(self, client, mock_db, regular_user_token, data, name, ctype):
        assert _post(client, regular_user_token, data, name, ctype).status_code == 422

    def test_nothing_is_stored(self, client, mock_db, regular_user_token):
        _post(client, regular_user_token, _image("HEIF"), "IMG_1.heic", "image/heic")
        assert mock_db["documents"].count_documents({}) == 0
