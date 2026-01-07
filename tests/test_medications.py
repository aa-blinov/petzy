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

        response = client.patch(
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
        now = datetime.now(timezone.utc)
        
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
            "date_time": datetime.utcnow(), # Use utcnow to match endpoint logic
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
