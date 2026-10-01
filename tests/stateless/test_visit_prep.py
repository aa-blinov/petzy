"""What a vet asks at an appointment beyond the records: the diet and the way of life in the profile, the complaint
on a visit, and «К приёму», what the household wants to tell the vet next time."""

import io
from datetime import date

import pytest
from pypdf import PdfReader

from web.security import create_access_token


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _card(client, token, pet):
    return client.get(f"/api/pets/{pet['_id']}/medical-card", headers=_auth(token)).get_json()["card"]


def _pdf_text(client, token, pet):
    response = client.get(f"/api/pets/{pet['_id']}/medical-card/pdf", headers=_auth(token))
    assert response.status_code == 200
    return " ".join("\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages).split())


def _put_profile(client, token, pet, body):
    return client.put(f"/api/pets/{pet['_id']}/medical-profile", json=body, headers=_auth(token))


def _put_prep(client, token, pet, body):
    return client.put(f"/api/pets/{pet['_id']}/visit-prep", json=body, headers=_auth(token))


@pytest.mark.health
class TestDietAndWayOfLife:
    def test_they_are_saved_and_come_back(self, client, mock_db, regular_user_token, test_pet):
        body = {
            "diet": "Сухой корм, два раза в день",
            "living": "Квартира, живёт с собакой",
            "reproduction": "Одна беременность",
        }
        assert _put_profile(client, regular_user_token, test_pet, body).status_code == 200
        profile = _card(client, regular_user_token, test_pet)["profile"]
        assert (profile["diet"], profile["living"], profile["reproduction"]) == tuple(body.values())

    def test_blank_ones_are_not_filled_in_and_the_limit_holds(self, client, mock_db, regular_user_token, test_pet):
        _put_profile(client, regular_user_token, test_pet, {"diet": "   ", "living": ""})
        profile = _card(client, regular_user_token, test_pet)["profile"]
        assert profile["diet"] is None and profile["living"] is None and profile["reproduction"] is None
        assert _put_profile(client, regular_user_token, test_pet, {"diet": "к" * 201}).status_code == 422

    def test_the_pdf_has_them(self, client, mock_db, regular_user_token, test_pet):
        _put_profile(client, regular_user_token, test_pet, {"diet": "Натуральное", "living": "Частный дом, выгул"})
        text = _pdf_text(client, regular_user_token, test_pet)
        assert "Питание: Натуральное" in text and "Условия жизни: Частный дом, выгул" in text


@pytest.mark.health
class TestComplaintOnAVisit:
    def _visit(self, client, token, pet, **extra):
        body = {
            "pet_id": str(pet["_id"]),
            "kind": "visit",
            "date": date.today().isoformat(),
            "title": "Осмотр",
            **extra,
        }
        return client.post("/api/medical-records", json=body, headers=_auth(token))

    def test_a_visit_keeps_its_complaint(self, client, mock_db, regular_user_token, test_pet):
        assert self._visit(client, regular_user_token, test_pet, complaint="Третий день не ест").status_code == 201
        (record,) = _card(client, regular_user_token, test_pet)["records"]["visit"]
        assert record["complaint"] == "Третий день не ест"

    def test_another_kind_does_not_keep_one(self, client, mock_db, regular_user_token, test_pet):
        body = {
            "pet_id": str(test_pet["_id"]),
            "kind": "procedure",
            "date": date.today().isoformat(),
            "title": "УЗИ",
            "complaint": "x",
        }
        client.post("/api/medical-records", json=body, headers=_auth(regular_user_token))
        (record,) = _card(client, regular_user_token, test_pet)["records"]["procedure"]
        assert record["complaint"] is None

    def test_the_limit(self, client, regular_user_token, test_pet):
        assert self._visit(client, regular_user_token, test_pet, complaint="к" * 501).status_code == 422

    def test_the_pdf_has_it(self, client, mock_db, regular_user_token, test_pet):
        self._visit(client, regular_user_token, test_pet, complaint="Третий день не ест", diagnosis="Гастрит")
        assert "Жалоба: Третий день не ест" in _pdf_text(client, regular_user_token, test_pet)


@pytest.mark.health
class TestVisitPrep:
    BODY = {"complaint": "Кашляет по ночам", "checks": {"appetite": "changed", "stool": "normal", "cough": "changed"}}

    def test_it_is_saved_and_comes_back_on_the_card(self, client, mock_db, regular_user_token, test_pet):
        assert _put_prep(client, regular_user_token, test_pet, self.BODY).status_code == 200
        prep = _card(client, regular_user_token, test_pet)["visit_prep"]
        assert prep["complaint"] == "Кашляет по ночам" and prep["checks"]["cough"] == "changed" and prep["updated_at"]

    def test_a_card_with_nothing_has_none(self, client, mock_db, regular_user_token, test_pet):
        assert _card(client, regular_user_token, test_pet)["visit_prep"] is None

    def test_an_empty_one_clears_it(self, client, mock_db, regular_user_token, test_pet):
        _put_prep(client, regular_user_token, test_pet, self.BODY)
        assert _put_prep(client, regular_user_token, test_pet, {}).get_json() == {"visit_prep": None}
        assert _card(client, regular_user_token, test_pet)["visit_prep"] is None
        assert "visit_prep" not in mock_db["pets"].find_one({"_id": test_pet["_id"]})

    @pytest.mark.parametrize(
        "body",
        [
            {"checks": {"smell": "changed"}},
            {"checks": {"appetite": "bad"}},
            {"complaint": "к" * 501},
        ],
    )
    def test_bad_ones_are_refused(self, client, regular_user_token, test_pet, body):
        assert _put_prep(client, regular_user_token, test_pet, body).status_code == 422

    def test_a_blank_complaint_with_no_checks_is_empty(self, client, mock_db, regular_user_token, test_pet):
        _put_prep(client, regular_user_token, test_pet, self.BODY)
        _put_prep(client, regular_user_token, test_pet, {"complaint": "   "})
        assert _card(client, regular_user_token, test_pet)["visit_prep"] is None

    def test_the_pdf_says_it_first_after_the_header(self, client, mock_db, regular_user_token, test_pet):
        _put_prep(client, regular_user_token, test_pet, self.BODY)
        text = _pdf_text(client, regular_user_token, test_pet)
        assert "На приём Кашляет по ночам Изменилось: аппетит, кашель. Как обычно: стул." in text

    def test_a_shared_user_may_a_stranger_may_not(self, client, mock_db, regular_user_token, test_pet):
        mock_db["users"].insert_one({"username": "friend", "is_active": True, "password_hash": "x"})
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["friend"]}})
        assert _put_prep(client, create_access_token("friend"), test_pet, self.BODY).status_code == 200
        mock_db["users"].insert_one({"username": "stranger", "is_active": True, "password_hash": "x"})
        assert _put_prep(client, create_access_token("stranger"), test_pet, self.BODY).status_code in (403, 404)

    def test_nobody_without_a_login(self, client, test_pet):
        assert client.put(f"/api/pets/{test_pet['_id']}/visit-prep", json=self.BODY).status_code == 401
