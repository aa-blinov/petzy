"""Tests for medication management endpoints."""

import pytest
from datetime import datetime, timezone, timedelta
from bson import ObjectId

@pytest.mark.medications
class TestMedicationManagement:
    """Test medication management endpoints."""

    def test_get_medications_requires_authentication(self, client, test_pet):
        """Test that getting medications requires authentication."""
        response = client.get(f"/api/medications?pet_id={test_pet['_id']}")
        assert response.status_code == 401

    def test_get_medications_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting list of medications for a pet."""
        # Insert a test medication
        medication_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": medication_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Antibiotic",
            "type": "pill",
            "dosage": "1.0",
            "unit": "шт",
            "schedule": {
                "days": [0, 1, 2, 3, 4, 5, 6],
                "times": ["08:00", "20:00"]
            },
            "inventory_enabled": True,
            "inventory_total": 20.0,
            "inventory_current": 10.0,
            "inventory_warning_threshold": 5.0,
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "owner": "testuser"
        })

        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "medications" in data
        assert len(data["medications"]) == 1
        assert data["medications"][0]["name"] == "Antibiotic"

    def test_create_medication_success(self, client, mock_db, regular_user_token, test_pet):
        """Test creating a new medication course."""
        medication_data = {
            "pet_id": str(test_pet["_id"]),
            "name": "Vitamin C",
            "type": "drop",
            "dosage": "5.0",
            "unit": "мл",
            "schedule": {
                "days": [1, 3, 5],
                "times": ["10:00"]
            },
            "inventory_enabled": True,
            "inventory_total": 100.0,
            "inventory_current": 100.0,
            "inventory_warning_threshold": 10.0,
            "is_active": True,
            "comment": "During meal"
        }

        response = client.post(
            "/api/medications",
            json=medication_data,
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["id"] is not None
        
        # Verify in DB
        med = mock_db["medications"].find_one({"_id": ObjectId(data["id"])})
        assert med is not None
        assert med["name"] == "Vitamin C"
        assert med["username"] == "testuser"

    def test_get_medication_by_id_success(self, client, mock_db, regular_user_token, test_pet):
        """Test fetching a single medication by id returns enriched detail."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Detail Med",
            "type": "pill",
            "dosage": "1.0",
            "unit": "шт",
            "schedule": {"days": [0, 3], "times": ["08:00", "20:00"]},
            "inventory_enabled": False,
            "is_active": True,
            "owner": "testuser",
        })

        response = client.get(
            f"/api/medications/{med_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        body = response.get_json()
        assert body["medication"]["_id"] == str(med_id)
        assert body["medication"]["name"] == "Detail Med"
        assert body["medication"]["intakes_today"] == 0
        assert body["medication"]["last_taken_at"] is None

    def test_get_medication_by_id_requires_auth(self, client, mock_db, regular_user_token, test_pet):
        """Anonymous GET /api/medications/<id> must return 401."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "No Auth Med",
            "type": "pill",
            "schedule": {"days": [0], "times": ["08:00"]},
            "inventory_enabled": False,
            "is_active": True,
            "owner": "testuser",
        })

        response = client.get(f"/api/medications/{med_id}")
        assert response.status_code == 401

    def test_get_medication_by_id_not_found(self, client, regular_user_token):
        """GET on a non-existent id returns 404."""
        missing_id = ObjectId()
        response = client.get(
            f"/api/medications/{missing_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 404

    def test_update_medication_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating an existing medication course."""
        # Insert a test medication
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Old Name",
            "type": "pill",
            "dosage": "1.0",
            "unit": "шт",
            "schedule": {"days": [0], "times": ["08:00"]},
            "is_active": True,
            "owner": "testuser"
        })

        update_data = {
            "name": "New Name",
            "dosage": "2.0",
            "is_active": False
        }

        response = client.put(
            f"/api/medications/{med_id}",
            json=update_data,
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        
        # Verify in DB
        med = mock_db["medications"].find_one({"_id": med_id})
        assert med["name"] == "New Name"
        assert med["dosage"] == "2.0"
        assert med["is_active"] is False

    def test_delete_medication_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a medication course."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "To be deleted",
            "owner": "testuser"
        })

        response = client.delete(
            f"/api/medications/{med_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        
        # Verify in DB
        med = mock_db["medications"].find_one({"_id": med_id})
        assert med is None

    def test_log_intake_success(self, client, mock_db, regular_user_token, test_pet):
        """Test logging a medication intake."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Antibiotic",
            "dosage": "1.0",
            "inventory_enabled": True,
            "inventory_current": 10.0,
            "owner": "testuser"
        })

        now = datetime.now(timezone.utc)
        log_data = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "dose_taken": 1.0,
            "comment": "Took it well"
        }

        response = client.post(
            f"/api/medications/{med_id}/log",
            json=log_data,
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 201
        
        # Verify intake record
        intake = mock_db["medication_intakes"].find_one({"medication_id": str(med_id)})
        assert intake is not None
        assert intake["dose_taken"] == 1.0

        # Verify inventory decreased
        med = mock_db["medications"].find_one({"_id": med_id})
        assert med["inventory_current"] == 9.0

    def test_get_upcoming_doses(self, client, mock_db, regular_user_token, test_pet):
        """Test getting upcoming doses for all pets."""
        # Use a fixed day of week for predictability in test
        # Let's say today is Monday (0)

        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Daily Med",
            "type": "pill",
            "schedule": {
                "days": [0, 1, 2, 3, 4, 5, 6], # everyday
                "times": ["23:59"] # late today
            },
            "inventory_enabled": True, # Ensure this is present
            "inventory_current": 10.0,
            "inventory_warning_threshold": 5.0,
            "is_active": True,
            "owner": "testuser"
        })

        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "doses" in data
        # Depending on time of day, it might be today or tomorrow, but it should be there
        assert len(data["doses"]) > 0
        assert data["doses"][0]["name"] == "Daily Med"

    def test_delete_intake_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a medication intake record restores inventory."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Antibiotic",
            "dosage": "1.0",
            "inventory_enabled": True,
            "inventory_current": 9.0,
            "owner": "testuser"
        })

        intake_id = ObjectId()
        mock_db["medication_intakes"].insert_one({
            "_id": intake_id,
            "medication_id": str(med_id),
            "pet_id": str(test_pet["_id"]),
            "dose_taken": 1.0,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })

        response = client.delete(
            f"/api/medications/intakes/{str(intake_id)}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        
        # Verify intake deleted
        intake = mock_db["medication_intakes"].find_one({"_id": intake_id})
        assert intake is None

        # Verify inventory restored
        med = mock_db["medications"].find_one({"_id": med_id})
        assert med["inventory_current"] == 10.0

    def test_get_medications_with_intakes_info(self, client, mock_db, regular_user_token, test_pet):
        """Test getting list of medications includes intakes_today and last_taken_at."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Daily Med",
            "type": "pill",
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["12:00"]},
            "inventory_enabled": False,
            "is_active": True,
            "owner": "testuser",
            "created_at": datetime.now(timezone.utc)
        })

        # Insert an intake for today
        mock_db["medication_intakes"].insert_one({
            "medication_id": str(med_id),
            "pet_id": str(test_pet["_id"]),
            "dose_taken": 1.0,
            "date_time": datetime.now(timezone.utc), # Use UTC to match endpoint logic
            "username": "testuser"
        })

        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["medications"]) == 1
        med = data["medications"][0]
        assert med["intakes_today"] == 1
        assert med["last_taken_at"] is not None

    def test_log_intake_insufficient_inventory(self, client, mock_db, regular_user_token, test_pet):
        """Test that logging intake fails when inventory is insufficient."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Antibiotic",
            "dosage": "1.0",
            "inventory_enabled": True,
            "inventory_current": 0.5,  # Less than dose_taken
            "owner": "testuser"
        })

        now = datetime.now(timezone.utc)
        log_data = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "dose_taken": 1.0,
            "comment": "Trying to take more than available"
        }

        response = client.post(
            f"/api/medications/{med_id}/log",
            json=log_data,
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 422  # validation_error
        data = response.get_json()
        assert "error" in data or "message" in data

    def test_delete_intake_with_inventory_total_limit(self, client, mock_db, regular_user_token, test_pet):
        """Test that deleting intake restores inventory but caps at inventory_total."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Antibiotic",
            "dosage": "1.0",
            "inventory_enabled": True,
            "inventory_current": 9.0,
            "inventory_total": 10.0,  # Set total limit
            "owner": "testuser"
        })

        intake_id = ObjectId()
        mock_db["medication_intakes"].insert_one({
            "_id": intake_id,
            "medication_id": str(med_id),
            "pet_id": str(test_pet["_id"]),
            "dose_taken": 2.0,  # More than would fit in total
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })

        response = client.delete(
            f"/api/medications/intakes/{str(intake_id)}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        
        # Verify intake deleted
        intake = mock_db["medication_intakes"].find_one({"_id": intake_id})
        assert intake is None

        # Verify inventory restored but capped at total (9.0 + 2.0 = 11.0, but capped at 10.0)
        med = mock_db["medications"].find_one({"_id": med_id})
        assert med["inventory_current"] == 10.0

    def test_get_upcoming_doses_excludes_taken(self, client, mock_db, regular_user_token, test_pet):
        """Test that upcoming doses excludes already taken doses today."""
        now = datetime.now(timezone.utc)
        current_day = now.weekday()
        
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Daily Med",
            "type": "pill",
            "schedule": {
                "days": [current_day],  # Today
                "times": ["08:00", "20:00"]
            },
            "inventory_enabled": False,
            "is_active": True,
            "owner": "testuser"
        })

        # Insert an intake for today at 08:00
        today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        mock_db["medication_intakes"].insert_one({
            "medication_id": str(med_id),
            "pet_id": str(test_pet["_id"]),
            "dose_taken": 1.0,
            "date_time": today_start.replace(hour=8, minute=0),
            "username": "testuser"
        })

        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "doses" in data
        # Should only return 20:00, not 08:00 (already taken)
        doses = data["doses"]
        times = [d["time"] for d in doses if d["medication_id"] == str(med_id)]
        assert "08:00" not in times
        assert "20:00" in times

    def test_log_intake_default_dose_success(self, client, mock_db, regular_user_token, test_pet):
        """Test logging a medication intake uses default dose when not provided."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Half pill",
            "default_dose": 0.5,
            "inventory_enabled": True,
            "inventory_current": 10.0,
            "owner": "testuser"
        })

        now = datetime.now(timezone.utc)
        log_data = {
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M")
            # dose_taken is missing
        }

        response = client.post(
            f"/api/medications/{med_id}/log",
            json=log_data,
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 201
        
        # Verify intake record
        intake = mock_db["medication_intakes"].find_one({"medication_id": str(med_id)})
        assert intake is not None
        assert intake["dose_taken"] == 0.5

        # Verify inventory decreased
        med = mock_db["medications"].find_one({"_id": med_id})
        assert med["inventory_current"] == 9.5

    def test_get_medications_timezone_logic(self, client, mock_db, regular_user_token, test_pet):
        """Test that client_date affects 'intakes_today' calculation."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Local Time Med",
            "type": "pill",
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["12:00"]},
            "is_active": True,
            "owner": "testuser",
            "inventory_enabled": False
        })

        # Let's use specific dates.
        fixed_dt = datetime(2024, 1, 1, 12, 0, 0)
        mock_db["medication_intakes"].insert_one({
            "medication_id": str(med_id),
            "pet_id": str(test_pet["_id"]),
            "dose_taken": 1.0,
            "date_time": fixed_dt,
            "username": "testuser"
        })
        
        # Case 1: Client date matches intake date
        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2024-01-01",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert response.status_code == 200
        assert response.get_json()["medications"][0]["intakes_today"] == 1

        # Case 2: Client date is next day
        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=2024-01-02",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert response.get_json()["medications"][0]["intakes_today"] == 0

    def test_get_upcoming_doses_timezone_logic(self, client, mock_db, regular_user_token, test_pet):
        """Test that client_datetime affects upcoming doses logic."""
        # This test ensures we use client time for "current day of week" and "current time".
        
        # Create a med scheduled for Mondays (0).
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Monday Med",
            "schedule": {"days": [0], "times": ["10:00"]},
            "is_active": True,
            "owner": "testuser",
            "inventory_enabled": False
        })
        
        # Case 1: Client time is Monday 09:00. Should see dose at 10:00.
        # 2024-01-01 was a Monday.
        client_dt_mon = "2024-01-01T09:00:00"
        
        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime={client_dt_mon}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["doses"]) == 1
        assert data["doses"][0]["time"] == "10:00"
        # In logic, is_overdue compares now (09:00) with dose_time (Today 10:00). 
        # Since now < dose_time, overdue should be false.
        assert not data["doses"][0]["is_overdue"]

        # Case 2: Client time is Monday 11:00. Dose visible but overdue?
        client_dt_mon_late = "2024-01-01T11:00:00"
        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime={client_dt_mon_late}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        data = response.get_json()
        assert len(data["doses"]) == 1
        assert data["doses"][0]["is_overdue"] is True

        # Case 3: Client time is Tuesday — nothing is scheduled today, so
        # the endpoint looks ahead to the next scheduled day rather than
        # returning an empty list. It used to return nothing at all, which
        # left the "next dose" widget blank for six days out of seven on a
        # once-a-week course.
        client_dt_tue = "2024-01-02T09:00:00"
        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime={client_dt_tue}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        data = response.get_json()
        assert len(data["doses"]) == 1
        assert data["doses"][0]["time"] == "10:00"
        # The Monday after that Tuesday.
        assert data["doses"][0]["date"] == "2024-01-08"
        # A dose that hasn't come round yet is never overdue.
        assert data["doses"][0]["is_overdue"] is False

    def test_delete_medication_deletes_all_intakes(self, client, mock_db, regular_user_token, test_pet):
        """Test that deleting a medication also deletes all related intakes atomically."""
        # Create a medication
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Test Med",
            "owner": "testuser"
        })

        # Create multiple intakes for this medication
        intake_ids = [ObjectId() for _ in range(5)]
        for intake_id in intake_ids:
            mock_db["medication_intakes"].insert_one({
                "_id": intake_id,
                "medication_id": str(med_id),
                "pet_id": str(test_pet["_id"]),
                "dose_taken": 1.0,
                "date_time": datetime.now(timezone.utc),
                "username": "testuser"
            })

        # Verify intakes exist
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(med_id)}) == 5

        # Delete medication
        response = client.delete(
            f"/api/medications/{med_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        
        # Verify medication is deleted
        assert mock_db["medications"].find_one({"_id": med_id}) is None
        
        # Verify all related intakes are deleted
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(med_id)}) == 0
        
        # Verify no intakes were left orphaned
        for intake_id in intake_ids:
            assert mock_db["medication_intakes"].find_one({"_id": intake_id}) is None

    def test_delete_medication_with_no_intakes(self, client, mock_db, regular_user_token, test_pet):
        """Test that deleting a medication with no intakes works correctly."""
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Solo Med",
            "owner": "testuser"
        })

        # Delete medication
        response = client.delete(
            f"/api/medications/{med_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        assert mock_db["medications"].find_one({"_id": med_id}) is None



@pytest.mark.medications
class TestMedicationsListEmptyAndFormatting:

    def test_get_medications_empty_list(self, client, mock_db, regular_user_token, test_pet):
        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.get_json()["medications"] == []

    def _complete_medication(self, pet_id):
        return {
            "pet_id": pet_id, "name": "Med", "type": "pill",
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00"]},
            "inventory_enabled": False, "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }

    def test_get_medications_unparseable_client_date_falls_back_to_utc(
        self, client, mock_db, regular_user_token, test_pet
    ):
        med_id = ObjectId()
        doc = self._complete_medication(str(test_pet["_id"]))
        doc["_id"] = med_id
        mock_db["medications"].insert_one(doc)

        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}&client_date=not-a-date",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.get_json()["medications"][0]["intakes_today"] == 0

    def test_get_medications_no_intakes_has_null_last_taken_at(
        self, client, mock_db, regular_user_token, test_pet
    ):
        med_id = ObjectId()
        doc = self._complete_medication(str(test_pet["_id"]))
        doc["_id"] = med_id
        mock_db["medications"].insert_one(doc)

        response = client.get(
            f"/api/medications?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.get_json()["medications"][0]["last_taken_at"] is None


@pytest.mark.medications
class TestUpdateMedicationValidation:

    def test_update_medication_no_fields_returns_error(self, client, mock_db, regular_user_token, test_pet):
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
        })

        response = client.put(
            f"/api/medications/{med_id}",
            json={},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422


@pytest.mark.medications
class TestDeleteMedicationEdgeCases:

    def test_delete_medication_intake_cleanup_failure_does_not_fail_request(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """Losing the medication's own intake history mid-cleanup
        shouldn't undo the fact that the medication itself is gone —
        matches the same best-effort tolerance already relied on for
        delete_pet's own cascade."""
        import web.app as app
        from unittest.mock import patch

        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
        })

        with patch.object(app.db.medication_intakes, "delete_many", side_effect=RuntimeError("boom")):
            response = client.delete(
                f"/api/medications/{med_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert mock_db["medications"].find_one({"_id": med_id}) is None

    def test_delete_medication_fallback_not_found_when_already_gone(
        self, client, mock_db, regular_user_token, test_pet
    ):
        import web.app as app
        from unittest.mock import patch, MagicMock

        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
        })

        with patch.object(app.db.medications, "delete_one", return_value=MagicMock(deleted_count=0)):
            response = client.delete(
                f"/api/medications/{med_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 404

    def test_delete_medication_via_real_transaction_path(self, client, mock_db, regular_user_token, test_pet):
        """Mirrors delete_pet's real-transaction test: mongomock can't
        take this branch natively, so `session=` support is stubbed
        while the actual deletes run for real against the mock store.
        """
        import web.app as app
        from unittest.mock import patch, MagicMock
        from mongomock.collection import Collection

        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
        })
        mock_db["medication_intakes"].insert_one({
            "medication_id": str(med_id), "pet_id": str(test_pet["_id"]),
            "dose_taken": 1.0, "date_time": datetime.now(timezone.utc), "username": "testuser",
        })

        session_cm = MagicMock()
        session_cm.__enter__.return_value = MagicMock()
        session_cm.__exit__.return_value = False
        txn_cm = MagicMock()
        txn_cm.__enter__.return_value = None
        txn_cm.__exit__.return_value = False
        session_cm.__enter__.return_value.start_transaction.return_value = txn_cm

        real_delete_many = Collection.delete_many
        real_delete_one = Collection.delete_one

        def tolerant_delete_many(self, *args, **kwargs):
            kwargs.pop("session", None)
            return real_delete_many(self, *args, **kwargs)

        def tolerant_delete_one(self, *args, **kwargs):
            kwargs.pop("session", None)
            return real_delete_one(self, *args, **kwargs)

        with patch.object(app.db.client, "start_session", return_value=session_cm), \
             patch.object(Collection, "delete_many", tolerant_delete_many), \
             patch.object(Collection, "delete_one", tolerant_delete_one):
            response = client.delete(
                f"/api/medications/{med_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert mock_db["medications"].find_one({"_id": med_id}) is None
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(med_id)}) == 0


