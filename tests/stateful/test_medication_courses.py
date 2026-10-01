"""A medication course has dates, a purpose and a prescriber, and every reader
of «is it going on?» agrees: the list, the upcoming doses, the push reminders,
the medical card.

Reminder scenario as in test_send_medication_reminders: Tuesday 2024-01-02,
an 08:00 dose, an owner subscribed from UTC+5.
"""

import io
from datetime import date, datetime, timedelta, timezone

import pytest
from bson import ObjectId
from pypdf import PdfReader

from scripts.send_medication_reminders import find_due_medication_reminders
from web.courses import ACTIVE, ENDED, PLANNED, course_covers, course_status

DUE_NOW_UTC = datetime(2024, 1, 2, 3, 0, 30, tzinfo=timezone.utc)  # 08:00:30 at UTC+5, a Tuesday
TODAY = date.today().isoformat()
NEXT_MONTH = (date.today() + timedelta(days=30)).isoformat()


class TestCourseRule:
    def test_a_course_without_dates_is_bounded_by_the_flag_alone(self):
        assert course_covers({}, "2030-01-01") is True
        assert course_status({"is_active": True}, TODAY) == ACTIVE
        assert course_status({"is_active": False}, TODAY) == ENDED
        assert course_status({}, TODAY) == ACTIVE  # an old document with no flag at all

    def test_dates_bound_the_days_inclusively(self):
        med = {"started_on": "2024-01-10", "ended_on": "2024-01-20"}
        assert [course_covers(med, d) for d in ("2024-01-09", "2024-01-10", "2024-01-20", "2024-01-21")] == [
            False,
            True,
            True,
            False,
        ]

    def test_status_follows_the_dates(self):
        med = {"is_active": True, "started_on": "2024-01-10", "ended_on": "2024-01-20"}
        assert course_status(med, "2024-01-05") == PLANNED
        assert course_status(med, "2024-01-20") == ACTIVE  # its last day
        assert course_status(med, "2024-01-21") == ENDED

    def test_switched_off_is_ended_whatever_the_dates(self):
        assert course_status({"is_active": False, "started_on": "2099-01-01"}, TODAY) == ENDED

    def test_a_stored_none_is_no_date(self):
        assert course_covers({"started_on": None, "ended_on": None}, "2024-01-01") is True


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _body(pet, **extra):
    return {
        "pet_id": str(pet["_id"]),
        "name": "Синулокс",
        "type": "Таблетка",
        "default_dose": 1,
        "dose_unit": "таб",
        "schedule": {"days": list(range(7)), "times": ["08:00"]},
        **extra,
    }


