"""Signing out ends one sign-in: the one on this device. A logout everywhere ends every sign-in of the user.

A sign-in is the family of refresh tokens that one login hands out and its rotations carry on. Its access tokens name
it (``sid``), so ending the sign-in stops them at once, while the sign-ins on the other devices carry on.
"""

import itertools

_addresses = itertools.count(1)
PAGE = {"Origin": "https://petzy.duckdns.org"}


def _from(extra=None):
    return {"X-Forwarded-For": f"198.19.1.{next(_addresses) % 250 + 1}", **(extra or {})}


def _sign_in(client):
    """A sign-in as the app makes it: the tokens come back in the body."""
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}, headers=_from())
    assert response.status_code == 200
    return response.get_json()


def _browser_sign_in(client):
    """A sign-in as the web app makes it: the tokens come back as cookies."""
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}, headers=_from(PAGE))
    assert response.status_code == 200
    return {
        header.split("=")[0]: header.split(";")[0].split("=", 1)[1] for header in response.headers.getlist("Set-Cookie")
    }


def _jar(client, **cookies):
    """A client that keeps the given cookies in its jar, as a browser does: a Cookie header sent by hand is replaced."""
    jar = client.application.test_client()
    for name, value in cookies.items():
        jar.set_cookie(name, value)
    return jar


def _session(client, access):
    return client.get("/api/auth/session", headers={"Authorization": f"Bearer {access}"})


def _refresh(client, refresh):
    return client.post("/api/auth/refresh", json={"refresh_token": refresh})


def _logout(client, body=None, headers=None):
    return client.post("/api/auth/logout", json=body, headers=headers or {})


class TestSignOut:
    def test_a_logout_ends_this_devices_sign_in_and_no_other(self, client):
        here = _sign_in(client)
        there = _sign_in(client)

        response = _logout(client, {"refresh_token": here["refresh_token"]})

        assert response.status_code == 200
        assert _session(client, here["access_token"]).status_code == 401
        assert _refresh(client, here["refresh_token"]).status_code == 401
        assert _session(client, there["access_token"]).status_code == 200
        assert _refresh(client, there["refresh_token"]).status_code == 200

    def test_a_browser_signs_out_by_its_cookies_and_only_there(self, client):
        browser = _browser_sign_in(client)
        native = _sign_in(client)

        response = _jar(client, **browser).post("/api/auth/logout", headers=PAGE)

        assert response.status_code == 200
        assert (
            _jar(client, access_token=browser["access_token"]).get("/api/auth/session", headers=PAGE).status_code == 401
        )
        assert (
            _jar(client, refresh_token=browser["refresh_token"]).post("/api/auth/refresh", headers=PAGE).status_code
            == 401
        )
        assert _session(client, native["access_token"]).status_code == 200

    def test_a_logout_everywhere_ends_every_sign_in(self, client):
        here = _sign_in(client)
        there = _sign_in(client)

        response = _logout(client, {"refresh_token": here["refresh_token"], "everywhere": True})

        assert response.status_code == 200
        assert _session(client, here["access_token"]).status_code == 401
        assert _session(client, there["access_token"]).status_code == 401
        assert _refresh(client, there["refresh_token"]).status_code == 401

    def test_a_logout_with_only_the_access_token_still_ends_its_sign_in(self, client):
        here = _sign_in(client)
        there = _sign_in(client)

        response = _logout(client, headers={"Authorization": f"Bearer {here['access_token']}"})

        assert response.status_code == 200
        assert _session(client, here["access_token"]).status_code == 401
        assert _session(client, there["access_token"]).status_code == 200

    def test_a_sign_in_ended_by_a_reused_refresh_token_stops_its_access_tokens(self, client, monkeypatch):
        monkeypatch.setattr("web.security.REFRESH_REUSE_GRACE_SECONDS", 0)
        here = _sign_in(client)
        there = _sign_in(client)
        assert _refresh(client, here["refresh_token"]).status_code == 200

        # The first token, presented again after its grace, is a stolen copy: this sign-in ends with its tokens.
        assert _refresh(client, here["refresh_token"]).status_code == 401
        assert _session(client, here["access_token"]).status_code == 401
        assert _session(client, there["access_token"]).status_code == 200
        assert _refresh(client, there["refresh_token"]).status_code == 200

    def test_a_token_naming_no_sign_in_takes_no_other_row_with_it(self, client, mock_db):
        """A row with no family must not match {"family": None}, which finds every row without one."""
        from web.db import refresh_token_hash

        legacy = _sign_in(client)["refresh_token"]
        mock_db["refresh_tokens"].update_one({"token_hash": refresh_token_hash(legacy)}, {"$unset": {"family": ""}})
        mock_db["refresh_tokens"].insert_one({"token_hash": refresh_token_hash("orphan"), "username": "admin"})

        response = _logout(client, {"refresh_token": "orphan"})

        assert response.status_code == 200
        assert mock_db["refresh_tokens"].find_one({"token_hash": refresh_token_hash("orphan")}) is None
        assert mock_db["refresh_tokens"].find_one({"token_hash": refresh_token_hash(legacy)}) is not None
