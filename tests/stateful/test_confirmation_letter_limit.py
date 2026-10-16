"""Confirmation letters to one address: three a day, however many sign-ups, address changes or resends ask for them.

Sign-up is limited per address of the asker (web/configs.py), which does not stop one mailbox from getting letters
from many accounts. Each letter is counted before it goes out, whichever of the three asks for it. A fourth one in a
day is refused with 429 and no letter, and nothing changes: no account is made, no address is set. The count is kept
for an address whether or not it has an account, and a letter that failed to send still counts.
"""

import itertools
from datetime import datetime, timedelta, timezone

import pytest

import web.account as account
from web import mail

ADDRESS = "vera@example.com"
REFUSED = "Письма на этот адрес уже отправляли за последние сутки, попробуйте позже"
_addresses = itertools.count(1)


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    monkeypatch.setenv("MAIL_OUTBOX", "memory")
    mail.OUTBOX.clear()
    yield mail.OUTBOX
    mail.OUTBOX.clear()


def _next_who():
    """A request from an address of its own: the limits on sign-up, sign-in and letters are per address too."""
    return {"X-Forwarded-For": f"203.0.113.{next(_addresses) % 250 + 1}"}


def _sign_up(client, username, email=ADDRESS):
    """One sign-up from an address of its own."""
    who = _next_who()
    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "kotik-2026",
            "full_name": "Вера",
            "email": email,
            "privacy_consent": True,
        },
        headers=who,
    )


def _three_letters(client):
    for name in ("vera1", "vera2", "vera3"):
        assert _sign_up(client, name).status_code == 201


def _window_ends_in(mock_db, delta):
    """Move the end of every counted letter's day to now plus ``delta``, as if days had gone by.
    The lockout tests move their rows the same way."""
    mock_db.verification_mail_log.update_many({}, {"$set": {"expires_at": datetime.now(timezone.utc) + delta}})


def _change_email(client, email):
    """The signed-in account asks for another address; the password is the one _sign_up gives every account."""
    return client.put("/api/me/email", json={"email": email, "password": "kotik-2026"}, headers=_next_who())


def _resend(client):
    return client.post("/api/me/email/resend", headers=_next_who())


def test_three_sign_ups_from_three_addresses_send_three_letters(client, mock_db, outbox):
    _three_letters(client)

    assert [letter["to"] for letter in outbox] == [ADDRESS] * 3
    assert mock_db["users"].count_documents({"username": {"$in": ["vera1", "vera2", "vera3"]}}) == 3


def test_a_letter_counts_for_a_day(client, mock_db, outbox):
    before = datetime.now(timezone.utc)
    _sign_up(client, "vera1")

    ends = mock_db.verification_mail_log.find_one({})["expires_at"]
    ends = ends if ends.tzinfo else ends.replace(tzinfo=timezone.utc)
    assert timedelta(hours=23, minutes=59) < ends - before <= timedelta(hours=24, minutes=1)


def test_the_fourth_sign_up_to_the_address_is_refused_and_makes_nothing(client, mock_db, outbox):
    _three_letters(client)

    refused = _sign_up(client, "vera4")

    assert refused.status_code == 429
    body = refused.get_json()
    assert body["code"] == "register_letter_limit"
    assert body["error"] == REFUSED
    # The window's length, as every 429 says it (web/openapi_doc.py).
    assert body["retry_after"] == 86400
    assert refused.headers["Retry-After"] == "86400"
    assert len(outbox) == 3
    assert mock_db["users"].find_one({"username": "vera4"}) is None


@pytest.mark.parametrize("written", [" Vera@Example.com ", "VERA@EXAMPLE.COM"])
def test_the_same_address_written_another_way_is_the_same_address(client, outbox, written):
    _three_letters(client)

    assert _sign_up(client, "vera4", email=written).status_code == 429
    assert len(outbox) == 3


def test_another_address_is_not_affected(client, outbox):
    _three_letters(client)

    assert _sign_up(client, "pyotr", email="pyotr@example.com").status_code == 201
    assert outbox[-1]["to"] == "pyotr@example.com"


def test_the_limit_lifts_once_the_day_is_over(client, mock_db, outbox):
    _three_letters(client)
    _window_ends_in(mock_db, timedelta(seconds=-1))

    assert _sign_up(client, "vera4").status_code == 201
    assert outbox[-1]["to"] == ADDRESS


def test_a_letter_still_counts_until_its_day_is_over(client, mock_db, outbox):
    _three_letters(client)
    # The three letters went out 23 hours ago.
    _window_ends_in(mock_db, timedelta(hours=1))

    assert _sign_up(client, "vera4").status_code == 429


