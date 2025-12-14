"""Tests for pet management endpoints."""

import pytest
from datetime import datetime
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
        response = client.get("/api/pets", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert "pets" in data
        assert len(data["pets"]) == 1
        assert data["pets"][0]["name"] == test_pet["name"]
        assert "_id" in data["pets"][0]
    
    def test_get_pets_only_accessible_pets(self, client, mock_db, regular_user_token, test_pet, admin_pet):
        """Test that users only see their own pets and shared pets."""
        response = client.get("/api/pets", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        # Should only see test_pet, not admin_pet
        assert len(data["pets"]) == 1
        assert data["pets"][0]["_id"] == str(test_pet["_id"])
    
    def test_create_pet_success_json(self, client, mock_db, regular_user_token):
        """Test creating a pet with JSON data."""
        response = client.post("/api/pets", json={
            "name": "New Cat",
            "breed": "Maine Coon",
            "birth_date": "2021-03-15",
            "gender": "Male"
        }, headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["pet"]["name"] == "New Cat"
        assert data["pet"]["owner"] == "testuser"
    
    def test_create_pet_success_form_data(self, client, mock_db, regular_user_token):
        """Test creating a pet with form data."""
        response = client.post("/api/pets", data={
            "name": "Form Cat",
            "breed": "British Shorthair",
            "birth_date": "2022-01-01",
            "gender": "Female"
        }, headers={
            "Authorization": f"Bearer {regular_user_token}"
        }, content_type="multipart/form-data")
        
        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["pet"]["name"] == "Form Cat"
    
    def test_create_pet_missing_name(self, client, regular_user_token):
        """Test creating pet without name."""
        response = client.post("/api/pets", json={
            "breed": "Persian"
        }, headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_get_pet_success(self, client, mock_db, regular_user_token, test_pet):
        """Test getting a specific pet."""
        response = client.get(f"/api/pets/{test_pet['_id']}", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["pet"]["name"] == test_pet["name"]
        assert data["pet"]["current_user_is_owner"] is True
    
    def test_get_pet_not_found(self, client, regular_user_token):
        """Test getting non-existent pet."""
        fake_id = str(ObjectId())
        response = client.get(f"/api/pets/{fake_id}", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
    
    def test_get_pet_invalid_id_format(self, client, regular_user_token):
        """Test getting pet with invalid ID format."""
        response = client.get("/api/pets/invalid_id", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Неверный формат" in data["error"] or "format" in data["error"].lower()
    
    def test_get_pet_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """Test getting pet without access."""
        response = client.get(f"/api/pets/{admin_pet['_id']}", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data
    
    def test_update_pet_success(self, client, mock_db, regular_user_token, test_pet):
        """Test updating pet information."""
        response = client.put(f"/api/pets/{test_pet['_id']}", json={
            "name": "Updated Cat",
            "breed": "Updated Breed",
            "birth_date": "2020-01-01",
            "gender": "Female"
        }, headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        
        # Verify update in database
        from web.app import db
        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        assert pet["name"] == "Updated Cat"
    
    def test_update_pet_not_owner(self, client, mock_db, regular_user_token, admin_pet):
        """Test updating pet when not owner."""
        response = client.put(f"/api/pets/{admin_pet['_id']}", json={
            "name": "Hacked Name"
        }, headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data
    
    def test_delete_pet_success(self, client, mock_db, regular_user_token, test_pet):
        """Test deleting a pet."""
        response = client.delete(f"/api/pets/{test_pet['_id']}", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        
        # Verify pet was deleted
        from web.app import db
        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        assert pet is None
    
    def test_delete_pet_not_owner(self, client, mock_db, regular_user_token, admin_pet):
        """Test deleting pet when not owner."""
        response = client.delete(f"/api/pets/{admin_pet['_id']}", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data
    
    def test_share_pet_success(self, client, mock_db, regular_user_token, test_pet, admin_pet):
        """Test sharing pet with another user."""
        # Create another user
        import bcrypt
        from web.app import db
        password_hash = bcrypt.hashpw("pass123".encode(), bcrypt.gensalt()).decode()
        db["users"].insert_one({
            "username": "shareuser",
            "password_hash": password_hash,
            "full_name": "Share User",
            "email": "",
            "created_at": datetime.utcnow(),
            "created_by": "admin",
            "is_active": True
        })
        
        response = client.post(f"/api/pets/{test_pet['_id']}/share", json={
            "username": "shareuser"
        }, headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        
        # Verify pet is shared
        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        assert "shareuser" in pet.get("shared_with", [])
    
    def test_share_pet_not_owner(self, client, mock_db, regular_user_token, admin_pet):
        """Test sharing pet when not owner."""
        response = client.post(f"/api/pets/{admin_pet['_id']}/share", json={
            "username": "testuser"
        }, headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 403
        data = response.get_json()
        assert "error" in data
    
    def test_share_pet_with_self(self, client, mock_db, regular_user_token, test_pet):
        """Test sharing pet with self (should fail)."""
        response = client.post(f"/api/pets/{test_pet['_id']}/share", json={
            "username": "testuser"
        }, headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_unshare_pet_success(self, client, mock_db, regular_user_token, test_pet):
        """Test removing access from user."""
        # First share the pet
        import bcrypt
        from web.app import db
        password_hash = bcrypt.hashpw("pass123".encode(), bcrypt.gensalt()).decode()
        db["users"].insert_one({
            "username": "shareuser",
            "password_hash": password_hash,
            "full_name": "Share User",
            "email": "",
            "created_at": datetime.utcnow(),
            "created_by": "admin",
            "is_active": True
        })
        
        # Share pet
        db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {"$addToSet": {"shared_with": "shareuser"}}
        )
        
        # Now unshare
        response = client.delete(
            f"/api/pets/{test_pet['_id']}/share/shareuser",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        
        # Verify access removed
        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        assert "shareuser" not in pet.get("shared_with", [])
    
    def test_request_access_success(self, client, mock_db, regular_user_token, admin_pet):
        """Test requesting access to a pet."""
        response = client.post(f"/api/pets/{admin_pet['_id']}/request-access", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        
        # Verify request was added
        from web.app import db
        pet = db["pets"].find_one({"_id": admin_pet["_id"]})
        requests = pet.get("access_requests", [])
        assert any(req.get("username") == "testuser" for req in requests)
    
    def test_request_access_already_has_access(self, client, mock_db, regular_user_token, test_pet):
        """Test requesting access when already has access."""
        response = client.post(f"/api/pets/{test_pet['_id']}/request-access", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
    
    def test_get_access_requests_owner_only(self, client, mock_db, regular_user_token, test_pet):
        """Test getting access requests (owner only)."""
        # Add a request
        from web.app import db
        db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {"$addToSet": {"access_requests": {
                "username": "requester",
                "requested_at": datetime.utcnow()
            }}}
        )
        
        response = client.get(f"/api/pets/{test_pet['_id']}/access-requests", headers={
            "Authorization": f"Bearer {regular_user_token}"
        })
        
        assert response.status_code == 200
        data = response.get_json()
        assert "requests" in data
        assert len(data["requests"]) == 1
    
    def test_approve_access_request(self, client, mock_db, regular_user_token, test_pet):
        """Test approving an access request."""
        # Add a request
        from web.app import db
        db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {"$addToSet": {"access_requests": {
                "username": "requester",
                "requested_at": datetime.utcnow()
            }}}
        )
        
        response = client.post(
            f"/api/pets/{test_pet['_id']}/access-requests/requester/approve",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        
        # Verify access granted and request removed
        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        assert "requester" in pet.get("shared_with", [])
        requests = pet.get("access_requests", [])
        assert not any(req.get("username") == "requester" for req in requests)
    
    def test_reject_access_request(self, client, mock_db, regular_user_token, test_pet):
        """Test rejecting an access request."""
        # Add a request
        from web.app import db
        db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {"$addToSet": {"access_requests": {
                "username": "requester",
                "requested_at": datetime.utcnow()
            }}}
        )
        
        response = client.post(
            f"/api/pets/{test_pet['_id']}/access-requests/requester/reject",
            headers={"Authorization": f"Bearer {regular_user_token}"}
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        
        # Verify request removed
        pet = db["pets"].find_one({"_id": test_pet["_id"]})
        requests = pet.get("access_requests", [])
        assert not any(req.get("username") == "requester" for req in requests)

