"""Hints about a password that arrive before the form is sent: whether the
letter's link still works, whether the password is one of the most guessed,
and whether the letter is already on its way."""

import itertools
import re
from datetime import datetime, timedelta, timezone

import pytest

from web import mail

_addresses = itertools.count(1)


def _from(client):
    """A fresh client address: every endpoint here is rate-limited per address."""
    return {"X-Forwarded-For": f"192.0.2.{next(_addresses) % 250 + 1}"}


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    monkeypatch.setenv("MAIL_OUTBOX", "memory")
    monkeypatch.setenv("APP_BASE_URL", "https://petzy.test")
    mail.OUTBOX.clear()
    yield mail.OUTBOX
    mail.OUTBOX.clear()


def _link_token(letter, path):
    match = re.search(rf"https://petzy\.test{path}\?token=([\w-]+)", letter["text"])
    assert match, letter["text"]
    return match.group(1)


def _sign_up(client, username="vera", email="vera@example.com", password="kotik-2026"):
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "email": email,
            "full_name": "Вера",
            "privacy_consent": True,
        },
        headers=_from(client),
    )
    assert response.status_code == 201, response.get_json()
    match = _link_token(mail.OUTBOX[-1], "/verify-email")
    assert client.post("/api/auth/email/verify", json={"token": match}, headers=_from(client)).status_code == 200
    return response


def _reset_link(client, login="vera"):
    client.post("/api/auth/password/forgot", json={"login": login}, headers=_from(client))
    return _link_token(mail.OUTBOX[-1], "/reset-password")


def _check(client, token):
    return client.get("/api/auth/password/reset/check", query_string={"token": token}, headers=_from(client))


def _common(client, password):
    return client.post("/api/auth/password/common", json={"password": password}, headers=_from(client))


# The link check


def test_a_fresh_link_passes_the_check(client, outbox):
    _sign_up(client)
    response = _check(client, _reset_link(client))
    assert response.status_code == 200
    assert response.get_json() == {"valid": True}


def test_the_check_does_not_spend_the_link(client, outbox):
    """The form still needs the link: asking about it changes nothing."""
    _sign_up(client)
    token = _reset_link(client)
    _check(client, token)
    assert (
        client.post(
            "/api/auth/password/reset", json={"token": token, "password": "new-secret-42"}, headers=_from(client)
        ).status_code
        == 200
    )


def test_a_link_that_was_used_does_not_pass(client, outbox):
    _sign_up(client)
    token = _reset_link(client)
    client.post("/api/auth/password/reset", json={"token": token, "password": "new-secret-42"}, headers=_from(client))
    assert _check(client, token).get_json() == {"valid": False}


def test_an_expired_link_does_not_pass(client, mock_db, outbox):
    _sign_up(client)
    token = _reset_link(client)
    mock_db["account_tokens"].update_many(
        {}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}}
    )
    assert _check(client, token).get_json() == {"valid": False}


def test_a_link_of_a_deleted_account_does_not_pass(client, mock_db, outbox):
    _sign_up(client)
    token = _reset_link(client)
    mock_db["users"].delete_many({})
    assert _check(client, token).get_json() == {"valid": False}


def test_an_unknown_token_does_not_pass(client, outbox):
    assert _check(client, "nothing-like-a-real-token").get_json() == {"valid": False}
    assert _check(client, "").get_json() == {"valid": False}


# The common passwords


def test_a_guessed_password_is_said_to_be_one(client):
    for password in ("password", "Password", "QWERTYUI", "йцукенгш", "12345678"):
        assert _common(client, password).get_json() == {"common": True}, password


def test_an_ordinary_password_is_not_one(client):
    assert _common(client, "kotik-2026").get_json() == {"common": False}


def test_the_list_of_guessed_passwords_does_not_leave_the_server(client):
    body = _common(client, "password").get_json()
    assert list(body) == ["common"]
    assert "password" not in str(body)


def test_a_password_nobody_would_guess_is_accepted_still(client, outbox):
    """The hint is a hint: the rule that refuses it is the old one."""
    _sign_up(client)
    weak = client.post("/api/auth/password/common", json={"password": "password"}, headers=_from(client))
    assert weak.get_json()["common"] is True
    assert (
        client.post(
            "/api/auth/register",
            json={
                "username": "boris",
                "password": "password",
                "full_name": "Борис",
                "email": "boris@example.com",
                "privacy_consent": True,
            },
            headers=_from(client),
        ).get_json()["code"]
        == "register_password_weak"
    )


# The letter that is already on its way


def test_the_first_request_says_the_letter_is_sent(client, outbox):
    _sign_up(client)
    body = client.post("/api/auth/password/forgot", json={"login": "vera"}, headers=_from(client)).get_json()
    assert body["already_sent"] is False
    assert len([letter for letter in outbox if letter["subject"] == "Petzy: новый пароль"]) == 1


def test_asking_again_by_the_confirmed_address_says_the_letter_is_already_on_its_way(client, outbox):
    _sign_up(client)
    client.post("/api/auth/password/forgot", json={"login": "vera@example.com"}, headers=_from(client))
    outbox.clear()
    body = client.post(
        "/api/auth/password/forgot", json={"login": "vera@example.com"}, headers=_from(client)
    ).get_json()
    assert body["already_sent"] is True
    # And no second letter is promised: none was sent.
    assert outbox == []


def test_asking_again_by_the_login_says_only_that_the_letter_went(client, outbox):
    # Someone who named the login has not proved they hold the mailbox, so the answer must not differ from the
    # answer for a login nobody has.
    _sign_up(client)
    client.post("/api/auth/password/forgot", json={"login": "vera"}, headers=_from(client))
    outbox.clear()
    body = client.post("/api/auth/password/forgot", json={"login": "vera"}, headers=_from(client)).get_json()
    assert body["already_sent"] is False
    assert outbox == []


def test_the_answer_says_nothing_about_which_logins_exist(client, outbox):
    _sign_up(client)
    client.post("/api/auth/password/forgot", json={"login": "vera"}, headers=_from(client))
    answers = {
        login: client.post("/api/auth/password/forgot", json={"login": login}, headers=_from(client)).get_json()
        for login in ("vera", "nobody-here", "ghost@example.com")
    }
    # The whole answer is the same for a real login and for a made-up one: neither the word nor the flag.
    assert len({answer["message"] for answer in answers.values()}) == 1
    assert {answer["already_sent"] for answer in answers.values()} == {False}


def test_asking_by_an_address_nobody_holds_says_nothing(client, outbox):
    _sign_up(client)
    client.post("/api/auth/password/forgot", json={"login": "vera@example.com"}, headers=_from(client))
    outbox.clear()
    body = client.post(
        "/api/auth/password/forgot", json={"login": "stranger@example.com"}, headers=_from(client)
    ).get_json()
    assert body["already_sent"] is False