@pytest.mark.health
class TestCourseApi:
    def test_create_keeps_the_course_fields(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/medications",
            json=_body(
                test_pet, started_on="2024-01-02", ended_on="2024-01-16", purpose="Цистит", prescribed_by="Др. Иванова"
            ),
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 201
        doc = mock_db["medications"].find_one({"_id": ObjectId(response.get_json()["id"])})
        assert (doc["started_on"], doc["ended_on"], doc["purpose"], doc["prescribed_by"]) == (
            "2024-01-02",
            "2024-01-16",
            "Цистит",
            "Др. Иванова",
        )

    @pytest.mark.parametrize(
        "extra",
        [
            {"started_on": "2024-02-01", "ended_on": "2024-01-01"},
            {"ended_on": "tomorrow"},
            {"started_on": "2024-13-45"},
        ],
    )
    def test_bad_dates_are_refused(self, client, regular_user_token, test_pet, extra):
        response = client.post("/api/medications", json=_body(test_pet, **extra), headers=_auth(regular_user_token))
        assert response.status_code == 422

    def _course(self, client, token, pet, **extra):
        response = client.post("/api/medications", json=_body(pet, **extra), headers=_auth(token))
        return response.get_json()["id"]

    def test_finishing_keeps_the_intakes_and_the_dates(self, client, mock_db, regular_user_token, test_pet):
        med_id = self._course(client, regular_user_token, test_pet, started_on="2024-01-02")
        client.post(
            f"/api/medications/{med_id}/log",
            json={"date": "2024-01-03", "time": "08:00"},
            headers=_auth(regular_user_token),
        )
        response = client.put(
            f"/api/medications/{med_id}",
            json={"is_active": False, "ended_on": "2024-01-10"},
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 200
        doc = mock_db["medications"].find_one({"_id": ObjectId(med_id)})
        assert (doc["is_active"], doc["ended_on"]) == (False, "2024-01-10")
        assert mock_db["medication_intakes"].count_documents({"medication_id": med_id}) == 1

    def test_an_empty_string_clears_a_date_and_text(self, client, mock_db, regular_user_token, test_pet):
        med_id = self._course(client, regular_user_token, test_pet, ended_on="2024-01-10", purpose="Цистит")
        client.put(
            f"/api/medications/{med_id}", json={"ended_on": "", "purpose": ""}, headers=_auth(regular_user_token)
        )
        doc = mock_db["medications"].find_one({"_id": ObjectId(med_id)})
        assert doc["ended_on"] is None and doc["purpose"] == ""

    def test_switching_a_course_back_on_takes_its_end_date_away(self, client, mock_db, regular_user_token, test_pet):
        med_id = self._course(client, regular_user_token, test_pet, ended_on="2024-01-10", is_active=False)
        client.put(f"/api/medications/{med_id}", json={"is_active": True}, headers=_auth(regular_user_token))
        doc = mock_db["medications"].find_one({"_id": ObjectId(med_id)})
        assert doc["is_active"] is True and doc["ended_on"] is None

    def test_switching_on_with_a_new_end_date_keeps_the_new_one(self, client, mock_db, regular_user_token, test_pet):
        med_id = self._course(client, regular_user_token, test_pet, ended_on="2024-01-10", is_active=False)
        client.put(
            f"/api/medications/{med_id}",
            json={"is_active": True, "ended_on": NEXT_MONTH},
            headers=_auth(regular_user_token),
        )
        assert mock_db["medications"].find_one({"_id": ObjectId(med_id)})["ended_on"] == NEXT_MONTH

    def test_the_order_is_checked_against_the_stored_dates(self, client, regular_user_token, test_pet):
        med_id = self._course(client, regular_user_token, test_pet, started_on="2024-01-10")
        response = client.put(
            f"/api/medications/{med_id}", json={"ended_on": "2024-01-01"}, headers=_auth(regular_user_token)
        )
        assert response.status_code == 422

    def test_an_empty_update_is_still_refused(self, client, regular_user_token, test_pet):
        med_id = self._course(client, regular_user_token, test_pet)
        assert client.put(f"/api/medications/{med_id}", json={}, headers=_auth(regular_user_token)).status_code == 422

    def test_the_list_says_where_each_course_stands(self, client, regular_user_token, test_pet):
        self._course(client, regular_user_token, test_pet, name="Идёт")
        self._course(client, regular_user_token, test_pet, name="Позже", started_on="2024-02-01")
        self._course(client, regular_user_token, test_pet, name="Закончился", ended_on="2024-01-05")
        self._course(client, regular_user_token, test_pet, name="Выключен", is_active=False)
        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2024-01-10", headers=_auth(regular_user_token)
        )
        status = {m["name"]: m["course_status"] for m in response.get_json()["medications"]}
        assert status == {"Идёт": "active", "Позже": "planned", "Закончился": "ended", "Выключен": "ended"}

    def test_upcoming_doses_respect_the_dates(self, client, mock_db, regular_user_token, test_pet):
        self._course(client, regular_user_token, test_pet, name="Кончился вчера", ended_on="2024-01-09")
        self._course(client, regular_user_token, test_pet, name="Сегодня последний", ended_on="2024-01-10")
        self._course(client, regular_user_token, test_pet, name="Начнётся завтра", started_on="2024-01-11")
        self._course(client, regular_user_token, test_pet, name="Без дат")
        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime=2024-01-10T07:00:00",
            headers=_auth(regular_user_token),
        )
        doses = response.get_json()["doses"]
        assert sorted(d["name"] for d in doses if d["date"] == "2024-01-10") == ["Без дат", "Сегодня последний"]


def _reminder_pet(mock_db):
    pet_id = ObjectId()
    mock_db.pets.insert_one({"_id": pet_id, "name": "Rex", "owner": "testuser", "shared_with": []})
    mock_db.push_subscriptions.insert_one(
        {
            "username": "testuser",
            "endpoint": "https://push.example/d",
            "keys": {"p256dh": "a", "auth": "b"},
            "timezone": "Etc/GMT-5",
        }
    )
    return pet_id


@pytest.mark.push
class TestCourseReminders:
    def _due(self, mock_db, **course):
        pet_id = _reminder_pet(mock_db)
        mock_db.medications.insert_one(
            {
                "pet_id": str(pet_id),
                "name": "Синулокс",
                "is_active": True,
                "schedule": {"days": [1], "times": ["08:00"]},
                **course,
            }
        )
        return find_due_medication_reminders(mock_db, DUE_NOW_UTC)

    def test_a_running_course_is_reminded(self, mock_db):
        assert len(self._due(mock_db, started_on="2024-01-01", ended_on="2024-01-31")) == 1

    def test_no_dates_no_change(self, mock_db):
        assert len(self._due(mock_db)) == 1

    def test_an_ended_course_is_not(self, mock_db):
        assert self._due(mock_db, ended_on="2024-01-01") == []

    def test_its_last_day_is_still_reminded(self, mock_db):
        assert len(self._due(mock_db, ended_on="2024-01-02")) == 1

    def test_a_course_that_has_not_begun_is_not(self, mock_db):
        assert self._due(mock_db, started_on="2024-01-03") == []


