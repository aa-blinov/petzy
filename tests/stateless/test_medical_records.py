"""Medical records: vaccinations, parasite treatments, vet visits, procedures."""

from datetime import date, datetime, timedelta, timezone

import pytest
from bson import ObjectId

from web.medical_records import due_status, normalize_title, record_states
from web.security import create_access_token

TODAY = date.today()


def iso(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _post(client, token, pet, kind="vaccination", **extra):
    body = {"pet_id": str(pet["_id"]), "kind": kind, "date": iso(-1), "title": "Нобивак", **extra}
    if kind == "parasite" and "target" not in extra:
        body["target"] = "both"
    return client.post("/api/medical-records", json=body, headers=_auth(token))


def _list(client, token, pet, query=""):
    response = client.get(f"/api/medical-records?pet_id={pet['_id']}{query}", headers=_auth(token))
    assert response.status_code == 200, response.get_json()
    return response.get_json()["records"]


class TestRules:
    def test_a_repeat_has_a_status_by_kind(self):
        assert due_status("vaccination", iso(-1), TODAY) == ("overdue", -1)
        assert due_status("vaccination", iso(0), TODAY) == ("soon", 0)
        assert due_status("vaccination", iso(14), TODAY) == ("soon", 14)
        assert due_status("vaccination", iso(15), TODAY) == ("ok", 15)
        assert due_status("parasite", iso(7), TODAY)[0] == "soon"
        assert due_status("parasite", iso(8), TODAY)[0] == "ok"

    def test_no_repeat_and_kinds_without_one_have_no_status(self):
        assert due_status("vaccination", None, TODAY) == ("none", None)
        assert due_status("visit", iso(-30), TODAY) == ("none", None)
        assert due_status("procedure", iso(5), TODAY) == ("none", None)
        assert due_status("vaccination", "not a date", TODAY) == ("none", None)

    def test_titles_are_compared_loosely(self):
        assert normalize_title("  Нобивак   DHPPi ") == normalize_title("нобивак dhppi")

    def _rec(self, kind, title, day, next_due=None, created=0):
        return {
            "_id": ObjectId(),
            "kind": kind,
            "title": title,
            "date": day,
            "next_due": next_due,
            "created_at": datetime(2024, 1, 1) + timedelta(seconds=created),
        }

    def test_only_the_latest_of_a_title_counts_for_the_repeat(self):
        old = self._rec("vaccination", "Бешенство", "2024-01-10", "2025-01-10")
        new = self._rec("vaccination", "бешенство ", "2025-01-12", iso(300))
        other = self._rec("vaccination", "Комплексная", "2024-06-01", iso(-5))
        states = record_states([old, new, other], TODAY)
        assert states[str(old["_id"])] == {"status": "none", "days_left": None, "superseded": True}
        assert states[str(new["_id"])]["status"] == "ok" and states[str(new["_id"])]["superseded"] is False
        assert states[str(other["_id"])]["status"] == "overdue"

    def test_the_same_title_under_another_kind_is_not_a_replacement(self):
        vaccine = self._rec("vaccination", "Drontal", "2024-01-01", iso(-3))
        treatment = self._rec("parasite", "Drontal", "2024-02-01", iso(30))
        states = record_states([vaccine, treatment], TODAY)
        assert states[str(vaccine["_id"])]["status"] == "overdue"
        assert states[str(treatment["_id"])]["status"] == "ok"

    def test_visits_are_never_replaced(self):
        a, b = self._rec("visit", "Осмотр", "2024-01-01"), self._rec("visit", "Осмотр", "2025-01-01")
        assert not any(s["superseded"] for s in record_states([a, b], TODAY).values())

    def test_a_tie_on_the_date_goes_to_the_one_added_later(self):
        first = self._rec("vaccination", "X", "2025-01-01", iso(10), created=0)
        second = self._rec("vaccination", "X", "2025-01-01", iso(400), created=5)
        states = record_states([first, second], TODAY)
        assert states[str(first["_id"])]["superseded"] and not states[str(second["_id"])]["superseded"]


@pytest.mark.health
class TestCrud:
    def test_each_kind_is_created_and_keeps_only_its_own_fields(self, client, mock_db, regular_user_token, test_pet):
        everything = {
            "batch": "B-77",
            "diagnosis": "Гастрит",
            "recommendations": "Диета",
            "clinic": "Друг",
            "vet": "Иванова",
            "note": "ок",
        }
        for kind, kept in [
            ("vaccination", {"batch"}),
            ("parasite", set()),
            ("visit", {"diagnosis", "recommendations"}),
            ("procedure", set()),
        ]:
            response = _post(client, regular_user_token, test_pet, kind=kind, title=f"t-{kind}", **everything)
            assert response.status_code == 201, (kind, response.get_json())
            doc = mock_db["medical_records"].find_one({"_id": ObjectId(response.get_json()["id"])})
            assert doc["kind"] == kind and doc["clinic"] == "Друг" and doc["vet"] == "Иванова" and doc["note"] == "ок"
            for field in ("batch", "diagnosis", "recommendations"):
                assert bool(doc[field]) == (field in kept), (kind, field)
        assert mock_db["medical_records"].find_one({"kind": "parasite"})["target"] == "both"
        assert mock_db["medical_records"].find_one({"kind": "vaccination"})["target"] is None

    @pytest.mark.parametrize(
        "extra",
        [
            {"kind": "weight"},
            {"title": ""},
            {"title": "x" * 101},
            {"date": "12.05.2026"},
            {"date": iso(5)},
            {"next_due": iso(-10), "date": iso(-1)},
            {"next_due": iso(4000)},
            {"batch": "x" * 51},
            {"document_ids": ["not-an-id"]},
        ],
    )
    def test_bad_records_are_refused(self, client, regular_user_token, test_pet, extra):
        body = {"pet_id": str(test_pet["_id"]), "kind": "vaccination", "date": iso(-1), "title": "Нобивак", **extra}
        assert client.post("/api/medical-records", json=body, headers=_auth(regular_user_token)).status_code == 422

    def test_a_treatment_must_say_against_what(self, client, regular_user_token, test_pet):
        body = {"pet_id": str(test_pet["_id"]), "kind": "parasite", "date": iso(-1), "title": "Дронтал"}
        assert client.post("/api/medical-records", json=body, headers=_auth(regular_user_token)).status_code == 422
        assert (
            client.post(
                "/api/medical-records", json={**body, "target": "lice"}, headers=_auth(regular_user_token)
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/medical-records", json={**body, "target": "worms"}, headers=_auth(regular_user_token)
            ).status_code
            == 201
        )

    def test_blank_optional_fields_are_none(self, client, mock_db, regular_user_token, test_pet):
        response = _post(client, regular_user_token, test_pet, clinic="   ", vet="", note=" ", next_due="")
        doc = mock_db["medical_records"].find_one({"_id": ObjectId(response.get_json()["id"])})
        assert doc["clinic"] is doc["vet"] is doc["note"] is doc["next_due"] is None

    def test_list_is_newest_first_filterable_and_carries_status(self, client, regular_user_token, test_pet):
        _post(client, regular_user_token, test_pet, title="Старая", date=iso(-400), next_due=iso(-30))
        _post(client, regular_user_token, test_pet, title="Новая", date=iso(-2), next_due=iso(100))
        _post(client, regular_user_token, test_pet, kind="visit", title="Осмотр", date=iso(-10))
        records = _list(client, regular_user_token, test_pet)
        assert [r["title"] for r in records] == ["Новая", "Осмотр", "Старая"]
        by_title = {r["title"]: r for r in records}
        assert by_title["Новая"]["status"] == "ok" and by_title["Старая"]["status"] == "overdue"
        assert [r["title"] for r in _list(client, regular_user_token, test_pet, "&kind=visit")] == ["Осмотр"]
        assert (
            client.get(
                f"/api/medical-records?pet_id={test_pet['_id']}&kind=nope", headers=_auth(regular_user_token)
            ).status_code
            == 422
        )

    def test_get_update_delete(self, client, mock_db, regular_user_token, test_pet):
        rid = _post(client, regular_user_token, test_pet, title="Нобивак", batch="A1").get_json()["id"]
        got = client.get(f"/api/medical-records/{rid}", headers=_auth(regular_user_token)).get_json()["record"]
        assert got["title"] == "Нобивак" and got["batch"] == "A1"

        body = {"date": iso(-3), "title": "Нобивак DHPPi", "next_due": iso(360), "batch": "A2", "diagnosis": "лишнее"}
        assert (
            client.put(f"/api/medical-records/{rid}", json=body, headers=_auth(regular_user_token)).status_code == 200
        )
        doc = mock_db["medical_records"].find_one({"_id": ObjectId(rid)})
        assert (doc["title"], doc["batch"], doc["kind"]) == ("Нобивак DHPPi", "A2", "vaccination")
        assert doc["diagnosis"] is None  # not a visit: not kept

        assert client.delete(f"/api/medical-records/{rid}", headers=_auth(regular_user_token)).status_code == 200
        assert mock_db["medical_records"].count_documents({}) == 0

    def test_a_treatment_update_still_needs_its_target(self, client, regular_user_token, test_pet):
        rid = _post(client, regular_user_token, test_pet, kind="parasite", title="Дронтал").get_json()["id"]
        response = client.put(
            f"/api/medical-records/{rid}", json={"date": iso(-1), "title": "Дронтал"}, headers=_auth(regular_user_token)
        )
        assert response.status_code == 422


@pytest.mark.health
class TestDocumentsOfARecord:
    def _doc(self, mock_db, pet, title="Сертификат", category="vaccination", expires=None):
        return str(
            mock_db["documents"]
            .insert_one(
                {
                    "pet_id": str(pet["_id"]),
                    "category": category,
                    "title": title,
                    "expires_at": expires,
                    "file_id": "f",
                    "created_at": datetime.now(timezone.utc),
                }
            )
            .inserted_id
        )

    def test_a_record_links_documents_of_its_own_pet(self, client, mock_db, regular_user_token, test_pet):
        doc = self._doc(mock_db, test_pet)
        rid = _post(client, regular_user_token, test_pet, document_ids=[doc, doc]).get_json()["id"]
        got = client.get(f"/api/medical-records/{rid}", headers=_auth(regular_user_token)).get_json()["record"]
        assert got["documents"] == [{"id": doc, "title": "Сертификат"}]
        assert mock_db["medical_records"].find_one({"_id": ObjectId(rid)})["document_ids"] == [doc]  # once

    def test_another_pets_document_is_refused(self, client, mock_db, regular_user_token, test_pet):
        foreign = str(
            mock_db["documents"]
            .insert_one({"pet_id": str(ObjectId()), "title": "Чужой", "category": "other"})
            .inserted_id
        )
        assert _post(client, regular_user_token, test_pet, document_ids=[foreign]).status_code == 422
        assert _post(client, regular_user_token, test_pet, document_ids=[str(ObjectId())]).status_code == 422

    def test_deleting_a_document_takes_it_off_the_record(self, client, mock_db, regular_user_token, test_pet):
        doc = self._doc(mock_db, test_pet)
        rid = _post(client, regular_user_token, test_pet, document_ids=[doc]).get_json()["id"]
        assert client.delete(f"/api/documents/{doc}", headers=_auth(regular_user_token)).status_code == 200
        assert mock_db["medical_records"].find_one({"_id": ObjectId(rid)})["document_ids"] == []

    def test_a_certificate_that_became_a_record_is_not_shown_twice(self, client, mock_db, regular_user_token, test_pet):
        linked = self._doc(mock_db, test_pet, title="Привязанный", expires=iso(100))
        self._doc(mock_db, test_pet, title="Одинокий", expires=iso(100))
        _post(client, regular_user_token, test_pet, title="Запись", document_ids=[linked])
        card = client.get(f"/api/pets/{test_pet['_id']}/medical-card", headers=_auth(regular_user_token)).get_json()[
            "card"
        ]
        assert [v["title"] for v in card["vaccinations"]] == ["Одинокий"]
        assert [r["title"] for r in card["records"]["vaccination"]] == ["Запись"]


@pytest.mark.health
class TestOnTheCard:
    def _card(self, client, token, pet):
        return client.get(f"/api/pets/{pet['_id']}/medical-card", headers=_auth(token)).get_json()["card"]

    def test_records_come_by_kind_with_counts_and_a_cap(self, client, mock_db, regular_user_token, test_pet):
        for i in range(12):
            _post(client, regular_user_token, test_pet, kind="visit", title=f"Визит {i:02d}", date=iso(-i - 1))
        _post(client, regular_user_token, test_pet, kind="procedure", title="Чистка зубов")
        card = self._card(client, regular_user_token, test_pet)
        assert set(card["records"]) == {"vaccination", "parasite", "visit", "procedure"}
        assert len(card["records"]["visit"]) == 10 and card["record_counts"]["visit"] == 12
        assert card["records"]["visit"][0]["title"] == "Визит 00"  # the newest
        assert card["record_counts"] == {"vaccination": 0, "parasite": 0, "visit": 12, "procedure": 1}

    def test_the_card_shows_the_status_and_the_replacement(self, client, regular_user_token, test_pet):
        _post(client, regular_user_token, test_pet, title="Бешенство", date=iso(-400), next_due=iso(-30))
        _post(client, regular_user_token, test_pet, title="Бешенство", date=iso(-5), next_due=iso(360))
        rows = self._card(client, regular_user_token, test_pet)["records"]["vaccination"]
        assert [(r["status"], r["superseded"]) for r in rows] == [("ok", False), ("none", True)]

    def test_an_empty_card_has_empty_kinds(self, client, regular_user_token, test_pet):
        card = self._card(client, regular_user_token, test_pet)
        assert card["records"] == {"vaccination": [], "parasite": [], "visit": [], "procedure": []}


@pytest.mark.health
class TestWhoAndCleanup:
    def test_a_member_may_add_edit_and_delete(self, client, mock_db, regular_user_token, test_pet):
        mock_db["users"].insert_one({"username": "friend", "is_active": True, "password_hash": "x"})
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["friend"]}})
        token = create_access_token("friend")
        rid = _post(client, token, test_pet).get_json()["id"]
        body = {"date": iso(-1), "title": "Поправка"}
        assert (
            client.put(f"/api/medical-records/{rid}", json=body, headers=_auth(regular_user_token)).status_code == 200
        )
        assert client.delete(f"/api/medical-records/{rid}", headers=_auth(token)).status_code == 200

    def test_a_stranger_reaches_nothing(self, client, mock_db, regular_user_token, test_pet):
        rid = _post(client, regular_user_token, test_pet).get_json()["id"]
        mock_db["users"].insert_one({"username": "stranger", "is_active": True, "password_hash": "x"})
        token = create_access_token("stranger")
        assert _post(client, token, test_pet).status_code in (403, 404)
        assert client.get(f"/api/medical-records?pet_id={test_pet['_id']}", headers=_auth(token)).status_code in (
            403,
            404,
        )
        for method in ("get", "delete"):
            assert getattr(client, method)(f"/api/medical-records/{rid}", headers=_auth(token)).status_code in (
                403,
                404,
            )
        assert client.put(
            f"/api/medical-records/{rid}", json={"date": iso(-1), "title": "x"}, headers=_auth(token)
        ).status_code in (403, 404)
        assert mock_db["medical_records"].count_documents({}) == 1

    def test_no_login_no_records(self, client, test_pet):
        assert client.get(f"/api/medical-records?pet_id={test_pet['_id']}").status_code == 401
        body = {"pet_id": str(test_pet["_id"]), "kind": "visit", "date": iso(-1), "title": "Осмотр"}
        assert client.post("/api/medical-records", json=body).status_code == 401

    def test_deleting_the_pet_deletes_its_records(self, client, mock_db, regular_user_token, test_pet):
        _post(client, regular_user_token, test_pet)
        assert client.delete(f"/api/pets/{test_pet['_id']}", headers=_auth(regular_user_token)).status_code == 200
        assert mock_db["medical_records"].count_documents({}) == 0

    def test_an_author_is_blanked_when_their_account_goes(self, mock_db):
        from web import account_deletion

        assert "medical_records" in account_deletion.AUTHORED_COLLECTIONS


