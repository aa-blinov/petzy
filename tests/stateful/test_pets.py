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

    def test_unshare_pet_not_owner(self, client, mock_db, regular_user_token, admin_pet):
        """Only the owner may revoke someone else's access."""
        response = client.delete(
            f"/api/pets/{admin_pet['_id']}/share/someone",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data

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
        db["asthma_attacks"].insert_one(
            {"pet_id": pet_id, "date_time": datetime.now(timezone.utc), "username": "testuser"}
        )
        db["defecations"].insert_one(
            {"pet_id": pet_id, "date_time": datetime.now(timezone.utc), "username": "testuser"}
        )
        db["weights"].insert_one(
            {"pet_id": pet_id, "date": datetime.now(timezone.utc), "weight": 5.0, "username": "testuser"}
        )
        db["feedings"].insert_one(
            {"pet_id": pet_id, "date": datetime.now(timezone.utc), "amount": 100, "username": "testuser"}
        )
        db["litter_changes"].insert_one(
            {"pet_id": pet_id, "date_time": datetime.now(timezone.utc), "username": "testuser"}
        )
        db["eye_drops"].insert_one({"pet_id": pet_id, "date_time": datetime.now(timezone.utc), "username": "testuser"})
        db["ear_cleaning"].insert_one(
            {"pet_id": pet_id, "date_time": datetime.now(timezone.utc), "username": "testuser"}
        )
        db["tooth_brushing"].insert_one(
            {"pet_id": pet_id, "date_time": datetime.now(timezone.utc), "username": "testuser"}
        )

        # Medications and intakes
        med_id = ObjectId()
        db["medications"].insert_one({"_id": med_id, "pet_id": pet_id, "name": "Test Med", "owner": "testuser"})
        db["medication_intakes"].insert_one(
            {
                "medication_id": str(med_id),
                "pet_id": pet_id,
                "dose_taken": 1.0,
                "date_time": datetime.now(timezone.utc),
                "username": "testuser",
            }
        )

        # Documents
        db["documents"].insert_one(
            {
                "pet_id": pet_id,
                "username": "testuser",
                "category": "other",
                "title": "Test Doc",
                "note": "",
                "file_id": str(ObjectId()),
                "original_filename": "doc.pdf",
                "content_type": "application/pdf",
                "file_size": 10,
                "created_at": datetime.now(timezone.utc),
            }
        )

        # Verify records exist
        assert db["asthma_attacks"].count_documents({"pet_id": pet_id}) == 1
        assert db["defecations"].count_documents({"pet_id": pet_id}) == 1
        assert db["weights"].count_documents({"pet_id": pet_id}) == 1
        assert db["feedings"].count_documents({"pet_id": pet_id}) == 1
        assert db["litter_changes"].count_documents({"pet_id": pet_id}) == 1
        assert db["eye_drops"].count_documents({"pet_id": pet_id}) == 1
        assert db["ear_cleaning"].count_documents({"pet_id": pet_id}) == 1
        assert db["tooth_brushing"].count_documents({"pet_id": pet_id}) == 1
        assert db["medications"].count_documents({"pet_id": pet_id}) == 1
        assert db["medication_intakes"].count_documents({"pet_id": pet_id}) == 1
        assert db["documents"].count_documents({"pet_id": pet_id}) == 1

        # Delete pet
        response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

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
        assert db["ear_cleaning"].count_documents({"pet_id": pet_id}) == 0
        assert db["tooth_brushing"].count_documents({"pet_id": pet_id}) == 0
        assert db["medications"].count_documents({"pet_id": pet_id}) == 0
        assert db["medication_intakes"].count_documents({"pet_id": pet_id}) == 0
        assert db["documents"].count_documents({"pet_id": pet_id}) == 0

    def test_delete_pet_with_documents(self, client, mock_db, regular_user_token, test_pet):
        """Deleting a pet also deletes each of its documents' GridFS files."""
        from unittest.mock import patch

        from web.app import db, fs

        pet_id = str(test_pet["_id"])
        file_ids = [ObjectId(), ObjectId()]
        for i, file_id in enumerate(file_ids):
            db["documents"].insert_one(
                {
                    "pet_id": pet_id,
                    "username": "testuser",
                    "category": "other",
                    "title": f"Doc {i}",
                    "note": "",
                    "file_id": str(file_id),
                    "original_filename": "doc.pdf",
                    "content_type": "application/pdf",
                    "file_size": 10,
                    "created_at": datetime.now(timezone.utc),
                }
            )

        deleted_ids = []

        def mock_delete(file_id):
            deleted_ids.append(file_id)

        with patch.object(fs, "delete", side_effect=mock_delete):
            response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        assert db["documents"].count_documents({"pet_id": pet_id}) == 0
        assert set(deleted_ids) == set(file_ids)

    def test_delete_pet_document_file_deletion_failure_does_not_fail_request(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """Losing a document's GridFS blob during cascade delete shouldn't
        block deleting the pet — same tolerance as the photo cleanup."""
        from unittest.mock import patch

        from web.app import db, fs

        pet_id = str(test_pet["_id"])
        db["documents"].insert_one(
            {
                "pet_id": pet_id,
                "username": "testuser",
                "category": "other",
                "title": "Doc",
                "note": "",
                "file_id": str(ObjectId()),
                "original_filename": "doc.pdf",
                "content_type": "application/pdf",
                "file_size": 10,
                "created_at": datetime.now(timezone.utc),
            }
        )

        with patch.object(fs, "delete", side_effect=RuntimeError("gridfs unavailable")):
            response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        assert db["pets"].find_one({"_id": test_pet["_id"]}) is None

    def test_delete_pet_with_photo(self, client, mock_db, regular_user_token, test_pet):
        """Test that deleting a pet also deletes its photo from GridFS."""
        from web.app import db, fs
        from unittest.mock import patch

        # Add photo to pet
        photo_file_id = ObjectId()
        db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_file_id)}})

        # Track if fs.delete was called
        delete_called = False

        def mock_delete(file_id):
            nonlocal delete_called
            delete_called = True
            # Don't actually delete since we didn't create the file

        with patch.object(fs, "delete", side_effect=mock_delete):
            response = client.delete(
                f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
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
            db["medications"].insert_one(
                {"_id": med_id, "pet_id": pet_id, "name": f"Med {med_id}", "owner": "testuser"}
            )

            # Create 5 intakes for each medication
            for _ in range(5):
                db["medication_intakes"].insert_one(
                    {
                        "medication_id": str(med_id),
                        "pet_id": pet_id,
                        "dose_taken": 1.0,
                        "date_time": datetime.now(timezone.utc),
                        "username": "testuser",
                    }
                )

        # Verify we have 3 medications and 15 intakes
        assert db["medications"].count_documents({"pet_id": pet_id}) == 3
        assert db["medication_intakes"].count_documents({"pet_id": pet_id}) == 15

        # Delete pet
        response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200

        # Verify everything is deleted
        assert db["pets"].find_one({"_id": test_pet["_id"]}) is None
        assert db["medications"].count_documents({"pet_id": pet_id}) == 0
        assert db["medication_intakes"].count_documents({"pet_id": pet_id}) == 0


@pytest.mark.pets
class TestPetListFormatting:
    """get_pets' per-pet response formatting — photo_url derivation and
    legacy-data tolerance in shared_with, not covered by the plain
    CRUD-shape checks above."""

    def test_get_pets_includes_photo_url_with_cache_busting(self, client, mock_db, regular_user_token, test_pet):
        photo_file_id = ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_file_id)}})

        response = client.get("/api/pets", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        pet = response.get_json()["pets"][0]
        from web.storage import file_version

        assert f"?v={file_version(str(photo_file_id))}" in pet["photo_url"]
        # The stored reference (a bucket key) stays on the server.
        assert "photo_file_id" not in pet

    def test_get_pets_converts_legacy_objectid_in_shared_with(self, client, mock_db, regular_user_token, test_pet):
        """shared_with is always written as a username string by share_pet,
        but the formatting loop also tolerates a raw ObjectId — a shape
        that could only come from data written outside the app's own
        write path (an older schema, a manual fix). Inserted directly to
        exercise that tolerance without pretending the API itself
        produces it.
        """
        legacy_uid = ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": [legacy_uid, "someone"]}})

        response = client.get("/api/pets", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        pet = response.get_json()["pets"][0]
        assert pet["shared_with"] == [str(legacy_uid), "someone"]


@pytest.mark.pets
class TestGetPetDetail:
    def test_get_pet_includes_photo_url_when_photo_set(self, client, mock_db, regular_user_token, test_pet):
        photo_file_id = ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_file_id)}})

        response = client.get(f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        pet = response.get_json()["pet"]
        from web.storage import file_version

        assert f"?v={file_version(str(photo_file_id))}" in pet["photo_url"]
        assert "photo_file_id" not in pet


@pytest.mark.pets
class TestCreatePetValidationAndFields:
    def test_create_pet_multipart_missing_name_rejected(self, client, regular_user_token):
        response = client.post(
            "/api/pets",
            data={"breed": "Persian"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 422

    def test_create_pet_with_explicit_tiles_settings(self, client, mock_db, regular_user_token):
        custom_order = {
            "order": ["weight"],
            "visible": {"weight": True},
        }
        response = client.post(
            "/api/pets",
            json={"name": "Tiled Cat", "tiles_settings": custom_order},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        assert response.get_json()["pet"]["tiles_settings"]["order"] == ["weight"]


@pytest.mark.pets
class TestUpdatePetFieldsAndValidation:
    def test_update_pet_multipart_invalid_data_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            data={"name": ""},  # min_length=1
            headers={"Authorization": f"Bearer {regular_user_token}"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 422

    def test_update_pet_json_fields_persist(self, client, mock_db, regular_user_token, test_pet):
        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            json={
                "species": "cat",
                "is_neutered": True,
                "health_notes": "Allergic to chicken",
                "tiles_settings": {"order": ["feeding"], "visible": {"feeding": True}},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 200
        pet = mock_db["pets"].find_one({"_id": test_pet["_id"]})
        assert pet["species"] == "cat"
        assert pet["is_neutered"] is True
        assert pet["health_notes"] == "Allergic to chicken"
        assert pet["tiles_settings"]["order"] == ["feeding"]

    def test_update_pet_json_photo_url_and_remove_photo(self, client, mock_db, regular_user_token, test_pet):
        # Setting photo_url directly (the JSON-only path — no file upload).
        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            json={"photo_url": "https://example.com/cat.png"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]})["photo_url"] == "https://example.com/cat.png"

        # remove_photo via JSON clears both fields, independent of the
        # multipart-only GridFS cleanup path.
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(ObjectId())}})
        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            json={"remove_photo": True},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        pet = mock_db["pets"].find_one({"_id": test_pet["_id"]})
        assert pet["photo_file_id"] is None
        assert pet["photo_url"] is None

    def test_update_pet_no_fields_returns_error(self, client, mock_db, regular_user_token, test_pet):
        response = client.put(
            f"/api/pets/{test_pet['_id']}",
            json={},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422

    def test_update_pet_old_photo_delete_failure_still_succeeds(self, client, mock_db, regular_user_token, test_pet):
        """Losing the old GridFS blob shouldn't block replacing it — the
        code logs and continues, matching the same tolerance already
        relied on for delete_pet's own photo cleanup."""
        import io
        from unittest.mock import patch
        from PIL import Image
        from web.app import fs

        old_photo_id = ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(old_photo_id)}})
        buf = io.BytesIO()
        Image.new("RGB", (10, 10), (1, 2, 3)).save(buf, format="PNG")
        buf.seek(0)

        with patch.object(fs, "delete", side_effect=RuntimeError("gridfs unavailable")):
            response = client.put(
                f"/api/pets/{test_pet['_id']}",
                data={"name": test_pet["name"], "photo_file": (buf, "new.png")},
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        # The new photo is in object storage and the pet points at it.
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]})["photo_file_id"].startswith("users/")

    def test_update_pet_remove_photo_delete_failure_still_succeeds(self, client, mock_db, regular_user_token, test_pet):
        """Same tolerance as the replace-photo path, but for a bare
        remove_photo=true request with no new file — losing the old
        GridFS blob shouldn't block the update."""
        from unittest.mock import patch
        from web.app import fs

        old_photo_id = ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(old_photo_id)}})

        with patch.object(fs, "delete", side_effect=RuntimeError("gridfs unavailable")):
            response = client.put(
                f"/api/pets/{test_pet['_id']}",
                data={"name": test_pet["name"], "remove_photo": "true"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        pet = mock_db["pets"].find_one({"_id": test_pet["_id"]})
        assert pet.get("photo_file_id") is None

    def test_update_pet_photo_optimization_failure_falls_back_to_original(
        self, client, mock_db, regular_user_token, test_pet, s3_storage
    ):
        import io
        from unittest.mock import patch

        with patch("web.pets.optimize_image", return_value=None):
            response = client.put(
                f"/api/pets/{test_pet['_id']}",
                data={"name": test_pet["name"], "photo_file": (io.BytesIO(b"raw"), "raw.png")},
                headers={"Authorization": f"Bearer {regular_user_token}"},
                content_type="multipart/form-data",
            )

        assert response.status_code == 200
        key = mock_db["pets"].find_one({"_id": test_pet["_id"]})["photo_file_id"]
        assert key.endswith(".png")  # stored as uploaded, not converted
        obj = s3_storage.get_object(Bucket="petzy-test", Key=key)
        assert obj["Body"].read() == b"raw"
        assert obj["ContentType"] == "image/png"


@pytest.mark.pets
class TestSharePetValidation:
    def test_share_pet_missing_username(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            f"/api/pets/{test_pet['_id']}/share",
            json={"username": "   "},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 422

    def test_share_pet_user_not_found(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            f"/api/pets/{test_pet['_id']}/share",
            json={"username": "nosuchuser"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 404
        assert "error" in response.get_json()

    def test_share_pet_already_shared(self, client, mock_db, regular_user_token, test_pet):
        first = client.post(
            f"/api/pets/{test_pet['_id']}/share",
            json={"username": "admin"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert first.status_code == 200

        second = client.post(
            f"/api/pets/{test_pet['_id']}/share",
            json={"username": "admin"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert second.status_code == 422


@pytest.mark.pets
class TestDeletePetEdgeCases:
    def test_delete_pet_photo_deletion_failure_does_not_fail_request(
        self, client, mock_db, regular_user_token, test_pet
    ):
        from unittest.mock import patch
        from web.app import fs

        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(ObjectId())}})

        with patch.object(fs, "delete", side_effect=RuntimeError("gridfs unavailable")):
            response = client.delete(
                f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 200
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}) is None

    def test_delete_pet_fallback_reports_not_found_when_already_gone(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """The fallback branch re-deletes the pet itself (rather than
        trusting the earlier access check is still valid a moment
        later); if that delete matches nothing, it's reported as
        pet_not_found instead of a false success."""
        import web.app as app
        from unittest.mock import patch, MagicMock

        no_match = MagicMock(deleted_count=0)
        with patch.object(app.db.pets, "delete_one", return_value=no_match):
            response = client.delete(
                f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 404

    def test_delete_pet_unexpected_error_is_not_treated_as_missing_transaction_support(
        self, client, mock_db, regular_user_token, test_pet
    ):
        """Only errors that actually look like 'this server can't do
        transactions' should fall back to best-effort deletion; anything
        else re-raises rather than being silently reinterpreted as that."""
        import web.app as app
        from unittest.mock import patch

        with patch.object(app.db.client, "start_session", side_effect=RuntimeError("totally unrelated failure")):
            response = client.delete(
                f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"}
            )

        assert response.status_code == 500
        # Re-raising means the fallback's own cascade never ran — the
        # pet must still be present.
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}) is not None

    def test_delete_pet_via_real_transaction_path(self, client, mock_db, regular_user_token, test_pet):
        """Exercises the transactional branch itself, which mongomock
        can never take natively (`start_session` always raises there,
        and its collections reject a `session=` kwarg outright) — the
        same fallback every test above this one has been exercising.
        Real MongoDB accepts `session=` transparently; that's the one
        piece stubbed here, everything else (the actual deletes) runs
        against the real mock collections so the results are genuine.
        """
        import web.app as app
        from unittest.mock import patch, MagicMock
        from mongomock.collection import Collection

        pet_id = str(test_pet["_id"])
        med_id = ObjectId()
        mock_db["medications"].insert_one({"_id": med_id, "pet_id": pet_id, "name": "M", "owner": "testuser"})
        mock_db["events"].insert_one(
            {
                "pet_id": pet_id,
                "type": "feeding",
                "date_time": datetime.now(timezone.utc),
                "fields": {},
                "comment": "",
                "username": "testuser",
            }
        )

        mock_session = MagicMock()
        session_cm = MagicMock()
        session_cm.__enter__.return_value = mock_session
        session_cm.__exit__.return_value = False
        txn_cm = MagicMock()
        txn_cm.__enter__.return_value = None
        txn_cm.__exit__.return_value = False
        mock_session.start_transaction.return_value = txn_cm

        real_delete_many = Collection.delete_many
        real_delete_one = Collection.delete_one

        def tolerant_delete_many(self, *args, **kwargs):
            kwargs.pop("session", None)
            return real_delete_many(self, *args, **kwargs)

        def tolerant_delete_one(self, *args, **kwargs):
            kwargs.pop("session", None)
            return real_delete_one(self, *args, **kwargs)

        with (
            patch.object(app.db.client, "start_session", return_value=session_cm),
            patch.object(Collection, "delete_many", tolerant_delete_many),
            patch.object(Collection, "delete_one", tolerant_delete_one),
        ):
            response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        assert mock_db["pets"].find_one({"_id": test_pet["_id"]}) is None
        assert mock_db["medications"].count_documents({"pet_id": pet_id}) == 0
        assert mock_db["events"].count_documents({"pet_id": pet_id}) == 0

    def test_delete_pet_transaction_failure_does_not_fall_back(self, client, mock_db, regular_user_token, test_pet):
        """If the pet document itself fails to delete inside a `with
        session.start_transaction()` block, that's raised as
        PetNotFoundDuringDeletion — a genuine application error, not a
        "this server doesn't support transactions" signal. It must not
        be reinterpreted as the latter and silently retried via the
        best-effort fallback.

        (mongomock has no real transaction rollback to verify here —
        real MongoDB would additionally roll back every delete_many
        already issued in the same transaction; that atomicity guarantee
        is exactly why the real path exists over the fallback's
        best-effort cascade, but it isn't something a mock store can
        demonstrate. What's verified here is the error-classification
        behavior, which is independent of that.)
        """
        import web.app as app
        from unittest.mock import patch, MagicMock
        from mongomock.collection import Collection

        pet_id = str(test_pet["_id"])

        mock_session = MagicMock()
        session_cm = MagicMock()
        session_cm.__enter__.return_value = mock_session
        session_cm.__exit__.return_value = False
        txn_cm = MagicMock()
        txn_cm.__enter__.return_value = None
        txn_cm.__exit__.return_value = False
        mock_session.start_transaction.return_value = txn_cm

        real_delete_many = Collection.delete_many

        def tolerant_delete_many(self, *args, **kwargs):
            kwargs.pop("session", None)
            return real_delete_many(self, *args, **kwargs)

        # The pet delete_one inside the transaction matches nothing —
        # as if it had already been removed a moment earlier.
        def vanished_delete_one(self, *args, **kwargs):
            return MagicMock(deleted_count=0)

        with (
            patch.object(app.db.client, "start_session", return_value=session_cm),
            patch.object(Collection, "delete_many", tolerant_delete_many),
            patch.object(Collection, "delete_one", vanished_delete_one),
        ):
            response = client.delete(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 500


@pytest.mark.pets
class TestGetPetPhotoResize:
    def _real_photo_bytes(self, size=(400, 200)):
        import io
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", size, (10, 20, 30)).save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    def test_resize_by_width_only_preserves_aspect_ratio(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import MagicMock, patch
        from web.app import fs

        photo_file_id = ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_file_id)}})
        mock_file = MagicMock()
        mock_file.read.return_value = self._real_photo_bytes(size=(400, 200))
        mock_file.content_type = "image/png"

        with patch.object(fs, "get", return_value=mock_file):
            response = client.get(
                f"/api/pets/{test_pet['_id']}/photo?w=96",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert response.content_type == "image/webp"
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(response.data))
        assert img.width == 96
        assert img.height == 48  # 400x200 at width=96 keeps 2:1

    def test_resize_by_height_only_preserves_aspect_ratio(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import MagicMock, patch
        from web.app import fs

        photo_file_id = ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_file_id)}})
        mock_file = MagicMock()
        mock_file.read.return_value = self._real_photo_bytes(size=(400, 200))
        mock_file.content_type = "image/png"

        with patch.object(fs, "get", return_value=mock_file):
            response = client.get(
                f"/api/pets/{test_pet['_id']}/photo?h=48",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(response.data))
        assert img.height == 48
        assert img.width == 96

    def test_resize_failure_falls_back_to_original_bytes(self, client, mock_db, regular_user_token, test_pet):
        """A corrupt/unreadable image shouldn't 500 the whole request —
        the caller still gets *something* back, just unresized."""
        from unittest.mock import MagicMock, patch
        from web.app import fs

        photo_file_id = ObjectId()
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"photo_file_id": str(photo_file_id)}})
        mock_file = MagicMock()
        mock_file.read.return_value = b"not a real image"
        mock_file.content_type = "image/png"

        with patch.object(fs, "get", return_value=mock_file):
            response = client.get(
                f"/api/pets/{test_pet['_id']}/photo?w=100&h=100",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 200
        assert response.data == b"not a real image"
        assert response.content_type == "image/png"


@pytest.mark.pets
class TestRouteLevelValueErrorHandling:
    """Each of these routes wraps its body in `except ValueError` as a
    safety net for anything unexpected raising one — normally unreachable
    since ObjectId parsing is already caught inside get_pet_and_validate
    and birth_date is already validated at the Pydantic schema layer.
    Forcing it via a mock verifies the net actually catches, without
    deleting a defensive layer on the strength of that reachability
    analysis alone.
    """

    def test_get_pet_value_error_handled(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import patch

        with patch("web.pets.get_pet_and_validate", side_effect=ValueError("simulated")):
            response = client.get(
                f"/api/pets/{test_pet['_id']}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 422

    def test_update_pet_value_error_handled(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import patch

        with patch("web.pets.get_pet_and_validate", side_effect=ValueError("simulated")):
            response = client.put(
                f"/api/pets/{test_pet['_id']}",
                json={"name": "X"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 422

    def test_share_pet_value_error_handled(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import patch

        with patch("web.pets.get_pet_and_validate", side_effect=ValueError("simulated")):
            response = client.post(
                f"/api/pets/{test_pet['_id']}/share",
                json={"username": "admin"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 422

    def test_unshare_pet_value_error_handled(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import patch

        with patch("web.pets.get_pet_and_validate", side_effect=ValueError("simulated")):
            response = client.delete(
                f"/api/pets/{test_pet['_id']}/share/admin",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 422

    def test_delete_pet_value_error_handled(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import patch

        with patch("web.pets.get_pet_and_validate", side_effect=ValueError("simulated")):
            response = client.delete(
                f"/api/pets/{test_pet['_id']}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 422

    def test_create_pet_value_error_handled(self, client, mock_db, regular_user_token):
        from unittest.mock import patch

        with patch("web.pets.parse_date", side_effect=ValueError("simulated")):
            response = client.post(
                "/api/pets",
                json={"name": "X", "birth_date": "2020-01-01"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 422

    def test_get_pet_returns_stored_tiles_settings_not_default(self, client, mock_db, regular_user_token, test_pet):
        custom = {"order": ["weight"], "visible": {"weight": True}}
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"tiles_settings": custom}})

        response = client.get(f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        assert response.get_json()["pet"]["tiles_settings"]["order"] == ["weight"]
