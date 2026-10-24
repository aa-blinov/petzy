"""Identical requests that arrive at the same instant are saved once (web/save_lock.py, web/idempotency.py).

A guard that looks for a twin and then writes lets every request of a simultaneous burst pass the look before the first
write. Each test fires the same request from several threads, and slows the look down so that every thread is inside
it together: without the lock the burst writes several records.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from bson import ObjectId
from flask import jsonify, request

import web.events as events
import web.medications as medications
import web.pets as pets
from web.app import app as flask_app
from web.db import ensure_indexes
from web.idempotency import idempotent
from web.save_lock import COLLECTION, acquire, release, single_flight

BURST = 6


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _slowed(original, seconds=0.15):
    """The same function, but it keeps the caller inside it for a while after it has looked."""

    def slow(*args, **kwargs):
        result = original(*args, **kwargs)
        time.sleep(seconds)
        return result

    return slow


def _status(answer):
    """The status of a view's answer, which is a ``(response, status)`` pair or a response."""
    return answer[1] if isinstance(answer, tuple) else answer.status_code


def _burst(send, count=BURST):
    with ThreadPoolExecutor(max_workers=count) as pool:
        return list(pool.map(lambda _: send(), range(count)))


@pytest.mark.health_records
class TestEventsAtTheSameInstant:
    def _send(self, token, pet_id, **overrides):
        body = {
            "pet_id": str(pet_id),
            "type": "weight",
            "date": "2026-10-01",
            "time": "09:00",
            "fields": {"weight": 12.4},
            "comment": "",
            "tz": "Asia/Almaty",
            **overrides,
        }
        with flask_app.test_client() as client:
            return client.post("/api/events", json=body, headers=_auth(token))

    def test_a_burst_of_identical_events_is_one_record(self, mock_db, regular_user_token, test_pet):
        with patch.object(events, "_same_record_just_saved", _slowed(events._same_record_just_saved)):
            answers = _burst(lambda: self._send(regular_user_token, test_pet["_id"]))

        assert sorted(a.status_code for a in answers) == [201] + [409] * (BURST - 1)
        assert {a.get_json()["code"] for a in answers if a.status_code == 409} == {"duplicate_event"}
        assert mock_db["events"].count_documents({"pet_id": str(test_pet["_id"]), "type": "weight"}) == 1
        assert mock_db[COLLECTION].count_documents({}) == 0

    def test_the_same_weighing_later_is_still_a_new_record(self, mock_db, regular_user_token, test_pet):
        """The lock is held for the save and let go: a repeat on purpose outside the guard's window is allowed."""
        assert self._send(regular_user_token, test_pet["_id"]).status_code == 201
        mock_db["events"].update_many({}, {"$set": {"created_at": datetime.now(timezone.utc) - timedelta(hours=1)}})

        assert self._send(regular_user_token, test_pet["_id"]).status_code == 201
        assert mock_db["events"].count_documents({}) == 2


@pytest.fixture
def course(mock_db, test_pet):
    med_id = ObjectId()
    mock_db["medications"].insert_one(
        {
            "_id": med_id,
            "pet_id": str(test_pet["_id"]),
            "name": "Габапентин",
            "type": "Таблетка",
            "default_dose": 1.0,
            "is_active": True,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:00", "20:00"]},
            "inventory_enabled": True,
            "inventory_current": 10.0,
            "created_at": datetime(2026, 9, 1),
        }
    )
    return med_id


@pytest.mark.medications
class TestDosesAtTheSameInstant:
    def _send(self, token, med_id):
        with flask_app.test_client() as client:
            return client.post(
                f"/api/medications/{med_id}/log",
                json={"date": "2026-10-02", "time": "10:51", "tz": "Asia/Almaty"},
                headers=_auth(token),
            )

    def test_a_burst_of_doses_without_a_slot_is_one_intake_and_one_dose_off_the_stock(
        self, mock_db, regular_user_token, course
    ):
        with patch.object(medications, "_already_handled", _slowed(medications._already_handled)):
            answers = _burst(lambda: self._send(regular_user_token, course))

        assert sorted(a.status_code for a in answers) == [201] + [409] * (BURST - 1)
        assert {a.get_json()["code"] for a in answers if a.status_code == 409} == {"duplicate_intake"}
        assert mock_db["medication_intakes"].count_documents({"medication_id": str(course)}) == 1
        assert mock_db["medications"].find_one({"_id": course})["inventory_current"] == 9.0
        assert mock_db[COLLECTION].count_documents({}) == 0


