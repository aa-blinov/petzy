"""Tests for timeline endpoint."""

import pytest
from datetime import datetime, timezone, timedelta
from bson import ObjectId


@pytest.mark.health
class TestTimeline:
    """Test timeline endpoint."""

    def test_get_timeline_requires_authentication(self, client):
        """Test that getting timeline requires authentication."""
        response = client.get("/api/history/timeline?pet_id=" + str(ObjectId()))
        assert response.status_code == 401

    def test_get_timeline_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting timeline records."""
        pet_id = str(test_pet["_id"])
        
        # Create some records
        mock_db["weights"].insert_one({
            "pet_id": pet_id,
            "date": datetime.now(timezone.utc) - timedelta(hours=1),
            "weight": 5.0,
            "username": "testuser"
        })
        mock_db["asthma_attacks"].insert_one({
            "pet_id": pet_id,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
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

    def test_get_timeline_filtering(self, client, mock_db, regular_user_token, test_pet):
        """Test getting timeline records with type filtering."""
        pet_id = str(test_pet["_id"])
        
        # Create different type records
        mock_db["weights"].insert_one({
            "pet_id": pet_id,
            "date": datetime.now(timezone.utc) - timedelta(hours=1),
            "weight": 5.0,
            "username": "testuser"
        })
        mock_db["asthma_attacks"].insert_one({
            "pet_id": pet_id,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })
        
        # Filter by weight only
        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&type=weight",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["items"][0]["record_type"] == "weight"

    def test_get_timeline_pagination(self, client, mock_db, regular_user_token, test_pet):
        """Test timeline pagination."""
        pet_id = str(test_pet["_id"])
        
        # Create 5 records
        for i in range(5):
            mock_db["asthma_attacks"].insert_one({
                "pet_id": pet_id,
                "date_time": datetime.now(timezone.utc) - timedelta(minutes=i),
                "username": "testuser"
            })
            
        # Get page 1 with page_size 2
        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&page=1&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["total"] == 5
        # In the real code, frontend calculates hasMore as: page * page_size < total
        assert data["page"] * data["page_size"] < data["total"]
        
        # Get page 3
        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&page=3&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["page"] == 3
        # No more pages: 3 * 2 >= 5
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
