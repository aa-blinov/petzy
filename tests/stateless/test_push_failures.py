"""A push subscription that cannot be saved is told so, and the server does not fall over (web/push.py).

The subscription rows are what the reminder sender reads, so a write that fails has to answer with an
error rather than a letterless success, and it has to say in the log that it was the save that failed
"""

import logging
from unittest.mock import patch

import pytest

VALID_SUBSCRIBE_BODY = {
    "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
    "keys": {"p256dh": "test-p256dh-key", "auth": "test-auth-key"},
    "timezone": "Asia/Almaty",
}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.push
class TestASubscriptionThatCannotBeSaved:
    def test_a_save_that_fails_answers_with_an_error(self, client, mock_db, regular_user_token, caplog):
        caplog.set_level(logging.ERROR)

        with patch.object(mock_db.push_subscriptions, "update_one", side_effect=RuntimeError("no connection")):
            response = client.post("/api/push/subscribe", json=VALID_SUBSCRIBE_BODY, headers=_auth(regular_user_token))

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"

    def test_the_log_says_the_save_failed(self, client, mock_db, regular_user_token, caplog):
        caplog.set_level(logging.ERROR)

        with patch.object(mock_db.push_subscriptions, "update_one", side_effect=RuntimeError("no connection")):
            client.post("/api/push/subscribe", json=VALID_SUBSCRIBE_BODY, headers=_auth(regular_user_token))

        assert "Error saving push subscription: no connection" in caplog.text

    def test_nothing_is_written_when_the_save_fails(self, client, mock_db, regular_user_token):
        with patch.object(mock_db.push_subscriptions, "update_one", side_effect=RuntimeError("no connection")):
            client.post("/api/push/subscribe", json=VALID_SUBSCRIBE_BODY, headers=_auth(regular_user_token))

        assert mock_db.push_subscriptions.count_documents({}) == 0


@pytest.mark.push
class TestARemovalThatCannotBeDone:
    def test_a_removal_that_fails_answers_with_an_error(self, client, mock_db, regular_user_token, caplog):
        caplog.set_level(logging.ERROR)
        client.post("/api/push/subscribe", json=VALID_SUBSCRIBE_BODY, headers=_auth(regular_user_token))

        with patch.object(mock_db.push_subscriptions, "delete_one", side_effect=RuntimeError("no connection")):
            response = client.post(
                "/api/push/unsubscribe",
                json={"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]},
                headers=_auth(regular_user_token),
            )

        assert response.status_code == 500
        assert response.get_json()["code"] == "internal_error"

    def test_the_log_says_the_removal_failed(self, client, mock_db, regular_user_token, caplog):
        caplog.set_level(logging.ERROR)
        client.post("/api/push/subscribe", json=VALID_SUBSCRIBE_BODY, headers=_auth(regular_user_token))

        with patch.object(mock_db.push_subscriptions, "delete_one", side_effect=RuntimeError("no connection")):
            client.post(
                "/api/push/unsubscribe",
                json={"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]},
                headers=_auth(regular_user_token),
            )

        assert "Error removing push subscription: no connection" in caplog.text

    def test_the_subscription_stays_when_the_removal_fails(self, client, mock_db, regular_user_token):
        client.post("/api/push/subscribe", json=VALID_SUBSCRIBE_BODY, headers=_auth(regular_user_token))

        with patch.object(mock_db.push_subscriptions, "delete_one", side_effect=RuntimeError("no connection")):
            client.post(
                "/api/push/unsubscribe",
                json={"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]},
                headers=_auth(regular_user_token),
            )

        assert mock_db.push_subscriptions.count_documents({"endpoint": VALID_SUBSCRIBE_BODY["endpoint"]}) == 1