def test_a_letter_that_fails_to_send_still_counts(client, outbox, monkeypatch, caplog):
    real_send = mail.send_mail
    smtp = {"down": True}

    def send(to, subject, text):
        if smtp["down"]:
            raise OSError("SMTP недоступен")
        real_send(to, subject, text)

    monkeypatch.setattr(mail, "send_mail", send)
    for name in ("vera1", "vera2", "vera3"):
        # The account is made as before; only the letter did not go.
        assert _sign_up(client, name).status_code == 201
    assert outbox == []
    assert "Verification letter not sent at sign-up" in caplog.text

    smtp["down"] = False
    assert _sign_up(client, "vera4").status_code == 429
    assert outbox == []


def test_without_mail_no_letter_is_due_so_nothing_is_counted(client, mock_db, monkeypatch):
    for name in ("MAIL_OUTBOX", "SMTP_HOST", "SMTP_FROM"):
        monkeypatch.delenv(name, raising=False)

    for name in ("vera1", "vera2", "vera3", "vera4"):
        assert _sign_up(client, name).status_code == 201
    assert mock_db.verification_mail_log.count_documents({}) == 0


def test_the_log_keeps_no_readable_address(client, mock_db, outbox):
    _sign_up(client, "vera1")

    row = mock_db.verification_mail_log.find_one({})
    assert "vera" not in str(row) and "example" not in str(row)


def test_a_sign_up_that_loses_its_login_in_a_race_gives_its_letter_back(client, mock_db, outbox, monkeypatch):
    mock_db["users"].create_index("username", unique=True)
    reserve = account.reserve_verification_letter

    def reserve_then_another_sign_up_takes_the_login(email):
        letter = reserve(email)
        # Another sign-up takes the login between the check and the insert.
        mock_db["users"].insert_one({"username": "vera1", "password_hash": "x", "is_active": True})
        return letter

    monkeypatch.setattr(account, "reserve_verification_letter", reserve_then_another_sign_up_takes_the_login)
    assert _sign_up(client, "vera1").get_json()["code"] == "register_username_taken"
    monkeypatch.setattr(account, "reserve_verification_letter", reserve)

    # The lost sign-up's letter was taken back, so three more still fit the day.
    for name in ("vera2", "vera3", "vera4"):
        assert _sign_up(client, name).status_code == 201
    assert _sign_up(client, "vera5").status_code == 429
    assert len(outbox) == 3


def test_a_change_to_an_address_with_three_letters_is_refused_and_sends_nothing(client, mock_db, outbox):
    _three_letters(client)
    _sign_up(client, "pyotr", email="pyotr@example.com")
    sent = len(outbox)

    refused = _change_email(client, ADDRESS)

    assert refused.status_code == 429
    body = refused.get_json()
    assert body["code"] == "register_letter_limit"
    assert body["error"] == REFUSED
    assert len(outbox) == sent
    # The refused change set no pending address: the one from sign-up stays.
    assert mock_db["users"].find_one({"username": "pyotr"})["pending_email"] == "pyotr@example.com"


def test_a_change_counts_with_the_sign_ups_to_its_address(client, outbox):
    _sign_up(client, "vera1")
    _sign_up(client, "vera2")
    # The third letter to the address, sent for vera2's own change rather than a sign-up.
    assert _change_email(client, ADDRESS).status_code == 200

    assert _change_email(client, ADDRESS).status_code == 429
    assert len(outbox) == 3


def test_a_resend_is_one_more_letter_to_the_address_and_is_limited(client, mock_db, outbox):
    _sign_up(client, "vera1")
    assert _resend(client).status_code == 200
    assert _resend(client).status_code == 200

    refused = _resend(client)

    assert refused.status_code == 429
    body = refused.get_json()
    assert body["code"] == "register_letter_limit"
    assert body["error"] == REFUSED
    assert len(outbox) == 3
    assert mock_db["users"].find_one({"username": "vera1"})["pending_email"] == ADDRESS


def test_a_resend_counts_with_the_sign_ups_to_its_address(client, outbox):
    _three_letters(client)  # the client is signed in as vera3, pending on the same address

    assert _resend(client).status_code == 429
    assert len(outbox) == 3


def test_the_day_lifts_the_limit_for_a_change_too(client, mock_db, outbox):
    _three_letters(client)
    _sign_up(client, "pyotr", email="pyotr@example.com")
    _window_ends_in(mock_db, timedelta(seconds=-1))

    assert _change_email(client, ADDRESS).status_code == 200
    assert outbox[-1]["to"] == ADDRESS


def test_the_dev_reset_gives_the_letter_counts_back(client, mock_db, outbox, monkeypatch):
    monkeypatch.setenv("PETZY_DEV_TOOLS", "1")
    _three_letters(client)
    assert _sign_up(client, "vera4").status_code == 429

    assert client.post("/api/dev/reset-limits").status_code == 200
    assert _sign_up(client, "vera4").status_code == 201
