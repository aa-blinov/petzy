"""Tests for push subscription management (/api/push/*)."""

from unittest.mock import patch

import pytest

VALID_SUBSCRIBE_BODY = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
    "keys": {"p256dh": "test-p256dh-key", "auth": "test-auth-key"},
    "timezone": "Asia/Almaty",
}


@pytest.mark.push
class TestVapidPublicKey:
    def test_requires_authentication(self, client):
        response = client.get("/api/push/vapid-public-key")
        assert response.status_code == 401

    def test_returns_key_when_configured(self, client, mock_db, regular_user_token):
        with patch.dict("web.push.PUSH_CONFIG", {"vapid_public_key": "test-public-key"}):
            response = client.get(
                "/api/push/vapid-public-key", headers={"Authorization": f"Bearer {regular_user_token}"}
            )
        assert response.status_code == 200
        assert response.get_json()["public_key"] == "test-public-key"

    def test_not_configured_returns_422(self, client, mock_db, regular_user_token):
        with patch.dict("web.push.PUSH_CONFIG", {"vapid_public_key": None}):
            response = client.get(
                "/api/push/vapid-public-key", headers={"Authorization": f"Bearer {regular_user_token}"}
            )
        assert response.status_code == 422
        assert response.get_json()["code"] == "push_not_configured"


@pytest.mark.push
class TestSubscribe:
    def test_requires_authentication(self, client):
        response = client.post("/api/push/subscribe", json=VALID_SUBSCRIBE_BODY)
        assert response.status_code == 401

    def test_create_success(self, client, mock_db, regular_user_token):
        response = client.post(
            "/api/push/subscribe",
            json=VALID_SUBSCRIBE_BODY,
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200

        saved = mock_db.push_subscriptions.find_one({"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]})
        assert saved is not None
        assert saved["username"] == "testuser"
        assert saved["timezone"] == "Asia/Almaty"
        assert saved["keys"] == VALID_SUBSCRIBE_BODY["keys"]

    def test_resubscribe_same_endpoint_updates_in_place(self, client, mock_db, regular_user_token):
        headers = {"Authorization": f"Bearer {regular_user_token}"}
        client.post("/api/push/subscribe", json=VALID_SUBSCRIBE_BODY, headers=headers)

        updated_body = {**VALID_SUBSCRIBE_BODY, "timezone": "Europe/Moscow"}
        response = client.post("/api/push/subscribe", json=updated_body, headers=headers)
        assert response.status_code == 200

        assert mock_db.push_subscriptions.count_documents({"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]}) == 1
        saved = mock_db.push_subscriptions.find_one({"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]})
        assert saved["timezone"] == "Europe/Moscow"

    def test_missing_fields_returns_422(self, client, mock_db, regular_user_token):
        response = client.post(
            "/api/push/subscribe",
            json={"endpoint": "https://example.com/x"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "bad_endpoint",
        [
            "http://fcm.googleapis.com/fcm/send/abc",  # not https
            "https://169.254.169.254/latest/meta-data/",  # cloud metadata IP
            "https://internal-db.local/anything",  # arbitrary internal host
            "https://fcm.googleapis.com.evil.com/x",  # suffix-match bypass attempt
            "https://[::1]/x",  # IPv6 loopback literal
        ],
        ids=["not-https", "metadata-ip", "arbitrary-host", "suffix-bypass", "ipv6-literal"],
    )
    def test_rejects_endpoints_outside_known_push_services(self, client, mock_db, regular_user_token, bad_endpoint):
        """A subscribed endpoint is later POSTed to by the reminder sender
        on a schedule the subscriber fully controls — accepting anything
        but a real push service's own domain would make this a self-service
        SSRF / internal-network-probe primitive."""
        response = client.post(
            "/api/push/subscribe",
            json={**VALID_SUBSCRIBE_BODY, "endpoint": bad_endpoint},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 422
        assert mock_db.push_subscriptions.count_documents({}) == 0

    def test_reassigning_another_users_endpoint_is_logged(
        self, client, mock_db, regular_user_token, admin_token, caplog
    ):
        """Two accounts subscribing the same browser (a shared device) is
        legitimate Push API behavior, not something to block — but it
        should leave a trace instead of silently moving reminders from
        one account's device to another's."""
        client.post(
            "/api/push/subscribe",
            json=VALID_SUBSCRIBE_BODY,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        with caplog.at_level("WARNING"):
            response = client.post(
                "/api/push/subscribe",
                json=VALID_SUBSCRIBE_BODY,
                headers={"Authorization": f"Bearer {regular_user_token}"},
            )
        assert response.status_code == 200
        saved = mock_db.push_subscriptions.find_one({"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]})
        assert saved["username"] == "testuser"
        assert any("reassigned" in record.message and "admin" in record.message for record in caplog.records)


@pytest.mark.push
class TestUnsubscribe:
    def test_requires_authentication(self, client):
        response = client.post("/api/push/unsubscribe", json={"endpoint": "https://example.com/x"})
        assert response.status_code == 401

    def test_removes_own_subscription(self, client, mock_db, regular_user_token):
        headers = {"Authorization": f"Bearer {regular_user_token}"}
        client.post("/api/push/subscribe", json=VALID_SUBSCRIBE_BODY, headers=headers)
        assert mock_db.push_subscriptions.count_documents({}) == 1

        response = client.post(
            "/api/push/unsubscribe", json={"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]}, headers=headers
        )
        assert response.status_code == 200
        assert mock_db.push_subscriptions.count_documents({}) == 0

    def test_unsubscribing_missing_endpoint_is_not_an_error(self, client, mock_db, regular_user_token):
        response = client.post(
            "/api/push/unsubscribe",
            json={"endpoint": "https://example.com/never-subscribed"},
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        assert response.status_code == 200

    def test_cannot_unsubscribe_another_users_device(self, client, mock_db, regular_user_token, admin_token):
        # regular user subscribes their own device
        client.post(
            "/api/push/subscribe",
            json=VALID_SUBSCRIBE_BODY,
            headers={"Authorization": f"Bearer {regular_user_token}"},
        )
        # admin tries to unsubscribe it by replaying the same endpoint
        response = client.post(
            "/api/push/unsubscribe",
            json={"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        # ...but the row is untouched, since it's scoped to admin's own username
        assert mock_db.push_subscriptions.count_documents({"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]}) == 1
