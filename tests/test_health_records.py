"""Tests for health records endpoints (asthma, defecation, litter, weight, feeding)."""

import pytest
from datetime import datetime, timezone


@pytest.mark.health_records
class TestAsthmaRecords:
    """Test asthma attack records endpoints."""

    def test_create_asthma_requires_authentication(self, client):
        """Test that creating asthma record requires authentication."""
        response = client.post("/api/asthma", json={"pet_id": "123", "duration": "5 minutes"})
        assert response.status_code == 401

    def test_create_asthma_requires_pet_selection(self, client, regular_user_token):
        """Test that creating asthma record requires pet_id."""
        response = client.post(
            "/api/asthma",
            json={"duration": "5 minutes", "reason": "Stress", "inhalation": "Yes"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 400

    def test_create_asthma_success(self, client, mock_db, regular_user_token, test_pet):
        """Test creating an asthma attack record."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        response = client.post(
            "/api/asthma",
            json={
                "pet_id": str(test_pet["_id"]),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": "Yes",
                "comment": "Test attack",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was created in database with correct fields
        from web.app import db
        record = db["asthma_attacks"].find_one({"pet_id": str(test_pet["_id"]), "username": "testuser"})
        assert record is not None
        assert record["duration"] == "5 minutes"
        assert record["reason"] == "Stress"
        assert record["inhalation"] == "Yes"
        assert record["comment"] == "Test attack"
        assert record["pet_id"] == str(test_pet["_id"])
        assert record["username"] == "testuser"
        assert "date_time" in record

    def test_get_asthma_requires_authentication(self, client):
        """Test that getting asthma records requires authentication."""
        response = client.get("/api/asthma?pet_id=123")
        assert response.status_code == 401

    def test_get_asthma_requires_pet_id(self, client, regular_user_token):
        """Test that getting asthma records requires pet_id."""
        response = client.get("/api/asthma", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 400

    def test_get_asthma_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting asthma records."""
        # Create a record first
        mock_db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": "Yes",
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.get(
            f"/api/asthma?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "attacks" in data
        assert len(data["attacks"]) == 1

    def test_update_asthma_requires_authentication(self, client):
        """Test that updating asthma record requires authentication."""
        response = client.put("/api/asthma/123", json={"duration": "10 minutes"})
        assert response.status_code == 401

    def test_update_asthma_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating an asthma record."""
        # Create a record first
        now = datetime.now(timezone.utc)
        record = mock_db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": "Yes",
                "username": "testuser",
                "date_time": now,
            }
        )

        response = client.put(
            f"/api/asthma/{record.inserted_id}",
            json={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "duration": "10 minutes",
                "reason": "Exercise",
                "inhalation": "No",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was updated in database with correct fields
        from web.app import db
        updated_record = db["asthma_attacks"].find_one({"_id": record.inserted_id})
        assert updated_record is not None
        assert updated_record["duration"] == "10 minutes"
        assert updated_record["reason"] == "Exercise"
        assert updated_record["inhalation"] == "No"
        assert updated_record["pet_id"] == str(test_pet["_id"])
        assert updated_record["username"] == "testuser"

    def test_delete_asthma_requires_authentication(self, client):
        """Test that deleting asthma record requires authentication."""
        response = client.delete("/api/asthma/123")
        assert response.status_code == 401

    def test_delete_asthma_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting an asthma record."""
        # Create a record first
        record = mock_db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": "Yes",
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.delete(
            f"/api/asthma/{record.inserted_id}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify record is deleted
        assert mock_db["asthma_attacks"].find_one({"_id": record.inserted_id}) is None


@pytest.mark.health_records
class TestDefecationRecords:
    """Test defecation records endpoints."""

    def test_create_defecation_success(self, client, mock_db, regular_user_token, test_pet):
        """Test creating a defecation record."""
        now = datetime.now(timezone.utc)
        response = client.post(
            "/api/defecation",
            json={
                "pet_id": str(test_pet["_id"]),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "stool_type": "Normal",
                "color": "Brown",
                "food": "Dry food",
                "comment": "Test defecation",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was created in database with correct fields
        from web.app import db
        record = db["defecations"].find_one({"pet_id": str(test_pet["_id"]), "username": "testuser"})
        assert record is not None
        assert record["stool_type"] == "Normal"
        assert record["color"] == "Brown"
        assert record["food"] == "Dry food"
        assert record["comment"] == "Test defecation"
        assert record["pet_id"] == str(test_pet["_id"])
        assert record["username"] == "testuser"
        assert "date_time" in record

    def test_get_defecation_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting defecation records."""
        # Create a record first
        mock_db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "stool_type": "Normal",
                "color": "Brown",
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.get(
            f"/api/defecation?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "defecations" in data
        assert len(data["defecations"]) == 1

    def test_update_defecation_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating a defecation record."""
        # Create a record first
        now = datetime.now(timezone.utc)
        record = mock_db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "stool_type": "Normal",
                "color": "Brown",
                "username": "testuser",
                "date_time": now,
            }
        )

        response = client.put(
            f"/api/defecation/{record.inserted_id}",
            json={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "stool_type": "Diarrhea",
                "color": "Yellow",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was updated in database with correct fields
        from web.app import db
        updated_record = db["defecations"].find_one({"_id": record.inserted_id})
        assert updated_record is not None
        assert updated_record["stool_type"] == "Diarrhea"
        assert updated_record["color"] == "Yellow"
        assert updated_record["pet_id"] == str(test_pet["_id"])
        assert updated_record["username"] == "testuser"

    def test_delete_defecation_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a defecation record."""
        # Create a record first
        record = mock_db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "stool_type": "Normal",
                "color": "Brown",
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.delete(
            f"/api/defecation/{record.inserted_id}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        assert mock_db["defecations"].find_one({"_id": record.inserted_id}) is None


@pytest.mark.health_records
class TestLitterRecords:
    """Test litter change records endpoints."""

    def test_create_litter_success(self, client, mock_db, regular_user_token, test_pet):
        """Test creating a litter change record."""
        now = datetime.now(timezone.utc)
        response = client.post(
            "/api/litter",
            json={
                "pet_id": str(test_pet["_id"]),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "comment": "Changed litter",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was created in database with correct fields
        from web.app import db
        record = db["litter_changes"].find_one({"pet_id": str(test_pet["_id"]), "username": "testuser"})
        assert record is not None
        assert record["comment"] == "Changed litter"
        assert record["pet_id"] == str(test_pet["_id"])
        assert record["username"] == "testuser"
        assert "date_time" in record

    def test_get_litter_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting litter change records."""
        # Create a record first
        mock_db["litter_changes"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.get(
            f"/api/litter?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "litter_changes" in data
        assert len(data["litter_changes"]) == 1

    def test_update_litter_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating a litter change record."""
        # Create a record first
        now = datetime.now(timezone.utc)
        record = mock_db["litter_changes"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "username": "testuser",
                "date_time": now,
            }
        )

        response = client.put(
            f"/api/litter/{record.inserted_id}",
            json={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "comment": "Updated comment",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was updated in database with correct fields
        from web.app import db
        updated_record = db["litter_changes"].find_one({"_id": record.inserted_id})
        assert updated_record is not None
        assert updated_record["comment"] == "Updated comment"
        assert updated_record["pet_id"] == str(test_pet["_id"])
        assert updated_record["username"] == "testuser"

    def test_delete_litter_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a litter change record."""
        # Create a record first
        record = mock_db["litter_changes"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.delete(
            f"/api/litter/{record.inserted_id}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        assert mock_db["litter_changes"].find_one({"_id": record.inserted_id}) is None


@pytest.mark.health_records
class TestWeightRecords:
    """Test weight records endpoints."""

    def test_create_weight_success(self, client, mock_db, regular_user_token, test_pet):
        """Test creating a weight record."""
        now = datetime.now(timezone.utc)
        response = client.post(
            "/api/weight",
            json={
                "pet_id": str(test_pet["_id"]),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "weight": 4.5,
                "food": "Dry food",
                "comment": "Test weight",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was created in database with correct fields
        from web.app import db
        record = db["weights"].find_one({"pet_id": str(test_pet["_id"]), "username": "testuser"})
        assert record is not None
        assert record["weight"] == 4.5
        assert record["food"] == "Dry food"
        assert record["comment"] == "Test weight"
        assert record["pet_id"] == str(test_pet["_id"])
        assert record["username"] == "testuser"
        assert "date_time" in record

    def test_get_weight_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting weight records."""
        # Create a record first
        mock_db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "weight": 4.5,
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.get(
            f"/api/weight?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "weights" in data
        assert len(data["weights"]) == 1

    def test_update_weight_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating a weight record."""
        # Create a record first
        now = datetime.now(timezone.utc)
        record = mock_db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "weight": 4.5,
                "username": "testuser",
                "date_time": now,
            }
        )

        response = client.put(
            f"/api/weight/{record.inserted_id}",
            json={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "weight": 5.0,
                "food": "Wet food",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was updated in database with correct fields
        from web.app import db
        updated_record = db["weights"].find_one({"_id": record.inserted_id})
        assert updated_record is not None
        assert updated_record["weight"] == 5.0
        assert updated_record["food"] == "Wet food"
        assert updated_record["pet_id"] == str(test_pet["_id"])
        assert updated_record["username"] == "testuser"

    def test_delete_weight_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a weight record."""
        # Create a record first
        record = mock_db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "weight": 4.5,
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.delete(
            f"/api/weight/{record.inserted_id}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        assert mock_db["weights"].find_one({"_id": record.inserted_id}) is None


@pytest.mark.health_records
class TestFeedingRecords:
    """Test feeding records endpoints."""

    def test_create_feeding_success(self, client, mock_db, regular_user_token, test_pet):
        """Test creating a feeding record."""
        now = datetime.now(timezone.utc)
        response = client.post(
            "/api/feeding",
            json={
                "pet_id": str(test_pet["_id"]),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "food_weight": 100,
                "comment": "Test feeding",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was created in database with correct fields
        from web.app import db
        record = db["feedings"].find_one({"pet_id": str(test_pet["_id"]), "username": "testuser"})
        assert record is not None
        assert record["food_weight"] == 100
        assert record["comment"] == "Test feeding"
        assert record["pet_id"] == str(test_pet["_id"])
        assert record["username"] == "testuser"
        assert "date_time" in record

    def test_get_feeding_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting feeding records."""
        # Create a record first
        mock_db["feedings"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "food_weight": 100,
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.get(
            f"/api/feeding?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "feedings" in data
        assert len(data["feedings"]) == 1

    def test_update_feeding_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating a feeding record."""
        # Create a record first
        now = datetime.now(timezone.utc)
        record = mock_db["feedings"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "food_weight": 100,
                "username": "testuser",
                "date_time": now,
            }
        )

        response = client.put(
            f"/api/feeding/{record.inserted_id}",
            json={
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "food_weight": 150,
                "comment": "Updated feeding",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "message" in data

        # Verify record was updated in database with correct fields
        from web.app import db
        updated_record = db["feedings"].find_one({"_id": record.inserted_id})
        assert updated_record is not None
        assert updated_record["food_weight"] == 150
        assert updated_record["comment"] == "Updated feeding"
        assert updated_record["pet_id"] == str(test_pet["_id"])
        assert updated_record["username"] == "testuser"

    def test_delete_feeding_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a feeding record."""
        # Create a record first
        record = mock_db["feedings"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "food_weight": 100,
                "username": "testuser",
                "date_time": datetime.now(timezone.utc),
            }
        )

        response = client.delete(
            f"/api/feeding/{record.inserted_id}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        assert mock_db["feedings"].find_one({"_id": record.inserted_id}) is None

