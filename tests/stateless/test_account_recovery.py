"""Recovery by email: confirm an address, get a one-time link, set a new password."""

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
        json={"username": username, "password": password, "email": email},
        headers=_from(client),
    )
    assert response.status_code == 201, response.get_json()
    return response


def _confirm(client, outbox):
    token = _link_token(outbox[-1], "/verify-email")
    return client.post("/api/auth/email/verify", json={"token": token}, headers=_from(client))


def test_sign_up_with_an_email_sends_a_confirmation(client, mock_db, outbox):
    _sign_up(client)
    assert outbox[-1]["to"] == "vera@example.com"
    user = mock_db["users"].find_one({"username": "vera"})
    assert user["pending_email"] == "vera@example.com" and not user["email_verified"]
    assert _confirm(client, outbox).status_code == 200
    user = mock_db["users"].find_one({"username": "vera"})
    assert user["email"] == "vera@example.com" and user["email_verified"] is True
    assert "pending_email" not in user


def test_the_reset_link_sets_a_new_password_once(client, mock_db, outbox):
    _sign_up(client)
    _confirm(client, outbox)
    other = client.application.test_client()
    other.post("/api/auth/login", json={"username": "vera", "password": "kotik-2026"}, headers=_from(client))

    assert client.post("/api/auth/password/forgot", json={"login": "vera"}, headers=_from(client)).status_code == 200
    token = _link_token(outbox[-1], "/reset-password")
    response = client.post(
        "/api/auth/password/reset", json={"token": token, "password": "new-secret-42"}, headers=_from(client)
    )
    assert response.status_code == 200
    # Signed in with the new password; the other device is signed out.
    assert client.get("/api/auth/session").get_json()["username"] == "vera"
    assert mock_db["refresh_tokens"].count_documents({"username": "vera"}) == 1
    assert (
        client.post(
            "/api/auth/login", json={"username": "vera", "password": "new-secret-42"}, headers=_from(client)
        ).status_code
        == 200
    )
    # The same link a second time does nothing.
    again = client.post(
        "/api/auth/password/reset", json={"token": token, "password": "third-pass-77"}, headers=_from(client)
    )
    assert again.status_code == 422
    assert again.get_json()["code"] == "account_link_invalid"


def test_the_email_itself_can_be_used_to_ask(client, outbox):
    _sign_up(client)
    _confirm(client, outbox)
    client.post("/api/auth/password/forgot", json={"login": "VERA@example.com"}, headers=_from(client))
    assert outbox[-1]["subject"] == "Petzy: новый пароль"


def test_the_answer_never_tells_whether_an_account_exists(client, outbox):
    _sign_up(client, email="")
    answers = {
        client.post("/api/auth/password/forgot", json={"login": login}, headers=_from(client)).get_json()["message"]
        for login in ("vera", "nobody-here", "ghost@example.com")
    }
    assert len(answers) == 1
    # vera has no confirmed email: nothing was sent to anyone.
    assert outbox == []


def test_an_unconfirmed_email_gets_no_reset_link(client, outbox):
    _sign_up(client)
    outbox.clear()
    client.post("/api/auth/password/forgot", json={"login": "vera"}, headers=_from(client))
    assert outbox == []


def test_an_expired_link_does_not_work(client, mock_db, outbox):
    _sign_up(client)
    _confirm(client, outbox)
    client.post("/api/auth/password/forgot", json={"login": "vera"}, headers=_from(client))
    token = _link_token(outbox[-1], "/reset-password")
    mock_db["account_tokens"].update_many(
        {}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}}
    )
    response = client.post(
        "/api/auth/password/reset", json={"token": token, "password": "new-secret-42"}, headers=_from(client)
    )
    assert response.get_json()["code"] == "account_link_invalid"


def test_a_weak_password_does_not_spend_the_link(client, outbox):
    _sign_up(client)
    _confirm(client, outbox)
    client.post("/api/auth/password/forgot", json={"login": "vera"}, headers=_from(client))
    token = _link_token(outbox[-1], "/reset-password")
    weak = client.post("/api/auth/password/reset", json={"token": token, "password": "123"}, headers=_from(client))
    assert weak.get_json()["code"] == "register_password_short"
    ok = client.post(
        "/api/auth/password/reset", json={"token": token, "password": "new-secret-42"}, headers=_from(client)
    )
    assert ok.status_code == 200


def test_only_the_hash_of_a_link_is_stored(client, mock_db, outbox):
    _sign_up(client)
    token = _link_token(outbox[-1], "/verify-email")
    stored = mock_db["account_tokens"].find_one({})
    assert token not in str(stored)


def test_changing_the_email_needs_the_password(client, mock_db, outbox):
    _sign_up(client, email="")
    wrong = client.put("/api/me/email", json={"email": "new@example.com", "password": "nope"}, headers=_from(client))
    assert wrong.get_json()["code"] == "account_wrong_password"
    ok = client.put("/api/me/email", json={"email": "new@example.com", "password": "kotik-2026"}, headers=_from(client))
    assert ok.status_code == 200
    assert ok.get_json()["pending_email"] == "new@example.com"
    assert outbox[-1]["to"] == "new@example.com"


def test_a_new_address_is_announced_to_the_old_one(client, outbox):
    _sign_up(client)
    _confirm(client, outbox)
    client.put("/api/me/email", json={"email": "vera2@example.com", "password": "kotik-2026"}, headers=_from(client))
    _confirm(client, outbox)
    notice = [letter for letter in outbox if letter["subject"] == "Petzy: почта аккаунта изменена"]
    assert notice and notice[0]["to"] == "vera@example.com"
    assert "vera2@example.com" not in notice[0]["text"]  # masked


def test_one_address_recovers_one_account(client, outbox):
    _sign_up(client)
    _confirm(client, outbox)
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/register",
        json={"username": "boris", "password": "kotik-2026", "email": "Vera@Example.com"},
        headers=_from(client),
    )
    assert response.get_json()["code"] == "account_email_taken"


def test_changing_the_password_in_settings(client, mock_db, outbox):
    _sign_up(client)
    _confirm(client, outbox)
    wrong = client.put(
        "/api/me/password", json={"current_password": "nope", "new_password": "new-secret-42"}, headers=_from(client)
    )
    assert wrong.get_json()["code"] == "account_wrong_password"
    ok = client.put(
        "/api/me/password",
        json={"current_password": "kotik-2026", "new_password": "new-secret-42"},
        headers=_from(client),
    )
    assert ok.status_code == 200
    assert outbox[-1]["subject"] == "Petzy: пароль изменён"
    # This session carries on with fresh cookies.
    assert client.get("/api/auth/session").status_code == 200


def test_the_account_shows_the_email_state(client, outbox):
    _sign_up(client)
    body = client.get("/api/me/account").get_json()
    assert body["email"] == "" and body["pending_email"] == "vera@example.com" and body["mail_enabled"] is True
    _confirm(client, outbox)
    body = client.get("/api/me/account").get_json()
    assert body["email"] == "vera@example.com" and body["email_verified"] is True and body["pending_email"] == ""


def test_the_dev_outbox_is_closed_in_production(client, monkeypatch):
    monkeypatch.delenv("MAIL_OUTBOX", raising=False)
    assert client.get("/api/dev/outbox").status_code == 404
