"""Tests for tooth brushing health record endpoints."""

from datetime import datetime, timezone


def test_add_tooth_brushing_success(client, mock_db, admin_token, admin_pet):
    """Test successful creation of tooth brushing record."""
    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/tooth_brushing",
        json={
            "pet_id": str(admin_pet["_id"]),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
            "brushing_type": "Марля",
            "comment": "Test tooth brushing",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["success"] is True
    assert data["message"] == "Запись о чистке зубов создана"

    # Verify in database
    record = mock_db["tooth_brushing"].find_one({"pet_id": str(admin_pet["_id"])})
    assert record is not None
    assert record["brushing_type"] == "Марля"
    assert record["comment"] == "Test tooth brushing"


def test_get_tooth_brushing_success(client, mock_db, admin_token, admin_pet):
    """Test successful retrieval of tooth brushing records."""
    # Add record
    mock_db["tooth_brushing"].insert_one(
        {
            "pet_id": str(admin_pet["_id"]),
            "date_time": datetime(2024, 1, 15, 14, 30),
            "brushing_type": "Щетка",
            "username": "admin",
        }
    )

    response = client.get(
        f"/api/tooth_brushing?pet_id={admin_pet['_id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "tooth_brushing" in data
    assert "page" in data
    assert "page_size" in data
    assert "total" in data
    assert len(data["tooth_brushing"]) == 1
    assert data["tooth_brushing"][0]["brushing_type"] == "Щетка"
    assert data["page"] == 1
    assert data["page_size"] == 100
    assert data["total"] == 1


def test_get_tooth_brushing_pagination(client, mock_db, admin_token, admin_pet):
    """Test pagination for tooth brushing records."""
    # Create 6 records
    for i in range(6):
        mock_db["tooth_brushing"].insert_one(
            {
                "pet_id": str(admin_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "brushing_type": "Щетка" if i % 2 == 0 else "Марля",
                "username": "admin",
            }
        )

    # Test first page with page_size=3
    response = client.get(
        f"/api/tooth_brushing?pet_id={admin_pet['_id']}&page=1&page_size=3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "tooth_brushing" in data
    assert len(data["tooth_brushing"]) == 3
    assert data["page"] == 1
    assert data["page_size"] == 3
    assert data["total"] == 6

    # Test second page
    response = client.get(
        f"/api/tooth_brushing?pet_id={admin_pet['_id']}&page=2&page_size=3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["tooth_brushing"]) == 3
    assert data["page"] == 2
    assert data["page_size"] == 3
    assert data["total"] == 6

    # Test page beyond available data
    response = client.get(
        f"/api/tooth_brushing?pet_id={admin_pet['_id']}&page=5&page_size=3",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["tooth_brushing"]) == 0
    assert data["page"] == 5
    assert data["page_size"] == 3
    assert data["total"] == 6


def test_get_tooth_brushing_pagination_different_page_sizes(client, mock_db, admin_token, admin_pet):
    """Test tooth brushing pagination with different page sizes."""
    # Create 40 records
    for i in range(40):
        mock_db["tooth_brushing"].insert_one(
            {
                "pet_id": str(admin_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "brushing_type": "Щетка" if i % 2 == 0 else "Марля",
                "username": "admin",
            }
        )

    # Test page_size=1 → should return 1 record
    response = client.get(
        f"/api/tooth_brushing?pet_id={admin_pet['_id']}&page=1&page_size=1",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["tooth_brushing"]) == 1
    assert data["page_size"] == 1
    assert data["total"] == 40

    # Test page_size=25 → should return 25 records
    response = client.get(
        f"/api/tooth_brushing?pet_id={admin_pet['_id']}&page=1&page_size=25",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["tooth_brushing"]) == 25
    assert data["page_size"] == 25
    assert data["total"] == 40

    # Test page_size=40 → should return all 40 records
    response = client.get(
        f"/api/tooth_brushing?pet_id={admin_pet['_id']}&page=1&page_size=40",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["tooth_brushing"]) == 40
    assert data["page_size"] == 40
    assert data["total"] == 40


def test_update_tooth_brushing_success(client, mock_db, admin_token, admin_pet):
    """Test successful update of tooth brushing record."""
    # Add record
    result = mock_db["tooth_brushing"].insert_one(
        {
            "pet_id": str(admin_pet["_id"]),
            "date_time": datetime(2024, 1, 15, 14, 30),
            "brushing_type": "Щетка",
            "username": "admin",
        }
    )
    record_id = str(result.inserted_id)

    response = client.put(
        f"/api/tooth_brushing/{record_id}",
        json={
            "brushing_type": "Марля",
            "comment": "Updated comment",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Verify in database
    record = mock_db["tooth_brushing"].find_one({"_id": result.inserted_id})
    assert record["brushing_type"] == "Марля"
    assert record["comment"] == "Updated comment"


def test_delete_tooth_brushing_success(client, mock_db, admin_token, admin_pet):
    """Test successful deletion of tooth brushing record."""
    # Add record
    result = mock_db["tooth_brushing"].insert_one(
        {
            "pet_id": str(admin_pet["_id"]),
            "date_time": datetime(2024, 1, 15, 14, 30),
            "brushing_type": "Щетка",
            "username": "admin",
        }
    )
    record_id = str(result.inserted_id)

    response = client.delete(
        f"/api/tooth_brushing/{record_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True

    # Verify in database
    assert mock_db["tooth_brushing"].count_documents({"_id": result.inserted_id}) == 0


def test_tooth_brushing_require_pet_id(client, admin_token):
    """Test that pet_id is required for adding tooth brushing."""
    response = client.post(
        "/api/tooth_brushing",
        json={
            "date": "2024-01-15",
            "time": "14:30",
            "brushing_type": "Щетка",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422
    data = response.get_json()
    # flask-pydantic-spec may return validation errors in different formats
    # Check for either our error format or flask-pydantic-spec format
    assert "error" in data or (isinstance(data, list) and len(data) > 0)

