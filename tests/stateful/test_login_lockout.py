"""A login locks after ten wrong passwords within fifteen minutes, whatever addresses they came from.

The per-address limit on sign-in (five a minute) cannot stop a guesser who uses several addresses, so each
attempt here comes from an address of its own: only the count kept for the login can refuse them. The
count is kept for a login that does not exist as well, and a locked login answers like a wrong password.
"""

import itertools
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import password_hash_for

PASSWORD = "user123"  # conftest's regular_user, testuser
_addresses = itertools.count(1)


def _login(client, username, password):
    """One sign-in attempt from an address of its own."""
    address = f"198.51.100.{next(_addresses) % 250 + 1}"
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
        headers={"X-Forwarded-For": address},
    )


def _wrong(client, username, times):
    for _ in range(times):
        assert _login(client, username, "wrong-guess").status_code == 401


def _end_row(mock_db, username, moment):
    mock_db.login_failures.update_one({"_id": username}, {"$set": {"expires_at": moment}})


def test_nine_wrong_passwords_do_not_lock_the_login(client, mock_db, regular_user):
    _wrong(client, "testuser", 9)

    assert _login(client, "testuser", PASSWORD).status_code == 200


def test_ten_wrong_passwords_lock_the_login_for_the_right_password_too(client, mock_db, regular_user):
    _wrong(client, "testuser", 10)
    started = datetime.now(timezone.utc)

    refused = _login(client, "testuser", PASSWORD)

    assert refused.status_code == 401
    assert refused.get_json()["code"] == "unauthorized_invalid_credentials"
    # The lock runs fifteen minutes from the tenth wrong password.
    ends = mock_db.login_failures.find_one({"_id": "testuser"})["expires_at"]
    ends = ends if ends.tzinfo else ends.replace(tzinfo=timezone.utc)
    assert timedelta(minutes=14) < ends - started <= timedelta(minutes=15)


def test_the_count_starts_again_once_its_window_is_over(client, mock_db, regular_user):
    _wrong(client, "testuser", 9)
    _end_row(mock_db, "testuser", datetime.now(timezone.utc) - timedelta(seconds=1))

    _wrong(client, "testuser", 9)

    assert _login(client, "testuser", PASSWORD).status_code == 200


def test_a_locked_login_answers_as_a_wrong_password_does_even_for_a_login_nobody_has(client, mock_db, regular_user):
    wrong_for_account = _login(client, "testuser", "wrong-guess")
    wrong_for_nobody = _login(client, "ghost", "wrong-guess")
    assert wrong_for_account.status_code == wrong_for_nobody.status_code == 401
    _wrong(client, "testuser", 9)
    _wrong(client, "ghost", 9)

    locked_account = _login(client, "testuser", PASSWORD)
    assert locked_account.status_code == 401
    assert locked_account.get_json() == wrong_for_account.get_json()

    # The count was kept for the login nobody had, so once someone registers it, its right password is refused too.
    mock_db["users"].insert_one(
        {
            "username": "ghost",
            "password_hash": password_hash_for(b"ghost-pass"),
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
    )
    locked_nobody = _login(client, "ghost", "ghost-pass")
    assert locked_nobody.status_code == 401
    assert locked_nobody.get_json() == wrong_for_nobody.get_json()


def test_a_right_password_before_the_lock_clears_the_count(client, mock_db, regular_user):
    _wrong(client, "testuser", 9)
    assert _login(client, "testuser", PASSWORD).status_code == 200

    _wrong(client, "testuser", 9)

    assert _login(client, "testuser", PASSWORD).status_code == 200


def test_capitals_and_spaces_count_as_the_same_login(client, mock_db, regular_user):
    spellings = ["TestUser", " testuser ", "TESTUSER", "testuser"]
    for i in range(10):
        assert _login(client, spellings[i % len(spellings)], "wrong-guess").status_code == 401

    assert _login(client, "TeStUsEr", PASSWORD).status_code == 401


def test_the_lock_ends_with_its_time(client, mock_db, regular_user):
    _wrong(client, "testuser", 10)
    assert _login(client, "testuser", PASSWORD).status_code == 401

    # The time of the lock is over; the row itself may still be there until the TTL monitor sweeps it.
    _end_row(mock_db, "testuser", datetime.now(timezone.utc) - timedelta(seconds=1))

    assert _login(client, "testuser", PASSWORD).status_code == 200


def test_deleting_the_account_clears_its_count(client, mock_db, regular_user, regular_user_token):
    _wrong(client, "testuser", 3)
    assert mock_db.login_failures.find_one({"_id": "testuser"}) is not None

    response = client.delete(
        "/api/me/account",
        json={"password": PASSWORD},
        headers={"Authorization": f"Bearer {regular_user_token}"},
    )

    assert response.status_code == 200
    assert mock_db.login_failures.find_one({"_id": "testuser"}) is None


def test_an_account_kept_with_capitals_shares_its_count_with_the_lowercase_login(client, mock_db):
    """An administrator's account keeps its spelling: «Vera» is found as typed, and its count is kept with «vera»."""
    mock_db["users"].insert_one(
        {
            "username": "Vera",
            "password_hash": password_hash_for(b"vera-pass"),
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
    )
    for i in range(10):
        spelling = "Vera" if i % 2 == 0 else "vera"
        assert _login(client, spelling, "wrong-guess").status_code == 401

    assert _login(client, "Vera", "vera-pass").status_code == 401


def test_the_lock_runs_from_the_tenth_wrong_password_not_from_the_start_of_the_window(client, mock_db, regular_user):
    _wrong(client, "testuser", 9)
    # The window would end in a minute; the tenth wrong password must still lock the login for fifteen minutes.
    _end_row(mock_db, "testuser", datetime.now(timezone.utc) + timedelta(minutes=1))
    _wrong(client, "testuser", 1)
    ends = mock_db.login_failures.find_one({"_id": "testuser"})["expires_at"]
    ends = ends if ends.tzinfo else ends.replace(tzinfo=timezone.utc)

    assert ends - datetime.now(timezone.utc) > timedelta(minutes=14)
    assert _login(client, "testuser", PASSWORD).status_code == 401


def test_the_dev_reset_on_the_local_stand_lifts_a_lock(client, mock_db, regular_user, monkeypatch):
    monkeypatch.setenv("PETZY_DEV_TOOLS", "1")
    monkeypatch.setenv("MAIL_OUTBOX", "memory")
    _wrong(client, "testuser", 10)
    assert _login(client, "testuser", PASSWORD).status_code == 401

    assert client.post("/api/dev/reset-limits").status_code == 200

    assert _login(client, "testuser", PASSWORD).status_code == 200


@pytest.mark.parametrize(
    "switches",
    [
        {"PETZY_DEV_TOOLS": "1"},  # one switch alone is not the local stand
        {"MAIL_OUTBOX": "memory"},
        {},  # production: neither switch
    ],
)
def test_the_dev_reset_is_404_off_the_local_stand_and_keeps_the_lock(
    client, mock_db, regular_user, monkeypatch, switches
):
    monkeypatch.delenv("PETZY_DEV_TOOLS", raising=False)
    monkeypatch.delenv("MAIL_OUTBOX", raising=False)
    for name, value in switches.items():
        monkeypatch.setenv(name, value)
    _wrong(client, "testuser", 10)

    assert client.post("/api/dev/reset-limits").status_code == 404
    assert _login(client, "testuser", PASSWORD).status_code == 401
