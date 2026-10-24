"""A medication course is stored only as something that can be followed (QA B-10), and the texts around it are Russian and one line (B-20)."""

import pytest
from bson import ObjectId

from web.helpers import parse_datetime
from web.schemas import validate_date_logic


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _body(pet, **extra):
    body = {
        "pet_id": str(pet["_id"]),
        "name": "Дронтал",
        "type": "Таблетка",
        "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
    }
    body.update(extra)
    return body


def _create(client, token, pet, **extra):
    return client.post("/api/medications", json=_body(pet, **extra), headers=_auth(token))


class TestName:
    @pytest.mark.parametrize("name", ["", "   ", "\n\t "])
    def test_an_empty_name_is_refused(self, client, regular_user_token, test_pet, name):
        assert _create(client, regular_user_token, test_pet, name=name).status_code == 422

    def test_the_name_is_one_line(self, client, mock_db, regular_user_token, test_pet):
        response = _create(client, regular_user_token, test_pet, name="  A\nB  C ")
        assert response.status_code == 201, response.get_json()
        assert mock_db["medications"].find_one({"pet_id": str(test_pet["_id"])})["name"] == "A B C"

    def test_an_edit_cannot_blank_or_split_the_name(self, client, mock_db, regular_user_token, test_pet):
        med_id = _create(client, regular_user_token, test_pet).get_json()["id"]
        url = f"/api/medications/{med_id}"
        assert client.put(url, json={"name": "   "}, headers=_auth(regular_user_token)).status_code == 422
        assert client.put(url, json={"name": "X\nY"}, headers=_auth(regular_user_token)).status_code == 200
        assert mock_db["medications"].find_one({"_id": ObjectId(med_id)})["name"] == "X Y"


class TestSchedule:
    @pytest.mark.parametrize("days", [[9], [-1, 3], [7], [10**30], [1.5], ["mon"], [True]], ids=lambda d: repr(d)[:20])
    def test_days_must_be_weekdays_0_to_6(self, client, regular_user_token, test_pet, days):
        response = _create(client, regular_user_token, test_pet, schedule={"days": days, "times": ["08:00"]})
        assert response.status_code == 422

    def test_repeated_days_are_one_day(self, client, mock_db, regular_user_token, test_pet):
        response = _create(
            client, regular_user_token, test_pet, schedule={"days": [3, 1, 3, 1, 1, 1, 1], "times": ["08:00"]}
        )
        assert response.status_code == 201, response.get_json()
        stored = mock_db["medications"].find_one({"pet_id": str(test_pet["_id"])})
        assert stored["schedule"]["days"] == [1, 3]

    def test_too_many_days_are_refused(self, client, regular_user_token, test_pet):
        response = _create(client, regular_user_token, test_pet, schedule={"days": [0] * 20, "times": ["08:00"]})
        assert response.status_code == 422

    def test_times_with_no_day_are_refused_unless_as_needed(self, client, regular_user_token, test_pet):
        empty_days = {"days": [], "times": ["08:00"]}
        assert _create(client, regular_user_token, test_pet, schedule=empty_days).status_code == 422
        assert _create(client, regular_user_token, test_pet, schedule=empty_days, as_needed=True).status_code == 201
        # An as-needed course with nothing scheduled is the old, ordinary one.
        nothing = {"days": [], "times": []}
        assert _create(client, regular_user_token, test_pet, name="Другой", schedule=nothing).status_code == 201

    def test_at_most_24_times_a_day(self, client, regular_user_token, test_pet):
        times = [f"{hour:02d}:00" for hour in range(24)]
        assert _create(client, regular_user_token, test_pet, schedule={"days": [0], "times": times}).status_code == 201
        times = [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 30)]
        assert _create(client, regular_user_token, test_pet, schedule={"days": [0], "times": times}).status_code == 422

    def test_an_edit_is_checked_the_same_way(self, client, regular_user_token, test_pet):
        med_id = _create(client, regular_user_token, test_pet).get_json()["id"]
        response = client.put(
            f"/api/medications/{med_id}",
            json={"schedule": {"days": [9], "times": ["08:00"]}},
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 422


class TestStock:
    def test_the_stock_cannot_exceed_the_package(self, client, regular_user_token, test_pet):
        response = _create(
            client,
            regular_user_token,
            test_pet,
            inventory_enabled=True,
            inventory_total=10,
            inventory_current=11,
        )
        assert response.status_code == 422

    def test_a_stock_within_the_package_is_fine(self, client, regular_user_token, test_pet):
        response = _create(
            client, regular_user_token, test_pet, inventory_enabled=True, inventory_total=10, inventory_current=10
        )
        assert response.status_code == 201

    def test_an_edit_cannot_set_the_stock_above_the_package(self, client, regular_user_token, test_pet):
        med_id = _create(client, regular_user_token, test_pet).get_json()["id"]
        response = client.put(
            f"/api/medications/{med_id}",
            json={"inventory_total": 5, "inventory_current": 6},
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 422


class TestRussianTexts:
    @pytest.mark.parametrize(
        ("days", "text"),
        [
            (1, "на 1 день в будущем"),
            (2, "на 2 дня в будущем"),
            (366, "на 366 дней в будущем"),
            (3650, "на 3650 дней в будущем"),
            (21, "на 21 день в будущем"),
        ],
    )
    def test_the_days_ahead_are_declined(self, days, text):
        with pytest.raises(ValueError, match=text):
            validate_date_logic("2999-01-01", allow_future=True, max_future_days=days)

    def test_no_days_ahead_is_not_zero_days(self):
        with pytest.raises(ValueError) as error:
            parse_datetime("2999-01-01", None, allow_future=False, max_future_days=0)
        assert "0 дн" not in str(error.value) and "(дней)" not in str(error.value)

    def test_the_past_limit_is_declined_too(self):
        with pytest.raises(ValueError, match="на 1 год в прошлом"):
            validate_date_logic("1900-01-01", allow_future=True, max_past_years=1)

    def test_an_unknown_chart_type_is_not_english(self, client, regular_user_token, test_pet):
        response = client.get(
            "/api/stats/health",
            query_string={"pet_id": str(test_pet["_id"]), "type": "nonexistent"},
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 422
        assert "Unsupported" not in response.get_json()["error"]

    def test_an_intake_of_a_missing_course_has_a_russian_name(self, client, mock_db, regular_user_token, test_pet):
        from datetime import datetime

        mock_db["medication_intakes"].insert_one(
            {
                "medication_id": str(ObjectId()),
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2026, 10, 1, 8, 0),
                "dose_taken": 1.0,
                "username": "testuser",
            }
        )
        response = client.get(
            "/api/medications/intakes", query_string={"pet_id": str(test_pet["_id"])}, headers=_auth(regular_user_token)
        )
        assert response.status_code == 200
        assert response.get_json()["intakes"][0]["medication_name"] == "Неизвестный курс"


class TestMedicalRecordTitle:
    def test_a_title_is_one_line(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/medical-records",
            json={
                "pet_id": str(test_pet["_id"]),
                "kind": "visit",
                "date": "2026-10-01",
                "title": " Осмотр\n\nглаз   и ушей ",
            },
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 201, response.get_json()
        assert mock_db["medical_records"].find_one({})["title"] == "Осмотр глаз и ушей"
