"""Tests for ear cleaning health record endpoints."""

from datetime import datetime, timezone


def test_add_ear_cleaning_success(client, mock_db, admin_token, admin_pet):
    """Test successful creation of ear cleaning record."""
    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/ear_cleaning",
        json={
            "pet_id": str(admin_pet["_id"]),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "cleaning_type": "Капли",
            "comment": "Test ear cleaning",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "Запись о чистке ушей создана"

    # Verify in database
    record = mock_db["ear_cleaning"].find_one({"pet_id": str(admin_pet["_id"])})
    assert record is not None
    assert record["cleaning_type"] == "Капли"
    assert record["comment"] == "Test ear cleaning"


def test_get_ear_cleaning_success(client, mock_db, admin_token, admin_pet):
    """Test successful retrieval of ear cleaning records."""
    # Add record
    mock_db["ear_cleaning"].insert_one(
        {
            "pet_id": str(admin_pet["_id"]),
            "date_time": datetime(2024, 1, 15, 14, 30),
            "cleaning_type": "Салфетка/Марля",
            "username": "admin",
        }
    )

    response = client.get(
        f"/api/ear_cleaning?pet_id={admin_pet['_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "ear_cleaning" in data
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert len(data["ear_cleaning"]) == 1
    assert data["ear_cleaning"][0]["cleaning_type"] == "Салфетка/Марля"
    assert data["page"] == 1
    assert data["page_size"] == 100
    assert data["total"] == 1


def test_get_ear_cleaning_pagination(client, mock_db, admin_token, admin_pet):
    """Test pagination for ear cleaning records."""
    # Create 6 records
    for i in range(6):
        mock_db["ear_cleaning"].insert_one(
            {
                "pet_id": str(admin_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "cleaning_type": "Салфетка/Марля" if i % 2 == 0 else "Капли",
                "username": "admin",
            }
        )

    # Test first page with page_size=3
    response = client.get(
        f"/api/ear_cleaning?pet_id={admin_pet['_id']}&page=1&page_size=3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "ear_cleaning" in data
    assert len(data["ear_cleaning"]) == 3
    assert data["page"] == 1
    assert data["page_size"] == 3
    assert data["total"] == 6

    # Test second page
    response = client.get(
        f"/api/ear_cleaning?pet_id={admin_pet['_id']}&page=2&page_size=3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["ear_cleaning"]) == 3
    assert data["page"] == 2
    assert data["page_size"] == 3
    assert data["total"] == 6

    # Test page beyond available data
    response = client.get(
        f"/api/ear_cleaning?pet_id={admin_pet['_id']}&page=5&page_size=3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["ear_cleaning"]) == 0
    assert data["page"] == 5
    assert data["page_size"] == 3
    assert data["total"] == 6


def test_get_ear_cleaning_pagination_different_page_sizes(client, mock_db, admin_token, admin_pet):
    """Test ear cleaning pagination with different page sizes."""
    # Create 40 records
    for i in range(40):
        mock_db["ear_cleaning"].insert_one(
            {
                "pet_id": str(admin_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "cleaning_type": "Салфетка/Марля" if i % 2 == 0 else "Капли",
                "username": "admin",
            }
        )

    # Test page_size=1 → should return 1 record
    response = client.get(
        f"/api/ear_cleaning?pet_id={admin_pet['_id']}&page=1&page_size=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["ear_cleaning"]) == 1
    assert data["page_size"] == 1
    assert data["total"] == 40

    # Test page_size=25 → should return 25 records
    response = client.get(
        f"/api/ear_cleaning?pet_id={admin_pet['_id']}&page=1&page_size=25",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["ear_cleaning"]) == 25
    assert data["page_size"] == 25
    assert data["total"] == 40

    # Test page_size=40 → should return all 40 records
    response = client.get(
        f"/api/ear_cleaning?pet_id={admin_pet['_id']}&page=1&page_size=40",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["ear_cleaning"]) == 40
    assert data["page_size"] == 40
    assert data["total"] == 40


def test_update_ear_cleaning_success(client, mock_db, admin_token, admin_pet):
    """Test successful update of ear cleaning record."""
    # Add record
    result = mock_db["ear_cleaning"].insert_one(
        {
            "pet_id": str(admin_pet["_id"]),
            "date_time": datetime(2024, 1, 15, 14, 30),
            "cleaning_type": "Салфетка/Марля",
            "username": "admin",
        }
    )
    record_id = str(result.inserted_id)

    response = client.put(
        f"/api/ear_cleaning/{record_id}",
        json={
            "cleaning_type": "Капли",
            "comment": "Updated comment",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Verify in database
    record = mock_db["ear_cleaning"].find_one({"_id": result.inserted_id})
    assert record["cleaning_type"] == "Капли"
    assert record["comment"] == "Updated comment"


def test_delete_ear_cleaning_success(client, mock_db, admin_token, admin_pet):
    """Test successful deletion of ear cleaning record."""
    # Add record
    result = mock_db["ear_cleaning"].insert_one(
        {
            "pet_id": str(admin_pet["_id"]),
            "date_time": datetime(2024, 1, 15, 14, 30),
            "cleaning_type": "Салфетка/Марля",
            "username": "admin",
        }
    )
    record_id = str(result.inserted_id)

    response = client.delete(
        f"/api/ear_cleaning/{record_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Verify in database
    assert mock_db["ear_cleaning"].count_documents({"_id": result.inserted_id}) == 0


def test_ear_cleaning_require_pet_id(client, admin_token):
    """Test that pet_id is required for adding ear cleaning."""
    response = client.post(
        "/api/ear_cleaning",
        json={
            "date": "2024-01-15",
            "time": "14:30",
            "cleaning_type": "Салфетка/Марля",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422
    data = response.get_json()
    # flask-pydantic-spec may return validation errors in different formats
    # Check for either our error format or flask-pydantic-spec format
    assert "error" in data or (isinstance(data, list) and len(data) > 0)


def test_get_ear_cleaning_invalid_page(client, mock_db, admin_token, admin_pet):
    """Test ear cleaning GET with invalid page parameter."""
    response = client.get(
        f"/api/ear_cleaning?pet_id={admin_pet['_id']}&page=0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


def test_get_ear_cleaning_invalid_page_size(client, mock_db, admin_token, admin_pet):
    """Test ear cleaning GET with invalid page_size parameter."""
    response = client.get(
        f"/api/ear_cleaning?pet_id={admin_pet['_id']}&page_size=0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422

