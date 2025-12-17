"""Tests for user management endpoints (admin only)."""

import pytest
from datetime import datetime, timezone
import bcrypt


@pytest.mark.admin
class TestUserManagement:
    """Test user management endpoints."""

    def test_get_users_requires_admin(self, client, regular_user_token):
        """Test that getting users requires admin privileges."""
        response = client.get("/api/users", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_get_users_success(self, client, mock_db, auth_headers):
        """Test getting list of users as admin."""
        # Create a test user
        password_hash = bcrypt.hashpw("test123".encode(), bcrypt.gensalt()).decode()
        from web.app import db

        db["users"].insert_one(
            {
                "username": "testuser2",
                "password_hash": password_hash,
                "full_name": "Test User 2",
                "email": "test2@example.com",
                "created_at": datetime.now(timezone.utc),
                "created_by": "admin",
                "is_active": True,
            }
        )

        response = client.get("/api/users", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert "users" in data
        assert len(data["users"]) >= 2  # admin + testuser2
        assert all("password_hash" not in user for user in data["users"])

    def test_create_user_success(self, client, mock_db, auth_headers):
        """Test creating a new user."""
        response = client.post(
            "/api/users",
            json={
                "username": "newuser",
                "password": "newpass123",
                "full_name": "New User",
                "email": "newuser@example.com",
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["user"]["username"] == "newuser"
        assert "password_hash" not in data["user"]

        # Verify user was created in database
        from web.app import db

        user = db["users"].find_one({"username": "newuser"})
        assert user is not None
        assert user["is_active"] is True

    def test_create_user_duplicate_username(self, client, mock_db, auth_headers, regular_user):
        """Test creating user with duplicate username."""
        response = client.post(
            "/api/users",
            json={"username": regular_user["username"], "password": "password123", "full_name": "Duplicate User"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "уже существует" in data["error"]

    def test_create_user_missing_fields(self, client, auth_headers):
        """Test creating user with missing required fields."""
        response = client.post("/api/users", json={"username": "incomplete"}, headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_get_user_success(self, client, mock_db, auth_headers, regular_user):
        """Test getting a specific user."""
        response = client.get(f"/api/users/{regular_user['username']}", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["user"]["username"] == regular_user["username"]
        assert "password_hash" not in data["user"]

    def test_get_user_not_found(self, client, auth_headers):
        """Test getting non-existent user."""
        response = client.get("/api/users/nonexistent", headers=auth_headers)

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_update_user_success(self, client, mock_db, auth_headers, regular_user):
        """Test updating user information."""
        response = client.put(
            f"/api/users/{regular_user['username']}",
            json={"full_name": "Updated Name", "email": "updated@example.com", "is_active": True},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify update in database
        from web.app import db

        user = db["users"].find_one({"username": regular_user["username"]})
        assert user["full_name"] == "Updated Name"
        assert user["email"] == "updated@example.com"

    def test_update_user_not_found(self, client, auth_headers):
        """Test updating non-existent user."""
        response = client.put("/api/users/nonexistent", json={"full_name": "New Name"}, headers=auth_headers)

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_update_user_no_data(self, client, auth_headers, regular_user):
        """Test updating user with no data."""
        response = client.put(f"/api/users/{regular_user['username']}", json={}, headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_delete_user_success(self, client, mock_db, auth_headers, regular_user):
        """Test deactivating a user."""
        response = client.delete(f"/api/users/{regular_user['username']}", headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify user is deactivated
        from web.app import db

        user = db["users"].find_one({"username": regular_user["username"]})
        assert user["is_active"] is False

    def test_delete_admin_not_allowed(self, client, auth_headers):
        """Test that admin cannot be deactivated."""
        response = client.delete("/api/users/admin", headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "администратора" in data["error"]

    def test_reset_user_password_success(self, client, mock_db, auth_headers, regular_user):
        """Test resetting user password."""
        new_password = "newpassword123"
        response = client.post(
            f"/api/users/{regular_user['username']}/reset-password",
            json={"password": new_password},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify password was changed
        from web.app import db

        user = db["users"].find_one({"username": regular_user["username"]})
        assert bcrypt.checkpw(new_password.encode(), user["password_hash"].encode())

    def test_reset_user_password_missing_password(self, client, auth_headers, regular_user):
        """Test resetting password without providing new password."""
        response = client.post(f"/api/users/{regular_user['username']}/reset-password", json={}, headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_reset_user_password_not_found(self, client, auth_headers):
        """Test resetting password for non-existent user."""
        response = client.post(
            "/api/users/nonexistent/reset-password", json={"password": "newpass"}, headers=auth_headers
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
