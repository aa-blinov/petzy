"""The key of a request that died, and the key taken by somebody else (web/idempotency.py).

Two moments the key changes hands in a way a person can run into: a request that fell over leaves its key
behind (the phone sends it again and it must not be told «already done»), and a key whose lease ran out is
taken over by whoever comes first (the second one is told to wait)
"""

import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from flask import jsonify, request

from web.app import app as flask_app
from web.db import ensure_indexes
from web.idempotency import idempotent


@pytest.fixture
def indexed(mock_db):
    with patch("web.db.db", mock_db):
        ensure_indexes()
    return mock_db


def _moment(offset: timedelta) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + offset


def _call(view, path, key, body=b"{}", username="vera"):
    with flask_app.test_request_context(path, method="POST", data=body, headers={"Idempotency-Key": key}):
        setattr(request, "current_user", username)
        return view()


def _busy_key(indexed, path, key, body):
    """A key whose lease ran out: nobody holds it, and the next request may take it over."""
    indexed["idempotency_keys"].insert_one(
        {
            "username": "vera",
            "path": path,
            "key": key,
            "digest": hashlib.sha256(body).hexdigest(),
            "state": "running",
            "lease_until": _moment(timedelta(minutes=-1)),
            "expires_at": _moment(timedelta(hours=1)),
        }
    )


class TestARequestThatFellOver:
    def test_the_key_is_released_so_the_request_can_be_sent_again(self, indexed):
        """A request that fell over saved nothing, so it must not keep the key: the phone sends it again
        and the answer is the one of the new attempt, not the memory of the failed one."""

        @idempotent
        def fall_over():
            raise RuntimeError("the view fell over")

        with pytest.raises(RuntimeError):
            _call(fall_over, "/api/fallen", "f-1")

        assert indexed["idempotency_keys"].count_documents({"key": "f-1"}) == 0

    def test_the_key_is_released_even_when_the_view_fell_over_after_saving(self, indexed):
        """The view may have saved something before it fell over; the answer never came, so the key is
        released anyway and the request can be sent again as it was."""

        @idempotent
        def fall_over():
            indexed["pets"].insert_one({"name": "Мурка", "owner": "vera"})
            raise RuntimeError("the view fell over")

        with pytest.raises(RuntimeError):
            _call(fall_over, "/api/fallen", "f-2")

        assert indexed["idempotency_keys"].count_documents({"key": "f-2"}) == 0


class TestAKeyTakenOverBySomebodyElse:
    def test_the_second_one_is_told_to_wait_when_the_key_was_taken_over(self, indexed):
        """The lease of a key ran out and somebody else took it over between our reading and our writing.
        The one that lost the race is told the request is still running, and saves nothing."""
        body = '{"name": "Гонка"}'.encode()
        path = "POST /api/race"
        _busy_key(indexed, path, "r-1", body)
        saved = []

        @idempotent
        def create():
            saved.append(1)
            return jsonify({"name": "Гонка"}), 201

        rows = indexed["idempotency_keys"]
        real_find_one = rows.find_one

        def find_one(*args, **kwargs):
            row = real_find_one(*args, **kwargs)
            # Somebody else took the key over a moment ago: the row we read is no longer the row in the database.
            rows.update_one({"_id": row["_id"]}, {"$set": {"lease_until": _moment(timedelta(minutes=5))}})
            return row

        with patch.object(rows, "find_one", find_one):
            response = _call(create, "/api/race", "r-1", body=body)

        assert response[1] == 409
        assert response[0].get_json()["code"] == "idempotency_in_progress"
        assert saved == []

    def test_a_key_released_a_moment_ago_is_answered_as_a_busy_key(self, indexed):
        """The key was taken a moment ago and released again: the client is asked to wait, as it would be
        for a busy key, and not told that the key is free."""
        body = '{"name": "Гонка"}'.encode()
        path = "POST /api/race2"
        _busy_key(indexed, path, "r-2", body)
        saved = []

        @idempotent
        def create():
            saved.append(1)
            return jsonify({"name": "Гонка"}), 201

        rows = indexed["idempotency_keys"]
        real_find_one = rows.find_one

        def find_one(*args, **kwargs):
            row = real_find_one(*args, **kwargs)
            # The request that held the key released it a moment ago: the row is gone by the time it is read.
            rows.delete_one({"_id": row["_id"]})
            return None

        with patch.object(rows, "find_one", find_one):
            response = _call(create, "/api/race2", "r-2", body=body)

        assert response[1] == 409
        assert response[0].get_json()["code"] == "idempotency_in_progress"
        assert saved == []
