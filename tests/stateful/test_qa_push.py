"""Push: a reminder is lost only when a push reached a device, and nothing goes to an account that was switched off (QA B-01, B-06)."""

from unittest.mock import MagicMock, patch

import pytest
from pywebpush import WebPushException

import scripts.send_medication_reminders as sender
from scripts.send_medication_reminders import send_reminders
from tests.stateful.test_send_medication_reminders import (
    DUE_NOW_UTC,
    _make_medication,
    _make_pet,
    _subscribe,
)
from web.push_delivery import get_pet_push_subscriptions

CLAIMS = {"sub": "mailto:test@example.com"}


@pytest.fixture(autouse=True)
def _any_hour_of_the_day(monkeypatch):
    monkeypatch.setattr("scripts.send_medication_reminders.DATE_REMINDER_HOUR", 0)


@pytest.mark.push
class TestAFailedDeliveryIsTriedAgain:
    def test_a_dose_whose_push_failed_is_not_recorded_and_goes_out_on_the_next_tick(self, mock_db):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/flaky-device")

        down = WebPushException("server error", response=MagicMock(status_code=503))
        with patch("web.push_delivery.webpush", side_effect=down):
            assert send_reminders(mock_db, DUE_NOW_UTC, "key", CLAIMS) == 0
        assert mock_db.medication_reminders_sent.count_documents({}) == 0

        with patch("web.push_delivery.webpush") as ok:
            assert send_reminders(mock_db, DUE_NOW_UTC, "key", CLAIMS) == 1
        ok.assert_called_once()
        assert mock_db.medication_reminders_sent.count_documents({}) == 1

    def test_a_subscription_that_never_works_is_given_up_after_a_cap(self, mock_db, monkeypatch):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/dead-device")
        monkeypatch.setattr(sender, "MAX_DELIVERY_ATTEMPTS", 3)

        down = WebPushException("server error", response=MagicMock(status_code=503))
        with patch("web.push_delivery.webpush", side_effect=down) as attempts:
            for _ in range(5):
                send_reminders(mock_db, DUE_NOW_UTC, "key", CLAIMS)
        assert attempts.call_count == 3
        assert mock_db.medication_reminders_sent.count_documents({}) == 1


@pytest.mark.push
class TestNothingGoesToAnInactiveAccount:
    def _deactivate(self, mock_db, username):
        mock_db.users.update_one({"username": username}, {"$set": {"is_active": False}}, upsert=True)

    def test_the_reminder_sender_skips_an_inactive_user(self, mock_db):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")
        self._deactivate(mock_db, "testuser")

        with patch("web.push_delivery.webpush") as push:
            assert send_reminders(mock_db, DUE_NOW_UTC, "key", CLAIMS) == 0
        push.assert_not_called()

    def test_an_inactive_person_sharing_the_pet_is_skipped_but_the_owner_still_hears(self, mock_db):
        pet_id = _make_pet(mock_db, shared_with=["friend"])
        _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")
        _subscribe(mock_db, "friend", "https://push.example/friend-device")
        self._deactivate(mock_db, "friend")

        with patch("web.push_delivery.webpush") as push:
            assert send_reminders(mock_db, DUE_NOW_UTC, "key", CLAIMS) == 1
        assert push.call_args.kwargs["subscription_info"]["endpoint"] == "https://push.example/owner-device"

    def test_the_in_request_alert_recipients_skip_an_inactive_user(self, mock_db):
        pet_id = _make_pet(mock_db, shared_with=["friend"])
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")
        _subscribe(mock_db, "friend", "https://push.example/friend-device")
        self._deactivate(mock_db, "friend")
        pet = mock_db.pets.find_one({"_id": pet_id})

        endpoints = [sub["endpoint"] for sub in get_pet_push_subscriptions(mock_db, pet)]
        assert endpoints == ["https://push.example/owner-device"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.push
class TestSubscriptionsGoWithTheSignIn:
    def test_a_deactivated_account_loses_its_subscriptions(self, client, mock_db, admin_token, regular_user):
        _subscribe(mock_db, "testuser", "https://push.example/a")
        _subscribe(mock_db, "other", "https://push.example/b")
        response = client.delete(f"/api/users/{regular_user['username']}", headers=_auth(admin_token))
        assert response.status_code == 200
        assert [s["username"] for s in mock_db.push_subscriptions.find({})] == ["other"]

    def test_an_admin_password_reset_drops_the_subscriptions(self, client, mock_db, admin_token, regular_user):
        _subscribe(mock_db, "testuser", "https://push.example/a")
        response = client.post(
            f"/api/users/{regular_user['username']}/reset-password",
            json={"password": "A-new-Strong-pass-77"},
            headers=_auth(admin_token),
        )
        assert response.status_code == 200
        assert mock_db.push_subscriptions.count_documents({}) == 0

    def test_logout_everywhere_drops_the_subscriptions(self, client, mock_db, regular_user_token):
        _subscribe(mock_db, "testuser", "https://push.example/a")
        _subscribe(mock_db, "testuser", "https://push.example/b")
        _subscribe(mock_db, "other", "https://push.example/c")
        response = client.post("/api/auth/logout", json={"everywhere": True}, headers=_auth(regular_user_token))
        assert response.status_code == 200
        assert [s["username"] for s in mock_db.push_subscriptions.find({})] == ["other"]

    def test_logout_drops_the_named_browser_subscription_only(self, client, mock_db, regular_user_token):
        _subscribe(mock_db, "testuser", "https://push.example/a")
        _subscribe(mock_db, "testuser", "https://push.example/b")
        _subscribe(mock_db, "other", "https://push.example/c")
        response = client.post(
            "/api/auth/logout",
            json={"push_endpoint": "https://push.example/a"},
            headers=_auth(regular_user_token),
        )
        assert response.status_code == 200
        left = sorted(s["endpoint"] for s in mock_db.push_subscriptions.find({}))
        assert left == ["https://push.example/b", "https://push.example/c"]

        # Another person's endpoint cannot be removed by naming it.
        client.post(
            "/api/auth/logout",
            json={"push_endpoint": "https://push.example/c"},
            headers=_auth(regular_user_token),
        )
        assert mock_db.push_subscriptions.count_documents({"endpoint": "https://push.example/c"}) == 1
