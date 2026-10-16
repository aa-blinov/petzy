"""«Сегодня» is the day of the person's zone, not of UTC.

The clock stands at 00:30 on 16 October in Moscow, which is 21:30 UTC on 15 October. A dose at 23:50 on 15 October
belongs to yesterday and one at 00:10 on 16 October to today. The zone decides the day when it is sent. Without a known
zone, the device's own date (client_date) decides, and without that UTC does, as before.
"""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

MIDNIGHT_IN_MOSCOW = datetime(2026, 10, 15, 21, 30, tzinfo=timezone.utc)
# 07:00 UTC on 16 October is 10:00 on 16 October in Moscow.
MORNING_IN_MOSCOW = datetime(2026, 10, 16, 7, 0, tzinfo=timezone.utc)
MOSCOW = "Europe/Moscow"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def course(mock_db, test_pet):
    """A course every day at 12:00, with two doses: 23:50 on 15 October and 00:10 on 16 October (Moscow clock)."""
    pet_id = str(test_pet["_id"])
    med_id = ObjectId()
    mock_db["medications"].insert_one(
        {
            "_id": med_id,
            "pet_id": pet_id,
            "name": "Габапентин",
            "type": "Таблетка",
            "default_dose": 1.0,
            "is_active": True,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["12:00"]},
            "inventory_enabled": False,
            "created_at": datetime(2026, 9, 1),
        }
    )
    for when in (datetime(2026, 10, 15, 23, 50), datetime(2026, 10, 16, 0, 10)):
        mock_db["medication_intakes"].insert_one(
            {
                "medication_id": str(med_id),
                "pet_id": pet_id,
                "dose_taken": 1.0,
                "date_time": when,
                "username": "testuser",
            }
        )
    return med_id


@pytest.mark.medications
class TestIntakesTodayCountTheZonesDay:
    @pytest.fixture(autouse=True)
    def midnight_in_moscow(self, frozen_clock):
        frozen_clock(MIDNIGHT_IN_MOSCOW)

    def test_the_list_counts_the_day_of_the_named_zone(self, client, regular_user_token, test_pet, course):
        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&tz={MOSCOW}", headers=_auth(regular_user_token)
        )

        assert response.status_code == 200
        assert response.get_json()["medications"][0]["intakes_today"] == 1

    def test_without_a_zone_the_list_counts_the_day_of_utc_as_before(
        self, client, regular_user_token, test_pet, course
    ):
        response = client.get(f"/api/medications?pet_id={test_pet['_id']}", headers=_auth(regular_user_token))

        assert response.get_json()["medications"][0]["intakes_today"] == 2

    def test_the_zone_is_read_before_the_device_date(self, client, regular_user_token, test_pet, course):
        # The device says 15 October, the zone says 16 October: the zone's day is the one counted.
        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2026-10-15&tz={MOSCOW}",
            headers=_auth(regular_user_token),
        )

        assert response.get_json()["medications"][0]["intakes_today"] == 1

    def test_without_a_zone_the_device_date_is_used_as_before(self, client, regular_user_token, test_pet, course):
        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2026-10-15",
            headers=_auth(regular_user_token),
        )

        assert response.get_json()["medications"][0]["intakes_today"] == 2

    def test_the_course_card_counts_the_day_of_the_named_zone(self, client, regular_user_token, course):
        response = client.get(f"/api/medications/{course}?tz={MOSCOW}", headers=_auth(regular_user_token))

        assert response.status_code == 200
        assert response.get_json()["medication"]["intakes_today"] == 1

    def test_without_a_zone_the_course_card_counts_the_day_of_utc_as_before(self, client, regular_user_token, course):
        response = client.get(f"/api/medications/{course}", headers=_auth(regular_user_token))

        assert response.get_json()["medication"]["intakes_today"] == 2


@pytest.mark.medications
class TestTheUpcomingDoseFollowsTheZonesDay:
    @pytest.fixture(autouse=True)
    def midnight_in_moscow(self, frozen_clock):
        frozen_clock(MIDNIGHT_IN_MOSCOW)

    @pytest.fixture
    def late_course(self, mock_db, test_pet):
        """A course at 23:55 every day, nothing marked: last night's dose is still offered for a few hours."""
        mock_db["medications"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "name": "Преднизолон",
                "type": "Таблетка",
                "default_dose": 1.0,
                "is_active": True,
                "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["23:55"]},
                "inventory_enabled": False,
                "created_at": datetime(2026, 9, 1),
            }
        )

    def test_without_the_device_clock_the_zones_clock_sets_the_day(
        self, client, regular_user_token, test_pet, late_course
    ):
        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&tz={MOSCOW}", headers=_auth(regular_user_token)
        )

        first = response.get_json()["doses"][0]
        assert first["date"] == "2026-10-15"
        assert first["carried_over"] is True

    def test_without_a_zone_utc_sets_the_day_and_last_nights_dose_is_not_carried(
        self, client, regular_user_token, test_pet, late_course
    ):
        response = client.get(f"/api/medications/upcoming?pet_id={test_pet['_id']}", headers=_auth(regular_user_token))

        first = response.get_json()["doses"][0]
        assert first["date"] == "2026-10-15"
        assert first["carried_over"] is False


@pytest.mark.datetime
class TestWhatIsTypedIsJudgedOnTheZonesClock:
    @pytest.fixture(autouse=True)
    def morning_in_moscow(self, frozen_clock):
        frozen_clock(MORNING_IN_MOSCOW)

    def test_a_weight_for_tomorrow_morning_is_accepted_in_the_zone(self, client, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])

        response = client.post(
            f"/api/events?pet_id={pet_id}",
            json={
                "pet_id": pet_id,
                "type": "weight",
                "date": "2026-10-17",
                "time": "09:00",
                "fields": {"weight": 5.0},
                "tz": MOSCOW,
            },
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 201, response.get_json()

    def test_a_dose_eight_days_ahead_is_accepted_in_the_zone(self, client, regular_user_token, course):
        response = client.post(
            f"/api/medications/{course}/log",
            json={"date": "2026-10-24", "time": "09:00", "tz": MOSCOW},
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 201, response.get_json()


@pytest.mark.pets
class TestBirthDateOfTodayInTheZone:
    @pytest.fixture(autouse=True)
    def midnight_in_moscow(self, frozen_clock):
        frozen_clock(MIDNIGHT_IN_MOSCOW)

    def test_a_pet_born_today_in_the_zone_is_accepted(self, client, regular_user_token):
        response = client.post(
            "/api/pets",
            json={"name": "Малыш", "birth_date": "2026-10-16", "tz": MOSCOW},
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 201, response.get_json()

    def test_a_birth_date_of_today_in_the_zone_is_accepted_on_update(self, client, regular_user_token, test_pet):
        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            json={"birth_date": "2026-10-16", "tz": MOSCOW},
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 200, response.get_json()
