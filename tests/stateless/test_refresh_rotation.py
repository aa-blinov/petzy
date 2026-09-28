"""Every refresh spends the token; a spent one presented later ends the sign-in."""

import itertools
from datetime import datetime, timedelta, timezone

from web import security

_addresses = itertools.count(1)


def _sign_in(client):
    who = {"X-Forwarded-For": f"198.18.1.{next(_addresses) % 250 + 1}"}
    return client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}, headers=who).get_json()


def _refresh(client, token):
    return client.application.test_client().post("/api/auth/refresh", json={"refresh_token": token})


def test_a_refresh_hands_out_a_new_refresh_token(client):
    first = _sign_in(client)["refresh_token"]
    response = _refresh(client, first)
    assert response.status_code == 200
    second = response.get_json()["refresh_token"]
    assert second and second != first
    # The successor works, and hands out one of its own.
    assert _refresh(client, second).status_code == 200


def test_two_refreshes_at_once_both_carry_on(client):
    first = _sign_in(client)["refresh_token"]
    a = _refresh(client, first).get_json()["refresh_token"]
    b = _refresh(client, first).get_json()["refresh_token"]
    assert a == b


def test_a_spent_token_used_later_ends_the_sign_in(client, mock_db):
    first = _sign_in(client)["refresh_token"]
    second = _refresh(client, first).get_json()["refresh_token"]
    # Past the grace window.
    mock_db["refresh_tokens"].update_one(
        {"token": first}, {"$set": {"rotated_at": datetime.now(timezone.utc) - timedelta(minutes=5)}}
    )
    assert _refresh(client, first).status_code == 401
    # The thief's copy and the owner's current token are both gone.
    assert _refresh(client, second).status_code == 401


def test_reuse_ends_only_that_sign_in(client, mock_db):
    phone = _sign_in(client)["refresh_token"]
    laptop = _sign_in(client)["refresh_token"]
    _refresh(client, phone)
    mock_db["refresh_tokens"].update_one(
        {"token": phone}, {"$set": {"rotated_at": datetime.now(timezone.utc) - timedelta(minutes=5)}}
    )
    assert _refresh(client, phone).status_code == 401
    assert _refresh(client, laptop).status_code == 200


def test_the_web_app_gets_the_new_token_as_a_cookie_only(client):
    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        headers={"Origin": "https://petzy.duckdns.org", "X-Forwarded-For": "198.18.2.1"},
    )
    assert login.status_code == 200
    response = client.post("/api/auth/refresh", headers={"Origin": "https://petzy.duckdns.org"})
    assert response.status_code == 200
    assert "refresh_token" not in response.get_json()
    cookies = " ".join(response.headers.getlist("Set-Cookie"))
    assert "refresh_token=ey" in cookies


def test_a_silent_refresh_renews_the_refresh_cookie_too(client, mock_db):
    refresh = security.create_refresh_token("admin")
    client.set_cookie("refresh_token", refresh)
    response = client.get("/api/pets")  # no access token: the refresh cookie signs it in
    assert response.status_code == 200
    cookies = " ".join(response.headers.getlist("Set-Cookie"))
    assert "access_token=ey" in cookies and "refresh_token=ey" in cookies
    assert mock_db["refresh_tokens"].find_one({"token": refresh})["rotated_at"]
