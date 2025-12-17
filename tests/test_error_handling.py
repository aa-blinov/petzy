"""Tests for error handling and edge cases."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from flask_limiter.errors import RateLimitExceeded


@pytest.mark.error_handling
class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_rate_limit_exceeded_api(self, client, mock_db):
        """Test rate limit exceeded for API requests."""
        from web.app import app, limiter

        # Make multiple login attempts to trigger rate limit
        for _ in range(6):
            client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})

        # Last request should be rate limited
        response = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})

        assert response.status_code == 429
        data = response.get_json()
        assert "error" in data

    def test_rate_limit_exceeded_html(self, client, mock_db):
        """Test rate limit exceeded for HTML requests."""
        from web.app import app, handle_rate_limit_exceeded
        from unittest.mock import MagicMock, patch

        # Create a mock RateLimitExceeded error
        mock_error = MagicMock()
        mock_error.description = "Too many requests"

        # Mock request to be HTML (not JSON/API)
        with app.test_request_context("/login", method="POST"):
            with patch("web.app.request") as mock_request:
                mock_request.is_json = False
                mock_request.path = "/login"

                response = handle_rate_limit_exceeded(mock_error)

                assert response[1] == 429  # status code
                # Should render login page with error (HTML response)
                assert "login" in str(response[0]).lower() or "error" in str(response[0]).lower()

    def test_update_record_invalid_id_format(self, client, mock_db, regular_user_token, test_pet):
        """Test updating record with invalid ID format."""
        response = client.put(
            "/api/asthma/invalid_id",
            json={"duration": "10 minutes"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_update_record_not_found(self, client, mock_db, regular_user_token, test_pet):
        """Test updating non-existent record."""
        from bson import ObjectId

        fake_id = ObjectId()
        now = datetime.now(timezone.utc)
        response = client.put(
            f"/api/asthma/{fake_id}",
            json={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "duration": "10 minutes",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_update_record_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """Test updating record without pet access."""
        from web.app import db
        from bson import ObjectId

        # Create record for admin's pet
        record_id = db["asthma_attacks"].insert_one(
            {
                "pet_id": str(admin_pet["_id"]),
                "duration": "5 minutes",
                "reason": "Stress",
                "username": "admin",
                "date_time": datetime.now(timezone.utc),
            }
        )

        now = datetime.now(timezone.utc)
        response = client.put(
            f"/api/asthma/{record_id.inserted_id}",
            json={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "duration": "10 minutes",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_create_record_invalid_datetime_format(self, client, mock_db, regular_user_token, test_pet):
        """Test creating record with invalid datetime format."""
        response = client.post(
            "/api/asthma",
            json={
                "pet_id": str(test_pet["_id"]),
                "date": "invalid-date",
                "time": "invalid-time",
                "duration": "5 minutes",
                "reason": "Stress",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_create_record_missing_datetime(self, client, mock_db, regular_user_token, test_pet):
        """Test creating record with missing date/time uses current datetime."""
        response = client.post(
            "/api/asthma",
            json={
                "pet_id": str(test_pet["_id"]),
                "duration": "5 minutes",
                "reason": "Stress",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        # Should succeed and use current datetime
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True

    def test_handle_error_value_error(self, client):
        """Test handle_error with ValueError."""
        from web.app import app, handle_error

        with app.app_context():
            response, status_code = handle_error(ValueError("Invalid input"), "test context", 500)

            assert status_code == 400
            data = response.get_json()
            assert "error" in data
            assert data["error"] == "Invalid input data"

    def test_handle_error_key_error(self, client):
        """Test handle_error with KeyError."""
        from web.app import app, handle_error

        with app.app_context():
            response, status_code = handle_error(KeyError("missing_key"), "test context", 500)

            assert status_code == 400
            data = response.get_json()
            assert "error" in data
            assert data["error"] == "Missing required data"

    def test_handle_error_attribute_error(self, client):
        """Test handle_error with AttributeError."""
        from web.app import app, handle_error

        with app.app_context():
            response, status_code = handle_error(AttributeError("no attribute"), "test context", 500)

            assert status_code == 400
            data = response.get_json()
            assert "error" in data
            assert data["error"] == "Missing required data"

    def test_handle_error_generic_exception(self, client):
        """Test handle_error with generic Exception."""
        from web.app import app, handle_error

        with app.app_context():
            response, status_code = handle_error(Exception("Unexpected error"), "test context", 500)

            assert status_code == 500
            data = response.get_json()
            assert "error" in data
            assert data["error"] == "Internal server error"

    def test_update_pet_exception_handling(self, client, mock_db, regular_user_token, test_pet):
        """Test exception handling in update_pet endpoint."""
        from web.app import db
        from unittest.mock import patch

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
        from unittest.mock import patch

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
        from unittest.mock import patch

        # Add some data
        db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 minutes",
                "reason": "Stress",
                "username": "testuser",
            }
        )

        # Mock collection.find to raise exception
        with patch.object(db["asthma_attacks"], "find", side_effect=Exception("Database error")):
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
        from unittest.mock import patch

        now = datetime.now(timezone.utc)

        # Mock database to raise exception
        with patch.object(db["asthma_attacks"], "insert_one", side_effect=Exception("Database error")):
            response = client.post(
                "/api/asthma",
                json={
                    "pet_id": str(test_pet["_id"]),
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M"),
                    "duration": "5 minutes",
                    "reason": "Stress",
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 500
        data = response.get_json()
        assert "error" in data

