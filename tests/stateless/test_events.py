"""Tests for the generic events CRUD (create/list/get/update/delete).

Replaces the old per-type test suites (test_health.py, test_health_records.py)
that hit /api/asthma, /api/defecation, etc. — one route now serves every
builtin and custom event type, so these tests exercise it generically and
per-type only where the type's own field validation differs.
"""

import pytest
from datetime import datetime, timezone


@pytest.mark.health_records
class TestCreateEvent:
    """POST /api/events"""

    def test_requires_authentication(self, client):
        response = client.post(
            "/api/events",
            json={"pet_id": "507f1f77bcf86cd799439011", "type": "defecation", "date": "2024-01-01", "time": "12:00"},
        )
        assert response.status_code == 401

    def test_requires_pet_id(self, client, regular_user_token):
        response = client.post(
            "/api/events",
            json={"type": "defecation", "date": "2024-01-01", "time": "12:00"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_requires_pet_access(self, client, mock_db, regular_user_token, admin_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(admin_pet["_id"]), "type": "defecation",
                "date": "2024-01-01", "time": "12:00", "fields": {"stool_type": "Обычный", "color": "Коричневый"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 403

    def test_unknown_type_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={"pet_id": str(test_pet["_id"]), "type": "nonexistent", "date": "2024-01-01", "time": "12:00"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 404

    def test_create_success_stores_fields_nested(self, client, mock_db, regular_user_token, test_pet):
        now = datetime.now(timezone.utc)
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "asthma",
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M"),
                "fields": {"duration": "Короткий", "reason": "Стресс", "inhalation": "true"},
                "comment": "Test attack",
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert "Приступ астмы" in data["message"]

        record = mock_db["events"].find_one({"pet_id": str(test_pet["_id"]), "type": "asthma"})
        assert record is not None
        assert record["fields"]["duration"] == "Короткий"
        assert record["fields"]["reason"] == "Стресс"
        assert record["fields"]["inhalation"] == "true"
        assert record["comment"] == "Test attack"
        assert record["username"] == "testuser"

    def test_missing_required_field_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]), "type": "defecation",
                "date": "2024-01-15", "time": "14:30", "fields": {},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_invalid_select_value_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]), "type": "defecation",
                "date": "2024-01-15", "time": "14:30",
                "fields": {"stool_type": "Не существует", "color": "Коричневый"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_non_numeric_number_field_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]), "type": "weight",
                "date": "2024-01-15", "time": "14:30", "fields": {"weight": "not-a-number"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_unknown_field_keys_are_dropped_not_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]), "type": "litter",
                "date": "2024-01-15", "time": "14:30", "fields": {"bogus_field": "x"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 201
        record = mock_db["events"].find_one({"pet_id": str(test_pet["_id"]), "type": "litter"})
        assert "bogus_field" not in record["fields"]

    def test_no_fields_type_creates_ok(self, client, mock_db, regular_user_token, test_pet):
        """`litter` has no extra fields at all."""
        response = client.post(
            "/api/events",
            json={"pet_id": str(test_pet["_id"]), "type": "litter", "date": "2024-01-15", "time": "14:30"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 201


@pytest.mark.health_records
class TestListEvents:
    """GET /api/events"""

    def test_requires_authentication(self, client):
        response = client.get("/api/events?pet_id=507f1f77bcf86cd799439011")
        assert response.status_code == 401

    def test_requires_pet_id(self, client, regular_user_token):
        response = client.get("/api/events", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 422

    def test_list_filtered_by_type(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "weight", "date_time": datetime.now(timezone.utc),
            "fields": {"weight": 4.5}, "comment": "", "username": "testuser",
        })
        mock_db["events"].insert_one({
            "pet_id": pet_id, "type": "feeding", "date_time": datetime.now(timezone.utc),
            "fields": {"food_weight": 50}, "comment": "", "username": "testuser",
        })

        response = client.get(
            f"/api/events?pet_id={pet_id}&type=weight",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == 1
        assert data["items"][0]["fields"]["weight"] == 4.5

    def test_list_without_type_returns_all(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        for t in ("weight", "feeding"):
            mock_db["events"].insert_one({
                "pet_id": pet_id, "type": t, "date_time": datetime.now(timezone.utc),
                "fields": {}, "comment": "", "username": "testuser",
            })
        response = client.get(f"/api/events?pet_id={pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 200
        assert response.get_json()["total"] == 2

    def test_pagination(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        for i in range(5):
            mock_db["events"].insert_one({
                "pet_id": pet_id, "type": "litter", "date_time": datetime.now(timezone.utc),
                "fields": {}, "comment": f"{i}", "username": "testuser",
            })

        response = client.get(
            f"/api/events?pet_id={pet_id}&page=1&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        data = response.get_json()
        assert len(data["items"]) == 2
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total"] == 5

        response = client.get(
            f"/api/events?pet_id={pet_id}&page=3&page_size=2",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        data = response.get_json()
        assert len(data["items"]) == 1
        assert data["page"] == 3


@pytest.mark.health_records
class TestGetUpdateDeleteEvent:
    """GET/PUT/DELETE /api/events/<id>"""

    def _create(self, client, token, pet_id, event_type="weight", fields=None):
        response = client.post(
            "/api/events",
            json={
                "pet_id": pet_id, "type": event_type, "date": "2024-01-15", "time": "14:30",
                "fields": fields or {"weight": 4.5},
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        return client.get(
            f"/api/events?pet_id={pet_id}&type={event_type}",
            headers={"Authorization": f"Bearer {token}"},
        ).get_json()["items"][0]["_id"]

    def test_get_one_success(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        event_id = self._create(client, regular_user_token, pet_id)
        response = client.get(f"/api/events/{event_id}", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 200
        assert response.get_json()["fields"]["weight"] == 4.5

    def test_get_one_not_found(self, client, mock_db, regular_user_token):
        response = client.get(
            "/api/events/507f1f77bcf86cd799439011",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 404

    def test_get_one_no_access(self, client, mock_db, regular_user_token, admin_pet, admin_token):
        event_id = self._create(client, admin_token, str(admin_pet["_id"]))
        response = client.get(f"/api/events/{event_id}", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 403

    def test_update_success(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        event_id = self._create(client, regular_user_token, pet_id)

        response = client.put(
            f"/api/events/{event_id}",
            json={"date": "2024-01-16", "time": "10:00", "fields": {"weight": 5.0}, "comment": "updated"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        assert "Вес" in response.get_json()["message"]

        record = mock_db["events"].find_one({"pet_id": pet_id})
        assert record["fields"]["weight"] == 5.0
        assert record["comment"] == "updated"

    def test_update_not_found(self, client, regular_user_token):
        response = client.put(
            "/api/events/507f1f77bcf86cd799439011",
            json={"date": "2024-01-16", "time": "10:00"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 404

    def test_delete_success(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        event_id = self._create(client, regular_user_token, pet_id)

        response = client.delete(f"/api/events/{event_id}", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 200
        assert mock_db["events"].count_documents({}) == 0

    def test_delete_not_found(self, client, regular_user_token):
        response = client.delete(
            "/api/events/507f1f77bcf86cd799439011",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 404
