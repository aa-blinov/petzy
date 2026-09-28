"""A native app (no Origin header) gets its tokens in the body and works with Bearer."""

import itertools

_addresses = itertools.count(1)


def _from():
    return {"X-Forwarded-For": f"198.18.0.{next(_addresses) % 250 + 1}"}


def test_a_native_login_returns_tokens_that_work_as_bearer(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}, headers=_from())
    body = response.get_json()
    assert response.status_code == 200 and body["access_token"] and body["refresh_token"]

    fresh = client.application.test_client()  # no cookies at all
    assert fresh.get("/api/pets", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 200


def test_a_native_client_refreshes_and_signs_out_with_the_body_token(client, mock_db):
    tokens = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}, headers=_from()
    ).get_json()
    fresh = client.application.test_client()
    refreshed = fresh.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200 and refreshed.get_json()["access_token"]

    assert fresh.post("/api/auth/logout", json={"refresh_token": tokens["refresh_token"]}).status_code == 200
    assert mock_db["refresh_tokens"].count_documents({"username": "admin"}) == 0
    assert fresh.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_a_page_never_gets_tokens_in_the_body(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        headers={"Origin": "https://petzy.duckdns.org", **_from()},
    )
    assert response.status_code == 200
    assert "access_token" not in response.get_json() and "refresh_token" not in response.get_json()


def test_a_native_sign_up_returns_tokens(client):
    response = client.post(
        "/api/auth/register",
        json={"username": "native1", "password": "kotik-2026", "full_name": "Вера", "privacy_consent": True},
        headers=_from(),
    )
    assert response.status_code == 201 and response.get_json()["refresh_token"]
