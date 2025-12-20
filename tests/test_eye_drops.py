"""Tests for eye drops health record endpoints."""

from datetime import datetime, timezone


def test_add_eye_drops_success(client, mock_db, admin_token, admin_pet):
    """Test successful creation of eye drops record."""
    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/eye_drops",
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
        f"/api/eye_drops?pet_id={admin_pet['_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "eye_drops" in data
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert len(data["eye_drops"]) == 1
    assert data["eye_drops"][0]["drops_type"] == "Обычные"
    assert data["page"] == 1
    assert data["page_size"] == 100
    assert data["total"] == 1


def test_get_eye_drops_pagination(client, mock_db, admin_token, admin_pet):
    """Test pagination for eye drops records."""
    # Create 6 records
    for i in range(6):
        mock_db["eye_drops"].insert_one(
            {
                "pet_id": str(admin_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "drops_type": "Обычные" if i % 2 == 0 else "Гелевые",
                "username": "admin",
            }
        )

    # Test first page with page_size=3
    response = client.get(
        f"/api/eye_drops?pet_id={admin_pet['_id']}&page=1&page_size=3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "eye_drops" in data
    assert len(data["eye_drops"]) == 3
    assert data["page"] == 1
    assert data["page_size"] == 3
    assert data["total"] == 6

    # Test second page
    response = client.get(
        f"/api/eye_drops?pet_id={admin_pet['_id']}&page=2&page_size=3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["eye_drops"]) == 3
    assert data["page"] == 2
    assert data["page_size"] == 3
    assert data["total"] == 6

    # Test page beyond available data
    response = client.get(
        f"/api/eye_drops?pet_id={admin_pet['_id']}&page=5&page_size=3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["eye_drops"]) == 0
    assert data["page"] == 5
    assert data["page_size"] == 3
    assert data["total"] == 6


def test_get_eye_drops_pagination_different_page_sizes(client, mock_db, admin_token, admin_pet):
    """Test eye drops pagination with different page sizes."""
    # Create 40 records
    for i in range(40):
        mock_db["eye_drops"].insert_one(
            {
                "pet_id": str(admin_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "drops_type": "Обычные" if i % 2 == 0 else "Гелевые",
                "username": "admin",
            }
        )

    # Test page_size=1 → should return 1 record
    response = client.get(
        f"/api/eye_drops?pet_id={admin_pet['_id']}&page=1&page_size=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["eye_drops"]) == 1
    assert data["page_size"] == 1
    assert data["total"] == 40

    # Test page_size=25 → should return 25 records
    response = client.get(
        f"/api/eye_drops?pet_id={admin_pet['_id']}&page=1&page_size=25",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["eye_drops"]) == 25
    assert data["page_size"] == 25
    assert data["total"] == 40

    # Test page_size=40 → should return all 40 records
    response = client.get(
        f"/api/eye_drops?pet_id={admin_pet['_id']}&page=1&page_size=40",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["eye_drops"]) == 40
    assert data["page_size"] == 40
    assert data["total"] == 40


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
        f"/api/eye_drops/{record_id}",
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
        f"/api/eye_drops/{record_id}",
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
        "/api/eye_drops",
        json={
            "date": "2024-01-15",
            "time": "14:30",
            "drops_type": "Обычные",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422
    data = response.get_json()
    # flask-pydantic-spec may return validation errors in different formats
    # Check for either our error format or flask-pydantic-spec format
    assert "error" in data or (isinstance(data, list) and len(data) > 0)
