"""Uploads can't run script on our origin, fill the bucket, or pass one type off as another."""

import io

import pytest
from PIL import Image

from web import documents, storage


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 80, 40)).save(buf, format="PNG")
    buf.seek(0)
    return buf


def _document(client, token, pet_id, body, filename, content_type):
    return client.post(
        "/api/documents",
        data={
            "pet_id": pet_id,
            "category": "other",
            "title": "Файл",
            "file": (io.BytesIO(body), filename, content_type),
        },
        headers=_auth(token),
        content_type="multipart/form-data",
    )


class TestPetPhoto:
    def test_an_html_photo_is_refused(self, client, mock_db, regular_user_token, test_pet, s3_storage):
        page = io.BytesIO(b"<html><script>fetch('/api/pets')</script></html>")
        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            data={"name": "Cat", "photo_file": (page, "x.html", "text/html")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )
        assert response.status_code in (400, 422)
        assert not mock_db["pets"].find_one({"_id": test_pet["_id"]}).get("photo_file_id")

    def test_a_photo_is_served_so_it_cannot_run(self, client, regular_user_token, test_pet, s3_storage):
        client.put(
            f"/api/pets/{test_pet['_id']}",
            data={"name": "Cat", "photo_file": (_png(), "cat.png", "image/png")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )
        response = client.get(f"/api/pets/{test_pet['_id']}/photo", headers=_auth(regular_user_token))
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "image/webp"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "sandbox" in response.headers["Content-Security-Policy"]

    def test_a_decompression_bomb_is_not_decoded(self, client, regular_user_token, test_pet, s3_storage):
        bomb = io.BytesIO()
        Image.new("1", (9000, 9000)).save(bomb, format="PNG")  # 81 MP, a few KB
        bomb.seek(0)
        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            data={"name": "Cat", "photo_file": (bomb, "big.png", "image/png")},
            headers=_auth(regular_user_token),
            content_type="multipart/form-data",
        )
        assert response.status_code in (400, 422)


class TestDocuments:
    def test_html_sent_as_a_pdf_is_refused(self, client, regular_user_token, test_pet, s3_storage):
        response = _document(
            client, regular_user_token, str(test_pet["_id"]), b"<html>hi</html>", "a.pdf", "application/pdf"
        )
        assert response.status_code == 422
        assert response.get_json()["code"] == "document_content_mismatch"

    def test_a_real_pdf_is_accepted(self, client, regular_user_token, test_pet, s3_storage):
        response = _document(
            client, regular_user_token, str(test_pet["_id"]), b"%PDF-1.4 x", "a.pdf", "application/pdf"
        )
        assert response.status_code == 201

    def test_the_quota_stops_uploads(self, client, regular_user_token, test_pet, s3_storage, monkeypatch):
        monkeypatch.setattr(documents, "STORAGE_QUOTA_BYTES", 20)
        pet_id = str(test_pet["_id"])
        assert (
            _document(client, regular_user_token, pet_id, b"%PDF-1.4 1234", "a.pdf", "application/pdf").status_code
            == 201
        )
        response = _document(client, regular_user_token, pet_id, b"%PDF-1.4 5678", "b.pdf", "application/pdf")
        assert response.status_code == 422
        assert response.get_json()["code"] == "storage_quota_exceeded"

    def test_a_scan_over_the_quota_gets_no_upload_link(
        self, client, regular_user_token, test_pet, s3_storage, monkeypatch
    ):
        monkeypatch.setattr(documents, "STORAGE_QUOTA_BYTES", 1000)
        response = client.post(
            "/api/documents/scans",
            json={"pet_id": str(test_pet["_id"]), "filename": "mri.zip", "size": 5000},
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 422
        assert response.get_json()["code"] == "storage_quota_exceeded"

    def test_only_a_few_scan_uploads_at_once(self, client, regular_user_token, test_pet, s3_storage):
        def start():
            return client.post(
                "/api/documents/scans",
                json={"pet_id": str(test_pet["_id"]), "filename": "mri.zip", "size": 64},
                headers=_auth(regular_user_token),
            )

        for _ in range(documents.MAX_PENDING_UPLOADS):
            assert start().status_code == 201
        assert start().status_code == 429


@pytest.mark.parametrize(
    ("size", "ttl"),
    [(64, 15 * 60), (500 * 1024 * 1024, (500 * 1024 * 1024) // (256 * 1024)), (10**12, 60 * 60)],
)
def test_an_upload_link_lives_only_as_long_as_the_file_needs(size, ttl):
    assert storage.upload_url_ttl(size) == ttl