@pytest.mark.medications
class TestLogIntakeValidation:

    def test_log_intake_invalid_datetime_rejected(self, client, mock_db, regular_user_token, test_pet):
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
        })

        response = client.post(
            f"/api/medications/{med_id}/log",
            json={"date": "not-a-date", "time": "25:99", "dose_taken": 1.0},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422


@pytest.mark.medications
class TestGetMedicationIntakes:
    """GET /api/medications/intakes had zero coverage before this class —
    not a single test called it."""

    def test_requires_authentication(self, client, test_pet):
        response = client.get(f"/api/medications/intakes?pet_id={test_pet['_id']}")
        assert response.status_code == 401

    def test_empty_list(self, client, mock_db, regular_user_token, test_pet):
        response = client.get(
            f"/api/medications/intakes?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["intakes"] == []
        assert data["total"] == 0

    def test_lists_intakes_with_resolved_medication_names_and_pagination(
        self, client, mock_db, regular_user_token, test_pet
    ):
        pet_id = str(test_pet["_id"])
        med_a = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Vitamin C", "owner": "testuser"})
        med_b = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Antibiotic", "owner": "testuser"})
        now = datetime.now(timezone.utc)
        for i in range(3):
            mock_db["medication_intakes"].insert_one({
                "medication_id": str(med_a.inserted_id), "pet_id": pet_id,
                "dose_taken": 1.0, "date_time": now - timedelta(minutes=i), "username": "testuser",
            })
        mock_db["medication_intakes"].insert_one({
            "medication_id": str(med_b.inserted_id), "pet_id": pet_id,
            "dose_taken": 1.0, "date_time": now - timedelta(minutes=10), "username": "testuser",
        })

        response = client.get(
            f"/api/medications/intakes?pet_id={pet_id}&page=1&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 4
        assert len(data["intakes"]) == 2
        assert data["intakes"][0]["medication_name"] == "Vitamin C"

    def test_no_access_to_other_pet(self, client, mock_db, regular_user_token, admin_pet):
        response = client.get(
            f"/api/medications/intakes?pet_id={admin_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 403


@pytest.mark.medications
class TestDeleteIntakeInventoryRestoreEdgeCases:

    def test_restore_stops_when_medication_deleted_mid_retry(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """If the medication vanishes between the initial lookup and the
        retry loop's own re-fetch (a race with a concurrent deletion),
        the restore loop must give up cleanly rather than crash."""
        import web.app as app
        from unittest.mock import patch

        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
            "inventory_enabled": True, "inventory_current": 5.0,
        })
        intake_id = ObjectId()
        mock_db["medication_intakes"].insert_one({
            "_id": intake_id, "medication_id": str(med_id), "pet_id": str(test_pet["_id"]),
            "dose_taken": 1.0, "date_time": datetime.now(timezone.utc), "username": "testuser",
        })

        real_find_one = app.db.medications.find_one
        call_count = {"n": 0}

        def vanishing_find_one(query, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return real_find_one(query, *args, **kwargs)
            return None

        with patch.object(app.db.medications, "find_one", side_effect=vanishing_find_one):
            response = client.delete(
                f"/api/medications/intakes/{intake_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert mock_db["medication_intakes"].find_one({"_id": intake_id}) is None

    def test_restore_stops_when_inventory_disabled_mid_retry(
        self, client, mock_db, regular_user_token, test_pet
    ):
        import web.app as app
        from unittest.mock import patch, MagicMock

        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
            "inventory_enabled": True, "inventory_current": 5.0,
        })
        intake_id = ObjectId()
        mock_db["medication_intakes"].insert_one({
            "_id": intake_id, "medication_id": str(med_id), "pet_id": str(test_pet["_id"]),
            "dose_taken": 1.0, "date_time": datetime.now(timezone.utc), "username": "testuser",
        })

        real_find_one = app.db.medications.find_one
        call_count = {"n": 0}

        def disables_inventory_find_one(query, *args, **kwargs):
            call_count["n"] += 1
            doc = real_find_one(query, *args, **kwargs)
            if call_count["n"] >= 2 and doc:
                doc = dict(doc)
                doc["inventory_current"] = None
            return doc

        with patch.object(app.db.medications, "find_one", side_effect=disables_inventory_find_one), \
             patch.object(app.db.medications, "update_one", return_value=MagicMock(matched_count=0)):
            response = client.delete(
                f"/api/medications/intakes/{intake_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert mock_db["medication_intakes"].find_one({"_id": intake_id}) is None


@pytest.mark.medications
class TestGetMedicationDetailWithIntakeHistory:

    def test_get_medication_by_id_includes_last_taken_at_when_intake_exists(
        self, client, mock_db, regular_user_token, test_pet
    ):
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "type": "pill",
            "schedule": {"days": [0], "times": ["08:00"]}, "inventory_enabled": False,
            "is_active": True, "owner": "testuser",
        })
        intake_time = datetime.now(timezone.utc) - timedelta(hours=2)
        mock_db["medication_intakes"].insert_one({
            "medication_id": str(med_id), "pet_id": str(test_pet["_id"]),
            "dose_taken": 1.0, "date_time": intake_time, "username": "testuser",
        })

        response = client.get(
            f"/api/medications/{med_id}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        assert response.get_json()["medication"]["last_taken_at"] == intake_time.strftime("%Y-%m-%d %H:%M")


@pytest.mark.medications
class TestLogIntakeRetryLoopEdgeCases:

    def test_log_intake_not_found_when_medication_deleted_mid_retry(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """`@require_record_access` already did its own find_one to load
        g.record before this handler runs — that lookup must succeed
        normally. Only the retry loop's OWN re-fetch (its second overall
        call) is the one simulated as racing a concurrent deletion.
        """
        import web.app as app
        from unittest.mock import patch, MagicMock

        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med",
            "inventory_enabled": True, "inventory_current": 9.0, "owner": "testuser",
        })
        now = datetime.now(timezone.utc)

        real_find_one = app.db.medications.find_one
        call_count = {"n": 0}

        def vanishing_find_one(query, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return real_find_one(query, *args, **kwargs)
            return None

        never_matches = MagicMock(matched_count=0)
        with patch.object(app.db.medications, "update_one", return_value=never_matches), \
             patch.object(app.db.medications, "find_one", side_effect=vanishing_find_one):
            response = client.post(
                f"/api/medications/{med_id}/log",
                json={"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M"), "dose_taken": 1.0},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 404

    def test_log_intake_proceeds_when_inventory_disabled_mid_retry(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """A conflicting update whose retry discovers inventory tracking
        was turned off in the meantime should still log the intake —
        there's nothing left to reconcile."""
        import web.app as app
        from unittest.mock import patch, MagicMock

        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med",
            "inventory_enabled": True, "inventory_current": 9.0, "owner": "testuser",
        })
        now = datetime.now(timezone.utc)

        real_find_one = app.db.medications.find_one
        call_count = {"n": 0}

        def disables_inventory_find_one(query, *args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return real_find_one(query, *args, **kwargs)
            doc = real_find_one(query, *args, **kwargs)
            doc = dict(doc)
            doc["inventory_enabled"] = False
            doc["inventory_current"] = None
            return doc

        never_matches = MagicMock(matched_count=0)
        with patch.object(app.db.medications, "update_one", return_value=never_matches), \
             patch.object(app.db.medications, "find_one", side_effect=disables_inventory_find_one):
            response = client.post(
                f"/api/medications/{med_id}/log",
                json={"date": now.strftime("%Y-%m-%d"), "time": now.strftime("%H:%M"), "dose_taken": 1.0},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 201
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(med_id)}) == 1


@pytest.mark.medications
class TestUpcomingDosesEdgeCases:

    def test_no_active_medications_returns_empty_list(self, client, mock_db, regular_user_token, test_pet):
        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.get_json()["doses"] == []

    def test_unparseable_client_datetime_falls_back_to_server_utc(
        self, client, mock_db, regular_user_token, test_pet
    ):
        now = datetime.now(timezone.utc)
        mock_db["medications"].insert_one({
            "pet_id": str(test_pet["_id"]), "name": "Med", "is_active": True,
            "schedule": {"days": [now.weekday()], "times": ["00:01"]},
        })

        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime=garbage",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200

    def test_medication_with_empty_schedule_is_skipped(self, client, mock_db, regular_user_token, test_pet):
        now = datetime.now(timezone.utc)
        mock_db["medications"].insert_one({
            "pet_id": str(test_pet["_id"]), "name": "No Schedule", "is_active": True,
            "schedule": {"days": [], "times": []},
        })

        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime={now.isoformat()}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.get_json()["doses"] == []

    def test_malformed_schedule_time_does_not_crash_overdue_check(
        self, client, mock_db, regular_user_token, test_pet
    ):
        now = datetime.now(timezone.utc)
        mock_db["medications"].insert_one({
            "pet_id": str(test_pet["_id"]), "name": "Bad Time", "is_active": True,
            "schedule": {"days": [now.weekday()], "times": ["not-a-time"]},
        })

        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime={now.isoformat()}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        doses = response.get_json()["doses"]
        assert len(doses) == 1
        assert doses[0]["is_overdue"] is False

    def test_lookahead_skips_medication_with_no_times_on_matching_day(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """Nothing scheduled today or any future day with a non-empty
        times list — even a day match with empty times must be skipped
        rather than crashing the "next dose" lookahead."""
        now = datetime.now(timezone.utc)
        other_day = (now.weekday() + 1) % 7
        mock_db["medications"].insert_one({
            "pet_id": str(test_pet["_id"]), "name": "Empty Times Tomorrow", "is_active": True,
            "schedule": {"days": [other_day], "times": []},
        })

        response = client.get(
            f"/api/medications/upcoming?pet_id={test_pet['_id']}&client_datetime={now.isoformat()}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        assert response.get_json()["doses"] == []


@pytest.mark.medications
class TestGenericExceptionHandling:
    """Each route's outermost `except Exception` is the last line of
    defence against something truly unexpected (a DB driver error, etc.)
    — forcing it via a mock verifies each one actually degrades to a
    clean 500 instead of leaking a stack trace or hanging.
    """

    def test_add_medication_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        import web.app as app
        from unittest.mock import patch
        with patch.object(app.db.medications, "insert_one", side_effect=RuntimeError("boom")):
            response = client.post(
                "/api/medications",
                json={
                    "pet_id": str(test_pet["_id"]), "name": "Med", "type": "pill",
                    "schedule": {"days": [0], "times": ["08:00"]},
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 500

    def test_get_medications_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        import web.app as app
        from unittest.mock import patch
        with patch.object(app.db.medications, "find", side_effect=RuntimeError("boom")):
            response = client.get(
                f"/api/medications?pet_id={test_pet['_id']}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 500

    def test_get_medication_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        import web.app as app
        from unittest.mock import patch
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "type": "pill",
            "schedule": {"days": [0], "times": ["08:00"]}, "inventory_enabled": False,
            "is_active": True, "owner": "testuser",
        })
        with patch.object(app.db.medication_intakes, "find_one", side_effect=RuntimeError("boom")):
            response = client.get(
                f"/api/medications/{med_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 500

    def test_update_medication_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        import web.app as app
        from unittest.mock import patch
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
        })
        with patch.object(app.db.medications, "update_one", side_effect=RuntimeError("boom")):
            response = client.put(
                f"/api/medications/{med_id}",
                json={"name": "New"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 500

    def test_delete_medication_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        """Something other than a transaction-support error escaping the
        outer try (not just the inner transaction/fallback handling)."""
        import web.app as app
        from unittest.mock import patch
        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
        })
        with patch.object(app.db.client, "start_session", side_effect=RuntimeError("boom")):
            response = client.delete(
                f"/api/medications/{med_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 500

    def test_get_medication_intakes_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        import web.app as app
        from unittest.mock import patch
        with patch.object(app.db.medication_intakes, "count_documents", side_effect=RuntimeError("boom")):
            response = client.get(
                f"/api/medications/intakes?pet_id={test_pet['_id']}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 500

    def test_delete_intake_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        import web.app as app
        from unittest.mock import patch
        intake_id = ObjectId()
        mock_db["medication_intakes"].insert_one({
            "_id": intake_id, "pet_id": str(test_pet["_id"]), "medication_id": str(ObjectId()),
            "dose_taken": 1.0, "date_time": datetime.now(timezone.utc), "username": "testuser",
        })
        with patch.object(app.db.medication_intakes, "delete_one", side_effect=RuntimeError("boom")):
            response = client.delete(
                f"/api/medications/intakes/{intake_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 500

    def test_get_upcoming_doses_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        import web.app as app
        from unittest.mock import patch
        with patch.object(app.db.medications, "find", side_effect=RuntimeError("boom")):
            response = client.get(
                f"/api/medications/upcoming?pet_id={test_pet['_id']}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 500

    def test_delete_medication_transaction_not_found_does_not_fall_back(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """Mirrors the same check for delete_pet: a genuine
        MedicationNotFoundDuringDeletion raised inside a (simulated) real
        transaction is an application error, not a "no transaction
        support" signal — it must not be silently retried via fallback.
        """
        import web.app as app
        from unittest.mock import patch, MagicMock
        from mongomock.collection import Collection

        med_id = ObjectId()
        mock_db["medications"].insert_one({
            "_id": med_id, "pet_id": str(test_pet["_id"]), "name": "Med", "owner": "testuser",
        })

        session_cm = MagicMock()
        session_cm.__enter__.return_value = MagicMock()
        session_cm.__exit__.return_value = False
        txn_cm = MagicMock()
        txn_cm.__enter__.return_value = None
        txn_cm.__exit__.return_value = False
        session_cm.__enter__.return_value.start_transaction.return_value = txn_cm

        real_delete_many = Collection.delete_many

        def tolerant_delete_many(self, *args, **kwargs):
            kwargs.pop("session", None)
            return real_delete_many(self, *args, **kwargs)

        def vanished_delete_one(self, *args, **kwargs):
            return MagicMock(deleted_count=0)

        with patch.object(app.db.client, "start_session", return_value=session_cm), \
             patch.object(Collection, "delete_many", tolerant_delete_many), \
             patch.object(Collection, "delete_one", vanished_delete_one):
            response = client.delete(
                f"/api/medications/{med_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 500
