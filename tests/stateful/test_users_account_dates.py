"""An account whose creation date was written as text is answered with that text.

Every account the app makes has a creation date as a date. A row written before the field existed
has none, and a row written by hand may hold the date as text. Neither may break the answer: the
administrator sees what is stored, and a profile without a date says nothing instead of a date
that was never there.
"""

from datetime import datetime, timezone


def _account(mock_db, username, **fields):
    mock_db["users"].insert_one(
        {
            "username": username,
            "password_hash": "unused",
            "full_name": "Старый",
            "email": "",
            "created_by": "admin",
            "is_active": True,
            **fields,
        }
    )


def test_the_account_list_shows_a_date_that_was_written_as_text(client, mock_db, auth_headers):
    _account(mock_db, "old", created_at="2020-01-02T03:04:05")

    body = client.get("/api/users", headers=auth_headers).get_json()

    entry = next(user for user in body["users"] if user["username"] == "old")
    assert entry["created_at"] == "2020-01-02T03:04:05"


def test_the_administrator_sees_a_date_that_was_written_as_text(client, mock_db, auth_headers):
    _account(mock_db, "old", created_at="2020-01-02T03:04:05")

    body = client.get("/api/users/old", headers=auth_headers).get_json()

    assert body["user"]["created_at"] == "2020-01-02T03:04:05"


def test_the_profile_of_an_account_without_a_date_says_nothing(client, mock_db, auth_headers):
    _account(mock_db, "old")

    body = client.get("/api/users/old/profile", headers=auth_headers).get_json()

    assert body["created_at"] == ""


def test_an_account_with_a_date_still_shows_it(client, mock_db, auth_headers):
    _account(mock_db, "new", created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc))

    body = client.get("/api/users/new/profile", headers=auth_headers).get_json()

    assert body["created_at"].startswith("2026-01-02")


def test_the_account_list_says_nothing_about_a_missing_date(client, mock_db, auth_headers):
    # A row written before the field existed: the answer needs a date, and there is none.
    _account(mock_db, "old")

    body = client.get("/api/users", headers=auth_headers).get_json()

    entry = next(user for user in body["users"] if user["username"] == "old")
    assert entry["created_at"] == ""


def test_the_administrator_sees_an_account_without_a_date(client, mock_db, auth_headers):
    _account(mock_db, "old")

    body = client.get("/api/users/old", headers=auth_headers).get_json()

    assert body["user"]["created_at"] == ""
