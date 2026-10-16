"""A refresh token is kept in the database only as its sha256, and the successor of a spent one only sealed.

A read of ``refresh_tokens`` hands out no session: a token is found by its hash, and the successor that the grace window
answers with (``replaced_by``) is encrypted with a key that lives in the server's environment, not in the database.
Sessions written before that change kept the token itself (``token``) and the successor as a plain token. Startup moves
both, so they keep working and nobody has to sign in again.
"""

import hashlib
import re

from web.configs import JWT_CONFIG
from web.db import (
    ensure_indexes,
    migrate_refresh_successors,
    migrate_refresh_token_hashes,
    open_refresh_successor,
    seal_refresh_successor,
)
from web.security import create_refresh_token, rotate_refresh_token

# A JWT is three base64url segments separated by dots; a sealed successor is one segment without dots.
JWT_SHAPE = re.compile(r"eyJ[\w-]*\.[\w-]*\.[\w-]*")


def _sha256(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _sign_in(client):
    # No Origin header: a native client, whose tokens come back in the body.
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return response.get_json()


def _row(mock_db, token):
    return mock_db["refresh_tokens"].find_one({"token_hash": _sha256(token)})


def _as_old_row(mock_db, token):
    """The row of ``token`` as the code before the change wrote it: the token itself, no hash."""
    mock_db["refresh_tokens"].update_one(
        {"token_hash": _sha256(token)}, {"$set": {"token": token}, "$unset": {"token_hash": ""}}
    )


def test_a_login_keeps_the_hash_and_not_the_token(client, mock_db):
    token = _sign_in(client)["refresh_token"]

    rows = list(mock_db["refresh_tokens"].find({"username": "admin"}))
    assert len(rows) == 1
    assert "token" not in rows[0]
    assert rows[0]["token_hash"] == _sha256(token)
    assert token not in repr(rows[0])


def test_a_refresh_with_the_issued_token_renews_the_session(client):
    token = _sign_in(client)["refresh_token"]

    response = client.post("/api/auth/refresh", json={"refresh_token": token})

    assert response.status_code == 200
    renewed = response.get_json()["refresh_token"]
    assert renewed and renewed != token


def test_a_logout_with_the_token_removes_its_session(client, mock_db):
    token = _sign_in(client)["refresh_token"]
    other = create_refresh_token("someone-else")

    response = client.post("/api/auth/logout", json={"refresh_token": token})

    assert response.status_code == 200
    assert mock_db["refresh_tokens"].find_one({"token_hash": _sha256(token)}) is None
    assert mock_db["refresh_tokens"].find_one({"token_hash": _sha256(other)}) is not None


def test_a_session_written_with_the_token_moves_to_its_hash_at_startup(client, mock_db):
    token = create_refresh_token("admin")
    _as_old_row(mock_db, token)

    ensure_indexes()

    row = mock_db["refresh_tokens"].find_one({"token_hash": _sha256(token)})
    assert row is not None and "token" not in row
    assert client.post("/api/auth/refresh", json={"refresh_token": token}).status_code == 200


def test_the_move_finds_the_row_by_its_hash_and_drops_the_token(mock_db):
    token = create_refresh_token("admin")
    _as_old_row(mock_db, token)

    assert migrate_refresh_token_hashes() == 1

    row = mock_db["refresh_tokens"].find_one({"token_hash": _sha256(token)})
    assert row is not None and "token" not in row


def test_the_move_is_fine_on_an_empty_collection_and_changes_nothing_twice(mock_db):
    assert migrate_refresh_token_hashes() == 0

    _as_old_row(mock_db, create_refresh_token("admin"))
    assert migrate_refresh_token_hashes() == 1
    assert migrate_refresh_token_hashes() == 0


def test_no_jwt_is_kept_in_any_field_after_refreshes(client, mock_db):
    first = _sign_in(client)["refresh_token"]
    second = client.post("/api/auth/refresh", json={"refresh_token": first}).get_json()["refresh_token"]
    third = client.post("/api/auth/refresh", json={"refresh_token": second}).get_json()["refresh_token"]

    rows = list(mock_db["refresh_tokens"].find({}))
    strings = [value for row in rows for value in row.values() if isinstance(value, str)]
    assert strings and not any(JWT_SHAPE.search(value) for value in strings)
    assert not any(token in repr(rows) for token in (first, second, third))


def test_a_spent_token_within_grace_gets_the_successor_it_was_given(client, mock_db):
    first = _sign_in(client)["refresh_token"]
    second = client.post("/api/auth/refresh", json={"refresh_token": first}).get_json()["refresh_token"]
    assert _row(mock_db, first)["replaced_by"] != second

    again = client.post("/api/auth/refresh", json={"refresh_token": first})

    assert again.status_code == 200
    assert again.get_json()["refresh_token"] == second


def test_a_successor_that_does_not_open_ends_the_sign_in(client, mock_db):
    first = _sign_in(client)["refresh_token"]
    second = client.post("/api/auth/refresh", json={"refresh_token": first}).get_json()["refresh_token"]
    mock_db["refresh_tokens"].update_one({"token_hash": _sha256(first)}, {"$set": {"replaced_by": "gAAAAAdamaged"}})

    assert client.post("/api/auth/refresh", json={"refresh_token": first}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": second}).status_code == 401


def test_a_successor_opens_only_when_it_was_sealed(mock_db):
    token = create_refresh_token("admin")
    sealed = seal_refresh_successor(token)

    assert sealed != token and not sealed.startswith("eyJ")
    assert open_refresh_successor(sealed) == token
    assert open_refresh_successor(token) is None
    assert open_refresh_successor(None) is None
    assert open_refresh_successor("gAAAAAdamaged") is None


def test_the_successor_key_comes_from_the_jwt_secret(mock_db, monkeypatch):
    sealed = seal_refresh_successor(create_refresh_token("admin"))

    monkeypatch.setitem(JWT_CONFIG, "secret_key", "a-different-secret")

    assert open_refresh_successor(sealed) is None


def test_startup_seals_a_successor_kept_as_a_token_and_the_grace_window_still_answers(client, mock_db):
    first = _sign_in(client)["refresh_token"]
    second = client.post("/api/auth/refresh", json={"refresh_token": first}).get_json()["refresh_token"]
    # The spent row as the code before the change wrote it: the successor itself, as a token.
    mock_db["refresh_tokens"].update_one({"token_hash": _sha256(first)}, {"$set": {"replaced_by": second}})

    ensure_indexes()

    stored = _row(mock_db, first)["replaced_by"]
    assert not stored.startswith("eyJ") and open_refresh_successor(stored) == second
    again = client.post("/api/auth/refresh", json={"refresh_token": first})
    assert again.status_code == 200 and again.get_json()["refresh_token"] == second


def test_the_move_seals_a_plain_successor_once(mock_db):
    first = create_refresh_token("admin")
    _, second = rotate_refresh_token(first)
    mock_db["refresh_tokens"].update_one({"token_hash": _sha256(first)}, {"$set": {"replaced_by": second}})

    assert migrate_refresh_successors() == 1
    assert open_refresh_successor(_row(mock_db, first)["replaced_by"]) == second
    assert migrate_refresh_successors() == 0


def test_the_move_leaves_a_sealed_successor_alone(client, mock_db):
    token = _sign_in(client)["refresh_token"]
    client.post("/api/auth/refresh", json={"refresh_token": token})
    sealed = _row(mock_db, token)["replaced_by"]

    assert migrate_refresh_successors() == 0
    assert _row(mock_db, token)["replaced_by"] == sealed
