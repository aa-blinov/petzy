"""Sessions end when an account is disabled or its password changes; the
login limit is per client; other sites get no CORS access."""

from web.security import create_refresh_token


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_a_disabled_user_is_signed_out_at_once(client, regular_user_token, auth_headers):
    assert client.get("/api/pets", headers=_bearer(regular_user_token)).status_code == 200
    assert client.delete("/api/users/testuser", headers=auth_headers).status_code == 200
    assert client.get("/api/pets", headers=_bearer(regular_user_token)).status_code == 401


def test_a_disabled_users_refresh_token_is_refused(client, mock_db, regular_user):
    refresh = create_refresh_token("testuser")
    mock_db["users"].update_one({"username": "testuser"}, {"$set": {"is_active": False}})
    client.set_cookie("refresh_token", refresh)
    assert client.post("/api/auth/refresh").status_code == 401


def test_a_password_reset_ends_open_sessions(client, mock_db, regular_user, auth_headers):
    create_refresh_token("testuser")
    response = client.post(
        "/api/users/testuser/reset-password", json={"password": "a-new-password-1"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert mock_db["refresh_tokens"].count_documents({"username": "testuser"}) == 0


def test_a_token_for_a_login_that_does_not_exist_is_refused(client):
    from web.security import create_access_token

    assert client.get("/api/pets", headers=_bearer(create_access_token("ghost"))).status_code == 401


def test_the_login_limit_is_per_client_not_global(client):
    attacker = {"X-Forwarded-For": "203.0.113.7"}
    # The window is fixed, so a minute boundary inside the run restarts the count: keep going until it trips.
    for _ in range(12):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}, headers=attacker)
        if response.status_code == 429:
            break
    assert response.status_code == 429
    someone_else = {"X-Forwarded-For": "203.0.113.8"}
    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}, headers=someone_else)
    assert response.status_code == 401


def test_other_sites_get_no_cors_access(client, auth_headers):
    response = client.get("/api/pets", headers={**auth_headers, "Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in response.headers


def test_a_new_password_ends_even_the_open_access_tokens(
    client, mock_db, regular_user, regular_user_token, auth_headers
):
    """The access token lives 15 minutes; a password reset must not wait for it."""
    import time as _time

    mock_db["users"].update_one({"username": "testuser"}, {"$set": {"sessions_valid_after": int(_time.time()) + 1}})
    assert client.get("/api/pets", headers=_bearer(regular_user_token)).status_code == 401
