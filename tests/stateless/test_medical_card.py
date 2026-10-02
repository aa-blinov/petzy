"""The medical card: a read-only page built from the pet's own records, and
the same page as a PDF."""

import io
from datetime import date, datetime, timedelta, timezone

import pytest
from bson import ObjectId
from pypdf import PdfReader

from web.medical_card import EXPIRY_SOON_DAYS, age_text, neutered_text, schedule_text


def _get(client, token, pet, suffix="", query=""):
    return client.get(
        f"/api/pets/{pet['_id']}/medical-card{suffix}{query}", headers={"Authorization": f"Bearer {token}"}
    )


class TestWording:
    @pytest.mark.parametrize(
        "born,expected",
        [
            ("2021-09-01", "5 лет"),
            ("2021-10-15", "4 года"),  # not yet 5 on 2026-09-30
            ("2026-01-10", "8 месяцев"),
            ("2026-08-01", "1 месяц"),
            ("2026-09-20", "1 неделя"),
            ("2026-09-28", "2 дня"),
            ("2031-01-01", None),  # in the future
            ("not a date", None),
            (None, None),
        ],
    )
    def test_age_reads_like_the_pet_card(self, born, expected):
        assert age_text(born, date(2026, 9, 30)) == expected

    def test_schedule_every_day_and_some_days(self):
        assert schedule_text({"days": [0, 1, 2, 3, 4, 5, 6], "times": ["20:00", "08:00"]}) == "Ежедневно в 08:00, 20:00"
        assert schedule_text({"days": [4, 0], "times": ["10:00"]}) == "По пн, пт в 10:00"

    @pytest.mark.parametrize(
        "neutered,gender,expected",
        [
            (True, "male", "кастрирован"),
            (False, "male", "не кастрирован"),
            (True, "female", "стерилизована"),
            (False, "Женский", "не стерилизована"),
            (True, None, "кастрация или стерилизация: да"),
            (False, "", "кастрация или стерилизация: нет"),
            (None, "male", None),
        ],
    )
    def test_neutering_wording_follows_the_gender(self, neutered, gender, expected):
        assert neutered_text(neutered, gender) == expected


