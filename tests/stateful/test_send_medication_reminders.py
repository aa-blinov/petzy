"""Tests for the medication reminder sender's pure logic against mongomock.

Everything here goes through find_due_reminders/send_reminders directly —
no HTTP client — since this script never runs inside a request; it's a
standalone loop with its own DB access (see the module docstring for why
it can't live inside the gunicorn app).

A fixed scenario is reused across most tests: a Tuesday, 08:00 dose, for
an owner subscribed from Etc/GMT-5 (a fixed, DST-free UTC+5 offset,
chosen over a real IANA zone so the test doesn't depend on tzdata's
politically-changeable rules) — this exercises the actual UTC-to-local
conversion, since a same-timezone test would pass even if that
conversion were silently wrong.
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from pywebpush import WebPushException

from scripts.send_medication_reminders import find_due_reminders, send_reminders

# 2024-01-02 is a Tuesday. 03:00:30 UTC = 08:00:30 at UTC+5 —
# 30 seconds after the 08:00 dose, comfortably inside the 90s tick window.
DUE_NOW_UTC = datetime(2024, 1, 2, 3, 0, 30, tzinfo=timezone.utc)
LOCAL_DATE_KEY = "2024-01-02"
TUESDAY = 1  # datetime.weekday(): Monday=0


def _make_pet(mock_db, owner="testuser", shared_with=None):
    pet_id = ObjectId()
    mock_db.pets.insert_one(
        {
            "_id": pet_id,
            "name": "Rex",
            "owner": owner,
            "shared_with": shared_with or [],
        }
    )
    return pet_id


def _make_medication(mock_db, pet_id, days=(TUESDAY,), times=("08:00",), is_active=True):
    med_id = ObjectId()
    mock_db.medications.insert_one(
        {
            "_id": med_id,
            "pet_id": str(pet_id),
            "name": "Синулокс",
            "is_active": is_active,
            "schedule": {"days": list(days), "times": list(times)},
        }
    )
    return med_id


def _subscribe(mock_db, username, endpoint, tz="Etc/GMT-5"):
    mock_db.push_subscriptions.insert_one(
        {
            "username": username,
            "endpoint": endpoint,
            "keys": {"p256dh": "p256dh-key", "auth": "auth-key"},
            "timezone": tz,
        }
    )


@pytest.mark.push
class TestFindDueReminders:
    def test_due_slot_not_yet_taken_is_returned(self, mock_db):
        pet_id = _make_pet(mock_db)
        med_id = _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")

        due = find_due_reminders(mock_db, DUE_NOW_UTC)

        assert len(due) == 1
        assert due[0]["medication"]["_id"] == med_id
        assert due[0]["date"] == LOCAL_DATE_KEY
        assert due[0]["time"] == "08:00"
        assert [s["endpoint"] for s in due[0]["subscriptions"]] == ["https://push.example/owner-device"]

    def test_already_taken_today_is_excluded(self, mock_db):
        pet_id = _make_pet(mock_db)
        med_id = _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")
        # Local-naive date_time, matching how log_intake actually stores it.
        mock_db.medication_intakes.insert_one({"medication_id": str(med_id), "date_time": datetime(2024, 1, 2, 8, 0)})

        assert find_due_reminders(mock_db, DUE_NOW_UTC) == []

    def test_already_notified_slot_is_excluded(self, mock_db):
        pet_id = _make_pet(mock_db)
        med_id = _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")
        mock_db.medication_reminders_sent.insert_one(
            {"medication_id": str(med_id), "date": LOCAL_DATE_KEY, "time": "08:00"}
        )

        assert find_due_reminders(mock_db, DUE_NOW_UTC) == []

    def test_wrong_weekday_is_excluded(self, mock_db):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id, days=[2])  # Wednesday, not Tuesday
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")

        assert find_due_reminders(mock_db, DUE_NOW_UTC) == []

    def test_not_yet_due_is_excluded(self, mock_db):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id, times=["20:00"])
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")

        assert find_due_reminders(mock_db, DUE_NOW_UTC) == []

    def test_inactive_medication_is_excluded(self, mock_db):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id, is_active=False)
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")

        assert find_due_reminders(mock_db, DUE_NOW_UTC) == []

    def test_owner_without_subscription_skips_pet_entirely(self, mock_db):
        pet_id = _make_pet(mock_db, owner="testuser", shared_with=["frienduser"])
        _make_medication(mock_db, pet_id)
        # Only the shared user subscribed — owner did not.
        _subscribe(mock_db, "frienduser", "https://push.example/friend-device")

        assert find_due_reminders(mock_db, DUE_NOW_UTC) == []

    def test_shared_user_with_subscription_is_also_notified(self, mock_db):
        pet_id = _make_pet(mock_db, owner="testuser", shared_with=["frienduser"])
        _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")
        _subscribe(mock_db, "frienduser", "https://push.example/friend-device")

        due = find_due_reminders(mock_db, DUE_NOW_UTC)

        assert len(due) == 1
        endpoints = {s["endpoint"] for s in due[0]["subscriptions"]}
        assert endpoints == {"https://push.example/owner-device", "https://push.example/friend-device"}

    def test_no_subscriptions_at_all_returns_empty_without_querying_pets(self, mock_db):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id)

        assert find_due_reminders(mock_db, DUE_NOW_UTC) == []


@pytest.mark.push
class TestSendReminders:
    def test_sends_push_and_records_dedupe_row(self, mock_db):
        pet_id = _make_pet(mock_db)
        med_id = _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")

        with patch("scripts.send_medication_reminders.webpush") as mock_webpush:
            sent = send_reminders(mock_db, DUE_NOW_UTC, "fake-private-key", {"sub": "mailto:test@example.com"})

        assert sent == 1
        mock_webpush.assert_called_once()
        call_kwargs = mock_webpush.call_args.kwargs
        assert call_kwargs["subscription_info"]["endpoint"] == "https://push.example/owner-device"
        assert call_kwargs["vapid_private_key"] == "fake-private-key"
        payload = json.loads(call_kwargs["data"])
        assert "Синулокс" in payload["body"]

        dedupe_row = mock_db.medication_reminders_sent.find_one(
            {"medication_id": str(med_id), "date": LOCAL_DATE_KEY, "time": "08:00"}
        )
        assert dedupe_row is not None

    def test_second_tick_does_not_resend_after_dedupe_row_exists(self, mock_db):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/owner-device")

        with patch("scripts.send_medication_reminders.webpush") as mock_webpush:
            send_reminders(mock_db, DUE_NOW_UTC, "fake-private-key", {"sub": "mailto:test@example.com"})
            mock_webpush.reset_mock()
            sent_again = send_reminders(mock_db, DUE_NOW_UTC, "fake-private-key", {"sub": "mailto:test@example.com"})

        assert sent_again == 0
        mock_webpush.assert_not_called()

    def test_expired_subscription_is_removed_on_410(self, mock_db):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/gone-device")

        gone_response = MagicMock(status_code=410)
        with patch(
            "scripts.send_medication_reminders.webpush",
            side_effect=WebPushException("gone", response=gone_response),
        ):
            sent = send_reminders(mock_db, DUE_NOW_UTC, "fake-private-key", {"sub": "mailto:test@example.com"})

        assert sent == 0
        assert mock_db.push_subscriptions.find_one({"endpoint": "https://push.example/gone-device"}) is None

    def test_non_expiry_failure_keeps_subscription(self, mock_db):
        pet_id = _make_pet(mock_db)
        _make_medication(mock_db, pet_id)
        _subscribe(mock_db, "testuser", "https://push.example/flaky-device")

        server_error_response = MagicMock(status_code=500)
        with patch(
            "scripts.send_medication_reminders.webpush",
            side_effect=WebPushException("server error", response=server_error_response),
        ):
            send_reminders(mock_db, DUE_NOW_UTC, "fake-private-key", {"sub": "mailto:test@example.com"})

        assert mock_db.push_subscriptions.find_one({"endpoint": "https://push.example/flaky-device"}) is not None
