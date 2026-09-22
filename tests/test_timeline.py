"""Tests for the timeline endpoint (now backed by `events` + `medication_intakes`)."""

import pytest
from datetime import datetime, timezone, timedelta
from bson import ObjectId


@pytest.mark.health
class TestTimeline:
    """Test timeline endpoint."""

    def test_get_timeline_requires_authentication(self, client):
        response = client.get("/api/history/timeline?pet_id=" + str(ObjectId()))
        assert response.status_code == 401

    def test_get_timeline_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting timeline records."""
        pet_id = str(test_pet["_id"])

        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "weight",
            "date_time": datetime.now(timezone.utc) - timedelta(hours=1),
            "fields": {"weight": 5.0}, "comment": "", "username": "testuser",
        })
        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "asthma",
            "date_time": datetime.now(timezone.utc),
            "fields": {}, "comment": "", "username": "testuser",
        })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "items" in data
        assert len(data["items"]) == 2
        # Check sorting (descending by date)
        assert data["items"][0]["record_type"] == "asthma"
        assert data["items"][1]["record_type"] == "weight"

    def test_get_timeline_includes_medications(self, client, mock_db, regular_user_token, test_pet):
        """Medications aren't part of the events collection but still show up."""
        pet_id = str(test_pet["_id"])
        med = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Vitamin C", "username": "testuser"})
        mock_db["medication_intakes"].insert_one({
            "pet_id": pet_id, "medication_id": str(med.inserted_id),
            "date_time": datetime.now(timezone.utc), "dose_taken": "1", "username": "testuser",
        })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["record_type"] == "medications"
        assert items[0]["medication_name"] == "Vitamin C"

    def test_get_timeline_filtering(self, client, mock_db, regular_user_token, test_pet):
        """Test getting timeline records with type filtering."""
        pet_id = str(test_pet["_id"])

        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "weight",
            "date_time": datetime.now(timezone.utc) - timedelta(hours=1),
            "fields": {"weight": 5.0}, "comment": "", "username": "testuser",
        })
        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "asthma",
            "date_time": datetime.now(timezone.utc),
            "fields": {}, "comment": "", "username": "testuser",
        })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&type=weight",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["record_type"] == "weight"

    def test_get_timeline_filtering_medications_excludes_events(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "weight", "date_time": datetime.now(timezone.utc),
            "fields": {"weight": 5.0}, "comment": "", "username": "testuser",
        })
        med = mock_db["medications"].insert_one({"pet_id": pet_id, "name": "Vitamin C", "username": "testuser"})
        mock_db["medication_intakes"].insert_one({
            "pet_id": pet_id, "medication_id": str(med.inserted_id),
            "date_time": datetime.now(timezone.utc), "dose_taken": "1", "username": "testuser",
        })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&type=medications",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        assert len(items) == 1
        assert items[0]["record_type"] == "medications"

    def test_get_timeline_pagination(self, client, mock_db, regular_user_token, test_pet):
        """Test timeline pagination."""
        pet_id = str(test_pet["_id"])

        for i in range(5):
            mock_db["events"].insert_one({
                "pet_id": pet_id, "type": "asthma",
                "date_time": datetime.now(timezone.utc) - timedelta(minutes=i),
                "fields": {}, "comment": "", "username": "testuser",
            })

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&page=1&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["total"] == 5
        assert data["page"] * data["page_size"] < data["total"]

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&page=3&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["page"] == 3
        assert data["page"] * data["page_size"] >= data["total"]

    def test_get_timeline_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """Test that user cannot see timeline for other's pet."""
        pet_id = str(admin_pet["_id"])

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 403

    def test_get_timeline_invalid_pet_id(self, client, regular_user_token):
        """Test timeline with invalid pet_id format."""
        response = client.get(
            "/api/history/timeline?pet_id=invalid_id",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 422
