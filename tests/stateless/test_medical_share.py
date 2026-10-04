"""A link to the medical card for a vet: made on purpose, read-only, with an end, and taken back at once."""

from datetime import timedelta

import pytest
from bson import ObjectId
from pypdf import PdfReader
import io

from web.medical_share import _now, hash_token
from web.security import create_access_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make(client, token, pet, days=7):
    return client.post(f"/api/pets/{pet['_id']}/medical-card/shares", json={"days": days}, headers=_auth(token))


@pytest.mark.health
class TestMakingALink:
    def test_the_secret_is_shown_once_and_only_its_hash_is_kept(self, client, mock_db, regular_user_token, test_pet):
        response = _make(client, regular_user_token, test_pet)
        assert response.status_code == 201
        body = response.get_json()
        token = body["token"]
        assert len(token) >= 40 and body["path"] == f"/share/medical/{token}"
        assert response.headers["Cache-Control"] == "private, no-store"
        stored = mock_db["medical_shares"].find_one({})
        assert stored["token_hash"] == hash_token(token) and token not in str(stored)
        # the list names the link without its secret
        listed = client.get(
            f"/api/pets/{test_pet['_id']}/medical-card/shares", headers=_auth(regular_user_token)
        ).get_json()
        assert [s["id"] for s in listed["shares"]] == [body["share"]["id"]]
        assert token not in str(listed)

    def test_it_ends_in_one_seven_or_thirty_days_and_not_otherwise(self, client, mock_db, regular_user_token, test_pet):
        for days in (1, 7, 30):
            assert _make(client, regular_user_token, test_pet, days).status_code == 201
        assert _make(client, regular_user_token, test_pet, 365).status_code == 422
        assert _make(client, regular_user_token, test_pet, 0).status_code == 422
        ends = sorted(s["expires_at"] - s["created_at"] for s in mock_db["medical_shares"].find({}))
        assert [d.days for d in ends] == [1, 7, 30]

    def test_a_pet_has_a_few_links_not_a_pile(self, client, regular_user_token, test_pet):
        for _ in range(10):
            assert _make(client, regular_user_token, test_pet).status_code == 201
        assert _make(client, regular_user_token, test_pet).status_code == 422

    def test_only_someone_who_can_see_the_pet_makes_one(self, client, mock_db, regular_user_token, test_pet):
        stranger = create_access_token("stranger")
        mock_db["users"].insert_one({"username": "stranger", "is_active": True})
        assert _make(client, stranger, test_pet).status_code in (403, 404)
        assert client.post(f"/api/pets/{test_pet['_id']}/medical-card/shares", json={"days": 7}).status_code == 401
        assert mock_db["medical_shares"].count_documents({}) == 0


