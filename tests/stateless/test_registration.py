"""Anyone can sign up; the login and password rules keep look-alikes and weak passwords out."""

import itertools

import pytest

from web import auth


_addresses = itertools.count(1)


def _register(client, username="vera", password="kotik-2026", **extra):
    # Each call from its own address: the sign-up limit is per address and
    # shared by the whole test run.
    who = {"X-Forwarded-For": f"203.0.113.{next(_addresses) % 250 + 1}"}
    return client.post("/api/auth/register", json={"username": username, "password": password, **extra}, headers=who)


def test_sign_up_creates_the_account_and_signs_it_in(client, mock_db):
    response = _register(client, full_name="Вера")
    assert response.status_code == 201
    user = mock_db["users"].find_one({"username": "vera"})
    assert user["is_active"] is True and user["created_by"] == "self" and user["full_name"] == "Вера"
    assert user["password_hash"] != "kotik-2026"
    cookies = " ".join(response.headers.getlist("Set-Cookie"))
    assert "access_token=" in cookies and "refresh_token=" in cookies
    # The session works right away.
    assert client.get("/api/auth/session").get_json()["username"] == "vera"


def test_the_login_is_stored_lowercase_and_login_ignores_case(client, mock_db):
    assert _register(client, username="  Vera ").status_code == 201
    assert mock_db["users"].find_one({"username": "vera"})
    login = client.post(
        "/api/auth/login",
        json={"username": "Vera", "password": "kotik-2026"},
        # Its own address: other tests use up the login limit of 127.0.0.1.
        headers={"X-Forwarded-For": "198.51.100.77"},
    )
    assert login.status_code == 200


@pytest.mark.parametrize("username", ["ab", "вера", "vera!", "-vera", "a" * 31, "vеra"])  # last one: Cyrillic «е»
def test_bad_logins_are_refused(client, username):
    response = _register(client, username=username)
    assert response.status_code == 422
    assert response.get_json()["code"] == "register_username_invalid"


@pytest.mark.parametrize("username", ["admin", "Admin", "support", "petzy"])
def test_the_admin_and_service_names_are_taken(client, username):
    response = _register(client, username=username)
    assert response.status_code == 422
    assert response.get_json()["code"] == "register_username_taken"


def test_a_login_differing_only_in_case_is_taken(client, mock_db):
    mock_db["users"].insert_one({"username": "Anna", "password_hash": "x", "is_active": True})
    response = _register(client, username="anna")
    assert response.get_json()["code"] == "register_username_taken"


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("short", "register_password_short"),
        ("12345678", "register_password_weak"),
        ("aaaaaaaaaa", "register_password_weak"),
        ("vera12345"[:0] + "vera", "register_password_short"),
        ("я" * 40, "register_password_long"),
    ],
)
def test_weak_passwords_are_refused(client, password, code):
    response = _register(client, password=password)
    assert response.status_code == 422
    assert response.get_json()["code"] == code


def test_the_password_cannot_be_the_login(client):
    assert _register(client, username="verochka", password="VEROCHKA").get_json()["code"] == "register_password_weak"


def test_sign_up_can_be_closed(client, monkeypatch):
    monkeypatch.setenv("REGISTRATION_ENABLED", "false")
    assert client.get("/api/auth/registration").get_json()["open"] is False
    response = _register(client)
    assert response.status_code == 403
    assert response.get_json()["code"] == "registration_closed"


def test_sign_up_is_open_by_default(client, monkeypatch):
    monkeypatch.delenv("REGISTRATION_ENABLED", raising=False)
    assert auth.registration_open() is True
    assert client.get("/api/auth/registration").get_json()["open"] is True


def test_mistakes_do_not_use_up_the_sign_up_limit(client):
    who = {"X-Forwarded-For": "198.51.100.40"}
    for _ in range(6):
        client.post("/api/auth/register", json={"username": "vera", "password": "short"}, headers=who)
    ok = client.post("/api/auth/register", json={"username": "vera", "password": "kotik-2026"}, headers=who)
    assert ok.status_code == 201


def test_one_address_cannot_make_many_accounts(client):
    who = {"X-Forwarded-For": "198.51.100.23"}
    codes = [
        client.post(
            "/api/auth/register", json={"username": f"bot{i:03d}", "password": "kotik-2026"}, headers=who
        ).status_code
        for i in range(7)
    ]
    assert codes[:5] == [201] * 5
    assert codes[5] == 429
