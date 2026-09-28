"""Sentry stays off without a DSN, and never gets cookies, tokens or passwords."""

from web.observability import FILTERED, init_sentry, scrub_event


def test_off_without_a_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    assert init_sentry("web") is False


def test_secrets_are_taken_out_of_a_request():
    event = {
        "request": {
            "url": "https://petzy.duckdns.org/api/auth/login",
            "cookies": {"refresh_token": "r", "access_token": "a"},
            "headers": {"Authorization": "Bearer x", "Cookie": "a=b", "User-Agent": "Safari"},
            "data": {
                "username": "vera",
                "password": "kotik-2026",
                "nested": {"refresh_token": "r", "keys": {"p256dh": "k", "auth": "s"}},
                "items": [{"new_password": "x"}],
            },
            "query_string": "token=abc&x=1",
        }
    }
    request = scrub_event(event)["request"]
    assert "cookies" not in request
    assert request["headers"]["Authorization"] == FILTERED and request["headers"]["Cookie"] == FILTERED
    assert request["headers"]["User-Agent"] == "Safari"
    assert request["data"]["username"] == "vera"
    assert request["data"]["password"] == FILTERED
    assert request["data"]["nested"]["refresh_token"] == FILTERED
    assert request["data"]["nested"]["keys"] == FILTERED
    assert request["data"]["items"][0]["new_password"] == FILTERED
    assert request["query_string"] == FILTERED


def test_an_event_without_a_request_passes():
    assert scrub_event({"message": "x"}) == {"message": "x"}


def test_frame_variables_extra_and_breadcrumbs_are_scrubbed():
    event = {
        "exception": {"values": [{"stacktrace": {"frames": [{"vars": {"password": "p", "username": "vera"}}]}}]},
        "extra": {"refresh_token": "r"},
        "breadcrumbs": {"values": [{"data": {"authorization": "Bearer x", "url": "/api/pets"}}]},
    }
    scrubbed = scrub_event(event)
    assert scrubbed["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"] == {
        "password": FILTERED,
        "username": "vera",
    }
    assert scrubbed["extra"]["refresh_token"] == FILTERED
    assert scrubbed["breadcrumbs"]["values"][0]["data"] == {"authorization": FILTERED, "url": "/api/pets"}
