"""Medication stock: days it lasts, running low, restocking."""

from datetime import datetime, timezone

import pytest
from bson import ObjectId

from web.medications import stock_status


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _med(**over):
    base = {
        "name": "Габапентин",
        "default_dose": 1.0,
        "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00", "20:00"]},
        "inventory_enabled": True,
        "inventory_current": 12.0,
    }
    return {**base, **over}


class TestStockStatus:
    def test_days_left_follow_the_schedule(self):
        assert stock_status(_med()) == (6.0, False)  # 2 a day

    def test_a_weekly_schedule_lasts_longer(self):
        days, _ = stock_status(_med(schedule={"days": [0], "times": ["08:00"]}, inventory_current=2.0))
        assert days == 14.0

    def test_half_doses(self):
        assert stock_status(_med(default_dose=0.5))[0] == 12.0

    @pytest.mark.parametrize(("current", "low"), [(12.0, False), (7.0, False), (6.0, True), (4.0, True), (0.0, True)])
    def test_low_at_three_days_by_default(self, current, low):
        # Two a day: 7 lasts 3.5 days, 6 exactly 3.
        assert stock_status(_med(inventory_current=current))[1] is low

    def test_the_course_sets_its_own_warning(self):
        assert stock_status(_med(inventory_current=10.0, inventory_warning_days=7))[1] is True

    def test_an_older_course_keeps_its_amount_threshold(self):
        assert stock_status(_med(inventory_current=10.0, inventory_warning_threshold=10))[1] is True
        assert stock_status(_med(inventory_current=4.0, inventory_warning_threshold=2))[1] is False

    def test_untracked_stock(self):
        assert stock_status(_med(inventory_enabled=False)) == (None, False)
        assert stock_status(_med(inventory_current=None)) == (None, False)

    def test_no_schedule_has_no_days_but_still_runs_out(self):
        assert stock_status(_med(schedule={"days": [], "times": []})) == (None, False)
        assert stock_status(_med(schedule={"days": [], "times": []}, inventory_current=0.0)) == (None, True)


@pytest.fixture
def med_id(mock_db, test_pet):
    doc = _med(pet_id=str(test_pet["_id"]), type="Капсула", is_active=True, username="testuser")
    return mock_db["medications"].insert_one(doc).inserted_id


class TestApi:
    def test_the_list_carries_days_left_and_low(self, client, regular_user_token, test_pet, med_id, mock_db):
        mock_db["medications"].update_one({"_id": med_id}, {"$set": {"inventory_current": 3.0}})

        response = client.get(f"/api/medications?pet_id={test_pet['_id']}", headers=_auth(regular_user_token))

        (med,) = response.get_json()["medications"]
        assert med["inventory_days_left"] == 1.5
        assert med["inventory_low"] is True

    def test_restock_adds_to_the_stock(self, client, regular_user_token, med_id, mock_db):
        response = client.post(
            f"/api/medications/{med_id}/restock", json={"amount": 30}, headers=_auth(regular_user_token)
        )

        assert response.status_code == 200
        assert response.get_json()["inventory_current"] == 42.0
        assert mock_db["medications"].find_one({"_id": med_id})["inventory_current"] == 42.0

    def test_restock_starts_tracking_an_untracked_course(self, client, regular_user_token, med_id, mock_db):
        mock_db["medications"].update_one(
            {"_id": med_id}, {"$set": {"inventory_enabled": False, "inventory_current": None}}
        )

        client.post(f"/api/medications/{med_id}/restock", json={"amount": 20}, headers=_auth(regular_user_token))

        med = mock_db["medications"].find_one({"_id": med_id})
        assert med["inventory_enabled"] is True and med["inventory_current"] == 20.0

    @pytest.mark.parametrize("amount", [0, -5])
    def test_restock_needs_a_positive_amount(self, client, regular_user_token, med_id, amount):
        response = client.post(
            f"/api/medications/{med_id}/restock", json={"amount": amount}, headers=_auth(regular_user_token)
        )
        assert response.status_code == 422

    def test_someone_elses_course_cannot_be_restocked(self, client, mock_db, admin_pet, regular_user_token):
        other = mock_db["medications"].insert_one(_med(pet_id=str(admin_pet["_id"]))).inserted_id

        response = client.post(
            f"/api/medications/{other}/restock", json={"amount": 5}, headers=_auth(regular_user_token)
        )

        assert response.status_code in (403, 404)
        assert mock_db["medications"].find_one({"_id": other})["inventory_current"] == 12.0

    def test_an_intake_that_empties_the_stock_says_so(self, client, regular_user_token, med_id, mock_db):
        mock_db["medications"].update_one({"_id": med_id}, {"$set": {"inventory_current": 1.0}})
        now = datetime.now(timezone.utc)

        response = client.post(
            f"/api/medications/{med_id}/log",
            json={"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M"), "dose_taken": 1},
            headers=_auth(regular_user_token),
        )

        assert response.status_code == 201
        assert response.get_json()["ran_out"] is True

    def test_upcoming_doses_warn_when_low(self, client, regular_user_token, test_pet, med_id, mock_db):
        mock_db["medications"].update_one({"_id": med_id}, {"$set": {"inventory_current": 2.0}})

        response = client.get(f"/api/medications/upcoming?pet_id={test_pet['_id']}", headers=_auth(regular_user_token))

        doses = response.get_json()["doses"]
        assert doses and all(d["inventory_warning"] for d in doses)
        assert isinstance(ObjectId(doses[0]["medication_id"]), ObjectId)