@pytest.mark.health
class TestMedicalCardData:
    def test_codes_are_shown_as_words_and_old_text_as_typed(self, client, mock_db, regular_user_token, test_pet):
        def pet(**fields):
            mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": fields})
            return _get(client, regular_user_token, test_pet).get_json()["card"]["pet"]

        assert (pet(species="dog", gender="male")["species"], pet(species="dog", gender="male")["gender"]) == (
            "Собака",
            "Мальчик",
        )
        card = pet(species="Кот", gender="Женский", is_neutered=True)
        assert (card["species"], card["gender"], card["neutered_text"]) == ("Кот", "Девочка", "стерилизована")
        card = pet(species="Аксолотль", gender="")
        assert (card["species"], card["gender"]) == ("Аксолотль", None)

    def test_an_empty_pet_gets_an_honest_empty_card(self, client, mock_db, regular_user_token, test_pet):
        response = _get(client, regular_user_token, test_pet)
        assert response.status_code == 200
        card = response.get_json()["card"]
        assert card["pet"]["name"] == test_pet["name"]
        assert card["weight"] is None
        assert card["medications"] == card["vaccinations"] == card["documents"] == []
        assert card["can_edit"] is True

    def test_it_is_assembled_from_what_the_app_keeps(self, client, mock_db, regular_user_token, test_pet):
        pid = str(test_pet["_id"])
        for day, kg in [(1, 4.0), (8, 4.2), (15, 4.3)]:
            mock_db["events"].insert_one(
                {
                    "pet_id": pid,
                    "type": "weight",
                    "date_time": datetime(2026, 9, day, 9, 0),
                    "fields": {"weight": kg},
                    "username": "u",
                }
            )
        mock_db["medications"].insert_one(
            {
                "pet_id": pid,
                "name": "Габапентин",
                "type": "Таблетка",
                "default_dose": 0.5,
                "dose_unit": "таб",
                "schedule": {"days": list(range(7)), "times": ["08:00", "20:00"]},
                "is_active": True,
            }
        )
        mock_db["medications"].insert_one(
            {"pet_id": pid, "name": "Закончил", "schedule": {"days": [0], "times": ["10:00"]}, "is_active": False}
        )
        mock_db["documents"].insert_one(
            {"pet_id": pid, "category": "lab_result", "title": "Кровь", "created_at": datetime(2026, 9, 10, 12, 0)}
        )
        mock_db["documents"].insert_one(
            {"pet_id": pid, "category": "insurance", "title": "Полис", "created_at": datetime(2026, 9, 11, 12, 0)}
        )

        card = _get(client, regular_user_token, test_pet).get_json()["card"]

        assert card["weight"]["latest"] == {"date": "2026-09-15", "value": 4.3}
        assert [p["value"] for p in card["weight"]["series"]] == [4.0, 4.2, 4.3]  # old to new
        assert [m["name"] for m in card["medications"]] == ["Габапентин"]  # an inactive one is left out
        assert card["medications"][0]["dose_text"] == "0,5 таб"
        assert card["medications"][0]["schedule_text"] == "Ежедневно в 08:00, 20:00"
        assert [d["title"] for d in card["documents"]] == ["Кровь"]  # insurance stays in «Документы»

    def test_vaccination_status_follows_the_expiry_window(self, client, mock_db, regular_user_token, test_pet):
        pid = str(test_pet["_id"])
        today = datetime.now(timezone.utc).date()

        def vaccination(title, days, expires=True):
            doc = {"pet_id": pid, "category": "vaccination", "title": title, "created_at": datetime.now(timezone.utc)}
            if expires:
                doc["expires_at"] = (today + timedelta(days=days)).isoformat()
            mock_db["documents"].insert_one(doc)

        vaccination("Далеко", 200)
        vaccination("Скоро", EXPIRY_SOON_DAYS)
        vaccination("Вчера", -1)
        vaccination("Без срока", 0, expires=False)

        by_title = {
            v["title"]: v for v in _get(client, regular_user_token, test_pet).get_json()["card"]["vaccinations"]
        }
        assert by_title["Далеко"]["status"] == "valid"
        assert by_title["Скоро"]["status"] == "soon"
        assert by_title["Вчера"]["status"] == "expired" and by_title["Вчера"]["days_left"] == -1
        assert by_title["Без срока"]["status"] == "none" and by_title["Без срока"]["days_left"] is None
        order = [v["title"] for v in _get(client, regular_user_token, test_pet).get_json()["card"]["vaccinations"]]
        assert order == ["Далеко", "Скоро", "Вчера", "Без срока"]  # the latest cover first, undated last

    def test_a_shared_user_sees_it_but_cannot_edit(self, client, mock_db, test_pet, regular_user_token):
        from web.security import create_access_token

        mock_db["users"].insert_one({"username": "friend", "is_active": True, "password_hash": "x"})
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["friend"]}})
        response = client.get(
            f"/api/pets/{test_pet['_id']}/medical-card",
            headers={"Authorization": f"Bearer {create_access_token('friend')}"},
        )
        assert response.status_code == 200
        assert response.get_json()["card"]["can_edit"] is False

    def test_a_stranger_gets_not_found(self, client, mock_db, test_pet):
        from web.security import create_access_token

        mock_db["users"].insert_one({"username": "stranger", "is_active": True, "password_hash": "x"})
        token = create_access_token("stranger")
        assert _get(client, token, test_pet).status_code in (403, 404)
        assert _get(client, token, test_pet, "/pdf").status_code in (403, 404)

    def test_no_login_no_card(self, client, test_pet):
        assert client.get(f"/api/pets/{test_pet['_id']}/medical-card").status_code == 401
        assert client.get(f"/api/pets/{ObjectId()}/medical-card/pdf").status_code == 401

    def test_today_follows_the_users_zone(self, client, mock_db, regular_user_token, test_pet):
        # Kiritimati (UTC+14) is a calendar day ahead of Niue (UTC-11) for most of any day.
        ahead = _get(client, regular_user_token, test_pet, query="?tz=Pacific/Kiritimati").get_json()["card"]
        behind = _get(client, regular_user_token, test_pet, query="?tz=Pacific/Niue").get_json()["card"]
        assert ahead["generated_at"] > behind["generated_at"]


