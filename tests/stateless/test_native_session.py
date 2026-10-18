"""A native app and a browser keep their sessions apart.

A browser keeps its session in httpOnly cookies and renews it by itself. A native app keeps its tokens itself: it gets
them in the body and no cookies, so there is only one copy of its refresh token. A request that names its token in the
header is never renewed from a cookie: that renewal would spend the copy the app keeps, and the next renewal by the app
would end the whole sign-in.
"""

import itertools

_addresses = itertools.count(1)
PAGE = {"Origin": "https://petzy.duckdns.org"}


def _from(extra=None):
    return {"X-Forwarded-For": f"198.19.0.{next(_addresses) % 250 + 1}", **(extra or {})}


def _login(client, headers):
    return client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}, headers=headers)


def _cookie_names(response):
    return [header.split("=")[0] for header in response.headers.getlist("Set-Cookie")]


def _jar(client, **cookies):
    """A client that keeps the given cookies in its jar, as a browser does. The test client takes cookies from its
    jar: a Cookie header sent by hand is replaced by it, and a test would pass without testing anything."""
    jar = client.application.test_client()
    for name, value in cookies.items():
        jar.set_cookie(name, value)
    return jar


def _cookie_value(response, name):
    header = next(h for h in response.headers.getlist("Set-Cookie") if h.startswith(name + "="))
    return header.split(";")[0].split("=", 1)[1]


class TestNativeAndBrowserSessions:
    def test_a_native_sign_in_gets_the_tokens_and_no_cookies(self, client):
        response = _login(client, _from())

        assert response.status_code == 200
        assert response.get_json()["access_token"] and response.get_json()["refresh_token"]
        assert _cookie_names(response) == []

    def test_a_browser_sign_in_gets_cookies_and_no_tokens_in_the_body(self, client):
        response = _login(client, _from(PAGE))

        assert response.status_code == 200
        assert {"access_token", "refresh_token"} <= set(_cookie_names(response))
        assert "refresh_token" not in response.get_json()

    def test_a_native_refresh_sets_no_cookies(self, client):
        tokens = _login(client, _from()).get_json()

        response = client.application.test_client().post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        assert response.status_code == 200
        assert response.get_json()["refresh_token"]
        assert _cookie_names(response) == []

    def test_a_bearer_request_with_a_spent_token_is_not_renewed_from_a_cookie(self, client):
        tokens = _login(client, _from()).get_json()

        response = _jar(client, refresh_token=tokens["refresh_token"]).get(
            "/api/pets", headers={"Authorization": "Bearer expired-token"}
        )

        assert response.status_code == 401
        assert _cookie_names(response) == []

    def test_the_app_can_still_renew_with_its_own_token_after_such_a_request(self, client, monkeypatch):
        """The grace is zero here: a spent token is refused at once, as a phone renewing after 30 seconds would be.
        The app's own token must still renew the sign-in after the refused request."""
        monkeypatch.setattr("web.security.REFRESH_REUSE_GRACE_SECONDS", 0)
        tokens = _login(client, _from()).get_json()
        _jar(client, refresh_token=tokens["refresh_token"]).get(
            "/api/pets", headers={"Authorization": "Bearer expired-token"}
        )

        response = client.application.test_client().post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

        assert response.status_code == 200

    def test_a_browser_whose_access_cookie_ran_out_is_renewed_from_its_cookie(self, client):
        browser = _login(client, _from(PAGE))
        refresh = _cookie_value(browser, "refresh_token")

        response = _jar(client, access_token="expired", refresh_token=refresh).get("/api/pets", headers=PAGE)

        assert response.status_code == 200
        assert "access_token" in _cookie_names(response)
