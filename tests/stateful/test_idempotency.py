"""A retried create is saved once: the same Idempotency-Key gets the first answer again, and no second record.

The unique key and its expiry are the ones the app declares (ensure_indexes), so the database here enforces them.
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


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_pet(client, token, key, name="Мурка"):
    return client.post("/api/pets", json={"name": name}, headers={**_auth(token), "Idempotency-Key": key})


def _moment(offset: timedelta) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + offset


class TestRetriedPetCreates:
    def test_the_same_key_gets_the_first_answer_and_no_second_pet(self, client, indexed, regular_user_token):
        first = _create_pet(client, regular_user_token, "k-1")
        second = _create_pet(client, regular_user_token, "k-1")

        assert first.status_code == 201
        assert second.status_code == 201
        assert second.get_json() == first.get_json()
        assert indexed["pets"].count_documents({"name": "Мурка"}) == 1

    def test_the_same_key_with_another_body_is_refused_and_saves_nothing(self, client, indexed, regular_user_token):
        _create_pet(client, regular_user_token, "k-2", name="Мурка")

        response = _create_pet(client, regular_user_token, "k-2", name="Барсик")

        assert response.status_code == 422
        assert response.get_json()["code"] == "idempotency_key_reused"
        assert indexed["pets"].count_documents({"name": "Барсик"}) == 0

    def test_another_user_may_use_the_same_key(self, client, indexed, regular_user_token, admin_token):
        _create_pet(client, regular_user_token, "k-3", name="Тиша")

        response = _create_pet(client, admin_token, "k-3", name="Тиша")

        assert response.status_code == 201
        assert indexed["pets"].count_documents({"name": "Тиша"}) == 2

    def test_a_request_without_the_key_is_saved_each_time(self, client, indexed, regular_user_token):
        for _ in range(2):
            client.post("/api/pets", json={"name": "Дубль"}, headers=_auth(regular_user_token))

        assert indexed["pets"].count_documents({"name": "Дубль"}) == 2

    def test_a_busy_key_gets_409_until_its_lease_runs_out(self, client, indexed, regular_user, regular_user_token):
        body = '{"name": "Занято"}'.encode()
        indexed["idempotency_keys"].insert_one(
            {
                "username": regular_user["username"],
                "path": "POST /api/pets",
                "key": "k-5",
                "digest": hashlib.sha256(body).hexdigest(),
                "state": "running",
                "lease_until": _moment(timedelta(seconds=30)),
                "expires_at": _moment(timedelta(hours=1)),
            }
        )

        response = client.post(
            "/api/pets",
            data=body,
            content_type="application/json",
            headers={**_auth(regular_user_token), "Idempotency-Key": "k-5"},
        )

        assert response.status_code == 409
        assert response.get_json()["code"] == "idempotency_in_progress"
        assert indexed["pets"].count_documents({"name": "Занято"}) == 0

    def test_a_request_whose_lease_ran_out_takes_the_key_over(self, client, indexed, regular_user, regular_user_token):
        body = '{"name": "Брошено"}'.encode()
        indexed["idempotency_keys"].insert_one(
            {
                "username": regular_user["username"],
                "path": "POST /api/pets",
                "key": "k-6",
                "digest": hashlib.sha256(body).hexdigest(),
                "state": "running",
                "lease_until": _moment(timedelta(minutes=-1)),
                "expires_at": _moment(timedelta(hours=1)),
            }
        )

        response = client.post(
            "/api/pets",
            data=body,
            content_type="application/json",
            headers={**_auth(regular_user_token), "Idempotency-Key": "k-6"},
        )

        assert response.status_code == 201
        assert indexed["pets"].count_documents({"name": "Брошено"}) == 1
        assert indexed["idempotency_keys"].find_one({"key": "k-6"})["state"] == "done"

    def test_a_key_too_long_or_with_a_space_is_refused(self, client, indexed, regular_user_token):
        for key in ("k" * 129, "с пробелом"):
            response = _create_pet(client, regular_user_token, key, name="Короткий")

            assert response.status_code == 422
            assert response.get_json()["code"] == "idempotency_key_invalid"
        assert indexed["pets"].count_documents({"name": "Короткий"}) == 0

    def test_the_key_is_removed_with_the_account_that_owns_it(self, indexed):
        from web.account_deletion import PERSONAL_COLLECTIONS

        assert "idempotency_keys" in PERSONAL_COLLECTIONS


class TestTheWrapper:
    """The same wrapper on small views, so each rule can be read without a route around it."""

    @staticmethod
    def _call(view, path, key, username="vera"):
        with flask_app.test_request_context(path, method="POST", data=b"{}", headers={"Idempotency-Key": key}):
            setattr(request, "current_user", username)
            return view()

    def test_a_refused_answer_releases_its_key(self, indexed):
        @idempotent
        def refuse():
            return jsonify({"code": "gone"}), 404

        response = self._call(refuse, "/api/refusal", "r-1")

        assert response.status_code == 404
        assert indexed["idempotency_keys"].count_documents({"key": "r-1"}) == 0

    def test_the_key_is_kept_to_its_own_path(self, indexed):
        calls = []

        @idempotent
        def create():
            calls.append(1)
            return jsonify({"n": len(calls)}), 201

        first = self._call(create, "/api/first", "p-1")
        elsewhere = self._call(create, "/api/second", "p-1")
        again = self._call(create, "/api/first", "p-1")

        assert first.get_json() == {"n": 1}
        assert elsewhere.get_json() == {"n": 2}
        assert again.get_json() == {"n": 1}
        assert len(calls) == 2