@pytest.mark.health
class TestMedicalCardPdf:
    def test_pdf_carries_the_cyrillic_content(self, client, mock_db, regular_user_token, test_pet):
        pid = str(test_pet["_id"])
        mock_db["pets"].update_one(
            {"_id": test_pet["_id"]}, {"$set": {"health_notes": "Аллергия на курицу", "species": "Собака"}}
        )
        mock_db["documents"].insert_one(
            {
                "pet_id": pid,
                "category": "vaccination",
                "title": "Нобивак",
                "expires_at": "2099-01-01",
                "created_at": datetime.now(timezone.utc),
            }
        )
        mock_db["medications"].insert_one(
            {
                "pet_id": pid,
                "name": "Габапентин",
                "default_dose": 1,
                "dose_unit": "таб",
                "schedule": {"days": [0], "times": ["10:00"]},
            }
        )

        response = _get(client, regular_user_token, test_pet, "/pdf")

        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        assert response.data.startswith(b"%PDF")
        assert response.headers["Cache-Control"] == "private, no-store"
        assert "filename*=UTF-8''" in response.headers["Content-Disposition"]
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(response.data)).pages)
        for needle in (
            test_pet["name"],
            "Медицинская карта: ",
            "Аллергия на курицу",
            "Нобивак",
            "Габапентин",
            "По пн в 10:00",
        ):
            assert needle in text, needle

    def test_an_empty_card_still_renders(self, client, mock_db, regular_user_token, test_pet):
        response = _get(client, regular_user_token, test_pet, "/pdf")
        assert response.status_code == 200
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(response.data)).pages)
        assert "Сейчас не принимает." in text and "Замеров нет." in text

    def test_a_long_list_runs_onto_a_second_page(self, client, mock_db, regular_user_token, test_pet):
        pid = str(test_pet["_id"])
        for i in range(60):
            mock_db["medications"].insert_one(
                {
                    "pet_id": pid,
                    "name": f"Лекарство {i}",
                    "default_dose": 1,
                    "schedule": {"days": [0], "times": ["10:00"]},
                }
            )
        reader = PdfReader(io.BytesIO(_get(client, regular_user_token, test_pet, "/pdf").data))
        assert len(reader.pages) >= 2


