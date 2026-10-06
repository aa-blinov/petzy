"""One pet by its own address: `GET /api/pets/<pet_id>`.

The edit form used to pull the whole roster (`GET /api/pets`) and look the pet up in it, so
opening one pet's card cost a request proportional to how many pets the person has, and the
form broke for anyone whose roster request failed. The form now asks for the pet by address;
these tests pin what that one request must answer with, so the address stays a way in on its own.
"""

import pytest
from datetime import datetime, timezone

from bson import ObjectId


@pytest.mark.pets
class TestGetSinglePet:
    def test_returns_the_pet_the_address_names(self, client, mock_db, regular_user_token, test_pet):
        """The owner's own pet: one pet, by its id, with the fields the edit form fills from."""
        pet_id = str(test_pet["_id"])
        response = client.get(f"/api/pets/{pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        pet = response.get_json()["pet"]
        assert pet["_id"] == pet_id
        assert pet["name"] == "Test Cat"
        assert pet["current_user_is_owner"] is True

    def test_says_who_may_change_it(self, client, mock_db, regular_user_token, test_pet):
        """A person the pet is shared with gets the same card with the answer in it: the form
        shows the card and does not offer to save it, and that answer comes from this request."""
        mock_db["pets"].update_one(
            {"_id": test_pet["_id"]},
            {"$set": {"shared_with": ["neighbour"]}},
        )
        mock_db["users"].insert_one(
            {"username": "neighbour", "password_hash": "x", "created_at": datetime.now(timezone.utc), "is_active": True}
        )
        from web.security import create_access_token

        token = create_access_token("neighbour")
        response = client.get(f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        pet = response.get_json()["pet"]
        assert pet["name"] == "Test Cat"
        assert pet["current_user_is_owner"] is False

    def test_another_person_address_is_not_a_way_in(self, client, mock_db, regular_user_token, test_pet):
        """The address is for people the pet reaches and nobody else."""
        mock_db["users"].insert_one(
            {"username": "stranger", "password_hash": "x", "created_at": datetime.now(timezone.utc), "is_active": True}
        )
        from web.security import create_access_token

        token = create_access_token("stranger")
        response = client.get(f"/api/pets/{test_pet['_id']}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code in (403, 404)
        assert "pet" not in (response.get_json() or {})

    def test_an_address_of_a_pet_that_is_not_there(self, client, regular_user_token):
        """A wrong id is said so, not answered with an empty card to fill in."""
        response = client.get(f"/api/pets/{ObjectId()}", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code in (403, 404)
