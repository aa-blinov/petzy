"""Tests for error handling and edge cases."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


@pytest.mark.error_handling
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_rate_limit_exceeded_api(self, client, mock_db):
        """Test rate limit exceeded for API requests."""

        # Make multiple login attempts to trigger rate limit
        for _ in range(6):
            client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})

        # Last request should be rate limited
        response = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})

        assert response.status_code == 429
        data = response.get_json()
        assert "error" in data

    def test_rate_limit_exceeded_is_json_even_outside_the_api(self, client, mock_db):
        """There are no HTML pages left to render an error into — a rate
        limit hit anywhere gets the same JSON error as the API."""
        from web.app import app, handle_rate_limit_exceeded

        with app.test_request_context("/anything", method="GET"):
            response, status = handle_rate_limit_exceeded(MagicMock(description="Too many requests"))

        assert status == 429
        assert response.get_json()["code"] == "rate_limit_exceeded"

    def test_update_record_invalid_id_format(self, client, mock_db, regular_user_token, test_pet):
        """Test updating record with invalid ID format."""
        response = client.put(
            "/api/events/invalid_id",
            json={"fields": {"duration": "10 minutes"}},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_update_record_not_found(self, client, mock_db, regular_user_token, test_pet):
        """Test updating non-existent record."""
        from bson import ObjectId

        fake_id = ObjectId()
        now = datetime.now(timezone.utc)
        response = client.put(
            f"/api/events/{fake_id}",
            json={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "fields": {"duration": "10 minutes"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_update_record_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """Test updating record without pet access."""
        from web.app import db

        # Create record for admin's pet
        record_id = db["events"].insert_one(
            {
                "pet_id": str(admin_pet["_id"]),
                "type": "asthma",
                "fields": {"duration": "5 minutes", "reason": "Stress"},
                "username": "admin",
                "date_time": datetime.now(timezone.utc),
            }
        )

        now = datetime.now(timezone.utc)
        response = client.put(
            f"/api/events/{record_id.inserted_id}",
            json={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "fields": {"duration": "10 minutes"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_create_record_invalid_datetime_format(self, client, mock_db, regular_user_token, test_pet):
        """Test creating record with invalid datetime format."""
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "asthma",
                "date": "invalid-date",
                "time": "invalid-time",
                "fields": {"duration": "5 minutes", "reason": "Stress"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_create_record_missing_datetime(self, client, mock_db, regular_user_token, test_pet):
        """Test creating record - date/time are required by schema."""
        # Date and time are required fields in HealthRecordBase schema
        # This test verifies that missing date/time returns validation error
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "asthma",
                "fields": {"duration": "5 minutes", "reason": "Stress"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        # Should fail validation because date and time are required
        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_update_pet_exception_handling(self, client, mock_db, regular_user_token, test_pet):
        """Test exception handling in update_pet endpoint."""
        from web.app import db

        # Mock database to raise exception
        with patch.object(db["pets"], "update_one", side_effect=Exception("Database error")):
            response = client.put(
                f"/api/pets/{test_pet['_id']}",
                json={"name": "Updated Cat"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data

    def test_create_pet_exception_handling(self, client, mock_db, regular_user_token):
        """Test exception handling in create_pet endpoint."""
        from web.app import db

        # Mock database to raise exception
        with patch.object(db["pets"], "insert_one", side_effect=Exception("Database error")):
            response = client.post(
                "/api/pets",
                json={"name": "New Cat", "breed": "Maine Coon", "birth_date": "2021-03-15", "gender": "Male"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data

    def test_export_exception_handling(self, client, mock_db, regular_user_token, test_pet):
        """Test exception handling in export endpoint."""
        from web.app import db

        # Add some data
        db["events"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "type": "asthma",
                "date_time": datetime(2024, 1, 15, 14, 30),
                "fields": {"duration": "5 minutes", "reason": "Stress"},
                "username": "testuser",
            }
        )

        # Mock collection.find to raise exception
        with patch.object(db["events"], "find", side_effect=Exception("Database error")):
            response = client.get(
                f"/api/export/asthma/csv?pet_id={test_pet['_id']}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data

    def test_create_health_record_exception_handling(self, client, mock_db, regular_user_token, test_pet):
        """Test exception handling in health record creation."""
        from web.app import db

        now = datetime.now(timezone.utc)

        # Mock database to raise exception
        with patch.object(db["events"], "insert_one", side_effect=Exception("Database error")):
            response = client.post(
                "/api/events",
                json={
                    "pet_id": str(test_pet["_id"]),
                    "type": "asthma",
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M"),
                    "fields": {"duration": "Короткий", "reason": "Stress", "inhalation": "false"},
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data