@pytest.mark.health
class TestCoursesOnTheCard:
    def _card(self, client, token, pet):
        return client.get(f"/api/pets/{pet['_id']}/medical-card", headers=_auth(token)).get_json()["card"]

    def test_running_and_finished_courses_are_apart(self, client, mock_db, regular_user_token, test_pet):
        pid = str(test_pet["_id"])
        for name, extra in [
            ("Идёт", {}),
            ("Позже", {"started_on": "2099-01-01"}),
            ("Старый", {"is_active": False, "ended_on": "2024-01-05", "started_on": "2023-12-20"}),
            ("Ещё старее", {"is_active": False, "ended_on": "2023-06-01"}),
        ]:
            mock_db["medications"].insert_one(
                {"pet_id": pid, "name": name, "is_active": True, "schedule": {"days": [0], "times": ["10:00"]}, **extra}
            )
        card = self._card(client, regular_user_token, test_pet)
        assert [(m["name"], m["status"]) for m in card["medications"]] == [("Идёт", "active"), ("Позже", "planned")]
        assert [m["name"] for m in card["past_courses"]] == ["Старый", "Ещё старее"]  # the latest end first

    def test_a_course_with_no_dates_takes_them_from_its_intakes(self, client, mock_db, regular_user_token, test_pet):
        pid = str(test_pet["_id"])
        med_id = str(
            mock_db["medications"]
            .insert_one(
                {
                    "pet_id": pid,
                    "name": "Старый курс",
                    "is_active": False,
                    "schedule": {"days": [0], "times": ["10:00"]},
                }
            )
            .inserted_id
        )
        for day, skipped in [(3, False), (5, False), (8, True), (9, False)]:
            mock_db["medication_intakes"].insert_one(
                {"medication_id": med_id, "pet_id": pid, "date_time": datetime(2024, 1, day, 10, 0), "skipped": skipped}
            )
        course = self._card(client, regular_user_token, test_pet)["past_courses"][0]
        assert (course["started_on"], course["ended_on"]) == ("2024-01-03", "2024-01-09")
        assert (course["given"], course["skipped"]) == (3, 1)

    def test_explicit_dates_win_over_intakes(self, client, mock_db, regular_user_token, test_pet):
        pid = str(test_pet["_id"])
        med_id = str(
            mock_db["medications"]
            .insert_one(
                {
                    "pet_id": pid,
                    "name": "С датами",
                    "is_active": False,
                    "started_on": "2024-01-01",
                    "ended_on": "2024-01-31",
                    "purpose": "Цистит",
                    "prescribed_by": "Др. Иванова",
                    "schedule": {"days": [0], "times": ["10:00"]},
                }
            )
            .inserted_id
        )
        mock_db["medication_intakes"].insert_one(
            {"medication_id": med_id, "pet_id": pid, "date_time": datetime(2024, 1, 15, 10, 0)}
        )
        course = self._card(client, regular_user_token, test_pet)["past_courses"][0]
        assert (course["started_on"], course["ended_on"], course["purpose"], course["prescribed_by"]) == (
            "2024-01-01",
            "2024-01-31",
            "Цистит",
            "Др. Иванова",
        )

    def test_the_pdf_has_the_courses(self, client, mock_db, regular_user_token, test_pet):
        pid = str(test_pet["_id"])
        mock_db["medications"].insert_one(
            {
                "pet_id": pid,
                "name": "Синулокс",
                "is_active": False,
                "started_on": "2024-01-01",
                "ended_on": "2024-01-14",
                "purpose": "Цистит",
                "prescribed_by": "Др. Иванова",
                "schedule": {"days": list(range(7)), "times": ["08:00", "20:00"]},
            }
        )
        response = client.get(f"/api/pets/{test_pet['_id']}/medical-card/pdf", headers=_auth(regular_user_token))
        text = " ".join("\n".join(p.extract_text() for p in PdfReader(io.BytesIO(response.data)).pages).split())
        for needle in (
            "Прошлые курсы",
            "Синулокс",
            "От чего: Цистит",
            "Назначил Др. Иванова",
            "с 01.01.2024 по 14.01.2024",
        ):
            assert needle in text, needle
