"""Tests for the event-type registry (GET/POST/PUT/DELETE /api/event-types)."""

import pytest

BUILTIN_KEYS = {
    "feeding", "weight", "asthma", "defecation", "litter",
    "eye_drops", "tooth_brushing", "ear_cleaning",
}


@pytest.mark.health_records
class TestListEventTypes:
    def test_requires_authentication(self, client):
        response = client.get("/api/event-types")
        assert response.status_code == 401

    def test_returns_all_builtin_types(self, client, mock_db, regular_user_token):
        response = client.get("/api/event-types", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 200
        data = response.get_json()["event_types"]
        assert {t["key"] for t in data} == BUILTIN_KEYS
        assert all(t["is_builtin"] for t in data)

        defecation = next(t for t in data if t["key"] == "defecation")
        field_names = {f["name"] for f in defecation["fields"]}
        assert field_names == {"stool_type", "color", "food"}
        assert defecation["chart"] == {"kind": "count", "value_field": None, "value_label": None}

        weight = next(t for t in data if t["key"] == "weight")
        assert weight["chart"]["kind"] == "value"
        assert weight["chart"]["value_field"] == "weight"


@pytest.mark.health_records
class TestCreateEventType:
    def test_requires_authentication(self, client):
        response = client.post("/api/event-types", json={"label": "Игра", "icon": "paw", "color": "blue"})
        assert response.status_code == 401

    def test_create_success(self, client, mock_db, regular_user_token):
        response = client.post(
            "/api/event-types",
            json={
                "label": "Игра", "icon": "paw", "color": "blue",
                "fields": [{"name": "duration_min", "label": "Длительность (мин)", "type": "number", "required": True}],
                "chart": {"kind": "count"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["key"].startswith("custom_")
        assert data["is_builtin"] is False
        assert data["label"] == "Игра"

        stored = mock_db["event_types"].find_one({"key": data["key"]})
        assert stored["created_by"] == "testuser"

    def test_reserved_field_name_rejected(self, client, regular_user_token):
        response = client.post(
            "/api/event-types",
            json={"label": "x", "icon": "i", "color": "blue", "fields": [{"name": "pet_id", "label": "y", "type": "text"}]},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_duplicate_field_names_rejected(self, client, regular_user_token):
        response = client.post(
            "/api/event-types",
            json={
                "label": "x", "icon": "i", "color": "blue",
                "fields": [
                    {"name": "dup", "label": "a", "type": "text"},
                    {"name": "dup", "label": "b", "type": "text"},
                ],
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_select_without_options_rejected(self, client, regular_user_token):
        response = client.post(
            "/api/event-types",
            json={"label": "x", "icon": "i", "color": "blue", "fields": [{"name": "s", "label": "S", "type": "select"}]},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422


@pytest.mark.health_records
class TestUpdateEventType:
    def test_update_builtin_label(self, client, mock_db, regular_user_token):
        response = client.put(
            "/api/event-types/weight",
            json={"label": "Взвешивание"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        assert response.get_json()["label"] == "Взвешивание"
        assert mock_db["event_types"].find_one({"key": "weight"})["label"] == "Взвешивание"

    def test_update_not_found(self, client, regular_user_token):
        response = client.put(
            "/api/event-types/nonexistent",
            json={"label": "x"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 404


@pytest.mark.health_records
class TestDeleteEventType:
    def _create_custom(self, client, token):
        response = client.post(
            "/api/event-types",
            json={"label": "Игра", "icon": "paw", "color": "blue", "fields": [], "chart": {"kind": "count"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        return response.get_json()["key"]

    def test_cannot_delete_builtin(self, client, regular_user_token):
        response = client.delete("/api/event-types/weight", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 422

    def test_delete_custom_without_events(self, client, mock_db, regular_user_token):
        key = self._create_custom(client, regular_user_token)
        response = client.delete(f"/api/event-types/{key}", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 200
        assert mock_db["event_types"].find_one({"key": key}) is None

    def test_cannot_delete_custom_with_events(self, client, mock_db, regular_user_token, test_pet):
        key = self._create_custom(client, regular_user_token)
        client.post(
            "/api/events",
            json={"pet_id": str(test_pet["_id"]), "type": key, "date": "2024-01-15", "time": "14:30"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        response = client.delete(f"/api/event-types/{key}", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 422
        assert mock_db["event_types"].find_one({"key": key}) is not None

    def test_delete_not_found(self, client, regular_user_token):
        response = client.delete(
            "/api/event-types/nonexistent",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 404
