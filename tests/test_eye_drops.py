"""Tests for eye drops health record endpoints."""

import pytest
from datetime import datetime, timezone


def test_add_eye_drops_success(client, mock_db, admin_token, admin_pet):
    """Test successful creation of eye drops record."""
    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/eye-drops",
        json={
            "pet_id": str(admin_pet["_id"]),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "drops_type": "Гелевые",
            "comment": "Test eye drops",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "Запись о каплях создана"

    # Verify in database
    record = mock_db["eye_drops"].find_one({"pet_id": str(admin_pet["_id"])})
    assert record is not None
    assert record["drops_type"] == "Гелевые"
    assert record["comment"] == "Test eye drops"


def test_get_eye_drops_success(client, mock_db, admin_token, admin_pet):
    """Test successful retrieval of eye drops records."""
    # Add record
    mock_db["eye_drops"].insert_one(
        {
            "pet_id": str(admin_pet["_id"]),
            "date_time": datetime(2024, 1, 15, 14, 30),
            "drops_type": "Обычные",
            "username": "admin",
        }
    )

    response = client.get(
        f"/api/eye-drops?pet_id={admin_pet['_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "eye-drops" in data
    assert len(data["eye-drops"]) == 1
    assert data["eye-drops"][0]["drops_type"] == "Обычные"


def test_update_eye_drops_success(client, mock_db, admin_token, admin_pet):
    """Test successful update of eye drops record."""
    # Add record
    result = mock_db["eye_drops"].insert_one(
        {
            "pet_id": str(admin_pet["_id"]),
            "date_time": datetime(2024, 1, 15, 14, 30),
            "drops_type": "Обычные",
            "username": "admin",
        }
    )
    record_id = str(result.inserted_id)

    response = client.put(
        f"/api/eye-drops/{record_id}",
        json={
            "drops_type": "Гелевые",
            "comment": "Updated comment",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Verify in database
    record = mock_db["eye_drops"].find_one({"_id": result.inserted_id})
    assert record["drops_type"] == "Гелевые"
    assert record["comment"] == "Updated comment"


def test_delete_eye_drops_success(client, mock_db, admin_token, admin_pet):
    """Test successful deletion of eye drops record."""
    # Add record
    result = mock_db["eye_drops"].insert_one(
        {
            "pet_id": str(admin_pet["_id"]),
            "date_time": datetime(2024, 1, 15, 14, 30),
            "drops_type": "Обычные",
            "username": "admin",
        }
    )
    record_id = str(result.inserted_id)

    response = client.delete(
        f"/api/eye-drops/{record_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Verify in database
    assert mock_db["eye_drops"].count_documents({"_id": result.inserted_id}) == 0


def test_eye_drops_require_pet_id(client, admin_token):
    """Test that pet_id is required for adding eye drops."""
    response = client.post(
        "/api/eye-drops",
        json={
            "date": "2024-01-15",
            "time": "14:30",
            "drops_type": "Обычные",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422
    data = response.get_json()
    assert "error" in data

