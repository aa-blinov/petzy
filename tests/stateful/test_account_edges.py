"""The account's own answers: what happens to an address, to a letter and to a link at its edges.

The rules a person runs into without noticing them: an address can be removed, an address that is
not an address is refused, a letter that cannot be sent does not take the change back, a link that
was spent or that belongs to an account that is gone does not work, and the answer to a request for
a reset letter is the same for every login.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import password_hash_for
from web import mail
from web.security import create_access_token, verify_user_credentials

PASSWORD = "kotik-2026"
NEW_PASSWORD = "new-secret-42"


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    monkeypatch.setenv("MAIL_OUTBOX", "memory")
    monkeypatch.setenv("APP_BASE_URL", "https://petzy.test")
    mail.OUTBOX.clear()
    yield mail.OUTBOX
    mail.OUTBOX.clear()


@pytest.fixture
def vera(mock_db):
    """An account with a confirmed address."""
    mock_db["users"].insert_one(
        {
            "username": "vera",
            "password_hash": password_hash_for(PASSWORD.encode()),
            "full_name": "Вера",
            "email": "vera@example.com",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "created_by": "admin",
            "is_active": True,
        }
    )
    return create_access_token("vera")


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _no_mail(monkeypatch):
    """No mail server and no outbox: letters cannot go anywhere."""
    monkeypatch.delenv("MAIL_OUTBOX", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)


def _mail_fails(monkeypatch):
    def refuse(*args, **kwargs):
        raise RuntimeError("the mail server says no")

    monkeypatch.setattr(mail, "send_mail", refuse)


# ---------------------------------------------------------------- the address


def test_an_empty_address_removes_the_confirmed_one_and_the_waiting_one(client, mock_db, vera):
    mock_db["users"].update_one({"username": "vera"}, {"$set": {"pending_email": "new@example.com"}})

    response = client.put("/api/me/email", json={"email": "", "password": PASSWORD}, headers=_auth(vera))

    assert response.status_code == 200
    user = mock_db["users"].find_one({"username": "vera"})
    assert user["email"] == "" and user["email_verified"] is False
    assert "pending_email" not in user


def test_an_address_that_is_not_an_address_is_refused(client, vera):
    response = client.put("/api/me/email", json={"email": "not-an-address", "password": PASSWORD}, headers=_auth(vera))

    assert response.status_code == 422
    assert response.get_json()["code"] == "account_email_invalid"


def test_an_address_cannot_be_changed_when_the_mail_is_not_set_up(client, vera, monkeypatch):
    _no_mail(monkeypatch)

    response = client.put("/api/me/email", json={"email": "new@example.com", "password": PASSWORD}, headers=_auth(vera))

    assert response.get_json()["code"] == "mail_not_configured"


def test_an_address_confirmed_on_another_account_is_refused(client, mock_db, vera):
    mock_db["users"].insert_one(
        {
            "username": "boris",
            "password_hash": password_hash_for(PASSWORD.encode()),
            "email": "boris@example.com",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "created_by": "admin",
            "is_active": True,
        }
    )

    response = client.put(
        "/api/me/email", json={"email": "boris@example.com", "password": PASSWORD}, headers=_auth(vera)
    )

    assert response.get_json()["code"] == "account_email_taken"


def test_the_same_address_again_changes_nothing(client, mock_db, vera, outbox):
    response = client.put(
        "/api/me/email", json={"email": "vera@example.com", "password": PASSWORD}, headers=_auth(vera)
    )

    assert response.status_code == 200
    assert response.get_json()["email"] == "vera@example.com"
    assert "pending_email" not in mock_db["users"].find_one({"username": "vera"})
    assert outbox == []


def test_a_letter_that_cannot_be_sent_leaves_the_address_waiting(client, mock_db, vera, monkeypatch):
    _mail_fails(monkeypatch)

    response = client.put("/api/me/email", json={"email": "new@example.com", "password": PASSWORD}, headers=_auth(vera))

    assert response.get_json()["code"] == "mail_send_failed"
    # The address is saved: the letter can be sent again.
    assert mock_db["users"].find_one({"username": "vera"})["pending_email"] == "new@example.com"


# ---------------------------------------------------------------- the letter again


def test_the_letter_cannot_be_sent_again_when_no_address_is_waiting(client, vera):
    response = client.post("/api/me/email/resend", headers=_auth(vera))

    assert response.status_code == 422
    assert response.get_json()["code"] == "account_no_pending_email"


def test_the_letter_cannot_be_sent_again_when_the_mail_is_not_set_up(client, mock_db, vera, monkeypatch):
    mock_db["users"].update_one({"username": "vera"}, {"$set": {"pending_email": "new@example.com"}})
    _no_mail(monkeypatch)

    response = client.post("/api/me/email/resend", headers=_auth(vera))

    assert response.get_json()["code"] == "mail_not_configured"


def test_the_letter_that_cannot_be_sent_again_is_not_faked(client, mock_db, vera, monkeypatch):
    mock_db["users"].update_one({"username": "vera"}, {"$set": {"pending_email": "new@example.com"}})
    _mail_fails(monkeypatch)

    response = client.post("/api/me/email/resend", headers=_auth(vera))

    assert response.get_json()["code"] == "mail_send_failed"


# ---------------------------------------------------------------- the confirmation link


def test_a_confirmation_link_that_is_not_ours_is_refused(client, mock_db):
    response = client.post("/api/auth/email/verify", json={"token": "not-a-token"})

    assert response.status_code == 422
    assert response.get_json()["code"] == "account_link_invalid"


def test_a_confirmation_link_stored_without_a_zone_still_works(client, mock_db, vera):
    """A link written without a zone in it is still read as the time it was made."""
    token = "the-confirmation-token"
    mock_db["users"].update_one({"username": "vera"}, {"$set": {"pending_email": "vera@example.com"}})
    mock_db["account_tokens"].insert_one(
        {
            "token_hash": _token_hash(token),
            "username": "vera",
            "purpose": "verify_email",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
            "email": "vera@example.com",
        }
    )

    response = client.post("/api/auth/email/verify", json={"token": token})

    assert response.status_code == 200
    assert mock_db["users"].find_one({"username": "vera"})["email_verified"] is True


def test_a_confirmation_link_for_an_address_that_has_changed_since_is_refused(client, mock_db, vera):
    token = "the-confirmation-token"
    mock_db["users"].update_one({"username": "vera"}, {"$set": {"pending_email": "another@example.com"}})
    mock_db["account_tokens"].insert_one(
        {
            "token_hash": _token_hash(token),
            "username": "vera",
            "purpose": "verify_email",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "email": "vera@example.com",
        }
    )

    response = client.post("/api/auth/email/verify", json={"token": token})

    assert response.get_json()["code"] == "account_link_invalid"


def test_a_confirmation_link_for_an_address_taken_meanwhile_is_refused(client, mock_db, vera):
    token = "the-confirmation-token"
    mock_db["users"].update_one({"username": "vera"}, {"$set": {"pending_email": "vera@example.com"}})
    mock_db["users"].insert_one(
        {
            "username": "boris",
            "password_hash": password_hash_for(PASSWORD.encode()),
            "email": "vera@example.com",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "created_by": "admin",
            "is_active": True,
        }
    )
    mock_db["account_tokens"].insert_one(
        {
            "token_hash": _token_hash(token),
            "username": "vera",
            "purpose": "verify_email",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
            "email": "vera@example.com",
        }
    )

    response = client.post("/api/auth/email/verify", json={"token": token})

    assert response.get_json()["code"] == "account_email_taken"


# ---------------------------------------------------------------- the reset letter and link


def test_a_reset_link_stored_without_a_zone_is_still_live(client, mock_db, vera):
    token = "the-reset-token"
    mock_db["account_tokens"].insert_one(
        {
            "token_hash": _token_hash(token),
            "username": "vera",
            "purpose": "reset",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        }
    )

    response = client.get("/api/auth/password/reset/check", query_string={"token": token})

    assert response.get_json() == {"valid": True}


def test_a_reset_letter_that_cannot_be_sent_answers_the_same_as_always(client, mock_db, vera, monkeypatch, outbox):
    _mail_fails(monkeypatch)

    response = client.post("/api/auth/password/forgot", json={"login": "vera"})
    for a_login in ("vera", "nobody-here"):
        assert (
            client.post("/api/auth/password/forgot", json={"login": a_login}).get_json()["message"]
            == (response.get_json()["message"])
        )

    # No letter went out to anyone.
    assert outbox == []


def test_a_reset_link_of_an_account_that_is_gone_does_not_work(client, mock_db):
    token = "the-reset-token"
    mock_db["account_tokens"].insert_one(
        {
            "token_hash": _token_hash(token),
            "username": "ghost",
            "purpose": "reset",
            "created_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
    )

    response = client.post("/api/auth/password/reset", json={"token": token, "password": NEW_PASSWORD})

    assert response.status_code == 422
    assert response.get_json()["code"] == "account_link_invalid"


# ---------------------------------------------------------------- the password


def test_a_password_the_server_refuses_does_not_change_the_password(client, mock_db, vera):
    response = client.put(
        "/api/me/password",
        json={"current_password": PASSWORD, "new_password": "123"},
        headers=_auth(vera),
    )

    assert response.status_code == 422
    assert response.get_json()["code"] == "register_password_short"
    assert verify_user_credentials("vera", PASSWORD)


def test_a_notice_that_cannot_be_sent_does_not_stop_the_password_change(client, mock_db, vera, monkeypatch):
    _mail_fails(monkeypatch)

    response = client.put(
        "/api/me/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=_auth(vera),
    )

    assert response.status_code == 200
    assert verify_user_credentials("vera", NEW_PASSWORD)
