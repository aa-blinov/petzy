"""Push reminders for a vaccination or treatment that is due again.

Scenario as in test_send_medication_reminders: the local date is 2024-01-02
(03:00 UTC is 08:00 for an owner subscribed from UTC+5). The reminder has no
time of day: it fires on the first tick that finds a repeat date inside its
window, once per (record, date, stage).
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from bson import ObjectId

from scripts.send_medication_reminders import (
    MEDICAL_OVERDUE_GRACE_DAYS,
    find_due_medical_reminders,
    medical_reminder_payload,
    send_reminders,
)

NOW_UTC = datetime(2024, 1, 2, 3, 0, 30, tzinfo=timezone.utc)
LOCAL_TODAY = datetime(2024, 1, 2).date()


def day(offset: int) -> str:
    return (LOCAL_TODAY + timedelta(days=offset)).isoformat()


def _pet(mock_db, owner="testuser", shared_with=None):
    pet_id = ObjectId()
    mock_db.pets.insert_one({"_id": pet_id, "name": "Рекс", "owner": owner, "shared_with": shared_with or []})
    return pet_id


def _subscribe(mock_db, username="testuser", endpoint="https://push.example/d", tz="Etc/GMT-5"):
    mock_db.push_subscriptions.insert_one(
        {"username": username, "endpoint": endpoint, "keys": {"p256dh": "a", "auth": "b"}, "timezone": tz}
    )


def _record(mock_db, pet_id, kind="vaccination", title="Рабизин", date_="2023-01-10", next_due=None, created=0):
    record_id = ObjectId()
    mock_db.medical_records.insert_one(
        {
            "_id": record_id,
            "pet_id": str(pet_id),
            "kind": kind,
            "title": title,
            "date": date_,
            "next_due": next_due,
            "created_at": datetime(2024, 1, 1) + timedelta(seconds=created),
        }
    )
    return record_id


@pytest.mark.push
class TestWhoIsDue:
    def test_a_repeat_inside_the_window_is_due(self, mock_db):
        pet_id = _pet(mock_db)
        rid = _record(mock_db, pet_id, next_due=day(10))
        _subscribe(mock_db)
        due = find_due_medical_reminders(mock_db, NOW_UTC)
        assert [(d["record"]["_id"], d["stage"], d["days_until"]) for d in due] == [(rid, "soon", 10)]

    @pytest.mark.parametrize(
        "kind,offset,expected",
        [
            ("vaccination", 0, "soon"),
            ("vaccination", 14, "soon"),
            ("vaccination", 15, None),
            ("parasite", 7, "soon"),
            ("parasite", 8, None),
            ("vaccination", -1, "overdue"),
            ("vaccination", -MEDICAL_OVERDUE_GRACE_DAYS, "overdue"),
            ("vaccination", -MEDICAL_OVERDUE_GRACE_DAYS - 1, None),
        ],
    )
    def test_the_windows_by_kind(self, mock_db, kind, offset, expected):
        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, kind=kind, next_due=day(offset))
        _subscribe(mock_db)
        due = find_due_medical_reminders(mock_db, NOW_UTC)
        assert [d["stage"] for d in due] == ([expected] if expected else [])

    def test_a_record_with_no_repeat_is_never_due(self, mock_db):
        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, next_due=None)
        _subscribe(mock_db)
        assert find_due_medical_reminders(mock_db, NOW_UTC) == []

    @pytest.mark.parametrize("kind", ["visit", "procedure"])
    def test_visits_and_procedures_are_not_reminded(self, mock_db, kind):
        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, kind=kind, next_due=day(3))
        _subscribe(mock_db)
        assert find_due_medical_reminders(mock_db, NOW_UTC) == []

    def test_a_replaced_record_is_not_reminded(self, mock_db):
        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, title="Рабизин", date_="2023-01-10", next_due=day(3), created=0)
        _record(mock_db, pet_id, title="рабизин ", date_="2023-12-30", next_due=day(360), created=5)
        _subscribe(mock_db)
        # the old one's date is near, but a newer shot of the same vaccine exists; the new one's is far
        assert find_due_medical_reminders(mock_db, NOW_UTC) == []

    def test_a_malformed_date_is_skipped(self, mock_db):
        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, next_due="soon")
        _subscribe(mock_db)
        assert find_due_medical_reminders(mock_db, NOW_UTC) == []

    def test_nobody_subscribed_nobody_reminded(self, mock_db):
        _record(mock_db, _pet(mock_db), next_due=day(3))
        assert find_due_medical_reminders(mock_db, NOW_UTC) == []

    def test_a_shared_user_is_a_recipient(self, mock_db):
        pet_id = _pet(mock_db, shared_with=["friend"])
        _record(mock_db, pet_id, next_due=day(3))
        _subscribe(mock_db, "testuser", "https://push.example/owner")
        _subscribe(mock_db, "friend", "https://push.example/friend")
        (item,) = find_due_medical_reminders(mock_db, NOW_UTC)
        assert {s["endpoint"] for s in item["subscriptions"]} == {
            "https://push.example/owner",
            "https://push.example/friend",
        }

    def test_today_is_the_subscribers_local_date(self, mock_db):
        # 20:30 UTC on 2024-01-01 is already 2024-01-02 at UTC+5: a repeat dated the 2nd is due today, not tomorrow
        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, next_due="2024-01-02")
        _subscribe(mock_db)
        (item,) = find_due_medical_reminders(mock_db, datetime(2024, 1, 1, 20, 30, tzinfo=timezone.utc))
        assert item["days_until"] == 0


@pytest.mark.push
class TestSending:
    def _send(self, mock_db):
        with patch("web.push_delivery.webpush") as mock_webpush:
            sent = send_reminders(mock_db, NOW_UTC, "fake-key", {"sub": "mailto:t@example.com"})
        return sent, mock_webpush

    def test_the_push_names_the_pet_the_record_and_when_and_links_to_the_card(self, mock_db):
        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, title="Рабизин", next_due=day(5))
        _subscribe(mock_db)
        sent, webpush = self._send(mock_db)
        assert sent == 1
        payload = json.loads(webpush.call_args.kwargs["data"])
        assert payload == {
            "title": "Скоро прививка",
            "body": "Рекс: Рабизин, через 5 дней",
            "url": f"/pets/{pet_id}/medical-card",
        }

    @pytest.mark.parametrize(
        "offset,phrase",
        [
            (0, "сегодня"),
            (1, "завтра"),
            (2, "через 2 дня"),
            (5, "через 5 дней"),
            (11, "через 11 дней"),
            (14, "через 14 дней"),
        ],
    )
    def test_the_wording_of_the_days(self, mock_db, offset, phrase):
        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, next_due=day(offset))
        _subscribe(mock_db)
        (item,) = find_due_medical_reminders(mock_db, NOW_UTC)
        assert medical_reminder_payload(item)["body"].endswith(phrase)

    def test_a_treatment_and_an_overdue_one_read_differently(self, mock_db):
        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, kind="parasite", title="Дронтал", next_due=day(-2))
        _subscribe(mock_db)
        (item,) = find_due_medical_reminders(mock_db, NOW_UTC)
        assert medical_reminder_payload(item) == {
            "title": "Обработка от паразитов просрочена",
            "body": "Рекс: Дронтал, срок был 31.12.2023",
            "url": f"/pets/{pet_id}/medical-card",
        }

    def test_once_per_date_and_stage(self, mock_db):
        pet_id = _pet(mock_db)
        rid = _record(mock_db, pet_id, next_due=day(5))
        _subscribe(mock_db)
        first, _ = self._send(mock_db)
        second, webpush = self._send(mock_db)
        assert (first, second) == (1, 0)
        webpush.assert_not_called()
        row = mock_db.medical_due_reminders_sent.find_one({"record_id": str(rid)})
        assert row["next_due"] == day(5) and row["stage"] == "soon" and "purge_at" in row

    def test_a_moved_date_is_a_new_reminder(self, mock_db):
        pet_id = _pet(mock_db)
        rid = _record(mock_db, pet_id, next_due=day(5))
        _subscribe(mock_db)
        self._send(mock_db)
        mock_db.medical_records.update_one({"_id": rid}, {"$set": {"next_due": day(9)}})
        sent, _ = self._send(mock_db)
        assert sent == 1

    def test_soon_and_then_overdue_are_two_pushes(self, mock_db):
        pet_id = _pet(mock_db)
        rid = _record(mock_db, pet_id, next_due=day(0))
        _subscribe(mock_db)
        self._send(mock_db)
        # two days on, the date has passed and nobody marked it done
        later = NOW_UTC + timedelta(days=2)
        with patch("web.push_delivery.webpush") as mock_webpush:
            sent = send_reminders(mock_db, later, "fake-key", {"sub": "mailto:t@example.com"})
        assert sent == 1
        assert json.loads(mock_webpush.call_args.kwargs["data"])["title"] == "Прививка просрочена"
        assert mock_db.medical_due_reminders_sent.count_documents({"record_id": str(rid)}) == 2

    def test_a_dead_subscription_is_dropped_and_the_rest_carry_on(self, mock_db):
        from unittest.mock import MagicMock

        from pywebpush import WebPushException

        pet_id = _pet(mock_db)
        _record(mock_db, pet_id, next_due=day(3))
        _subscribe(mock_db, endpoint="https://push.example/gone")
        with patch(
            "web.push_delivery.webpush", side_effect=WebPushException("gone", response=MagicMock(status_code=410))
        ):
            sent = send_reminders(mock_db, NOW_UTC, "fake-key", {"sub": "mailto:t@example.com"})
        assert sent == 0
        assert mock_db.push_subscriptions.find_one({"endpoint": "https://push.example/gone"}) is None


def _document(mock_db, pet_id, title="Сертификат", expires="2024-01-06"):
    doc_id = ObjectId()
    mock_db.documents.insert_one(
        {"_id": doc_id, "pet_id": str(pet_id), "title": title, "category": "vaccination", "expires_at": expires}
    )
    return doc_id


@pytest.mark.push
class TestOneReminderPerVaccination:
    """A certificate linked to a vaccination record is the same vaccination: the record's
    reminder covers it, and the document's own «скоро истекает» must not come on top."""

    def _titles(self, mock_db):
        with patch("web.push_delivery.webpush") as mock_webpush:
            send_reminders(mock_db, NOW_UTC, "fake-key", {"sub": "mailto:t@example.com"})
        return [json.loads(c.kwargs["data"])["title"] for c in mock_webpush.call_args_list]

    def test_a_linked_certificate_is_not_reminded_twice(self, mock_db):
        pet_id = _pet(mock_db)
        doc = _document(mock_db, pet_id, expires=day(4))
        _record(mock_db, pet_id, next_due=day(4))
        mock_db.medical_records.update_one({"pet_id": str(pet_id)}, {"$set": {"document_ids": [str(doc)]}})
        _subscribe(mock_db)
        assert self._titles(mock_db) == ["Скоро прививка"]

    def test_a_certificate_linked_to_an_older_replaced_record_is_quiet_too(self, mock_db):
        pet_id = _pet(mock_db)
        doc = _document(mock_db, pet_id, expires=day(4))
        old = _record(mock_db, pet_id, title="Рабизин", date_="2023-01-10", next_due=day(4), created=0)
        mock_db.medical_records.update_one({"_id": old}, {"$set": {"document_ids": [str(doc)]}})
        _record(mock_db, pet_id, title="Рабизин", date_="2023-12-30", next_due=day(360), created=5)
        _subscribe(mock_db)
        assert self._titles(mock_db) == []

    def test_an_unlinked_certificate_is_still_reminded(self, mock_db):
        pet_id = _pet(mock_db)
        _document(mock_db, pet_id, expires=day(4))
        _subscribe(mock_db)
        assert self._titles(mock_db) == ["Скоро истекает срок документа"]

    def test_a_document_linked_to_a_visit_is_still_reminded(self, mock_db):
        pet_id = _pet(mock_db)
        doc = _document(mock_db, pet_id, expires=day(4))
        visit = _record(mock_db, pet_id, kind="visit", title="Осмотр")
        mock_db.medical_records.update_one({"_id": visit}, {"$set": {"document_ids": [str(doc)]}})
        _subscribe(mock_db)
        assert self._titles(mock_db) == ["Скоро истекает срок документа"]
