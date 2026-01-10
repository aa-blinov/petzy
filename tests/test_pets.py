"""Tests for pet management endpoints."""

import pytest
from datetime import datetime, timezone
from bson import ObjectId


@pytest.mark.pets
class TestPetManagement:
    """Test pet management endpoints."""

    def test_get_pets_requires_authentication(self, client):
        """Test that getting pets requires authentication."""
        response = client.get("/api/pets")
        assert response.status_code == 401

    def test_get_pets_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting list of pets."""
        response = client.get("/api/pets", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        data = response.get_json()
        assert "pets" in data
        assert len(data["pets"]) == 1
        assert data["pets"][0]["name"] == test_pet["name"]
        assert "_id" in data["pets"][0]

    def test_get_pets_only_accessible_pets(self, client, mock_db, regular_user_token, test_pet, admin_pet):
        """Test that users only see their own pets and shared pets."""
        response = client.get("/api/pets", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        data = response.get_json()
        # Should only see test_pet, not admin_pet
        assert len(data["pets"]) == 1
        assert data["pets"][0]["_id"] == str(test_pet["_id"])

    def test_create_pet_success_json(self, client, mock_db, regular_user_token):
        """Test creating a pet with JSON data."""
        response = client.post(
            "/api/pets",
            json={"name": "New Cat", "breed": "Maine Coon", "birth_date": "2021-03-15", "gender": "Male"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["pet"]["name"] == "New Cat"
        assert data["pet"]["owner"] == "testuser"

    def test_create_pet_success_form_data(self, client, mock_db, regular_user_token):
        """Test creating a pet with form data."""
        response = client.post(
            "/api/pets",
            data={"name": "Form Cat", "breed": "British Shorthair", "birth_date": "2022-01-01", "gender": "Female"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["pet"]["name"] == "Form Cat"

    def test_create_pet_missing_name(self, client, regular_user_token):
        """Test creating pet without name."""
        response = client.post(
            "/api/pets", json={"breed": "Persian"}, headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_get_pet_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting a specific pet."""
        response = client.get(f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["pet"]["name"] == test_pet["name"]
        assert data["pet"]["current_user_is_owner"] is True

    def test_get_pet_not_found(self, client, regular_user_token):
        """Test getting non-existent pet."""
        fake_id = str(ObjectId())
        response = client.get(f"/api/pets/{fake_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_get_pet_invalid_id_format(self, client, regular_user_token):
        """Test getting pet with invalid ID format."""
        response = client.get("/api/pets/invalid_id", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)
        assert "Неверный формат" in data["error"] or "format" in data["error"].lower()

    def test_get_pet_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """Test getting pet without access."""
        response = client.get(
            f"/api/pets/{admin_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_update_pet_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating pet information."""
        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            json={"name": "Updated Cat", "breed": "Updated Breed", "birth_date": "2020-01-01", "gender": "Female"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify update in database
        from web.app import db

        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        assert pet["name"] == "Updated Cat"

    def test_update_pet_not_owner(self, client, mock_db, regular_user_token, admin_pet):
        """Test updating pet when not owner."""
        response = client.put(
            f"/api/pets/{admin_pet['_id']}",
            json={"name": "Hacked Name"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_delete_pet_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a pet."""
        response = client.delete(
            f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify pet was deleted
        from web.app import db

        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        assert pet is None

    def test_delete_pet_not_owner(self, client, mock_db, regular_user_token, admin_pet):
        """Test deleting pet when not owner."""
        response = client.delete(
            f"/api/pets/{admin_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_share_pet_success(self, client, mock_db, regular_user_token, test_pet, admin_pet):
        """Test sharing pet with another user."""
        # Create another user
        import bcrypt
        from web.app import db

        password_hash = bcrypt.hashpw("pass123".encode(), bcrypt.gensalt()).decode()
        db["users"].insert_one(
            {
                "username": "shareuser",
                "password_hash": password_hash,
                "full_name": "Share User",
                "email": "",
                "created_at": datetime.now(timezone.utc),
                "created_by": "admin",
                "is_active": True,
            }
        )

        response = client.post(
            f"/api/pets/{test_pet['_id']}/share",
            json={"username": "shareuser"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify pet is shared
        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        assert "shareuser" in pet.get("shared_with", [])

    def test_share_pet_not_owner(self, client, mock_db, regular_user_token, admin_pet):
        """Test sharing pet when not owner."""
        response = client.post(
            f"/api/pets/{admin_pet['_id']}/share",
            json={"username": "testuser"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

    def test_share_pet_with_self(self, client, mock_db, regular_user_token, test_pet):
        """Test sharing pet with self (should fail)."""
        response = client.post(
            f"/api/pets/{test_pet['_id']}/share",
            json={"username": "testuser"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_unshare_pet_success(self, client, mock_db, regular_user_token, test_pet):
        """Test removing access from user."""
        # First share the pet
        import bcrypt
        from web.app import db

        password_hash = bcrypt.hashpw("pass123".encode(), bcrypt.gensalt()).decode()
        db["users"].insert_one(
            {
                "username": "shareuser",
                "password_hash": password_hash,
                "full_name": "Share User",
                "email": "",
                "created_at": datetime.now(timezone.utc),
                "created_by": "admin",
                "is_active": True,
            }
        )

        # Share pet
        db["pets"].update_one({"_id": test_pet["_id"]}, {"$addToSet": {"shared_with": "shareuser"}})

        # Now unshare
        response = client.delete(
            f"/api/pets/{test_pet['_id']}/share/shareuser", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Verify access removed
        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        assert "shareuser" not in pet.get("shared_with", [])

    def test_get_pet_photo_requires_authentication(self, client):
        """Test that getting pet photo requires authentication."""
        response = client.get("/api/pets/123/photo")
        assert response.status_code == 401

    def test_get_pet_photo_requires_access(self, client, mock_db, regular_user_token, admin_pet):
        """Test that getting pet photo requires access to pet."""
        # Create pet with photo
        from web.app import db
        from bson import ObjectId

        photo_file_id = ObjectId()
        db["pets"].update_one({"_id": admin_pet["_id"]}, {"$set": {"photo_file_id": str(photo_file_id)}})

        response = client.get(
            f"/api/pets/{admin_pet['_id']}/photo", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 403

    def test_get_pet_photo_not_found(self, client, mock_db, regular_user_token, test_pet):
        """Test getting photo for pet without photo."""
        response = client.get(
            f"/api/pets/{test_pet['_id']}/photo", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_get_pet_photo_success(self, client, mock_db, regular_user_token, test_pet):
        """Test successfully getting pet photo."""
        from web.app import db, fs
        from bson import ObjectId
        from unittest.mock import MagicMock, patch

        # Create photo file ID
        photo_file_id = ObjectId()
        db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_file_id)}})

        # Mock GridFS file
        mock_file = MagicMock()
        mock_file.read.return_value = b"fake_image_data"
        mock_file.content_type = "image/jpeg"

        with patch.object(fs, "get", return_value=mock_file):
            response = client.get(
                f"/api/pets/{test_pet['_id']}/photo", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 200
        assert response.data == b"fake_image_data"
        assert response.content_type == "image/jpeg"
        assert "inline" in response.headers.get("Content-Disposition", "")
        assert "max-age=" in response.headers.get("Cache-Control", "")

    def test_get_pet_photo_invalid_pet_id(self, client, regular_user_token):
        """Test getting photo with invalid pet_id format."""
        response = client.get("/api/pets/invalid_id/photo", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 422
        data = response.get_json()
        assert "error" in data or isinstance(data, list)

    def test_get_pet_photo_pet_not_found(self, client, mock_db, regular_user_token):
        """Test getting photo for non-existent pet."""
        from bson import ObjectId

        fake_pet_id = ObjectId()
        response = client.get(
            f"/api/pets/{fake_pet_id}/photo", headers={"Authorization": f"Bearer {regular_user_token}"}
        )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_get_pet_photo_gridfs_error(self, client, mock_db, regular_user_token, test_pet):
        """Test handling GridFS errors when getting photo."""
        from web.app import db, fs
        from bson import ObjectId
        from unittest.mock import patch

        # Create photo file ID
        photo_file_id = ObjectId()
        db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_file_id)}})

        # Mock GridFS to raise an error
        with patch.object(fs, "get", side_effect=Exception("GridFS error")):
            response = client.get(
                f"/api/pets/{test_pet['_id']}/photo", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "Ошибка загрузки фото" in data["error"] or "error" in data

    def test_delete_pet_cascades_to_all_records(self, client, mock_db, regular_user_token, test_pet):
        """Test that deleting a pet cascades to all related records."""
        from web.app import db
        
        pet_id = str(test_pet["_id"])
        
        # Create various related records
        # Health records
        db["asthma_attacks"].insert_one({
            "pet_id": pet_id,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })
        db["defecations"].insert_one({
            "pet_id": pet_id,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })
        db["weights"].insert_one({
            "pet_id": pet_id,
            "date": datetime.now(timezone.utc),
            "weight": 5.0,
            "username": "testuser"
        })
        db["feedings"].insert_one({
            "pet_id": pet_id,
            "date": datetime.now(timezone.utc),
            "amount": 100,
            "username": "testuser"
        })
        db["litter_changes"].insert_one({
            "pet_id": pet_id,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })
        db["eye_drops"].insert_one({
            "pet_id": pet_id,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })
        db["ear_cleanings"].insert_one({
            "pet_id": pet_id,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })
        db["tooth_brushings"].insert_one({
            "pet_id": pet_id,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })
        
        # Medications and intakes
        med_id = ObjectId()
        db["medications"].insert_one({
            "_id": med_id,
            "pet_id": pet_id,
            "name": "Test Med",
            "owner": "testuser"
        })
        db["medication_intakes"].insert_one({
            "medication_id": str(med_id),
            "pet_id": pet_id,
            "dose_taken": 1.0,
            "date_time": datetime.now(timezone.utc),
            "username": "testuser"
        })
        
        # Verify records exist
        assert db["asthma_attacks"].count_documents({"pet_id": pet_id}) == 1
        assert db["defecations"].count_documents({"pet_id": pet_id}) == 1
        assert db["weights"].count_documents({"pet_id": pet_id}) == 1
        assert db["feedings"].count_documents({"pet_id": pet_id}) == 1
        assert db["litter_changes"].count_documents({"pet_id": pet_id}) == 1
        assert db["eye_drops"].count_documents({"pet_id": pet_id}) == 1
        assert db["ear_cleanings"].count_documents({"pet_id": pet_id}) == 1
        assert db["tooth_brushings"].count_documents({"pet_id": pet_id}) == 1
        assert db["medications"].count_documents({"pet_id": pet_id}) == 1
        assert db["medication_intakes"].count_documents({"pet_id": pet_id}) == 1
        
        # Delete pet
        response = client.delete(
            f"/api/pets/{pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        
        assert response.status_code == 200
        
        # Verify pet is deleted
        assert db["pets"].find_one({"_id": test_pet["_id"]}) is None
        
        # Verify all related records are deleted
        assert db["asthma_attacks"].count_documents({"pet_id": pet_id}) == 0
        assert db["defecations"].count_documents({"pet_id": pet_id}) == 0
        assert db["weights"].count_documents({"pet_id": pet_id}) == 0
        assert db["feedings"].count_documents({"pet_id": pet_id}) == 0
        assert db["litter_changes"].count_documents({"pet_id": pet_id}) == 0
        assert db["eye_drops"].count_documents({"pet_id": pet_id}) == 0
        assert db["ear_cleanings"].count_documents({"pet_id": pet_id}) == 0
        assert db["tooth_brushings"].count_documents({"pet_id": pet_id}) == 0
        assert db["medications"].count_documents({"pet_id": pet_id}) == 0
        assert db["medication_intakes"].count_documents({"pet_id": pet_id}) == 0

    def test_delete_pet_with_photo(self, client, mock_db, regular_user_token, test_pet):
        """Test that deleting a pet also deletes its photo from GridFS."""
        from web.app import db, fs
        from unittest.mock import patch
        
        # Add photo to pet
        photo_file_id = ObjectId()
        db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {"$set": {"photo_file_id": str(photo_file_id)}}
        )
        
        # Track if fs.delete was called
        delete_called = False
        original_delete = fs.delete
        
        def mock_delete(file_id):
            nonlocal delete_called
            delete_called = True
            # Don't actually delete since we didn't create the file
            
        with patch.object(fs, 'delete', side_effect=mock_delete):
            response = client.delete(
                f"/api/pets/{test_pet['_id']}",
                headers={"Authorization": f"Bearer {regular_user_token}"}
            )
        
        assert response.status_code == 200
        assert delete_called, "Photo deletion should have been attempted"
        
        # Verify pet is deleted
        assert db["pets"].find_one({"_id": test_pet["_id"]}) is None

    def test_delete_pet_with_multiple_medications_and_intakes(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting pet with multiple medications each having multiple intakes."""
        from web.app import db
        
        pet_id = str(test_pet["_id"])
        
        # Create 3 medications
        med_ids = [ObjectId() for _ in range(3)]
        for med_id in med_ids:
            db["medications"].insert_one({
                "_id": med_id,
                "pet_id": pet_id,
                "name": f"Med {med_id}",
                "owner": "testuser"
            })
            
            # Create 5 intakes for each medication
            for _ in range(5):
                db["medication_intakes"].insert_one({
                    "medication_id": str(med_id),
                    "pet_id": pet_id,
                    "dose_taken": 1.0,
                    "date_time": datetime.now(timezone.utc),
                    "username": "testuser"
                })
        
        # Verify we have 3 medications and 15 intakes
        assert db["medications"].count_documents({"pet_id": pet_id}) == 3
        assert db["medication_intakes"].count_documents({"pet_id": pet_id}) == 15
        
        # Delete pet
        response = client.delete(
            f"/api/pets/{pet_id}",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        
        assert response.status_code == 200
        
        # Verify everything is deleted
        assert db["pets"].find_one({"_id": test_pet["_id"]}) is None
        assert db["medications"].count_documents({"pet_id": pet_id}) == 0
        assert db["medication_intakes"].count_documents({"pet_id": pet_id}) == 0