@pytest.mark.health
class TestOpeningByTheLink:
    def test_the_card_opens_without_signing_in_and_cannot_be_edited(
        self, client, mock_db, regular_user_token, test_pet
    ):
        token = _make(client, regular_user_token, test_pet).get_json()["token"]
        response = client.get(f"/api/shared/medical-card/{token}")
        assert response.status_code == 200
        body = response.get_json()
        assert body["card"]["pet"]["name"] == "Test Cat" and body["card"]["can_edit"] is False
        assert body["expires_at"].endswith("Z")
        assert response.headers["Cache-Control"] == "private, no-store"
        assert "noindex" in response.headers["X-Robots-Tag"] and response.headers["Referrer-Policy"] == "no-referrer"

    def test_the_pdf_opens_by_the_same_link(self, client, regular_user_token, test_pet):
        token = _make(client, regular_user_token, test_pet).get_json()["token"]
        response = client.get(f"/api/shared/medical-card/{token}/pdf")
        assert response.status_code == 200 and response.mimetype == "application/pdf"
        assert "Test Cat" in "".join(page.extract_text() for page in PdfReader(io.BytesIO(response.data)).pages)
        assert "noindex" in response.headers["X-Robots-Tag"]

    def test_a_wrong_an_ended_and_a_revoked_link_look_the_same(self, client, mock_db, regular_user_token, test_pet):
        made = _make(client, regular_user_token, test_pet).get_json()
        token = made["token"]
        assert client.get("/api/shared/medical-card/not-a-link").status_code == 404
        assert client.get(f"/api/shared/medical-card/{'x' * 200}").status_code == 404
        # ended
        mock_db["medical_shares"].update_one({}, {"$set": {"expires_at": _now() - timedelta(seconds=1)}})
        ended = client.get(f"/api/shared/medical-card/{token}")
        assert ended.status_code == 404 and client.get(f"/api/shared/medical-card/{token}/pdf").status_code == 404
        mock_db["medical_shares"].update_one({}, {"$set": {"expires_at": _now() + timedelta(days=1)}})
        assert client.get(f"/api/shared/medical-card/{token}").status_code == 200
        # revoked
        assert (
            client.delete(
                f"/api/pets/{test_pet['_id']}/medical-card/shares/{made['share']['id']}",
                headers=_auth(regular_user_token),
            ).status_code
            == 200
        )
        revoked = client.get(f"/api/shared/medical-card/{token}")
        assert revoked.status_code == 404 and revoked.get_json() == ended.get_json()

    def test_a_link_shows_only_its_own_pet(self, client, mock_db, regular_user, regular_user_token, test_pet):
        other = mock_db["pets"].insert_one({"name": "Другой", "owner": regular_user["username"], "shared_with": []})
        token = _make(client, regular_user_token, test_pet).get_json()["token"]
        body = client.get(f"/api/shared/medical-card/{token}").get_json()
        assert body["card"]["pet"]["name"] == "Test Cat" and "Другой" not in str(body)
        assert other.inserted_id is not None

    def test_the_link_dies_with_its_pet(self, client, mock_db, regular_user_token, test_pet):
        token = _make(client, regular_user_token, test_pet).get_json()["token"]
        assert client.delete(f"/api/pets/{test_pet['_id']}", headers=_auth(regular_user_token)).status_code in (
            200,
            204,
        )
        assert mock_db["medical_shares"].count_documents({}) == 0
        assert client.get(f"/api/shared/medical-card/{token}").status_code == 404


@pytest.mark.health
class TestTakingItBack:
    def test_a_revoked_link_leaves_the_list_and_a_second_revoke_is_not_found(
        self, client, regular_user_token, test_pet
    ):
        made = _make(client, regular_user_token, test_pet).get_json()
        url = f"/api/pets/{test_pet['_id']}/medical-card/shares/{made['share']['id']}"
        assert client.delete(url, headers=_auth(regular_user_token)).status_code == 200
        assert (
            client.get(
                f"/api/pets/{test_pet['_id']}/medical-card/shares", headers=_auth(regular_user_token)
            ).get_json()["shares"]
            == []
        )
        assert client.delete(url, headers=_auth(regular_user_token)).status_code == 404
        assert (
            client.delete(
                f"/api/pets/{test_pet['_id']}/medical-card/shares/{ObjectId()}", headers=_auth(regular_user_token)
            ).status_code
            == 404
        )
        assert (
            client.delete(
                f"/api/pets/{test_pet['_id']}/medical-card/shares/nonsense", headers=_auth(regular_user_token)
            ).status_code
            == 404
        )

    def test_a_link_of_another_pet_cannot_be_revoked_through_this_one(
        self, client, mock_db, regular_user, regular_user_token, test_pet
    ):
        other = (
            mock_db["pets"]
            .insert_one({"name": "Другой", "owner": regular_user["username"], "shared_with": []})
            .inserted_id
        )
        made = client.post(
            f"/api/pets/{other}/medical-card/shares", json={"days": 7}, headers=_auth(regular_user_token)
        ).get_json()
        wrong = client.delete(
            f"/api/pets/{test_pet['_id']}/medical-card/shares/{made['share']['id']}", headers=_auth(regular_user_token)
        )
        assert wrong.status_code == 404
        assert client.get(f"/api/shared/medical-card/{made['token']}").status_code == 200
