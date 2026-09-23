"""Tests for the generic events CRUD (create/list/get/update/delete).

Replaces the old per-type test suites (test_health.py, test_health_records.py)
that hit /api/asthma, /api/defecation, etc. — one route now serves every
builtin and custom event type, so these tests exercise it generically and
per-type only where the type's own field validation differs.
"""

import pytest
from datetime import datetime, timezone, timedelta


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
                "pet_id": str(admin_pet["_id"]),
                "type": "defecation",
                "date": "2024-01-01",
                "time": "12:00",
                "fields": {"stool_type": "Обычный", "color": "Коричневый"},
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
                "pet_id": str(test_pet["_id"]),
                "type": "defecation",
                "date": "2024-01-15",
                "time": "14:30",
                "fields": {},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_invalid_select_value_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "defecation",
                "date": "2024-01-15",
                "time": "14:30",
                "fields": {"stool_type": "Не существует", "color": "Коричневый"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_non_numeric_number_field_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date": "2024-01-15",
                "time": "14:30",
                "fields": {"weight": "not-a-number"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_number_field_below_min_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date": "2024-01-15",
                "time": "14:30",
                "fields": {"weight": -1},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_number_field_above_max_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date": "2024-01-15",
                "time": "14:30",
                # weight's builtin bound is max=100 — a fat-fingered extra
                # digit like this must not be accepted as a real weight.
                "fields": {"weight": 5000},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_number_field_within_bounds_accepted(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date": "2024-01-15",
                "time": "14:30",
                # Comfortably above a small pet but still a realistic large
                # dog breed — and still well under the max=100 bound.
                "fields": {"weight": 38.5},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 201

    def test_number_field_with_only_a_min_rejects_negative(self, client, mock_db, regular_user_token, test_pet):
        # feeding's food_weight declares min=0 but no max — the negative
        # side is still worth rejecting even without an upper bound.
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "feeding",
                "date": "2024-01-15",
                "time": "14:30",
                "fields": {"food_weight": -5},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_unknown_field_keys_are_dropped_not_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "litter",
                "date": "2024-01-15",
                "time": "14:30",
                "fields": {"bogus_field": "x"},
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


def _insert_prior_weight_events(mock_db, pet_id, values):
    for i, v in enumerate(values):
        mock_db.events.insert_one(
            {
                "pet_id": str(pet_id),
                "type": "weight",
                "date_time": datetime(2024, 1, 1 + i),
                "fields": {"weight": v},
            }
        )


def _subscribe_owner(mock_db, username="testuser", endpoint="https://push.example/owner-device"):
    mock_db.push_subscriptions.insert_one(
        {
            "username": username,
            "endpoint": endpoint,
            "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
            "timezone": "UTC",
        }
    )


@pytest.mark.health_records
class TestCreateEventTrendAlert:
    """POST /api/events also pushes the pet's subscribers when the new
    reading looks abnormal against that pet's own recent history for a
    numeric ("value" chart) field — see web/trend_alerts.py."""

    def test_abnormal_weight_sends_a_push(self, client, mock_db, regular_user_token, test_pet):
        _insert_prior_weight_events(mock_db, test_pet["_id"], [5.0, 5.0, 5.0, 5.0])
        _subscribe_owner(mock_db)

        from unittest.mock import patch

        with (
            patch.dict("web.events.PUSH_CONFIG", {"vapid_private_key": "fake-key", "vapid_claims_email": "a@b.c"}),
            patch("web.push_delivery.webpush") as mock_webpush,
        ):
            response = client.post(
                "/api/events",
                json={
                    "pet_id": str(test_pet["_id"]),
                    "type": "weight",
                    "date": "2024-01-10",
                    "time": "10:00",
                    "fields": {"weight": 6.5},  # +30% vs. the 5.0 average
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 201
        mock_webpush.assert_called_once()
        assert mock_webpush.call_args.kwargs["subscription_info"]["endpoint"] == "https://push.example/owner-device"
        import json as json_module

        payload = json_module.loads(mock_webpush.call_args.kwargs["data"])
        assert "6.5" in payload["body"]
        assert "5.0" in payload["body"]

    def test_normal_weight_sends_no_push(self, client, mock_db, regular_user_token, test_pet):
        _insert_prior_weight_events(mock_db, test_pet["_id"], [5.0, 5.0, 5.0, 5.0])
        _subscribe_owner(mock_db)

        from unittest.mock import patch

        with (
            patch.dict("web.events.PUSH_CONFIG", {"vapid_private_key": "fake-key"}),
            patch("web.push_delivery.webpush") as mock_webpush,
        ):
            response = client.post(
                "/api/events",
                json={
                    "pet_id": str(test_pet["_id"]),
                    "type": "weight",
                    "date": "2024-01-10",
                    "time": "10:00",
                    "fields": {"weight": 5.1},
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 201
        mock_webpush.assert_not_called()

    def test_not_enough_history_sends_no_push(self, client, mock_db, regular_user_token, test_pet):
        _insert_prior_weight_events(mock_db, test_pet["_id"], [5.0])  # only 1, need 3
        _subscribe_owner(mock_db)

        from unittest.mock import patch

        with (
            patch.dict("web.events.PUSH_CONFIG", {"vapid_private_key": "fake-key"}),
            patch("web.push_delivery.webpush") as mock_webpush,
        ):
            response = client.post(
                "/api/events",
                json={
                    "pet_id": str(test_pet["_id"]),
                    "type": "weight",
                    "date": "2024-01-10",
                    "time": "10:00",
                    "fields": {"weight": 50.0},
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 201
        mock_webpush.assert_not_called()

    def test_push_not_configured_sends_no_push(self, client, mock_db, regular_user_token, test_pet):
        """Push is an optional, self-hostable feature — an abnormal
        reading must never fail event creation just because no VAPID key
        is configured on this deployment."""
        _insert_prior_weight_events(mock_db, test_pet["_id"], [5.0, 5.0, 5.0, 5.0])
        _subscribe_owner(mock_db)

        from unittest.mock import patch

        with (
            patch.dict("web.events.PUSH_CONFIG", {"vapid_private_key": None}),
            patch("web.push_delivery.webpush") as mock_webpush,
        ):
            response = client.post(
                "/api/events",
                json={
                    "pet_id": str(test_pet["_id"]),
                    "type": "weight",
                    "date": "2024-01-10",
                    "time": "10:00",
                    "fields": {"weight": 6.5},
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 201
        mock_webpush.assert_not_called()

    def test_count_type_event_never_checked(self, client, mock_db, regular_user_token, test_pet):
        """asthma is a `count`-chart type — it has no numeric value_field,
        so there's nothing here to compare against a "normal" average."""
        for i in range(5):
            mock_db.events.insert_one(
                {
                    "pet_id": str(test_pet["_id"]),
                    "type": "asthma",
                    "date_time": datetime(2024, 1, 1 + i),
                    "fields": {"duration": "Короткий", "inhalation": "false", "reason": "x"},
                }
            )
        _subscribe_owner(mock_db)

        from unittest.mock import patch

        with (
            patch.dict("web.events.PUSH_CONFIG", {"vapid_private_key": "fake-key"}),
            patch("web.push_delivery.webpush") as mock_webpush,
        ):
            response = client.post(
                "/api/events",
                json={
                    "pet_id": str(test_pet["_id"]),
                    "type": "asthma",
                    "date": "2024-01-10",
                    "time": "10:00",
                    "fields": {"duration": "Длительный", "inhalation": "true", "reason": "y"},
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 201
        mock_webpush.assert_not_called()

    def test_shared_user_is_also_notified(self, client, mock_db, regular_user_token, test_pet):
        mock_db["pets"].update_one({"_id": test_pet["_id"]}, {"$set": {"shared_with": ["frienduser"]}})
        _insert_prior_weight_events(mock_db, test_pet["_id"], [5.0, 5.0, 5.0, 5.0])
        _subscribe_owner(mock_db, username="testuser", endpoint="https://push.example/owner-device")
        _subscribe_owner(mock_db, username="frienduser", endpoint="https://push.example/friend-device")

        from unittest.mock import patch

        with (
            patch.dict("web.events.PUSH_CONFIG", {"vapid_private_key": "fake-key"}),
            patch("web.push_delivery.webpush") as mock_webpush,
        ):
            response = client.post(
                "/api/events",
                json={
                    "pet_id": str(test_pet["_id"]),
                    "type": "weight",
                    "date": "2024-01-10",
                    "time": "10:00",
                    "fields": {"weight": 6.5},
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 201
        assert mock_webpush.call_count == 2
        notified_endpoints = {c.kwargs["subscription_info"]["endpoint"] for c in mock_webpush.call_args_list}
        assert notified_endpoints == {"https://push.example/owner-device", "https://push.example/friend-device"}

    def test_a_push_failure_does_not_fail_the_request(self, client, mock_db, regular_user_token, test_pet):
        """The event itself must still be saved and the request must still
        succeed even if sending the follow-up push blows up."""
        _insert_prior_weight_events(mock_db, test_pet["_id"], [5.0, 5.0, 5.0, 5.0])
        _subscribe_owner(mock_db)

        from unittest.mock import patch

        with (
            patch.dict("web.events.PUSH_CONFIG", {"vapid_private_key": "fake-key"}),
            patch("web.push_delivery.webpush", side_effect=RuntimeError("network is down")),
        ):
            response = client.post(
                "/api/events",
                json={
                    "pet_id": str(test_pet["_id"]),
                    "type": "weight",
                    "date": "2024-01-10",
                    "time": "10:00",
                    "fields": {"weight": 6.5},
                },
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )

        assert response.status_code == 201
        assert mock_db["events"].find_one({"type": "weight", "fields.weight": 6.5}) is not None


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
        mock_db["events"].insert_one(
            {
                "pet_id": pet_id,
                "type": "weight",
                "date_time": datetime.now(timezone.utc),
                "fields": {"weight": 4.5},
                "comment": "",
                "username": "testuser",
            }
        )
        mock_db["events"].insert_one(
            {
                "pet_id": pet_id,
                "type": "feeding",
                "date_time": datetime.now(timezone.utc),
                "fields": {"food_weight": 50},
                "comment": "",
                "username": "testuser",
            }
        )

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
            mock_db["events"].insert_one(
                {
                    "pet_id": pet_id,
                    "type": t,
                    "date_time": datetime.now(timezone.utc),
                    "fields": {},
                    "comment": "",
                    "username": "testuser",
                }
            )
        response = client.get(f"/api/events?pet_id={pet_id}", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 200
        assert response.get_json()["total"] == 2

    def test_pagination(self, client, mock_db, regular_user_token, test_pet):
        pet_id = str(test_pet["_id"])
        for i in range(5):
            mock_db["events"].insert_one(
                {
                    "pet_id": pet_id,
                    "type": "litter",
                    "date_time": datetime.now(timezone.utc),
                    "fields": {},
                    "comment": f"{i}",
                    "username": "testuser",
                }
            )

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
                "pet_id": pet_id,
                "type": event_type,
                "date": "2024-01-15",
                "time": "14:30",
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


@pytest.mark.health_records
class TestCreateEventDatetimeValidation:
    def test_invalid_date_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "feeding",
                "date": "not-a-date",
                "time": "12:00",
                "fields": {},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422


@pytest.mark.health_records
class TestUpdateEventEdgeCases:
    def test_update_rejects_invalid_datetime(self, client, mock_db, regular_user_token, test_pet):
        create_resp = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "feeding",
                "date": "2024-01-01",
                "time": "12:00",
                "fields": {"food_weight": 50},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert create_resp.status_code == 201
        record_id = str(mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["_id"])

        response = client.put(
            f"/api/events/{record_id}",
            json={"date": "not-a-date", "time": "12:00"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_update_rejects_invalid_field_value(self, client, mock_db, regular_user_token, test_pet):
        create_resp = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date": "2024-01-01",
                "time": "12:00",
                "fields": {"weight": 4.5},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert create_resp.status_code == 201
        record_id = str(mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["_id"])

        response = client.put(
            f"/api/events/{record_id}",
            json={"date": "2024-01-01", "time": "12:00", "fields": {"weight": "not-a-number"}},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_update_when_event_type_deleted_from_registry(self, client, mock_db, regular_user_token, test_pet):
        """An event referencing a type that's since been removed from the
        registry (a custom type, deleted after events using it already
        existed) can't be validated against fields that no longer exist
        anywhere — update must fail cleanly instead of crashing."""
        create_resp = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "feeding",
                "date": "2024-01-01",
                "time": "12:00",
                "fields": {"food_weight": 50},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert create_resp.status_code == 201
        record_id = str(mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["_id"])

        mock_db["event_types"].delete_one({"key": "feeding"})

        response = client.put(
            f"/api/events/{record_id}",
            json={"date": "2024-01-01", "time": "12:00"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 404


@pytest.mark.health_records
class TestUpdateEventTypeFields:
    """PUT /api/event-types/<key> — only the label-update case was covered
    before this class; icon/color/fields/chart each has its own `if` branch."""

    def test_update_icon_and_color(self, client, mock_db, regular_user_token):
        response = client.put(
            "/api/event-types/feeding",
            json={"icon": "star", "color": "purple"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        updated = mock_db["event_types"].find_one({"key": "feeding"})
        assert updated["icon"] == "star"
        assert updated["color"] == "purple"

    def test_update_fields_and_chart(self, client, mock_db, regular_user_token):
        response = client.put(
            "/api/event-types/feeding",
            json={
                "fields": [{"name": "amount", "label": "Amount", "type": "number", "required": True}],
                "chart": {"kind": "value", "value_field": "amount", "value_label": "Amount"},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        updated = mock_db["event_types"].find_one({"key": "feeding"})
        assert updated["fields"][0]["name"] == "amount"
        assert updated["chart"]["kind"] == "value"


@pytest.mark.health_records
class TestGetHealthStats:
    """GET /api/stats/health — powers the History chart. Untested before
    this class."""

    def test_requires_pet_access(self, client, mock_db, regular_user_token, admin_pet):
        response = client.get(
            f"/api/stats/health?pet_id={admin_pet['_id']}&type=feeding",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 403

    def test_invalid_type_rejected(self, client, mock_db, regular_user_token, test_pet):
        response = client.get(
            f"/api/stats/health?pet_id={test_pet['_id']}&type=not_a_real_type",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_count_type_returns_one_point_per_event(self, client, mock_db, regular_user_token, test_pet):
        now = datetime.now(timezone.utc)
        mock_db["events"].insert_many(
            [
                {
                    "pet_id": str(test_pet["_id"]),
                    "type": "asthma",
                    "date_time": now,
                    "fields": {"duration": "Короткий", "inhalation": "false", "reason": "test"},
                    "comment": "",
                    "username": "testuser",
                }
                for _ in range(3)
            ]
        )

        response = client.get(
            f"/api/stats/health?pet_id={test_pet['_id']}&type=asthma&days=30",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert len(data) == 3
        assert all(point["value"] == 1 for point in data)

    def test_value_type_returns_field_value(self, client, mock_db, regular_user_token, test_pet):
        now = datetime.now(timezone.utc)
        mock_db["events"].insert_one(
            {
                "pet_id": str(test_pet["_id"]),
                "type": "weight",
                "date_time": now,
                "fields": {"weight": 4.2},
                "comment": "",
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/stats/health?pet_id={test_pet['_id']}&type=weight&days=30",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert data[0]["value"] == 4.2

    def test_medications_type_counts_intakes(self, client, mock_db, regular_user_token, test_pet):
        from bson import ObjectId

        med_id = ObjectId()
        mock_db["medications"].insert_one(
            {"_id": med_id, "pet_id": str(test_pet["_id"]), "name": "M", "owner": "testuser"}
        )
        mock_db["medication_intakes"].insert_one(
            {
                "medication_id": str(med_id),
                "pet_id": str(test_pet["_id"]),
                "dose_taken": 1.0,
                "date_time": datetime.now(timezone.utc),
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/stats/health?pet_id={test_pet['_id']}&type=medications&days=30",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        assert len(response.get_json()["data"]) == 1


@pytest.mark.health_records
class TestTimelineToleratesMalformedMedicationId:
    def test_unparseable_medication_id_is_skipped_not_crashed(self, client, mock_db, regular_user_token, test_pet):
        """A medication_intake row with a corrupt medication_id (not a
        valid ObjectId) shouldn't crash the whole timeline — its name is
        just left unresolved."""
        pet_id = str(test_pet["_id"])
        mock_db["medication_intakes"].insert_one(
            {
                "pet_id": pet_id,
                "medication_id": "not-a-valid-object-id",
                "dose_taken": 1.0,
                "date_time": datetime.now(timezone.utc),
                "username": "testuser",
            }
        )

        response = client.get(
            f"/api/history/timeline?pet_id={pet_id}&page=1&page_size=20",
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200
        items = response.get_json()["items"]
        assert len(items) == 1
        assert "medication_name" not in items[0]


@pytest.mark.health_records
class TestEventDatetimeCombinedBoundsCheck:
    """The date and time fields each pass their own Pydantic format/range
    validator independently (date compared at midnight), but the route
    additionally combines date+time into one instant and re-checks the
    future bound — a combination that can fail even when both fields
    individually passed. "Tomorrow 23:59" only demonstrates this right
    at the boundary (it's already >24h out only late enough in the day),
    so these use the day after tomorrow — always outside the 1-day bound
    regardless of what time the suite happens to run.
    """

    def test_create_event_rejects_combined_datetime_too_far_future(self, client, mock_db, regular_user_token, test_pet):
        day_after_tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
        response = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "feeding",
                "date": day_after_tomorrow,
                "time": "23:59",
                "fields": {"food_weight": 50},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    def test_update_event_rejects_combined_datetime_too_far_future(self, client, mock_db, regular_user_token, test_pet):
        create_resp = client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "feeding",
                "date": "2024-01-01",
                "time": "12:00",
                "fields": {"food_weight": 50},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert create_resp.status_code == 201
        record_id = str(mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["_id"])

        day_after_tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
        response = client.put(
            f"/api/events/{record_id}",
            json={"date": day_after_tomorrow, "time": "23:59"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422


@pytest.mark.health_records
class TestEventRouteRaceConditionsAndErrors:
    def test_get_event_unexpected_error(self, client, mock_db, regular_user_token, test_pet):
        from unittest.mock import patch

        client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "feeding",
                "date": "2024-01-01",
                "time": "12:00",
                "fields": {"food_weight": 50},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        record_id = str(mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["_id"])

        with patch("web.events._serialize_event", side_effect=RuntimeError("boom")):
            response = client.get(
                f"/api/events/{record_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 500

    def test_update_event_race_condition_reports_not_found(self, client, mock_db, regular_user_token, test_pet):
        """The record existed for @require_record_access's own lookup but
        vanished (concurrent delete) before this handler's own
        update_one ran."""
        import web.app as app
        from unittest.mock import patch, MagicMock

        client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "feeding",
                "date": "2024-01-01",
                "time": "12:00",
                "fields": {"food_weight": 50},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        record_id = str(mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["_id"])

        with patch.object(app.db.events, "update_one", return_value=MagicMock(matched_count=0)):
            response = client.put(
                f"/api/events/{record_id}",
                json={"date": "2024-01-02", "time": "12:00"},
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 404

    def test_delete_event_race_condition_reports_not_found(self, client, mock_db, regular_user_token, test_pet):
        import web.app as app
        from unittest.mock import patch, MagicMock

        client.post(
            "/api/events",
            json={
                "pet_id": str(test_pet["_id"]),
                "type": "feeding",
                "date": "2024-01-01",
                "time": "12:00",
                "fields": {"food_weight": 50},
            },
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        record_id = str(mock_db["events"].find_one({"pet_id": str(test_pet["_id"])})["_id"])

        with patch.object(app.db.events, "delete_one", return_value=MagicMock(deleted_count=0)):
            response = client.delete(
                f"/api/events/{record_id}",
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 404