@pytest.mark.health
class TestRecordsInThePdf:
    def _text(self, client, token, pet):
        import io

        from pypdf import PdfReader

        response = client.get(f"/api/pets/{pet['_id']}/medical-card/pdf", headers=_auth(token))
        assert response.status_code == 200
        return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages)

    def test_every_kind_is_in_the_pdf_with_its_details(self, client, mock_db, regular_user_token, test_pet):
        _post(
            client,
            regular_user_token,
            test_pet,
            title="Рабизин",
            date=iso(-10),
            next_due=iso(-1),
            batch="B-77",
            clinic="Друг",
            vet="Иванова",
        )
        _post(client, regular_user_token, test_pet, kind="parasite", title="Дронтал", target="worms", next_due=iso(3))
        _post(
            client,
            regular_user_token,
            test_pet,
            kind="visit",
            title="Осмотр",
            diagnosis="Гастрит",
            recommendations="Диета",
        )
        _post(client, regular_user_token, test_pet, kind="procedure", title="Чистка зубов", note="без осложнений")
        text = " ".join(self._text(client, regular_user_token, test_pet).split())
        for needle in (
            "Рабизин (серия B-77)",
            "Дронтал",
            "От глистов",
            "Визит к врачу",
            "Диагноз: Гастрит",
            "Рекомендации: Диета",
            "Операция или процедура",
            "Чистка зубов",
            "Заметка: без осложнений",
            "врач Иванова",
            "Просрочено",
            "Скоро",
        ):
            assert needle in text, needle

    def test_a_replaced_record_carries_no_status(self, client, mock_db, regular_user_token, test_pet):
        _post(client, regular_user_token, test_pet, title="Рабизин", date=iso(-400), next_due=iso(-35))
        _post(client, regular_user_token, test_pet, title="Рабизин", date=iso(-5), next_due=iso(360))
        text = self._text(client, regular_user_token, test_pet)
        assert "Просрочено" not in text and "Следующая" in text