@pytest.fixture
def indexed(mock_db):
    with patch("web.db.db", mock_db):
        ensure_indexes()
    return mock_db


def _call(view, path, username="vera", **headers):
    with flask_app.test_request_context(path, method="POST", data=b"{}", headers=headers):
        setattr(request, "current_user", username)
        return view()


class TestTheKeyAtTheSameInstant:
    def test_a_burst_with_one_key_runs_the_request_once(self, indexed):
        """_hold takes the key with an insert the unique index settles: one request runs, the others are told to wait."""
        runs = []

        @idempotent
        def create():
            runs.append(1)
            time.sleep(0.15)
            return jsonify({"success": True}), 201

        answers = _burst(lambda: _call(create, "/api/things", **{"Idempotency-Key": "k-1"}))

        assert len(runs) == 1
        assert sorted(_status(a) for a in answers) == [201] + [409] * (BURST - 1)


class TestARequestWithoutAKeyAtTheSameInstant:
    def test_an_identical_request_in_flight_is_told_to_wait(self, indexed):
        runs = []

        @single_flight
        def create():
            runs.append(1)
            time.sleep(0.15)
            return jsonify({"success": True}), 201

        answers = _burst(lambda: _call(create, "/api/things"))

        assert len(runs) == 1
        assert sorted(_status(a) for a in answers) == [201] + [409] * (BURST - 1)

    def test_a_repeat_after_the_first_has_finished_is_a_new_request(self, indexed):
        runs = []

        @single_flight
        def create():
            runs.append(1)
            return jsonify({"success": True}), 201

        _call(create, "/api/things")
        _call(create, "/api/things")

        assert len(runs) == 2

    def test_a_burst_of_identical_pets_is_one_pet(self, mock_db, regular_user_token):
        body = {"name": "Бублик", "species": "dog"}

        def send():
            with flask_app.test_client() as client:
                return client.post("/api/pets", json=body, headers=_auth(regular_user_token))

        with patch.object(pets, "parse_date", _slowed(pets.parse_date)):
            answers = _burst(send)

        assert sorted(a.status_code for a in answers) == [201] + [409] * (BURST - 1)
        assert mock_db["pets"].count_documents({"name": "Бублик"}) == 1

    def test_a_key_that_is_there_leaves_the_request_to_the_idempotency_decorator(self, indexed):
        runs = []

        @single_flight
        def create():
            runs.append(1)
            return jsonify({"success": True}), 201

        _call(create, "/api/things", **{"Idempotency-Key": "k-2"})

        assert runs == [1]
        assert indexed[COLLECTION].count_documents({}) == 0


class TestTheLock:
    def test_it_is_held_by_one_and_taken_over_after_its_lease(self, mock_db):
        parts = ("x", 1)
        token = acquire(parts, wait=0)
        assert token is not None
        assert acquire(parts, wait=0) is None

        mock_db[COLLECTION].update_many({}, {"$set": {"expires_at": datetime(2000, 1, 1)}})
        taken = acquire(parts, wait=0)
        assert taken is not None

        release(parts, token)  # the old holder frees nothing that is not its own
        assert mock_db[COLLECTION].count_documents({}) == 1
        release(parts, taken)
        assert mock_db[COLLECTION].count_documents({}) == 0

    def test_a_request_waits_for_the_holder_to_let_go(self, mock_db):
        parts = ("y", 1)
        token = acquire(parts, wait=0)

        with ThreadPoolExecutor(max_workers=1) as pool:
            waiting = pool.submit(acquire, parts, 2.0)
            time.sleep(0.1)
            release(parts, token)
            assert waiting.result() is not None
