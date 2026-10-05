"""Tests for the event-type registry (GET/POST/PUT/DELETE /api/event-types)."""

import pytest

from web.builtin_event_types import BUILTIN_TYPE_ORDER

BUILTIN_KEYS = set(BUILTIN_TYPE_ORDER)
# The original eight, which older installs and every old pet's tiles know by name.
ORIGINAL_KEYS = {
    "feeding",
    "weight",
    "asthma",
    "defecation",
    "litter",
    "eye_drops",
    "tooth_brushing",
    "ear_cleaning",
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
        assert ORIGINAL_KEYS <= BUILTIN_KEYS
        assert all(t["category"] for t in data)

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
        response = client.post("/api/event-types", json={"label": "Массаж", "icon": "paw", "color": "blue"})
        assert response.status_code == 401

    def test_create_success(self, client, mock_db, regular_user_token):
        response = client.post(
            "/api/event-types",
            json={
                "label": "Массаж",
                "icon": "paw",
                "color": "blue",
                "fields": [{"name": "duration_min", "label": "Длительность (мин)", "type": "number", "required": True}],
                "chart": {"kind": "count"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["key"].startswith("custom_")
        assert data["is_builtin"] is False
        assert data["label"] == "Массаж"

        stored = mock_db["event_types"].find_one({"key": data["key"]})
        assert stored["created_by"] == "testuser"

    def test_reserved_field_name_rejected(self, client, regular_user_token):
        response = client.post(
            "/api/event-types",
            json={
                "label": "x",
                "icon": "i",
                "color": "blue",
                "fields": [{"name": "pet_id", "label": "y", "type": "text"}],
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_duplicate_field_names_rejected(self, client, regular_user_token):
        response = client.post(
            "/api/event-types",
            json={
                "label": "x",
                "icon": "i",
                "color": "blue",
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
            json={
                "label": "x",
                "icon": "i",
                "color": "blue",
                "fields": [{"name": "s", "label": "S", "type": "select"}],
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_number_field_with_min_above_max_rejected(self, client, regular_user_token):
        response = client.post(
            "/api/event-types",
            json={
                "label": "x",
                "icon": "i",
                "color": "blue",
                "fields": [{"name": "n", "label": "N", "type": "number", "min": 10, "max": 5}],
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_number_field_with_bounds_accepted(self, client, mock_db, regular_user_token):
        response = client.post(
            "/api/event-types",
            json={
                "label": "x",
                "icon": "i",
                "color": "blue",
                "fields": [{"name": "n", "label": "N", "type": "number", "min": 0, "max": 100, "step": 1}],
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 201
        stored = mock_db["event_types"].find_one({"key": response.get_json()["key"]})
        assert stored["fields"][0]["min"] == 0
        assert stored["fields"][0]["max"] == 100


@pytest.mark.health_records
class TestWhatATypeMayBeCalledAndLookLike:
    BODY = {"label": "Массаж", "icon": "paw", "color": "blue", "fields": [], "chart": {"kind": "count"}}

    def _post(self, client, token, **patch):
        return client.post(
            "/api/event-types", json={**self.BODY, **patch}, headers={"Authorization": f"Bearer {token}"}
        )

    def test_a_name_of_spaces_is_refused_and_a_padded_one_is_trimmed(self, client, mock_db, regular_user_token):
        assert self._post(client, regular_user_token, label="   ").status_code == 422
        created = self._post(client, regular_user_token, label="  Массаж  ")
        assert created.status_code == 201 and created.get_json()["label"] == "Массаж"

    def test_a_name_that_is_taken_is_refused_whoever_took_it(self, client, mock_db, regular_user_token):
        assert self._post(client, regular_user_token).status_code == 201
        for same in ("Массаж", "  массаж ", "МАССАЖ"):
            response = self._post(client, regular_user_token, label=same)
            assert response.status_code == 422 and "уже есть" in response.get_json()["error"], same
        # and a built-in's name too: two tiles of one name cannot be told apart
        assert self._post(client, regular_user_token, label="кормление").status_code == 422

    def test_renaming_into_a_taken_name_is_refused_but_saving_a_type_as_it_is_is_not(
        self, client, mock_db, regular_user_token
    ):
        headers = {"Authorization": f"Bearer {regular_user_token}"}
        first = self._post(client, regular_user_token).get_json()["key"]
        second = self._post(client, regular_user_token, label="Выгул").get_json()["key"]
        assert client.put(f"/api/event-types/{second}", json={"label": "массаж"}, headers=headers).status_code == 422
        assert (
            client.put(
                f"/api/event-types/{second}", json={"label": "Выгул", "color": "red"}, headers=headers
            ).status_code
            == 200
        )
        assert client.put(f"/api/event-types/{first}", json={"label": "Массаж"}, headers=headers).status_code == 200

    def test_a_colour_the_app_does_not_have_is_refused(self, client, mock_db, regular_user_token):
        assert self._post(client, regular_user_token, label="Один", color="neon").status_code == 422
        assert self._post(client, regular_user_token, label="Два", color="red; background:url(x)").status_code == 422
        assert self._post(client, regular_user_token, label="Три", color="gray").status_code == 201

    def test_an_icon_key_is_a_plain_key(self, client, mock_db, regular_user_token):
        assert self._post(client, regular_user_token, label="Один", icon="<b>").status_code == 422
        assert self._post(client, regular_user_token, label="Два", icon="a b").status_code == 422
        assert self._post(client, regular_user_token, label="Три", icon="paw-print").status_code == 201

    def test_a_chart_of_values_needs_a_number_field_of_the_type(self, client, mock_db, regular_user_token):
        chart = {"kind": "value", "value_field": "dose", "value_label": "мл"}
        text_field = {"name": "dose", "label": "Доза", "type": "text", "required": False}
        number_field = {"name": "dose", "label": "Доза", "type": "number", "required": False}
        assert self._post(client, regular_user_token, label="Один", chart=chart, fields=[]).status_code == 422
        assert self._post(client, regular_user_token, label="Два", chart=chart, fields=[text_field]).status_code == 422
        assert (
            self._post(client, regular_user_token, label="Три", chart=chart, fields=[number_field]).status_code == 201
        )


@pytest.mark.health_records
class TestUpdateEventType:
    def test_update_builtin_label(self, client, mock_db, auth_headers):
        """A builtin type is everyone's: an admin may rename it."""
        response = client.put("/api/event-types/weight", json={"label": "Взвешивание"}, headers=auth_headers)
        assert response.status_code == 200
        assert response.get_json()["label"] == "Взвешивание"
        assert mock_db["event_types"].find_one({"key": "weight"})["label"] == "Взвешивание"

    def test_a_user_cannot_rename_a_builtin_for_everyone(self, client, mock_db, regular_user_token):
        before = mock_db["event_types"].find_one({"key": "weight"})["label"]
        response = client.put(
            "/api/event-types/weight",
            json={"label": "Взвешивание"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 403
        assert mock_db["event_types"].find_one({"key": "weight"})["label"] == before

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
            json={"label": "Массаж", "icon": "paw", "color": "blue", "fields": [], "chart": {"kind": "count"}},
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


@pytest.mark.health_records
class TestUsedTypes:
    def test_lists_only_the_types_the_pet_has_records_of(self, client, mock_db, regular_user_token, test_pet):
        headers = {"Authorization": f"Bearer {regular_user_token}"}
        base = {"pet_id": str(test_pet["_id"]), "date": "2026-10-01", "time": "08:00"}
        assert (
            client.post(
                "/api/events", json={**base, "type": "feeding", "fields": {"food_weight": 100}}, headers=headers
            ).status_code
            == 201
        )
        assert (
            client.post(
                "/api/events",
                json={**base, "type": "litter", "fields": {"litter_type": "Комкующийся"}},
                headers=headers,
            ).status_code
            == 201
        )
        response = client.get(f"/api/events/used-types?pet_id={test_pet['_id']}", headers=headers)
        assert response.status_code == 200
        assert response.get_json() == {"types": ["feeding", "litter"]}

    def test_someone_else_s_pet_is_refused(self, client, mock_db, regular_user_token, admin_pet):
        response = client.get(
            f"/api/events/used-types?pet_id={admin_pet['_id']}",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code in (403, 404)