def _alerts(client, token, pet):
    response = client.get(f"/api/pets/{pet['_id']}/medical-card/alerts", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    return response.get_json()["alerts"]


@pytest.mark.health
class TestMedicalAlerts:
    """The dot on the «Медкарта» tab: the card's own overdue rule, without building the card."""

    @staticmethod
    def _record(mock_db, pet, kind, title, days_ago, due_in):
        today = date.today()
        mock_db["medical_records"].insert_one(
            {
                "pet_id": str(pet["_id"]),
                "kind": kind,
                "title": title,
                "date": (today - timedelta(days=days_ago)).isoformat(),
                "next_due": (today + timedelta(days=due_in)).isoformat(),
                "created_at": datetime.now(timezone.utc),
            }
        )

    def test_nothing_overdue_on_an_empty_card(self, client, mock_db, regular_user_token, test_pet):
        assert _alerts(client, regular_user_token, test_pet) == {
            "vaccination": False,
            "parasite": False,
            "medication": False,
        }

    def test_an_overdue_vaccination_and_an_overdue_treatment_are_told_apart(
        self, client, mock_db, regular_user_token, test_pet
    ):
        self._record(mock_db, test_pet, "vaccination", "Нобивак", 400, -5)
        assert _alerts(client, regular_user_token, test_pet) == {
            "vaccination": True,
            "parasite": False,
            "medication": False,
        }
        self._record(mock_db, test_pet, "parasite", "Бравекто", 100, -2)
        assert _alerts(client, regular_user_token, test_pet) == {
            "vaccination": True,
            "parasite": True,
            "medication": False,
        }

    def test_soon_is_not_overdue(self, client, mock_db, regular_user_token, test_pet):
        self._record(mock_db, test_pet, "vaccination", "Нобивак", 350, 10)
        assert _alerts(client, regular_user_token, test_pet) == {
            "vaccination": False,
            "parasite": False,
            "medication": False,
        }

    def test_a_newer_record_of_the_same_name_ends_the_alarm(self, client, mock_db, regular_user_token, test_pet):
        self._record(mock_db, test_pet, "vaccination", "Нобивак", 400, -5)
        self._record(mock_db, test_pet, "vaccination", "нобивак ", 1, 364)
        assert _alerts(client, regular_user_token, test_pet)["vaccination"] is False

    def test_an_expired_certificate_counts_but_one_that_became_a_record_counts_once(
        self, client, mock_db, regular_user_token, test_pet
    ):
        pid = str(test_pet["_id"])
        doc = mock_db["documents"].insert_one(
            {"pet_id": pid, "category": "vaccination", "title": "Сертификат", "expires_at": "2020-01-01"}
        )
        assert _alerts(client, regular_user_token, test_pet)["vaccination"] is True
        # The certificate is now attached to a record that is not due: the card shows the record, and so does the dot.
        today = date.today()
        mock_db["medical_records"].insert_one(
            {
                "pet_id": pid,
                "kind": "vaccination",
                "title": "Нобивак",
                "date": today.isoformat(),
                "next_due": (today + timedelta(days=300)).isoformat(),
                "document_ids": [str(doc.inserted_id)],
                "created_at": datetime.now(timezone.utc),
            }
        )
        assert _alerts(client, regular_user_token, test_pet)["vaccination"] is False

    def test_it_agrees_with_the_card(self, client, mock_db, regular_user_token, test_pet):
        self._record(mock_db, test_pet, "vaccination", "Нобивак", 400, -5)
        self._record(mock_db, test_pet, "parasite", "Бравекто", 30, 60)
        card = _get(client, regular_user_token, test_pet).get_json()["card"]
        from_card = {
            kind: any(r["status"] == "overdue" and not r["superseded"] for r in card["records"][kind])
            for kind in ("vaccination", "parasite")
        }
        assert {
            k: v for k, v in _alerts(client, regular_user_token, test_pet).items() if k != "medication"
        } == from_card

    def test_a_stranger_and_a_visitor_are_refused(self, client, mock_db, test_pet):
        from web.security import create_access_token

        mock_db["users"].insert_one({"username": "stranger", "is_active": True, "password_hash": "x"})
        response = client.get(
            f"/api/pets/{test_pet['_id']}/medical-card/alerts",
            headers={"Authorization": f"Bearer {create_access_token('stranger')}"},
        )
        assert response.status_code in (403, 404)
        assert client.get(f"/api/pets/{test_pet['_id']}/medical-card/alerts").status_code == 401


@pytest.mark.health
class TestOverdueFromAllRecordsAndRenewedCertificates:
    def _record(self, mock_db, pet, title, days_ago, due_in, kind="vaccination"):
        today = date.today()
        mock_db["medical_records"].insert_one(
            {
                "pet_id": str(pet["_id"]),
                "kind": kind,
                "title": title,
                "date": (today - timedelta(days=days_ago)).isoformat(),
                "next_due": (today + timedelta(days=due_in)).isoformat(),
                "created_at": datetime.now(timezone.utc),
            }
        )

    def test_an_overdue_record_older_than_the_latest_ten_is_still_listed(
        self, client, mock_db, regular_user_token, test_pet
    ):
        self._record(mock_db, test_pet, "Старая", 900, -30)
        for i in range(12):
            self._record(mock_db, test_pet, f"Новая {i}", 5 + i, 300)
        card = _get(client, regular_user_token, test_pet).get_json()["card"]
        assert "Старая" not in [r["title"] for r in card["records"]["vaccination"]]
        assert [r["title"] for r in card["overdue_records"]] == ["Старая"]

    def test_a_superseded_record_is_not_listed_as_overdue(self, client, mock_db, regular_user_token, test_pet):
        self._record(mock_db, test_pet, "Нобивак", 400, -5)
        self._record(mock_db, test_pet, "нобивак", 1, 364)
        assert _get(client, regular_user_token, test_pet).get_json()["card"]["overdue_records"] == []

    def test_a_shot_of_the_same_vaccine_after_the_certificate_renews_it(
        self, client, mock_db, regular_user_token, test_pet
    ):
        mock_db["documents"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "category": "vaccination",
                "title": "Бешенство",
                "expires_at": "2020-01-01",
                "created_at": datetime(2019, 6, 1),
            }
        )
        assert [v["status"] for v in _get(client, regular_user_token, test_pet).get_json()["card"]["vaccinations"]] == [
            "expired"
        ]
        self._record(mock_db, test_pet, " бешенство ", 3, 360)
        assert _get(client, regular_user_token, test_pet).get_json()["card"]["vaccinations"] == []

    def test_a_shot_of_another_vaccine_leaves_the_certificate_alone(
        self, client, mock_db, regular_user_token, test_pet
    ):
        mock_db["documents"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "category": "vaccination",
                "title": "Бешенство",
                "expires_at": "2020-01-01",
                "created_at": datetime(2019, 6, 1),
            }
        )
        self._record(mock_db, test_pet, "Нобивак", 3, 360)
        assert len(_get(client, regular_user_token, test_pet).get_json()["card"]["vaccinations"]) == 1
