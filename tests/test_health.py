"""Tests for health tracking endpoints."""

import pytest
from datetime import datetime
from bson import ObjectId


@pytest.mark.health
class TestHealthTracking:
    """Test health tracking endpoints."""

    def test_add_asthma_attack_success(self, client, mock_db, regular_user_token, test_pet):
        """Test adding an asthma attack."""
        response = client.post(
            "/api/asthma?pet_id=" + str(test_pet["_id"]),
            json={
                "date": "2024-01-15",
                "time": "14:30",
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": True,
                "comment": "Mild attack",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True

        # Verify record was created
        from web.app import db

        attacks = list(db["asthma_attacks"].find({"pet_id": str(test_pet["_id"])}))
        assert len(attacks) == 1
        assert attacks[0]["duration"] == "5 minutes"
        assert attacks[0]["username"] == "testuser"

    def test_add_asthma_attack_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """Test adding asthma attack without pet access."""
        response = client.post(
            "/api/asthma?pet_id=" + str(admin_pet["_id"]),
            json={"date": "2024-01-15", "time": "14:30"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_add_asthma_attack_invalid_pet_id(self, client, mock_db, regular_user_token):
        """Test adding asthma attack with invalid pet_id format."""
        response = client.post(
            "/api/asthma?pet_id=invalid_id",
            json={"date": "2024-01-15", "time": "14:30"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_get_asthma_attacks_invalid_pet_id(self, client, regular_user_token):
        """Test getting asthma attacks with invalid pet_id format."""
        response = client.get(
            "/api/asthma?pet_id=invalid_id", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_get_asthma_attacks_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting asthma attacks."""
        # Add some attacks
        from web.app import db

        db["asthma_attacks"].insert_many(
            [
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 15, 14, 30),
                    "duration": "5 minutes",
                    "reason": "Stress",
                    "inhalation": True,
                    "comment": "Attack 1",
                },
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 16, 10, 0),
                    "duration": "3 minutes",
                    "reason": "Exercise",
                    "inhalation": False,
                    "comment": "Attack 2",
                },
            ]
        )

        response = client.get(
            f"/api/asthma?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "attacks" in data
        assert "page" in data
        assert "page_size" in data
        assert "total" in data
        assert len(data["attacks"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 100
        assert data["total"] == 2

    def test_update_asthma_attack_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating an asthma attack."""
        # Create an attack
        from web.app import db

        result = db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": True,
                "comment": "Original",
            }
        )
        attack_id = str(result.inserted_id)

        response = client.put(
            f"/api/asthma/{attack_id}",
            json={
                "date": "2024-01-15",
                "time": "15:00",
                "duration": "10 minutes",
                "reason": "Updated reason",
                "inhalation": False,
                "comment": "Updated",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify update
        attack = db["asthma_attacks"].find_one({"_id": ObjectId(attack_id)})
        assert attack["duration"] == "10 minutes"
        assert attack["comment"] == "Updated"

    def test_delete_asthma_attack_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting an asthma attack."""
        # Create an attack
        from web.app import db

        result = db["asthma_attacks"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "duration": "5 minutes",
                "reason": "Stress",
                "inhalation": True,
                "comment": "To delete",
            }
        )
        attack_id = str(result.inserted_id)

        response = client.delete(f"/api/asthma/{attack_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify deletion
        attack = db["asthma_attacks"].find_one({"_id": ObjectId(attack_id)})
        assert attack is None

    def test_add_defecation_success(self, client, mock_db, regular_user_token, test_pet):
        """Test adding a defecation record."""
        response = client.post(
            "/api/defecation?pet_id=" + str(test_pet["_id"]),
            json={
                "date": "2024-01-15",
                "time": "14:30",
                "stool_type": "Normal",
                "color": "Brown",
                "food": "Dry food",
                "comment": "Normal defecation",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True

        # Verify record was created
        from web.app import db

        defecations = list(db["defecations"].find({"pet_id": str(test_pet["_id"])}))
        assert len(defecations) == 1
        assert defecations[0]["username"] == "testuser"

    def test_get_defecations_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting defecation records."""
        # Add some records
        from web.app import db

        db["defecations"].insert_many(
            [
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 15, 14, 30),
                    "stool_type": "Normal",
                    "color": "Brown",
                    "food": "Dry food",
                    "comment": "Record 1",
                }
            ]
        )

        response = client.get(
            f"/api/defecation?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "defecations" in data
        assert "page" in data
        assert "page_size" in data
        assert "total" in data
        assert len(data["defecations"]) == 1
        assert data["page"] == 1
        assert data["page_size"] == 100
        assert data["total"] == 1

    def test_update_defecation_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating a defecation record."""
        from web.app import db

        result = db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "stool_type": "Normal",
                "color": "Brown",
                "food": "Dry food",
                "comment": "Original",
            }
        )
        record_id = str(result.inserted_id)

        response = client.put(
            f"/api/defecation/{record_id}",
            json={
                "date": "2024-01-15",
                "time": "15:00",
                "stool_type": "Loose",
                "color": "Brown",
                "food": "Wet food",
                "comment": "Updated",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_delete_defecation_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a defecation record."""
        from web.app import db

        result = db["defecations"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "stool_type": "Normal",
                "color": "Brown",
                "food": "Dry food",
                "comment": "To delete",
            }
        )
        record_id = str(result.inserted_id)

        response = client.delete(
            f"/api/defecation/{record_id}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_add_litter_change_success(self, client, mock_db, regular_user_token, test_pet):
        """Test adding a litter change record."""
        response = client.post(
            "/api/litter?pet_id=" + str(test_pet["_id"]),
            json={"date": "2024-01-15", "time": "14:30", "comment": "Full change"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True

        # Verify record was created
        from web.app import db

        changes = list(db["litter_changes"].find({"pet_id": str(test_pet["_id"])}))
        assert len(changes) == 1
        assert changes[0]["username"] == "testuser"

    def test_get_litter_changes_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting litter change records."""
        from web.app import db

        db["litter_changes"].insert_one(
            {"pet_id": str(test_pet["_id"]), "date_time": datetime(2024, 1, 15, 14, 30), "comment": "Change 1"}
        )

        response = client.get(
            f"/api/litter?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "litter_changes" in data
        assert "page" in data
        assert "page_size" in data
        assert "total" in data
        assert len(data["litter_changes"]) == 1
        assert data["page"] == 1
        assert data["page_size"] == 100
        assert data["total"] == 1

    def test_update_litter_change_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating a litter change record."""
        from web.app import db

        result = db["litter_changes"].insert_one(
            {"pet_id": str(test_pet["_id"]), "date_time": datetime(2024, 1, 15, 14, 30), "comment": "Original"}
        )
        record_id = str(result.inserted_id)

        response = client.put(
            f"/api/litter/{record_id}",
            json={"date": "2024-01-15", "time": "15:00", "comment": "Updated"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_delete_litter_change_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a litter change record."""
        from web.app import db

        result = db["litter_changes"].insert_one(
            {"pet_id": str(test_pet["_id"]), "date_time": datetime(2024, 1, 15, 14, 30), "comment": "To delete"}
        )
        record_id = str(result.inserted_id)

        response = client.delete(f"/api/litter/{record_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_add_weight_success(self, client, mock_db, regular_user_token, test_pet):
        """Test adding a weight measurement."""
        response = client.post(
            "/api/weight?pet_id=" + str(test_pet["_id"]),
            json={
                "date": "2024-01-15",
                "time": "14:30",
                "weight": "4.5",
                "food": "Dry food",
                "comment": "Regular check",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True

        # Verify record was created
        from web.app import db

        weights = list(db["weights"].find({"pet_id": str(test_pet["_id"])}))
        assert len(weights) == 1
        assert weights[0]["weight"] == "4.5"
        assert weights[0]["username"] == "testuser"

    def test_get_weights_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting weight measurements."""
        from web.app import db

        db["weights"].insert_many(
            [
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 15, 14, 30),
                    "weight": "4.5",
                    "food": "Dry food",
                    "comment": "Weight 1",
                },
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 20, 10, 0),
                    "weight": "4.7",
                    "food": "Wet food",
                    "comment": "Weight 2",
                },
            ]
        )

        response = client.get(
            f"/api/weight?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "weights" in data
        assert "page" in data
        assert "page_size" in data
        assert "total" in data
        assert len(data["weights"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 100
        assert data["total"] == 2

    def test_update_weight_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating a weight measurement."""
        from web.app import db

        result = db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "weight": "4.5",
                "food": "Dry food",
                "comment": "Original",
            }
        )
        record_id = str(result.inserted_id)

        response = client.put(
            f"/api/weight/{record_id}",
            json={"date": "2024-01-15", "time": "15:00", "weight": "4.6", "food": "Wet food", "comment": "Updated"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify update
        weight = db["weights"].find_one({"_id": ObjectId(record_id)})
        assert weight["weight"] == "4.6"

    def test_delete_weight_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a weight measurement."""
        from web.app import db

        result = db["weights"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 14, 30),
                "weight": "4.5",
                "food": "Dry food",
                "comment": "To delete",
            }
        )
        record_id = str(result.inserted_id)

        response = client.delete(f"/api/weight/{record_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_add_feeding_success(self, client, mock_db, regular_user_token, test_pet):
        """Test adding a feeding record."""
        response = client.post(
            "/api/feeding?pet_id=" + str(test_pet["_id"]),
            json={"date": "2024-01-15", "time": "14:30", "food_weight": "100", "comment": "Morning feeding"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True

        # Verify record was created
        from web.app import db

        feedings = list(db["feedings"].find({"pet_id": str(test_pet["_id"])}))
        assert len(feedings) == 1
        assert feedings[0]["food_weight"] == "100"
        assert feedings[0]["username"] == "testuser"

    def test_get_feedings_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting feeding records."""
        from web.app import db

        db["feedings"].insert_many(
            [
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 15, 8, 0),
                    "food_weight": "100",
                    "comment": "Morning",
                },
                {
                    "pet_id": str(test_pet["_id"]),
                    "date_time": datetime(2024, 1, 15, 18, 0),
                    "food_weight": "150",
                    "comment": "Evening",
                },
            ]
        )

        response = client.get(
            f"/api/feeding?pet_id={test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "feedings" in data
        assert "page" in data
        assert "page_size" in data
        assert "total" in data
        assert len(data["feedings"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 100
        assert data["total"] == 2

    def test_update_feeding_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating a feeding record."""
        from web.app import db

        result = db["feedings"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 8, 0),
                "food_weight": "100",
                "comment": "Original",
            }
        )
        record_id = str(result.inserted_id)

        response = client.put(
            f"/api/feeding/{record_id}",
            json={"date": "2024-01-15", "time": "9:00", "food_weight": "120", "comment": "Updated"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify update
        feeding = db["feedings"].find_one({"_id": ObjectId(record_id)})
        assert feeding["food_weight"] == "120"

    def test_delete_feeding_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a feeding record."""
        from web.app import db

        result = db["feedings"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "date_time": datetime(2024, 1, 15, 8, 0),
                "food_weight": "100",
                "comment": "To delete",
            }
        )
        record_id = str(result.inserted_id)

        response = client.delete(f"/api/feeding/{record_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_health_endpoints_require_pet_id(self, client, regular_user_token):
        """Test that health endpoints require pet_id."""
        endpoints = [
            ("/api/asthma", "GET"),
            ("/api/defecation", "GET"),
            ("/api/litter", "GET"),
            ("/api/weight", "GET"),
            ("/api/feeding", "GET"),
        ]

        for endpoint, method in endpoints:
            if method == "GET":
                response = client.get(endpoint, headers={"Authorization": f"Bearer {regular_user_token}"})
            else:
                response = client.post(endpoint, json={}, headers={"Authorization": f"Bearer {regular_user_token}"})

            assert response.status_code == 422
            data = response.get_json()
            assert "error" in data or isinstance(data, list)
