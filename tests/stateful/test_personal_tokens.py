"""Personal access tokens: made with the login, used on the routes they name, and nothing more.

Which routes name a token is checked in test_personal_token_routes.py (stateless). Here: making, listing and revoking
them, what each request with one is checked for, the limit on requests, the log line, and the account deletion.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

from web.account import _new_token
from web.security import PERSONAL_TOKEN_PREFIX, hash_personal_token

EVENT = {"type": "weight", "date": "2026-10-01", "time": "09:00", "fields": {"weight": 12.4}, "comment": ""}
ALL_SCOPES = ["pets:read", "events:write", "history:read", "medical:read"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _utc_now_naive():
    """What the database keeps: UTC without a zone."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make(client, jwt, scopes=ALL_SCOPES, name="Ассистент", **extra):
    response = client.post("/api/me/tokens", json={"name": name, "scopes": scopes, **extra}, headers=_bearer(jwt))
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def _refused(response, status, code):
    assert response.status_code == status, (response.status_code, response.get_json())
    assert response.get_json()["code"] == code


# Making and listing ---------------------------------------------------------------------------------------------------


def test_the_secret_is_shown_once_and_the_list_never_repeats_it(client, regular_user_token):
    made = _make(client, regular_user_token, scopes=["pets:read"])
    token = made["token"]

    assert re.fullmatch(r"ptz_[A-Za-z0-9_-]{43}", token)
    assert made["prefix"] == token[:8]
    assert made["scopes"] == ["pets:read"]

    listed = client.get("/api/me/tokens", headers=_bearer(regular_user_token))
    assert listed.status_code == 200
    [item] = listed.get_json()["tokens"]
    assert item["id"] == made["id"]
    assert item["prefix"] == token[:8]
    assert "token" not in item
    assert token not in listed.get_data(as_text=True)


def test_the_database_keeps_the_hash_and_never_the_token(client, mock_db, regular_user_token):
    made = _make(client, regular_user_token)
    record = mock_db["api_tokens"].find_one({"_id": ObjectId(made["id"])})

    assert record["token_hash"] == hashlib.sha256(made["token"].encode("utf-8")).hexdigest()
    assert record["token_hash"] == hash_personal_token(made["token"])
    assert all(made["token"] not in str(value) for value in record.values())


def test_a_token_lasts_ninety_days_unless_told_otherwise(client, regular_user_token):
    made = _make(client, regular_user_token)
    expires = datetime.fromisoformat(made["expires_at"].rstrip("Z"))

    assert timedelta(days=89, hours=23) < expires - _utc_now_naive() <= timedelta(days=90)


@pytest.mark.parametrize("days", [1, 365])
def test_the_expiry_from_one_to_365_days_is_accepted(client, regular_user_token, days):
    _make(client, regular_user_token, expires_in_days=days)


@pytest.mark.parametrize("days", [0, -1, 366])
def test_an_expiry_outside_that_range_is_refused(client, regular_user_token, days):
    response = client.post(
        "/api/me/tokens",
        json={"name": "Срок", "scopes": ["pets:read"], "expires_in_days": days},
        headers=_bearer(regular_user_token),
    )
    _refused(response, 422, "personal_token_expiry_invalid")


def test_a_flag_is_not_a_number_of_days(client, regular_user_token):
    response = client.post(
        "/api/me/tokens",
        json={"name": "Срок", "scopes": ["pets:read"], "expires_in_days": True},
        headers=_bearer(regular_user_token),
    )
    _refused(response, 422, "validation_error")


def test_an_unknown_scope_is_refused(client, regular_user_token):
    response = client.post(
        "/api/me/tokens", json={"name": "Всё", "scopes": ["pets:write"]}, headers=_bearer(regular_user_token)
    )
    _refused(response, 422, "personal_token_scope_unknown")


def test_a_token_needs_at_least_one_scope(client, regular_user_token):
    response = client.post("/api/me/tokens", json={"name": "Пусто", "scopes": []}, headers=_bearer(regular_user_token))
    _refused(response, 422, "personal_token_scope_required")


def test_the_name_is_one_line_and_at_most_sixty_characters(client, regular_user_token):
    made = _make(client, regular_user_token, name="  Мой\n  ассистент  ")
    assert made["name"] == "Мой ассистент"

    too_long = client.post(
        "/api/me/tokens", json={"name": "а" * 61, "scopes": ["pets:read"]}, headers=_bearer(regular_user_token)
    )
    _refused(too_long, 422, "validation_error")
    blank = client.post(
        "/api/me/tokens", json={"name": "   ", "scopes": ["pets:read"]}, headers=_bearer(regular_user_token)
    )
    _refused(blank, 422, "validation_error")


def test_a_person_has_at_most_ten_working_tokens_and_a_revoked_one_frees_its_place(client, regular_user_token):
    made = [_make(client, regular_user_token) for _ in range(10)]

    refused = client.post(
        "/api/me/tokens", json={"name": "Лишний", "scopes": ["pets:read"]}, headers=_bearer(regular_user_token)
    )
    _refused(refused, 422, "personal_token_limit")

    revoked = client.delete(f"/api/me/tokens/{made[0]['id']}", headers=_bearer(regular_user_token))
    assert revoked.status_code == 200
    _make(client, regular_user_token)


def test_an_expired_token_does_not_count_against_the_ten(client, mock_db, regular_user_token):
    made = [_make(client, regular_user_token) for _ in range(10)]
    mock_db["api_tokens"].update_one(
        {"_id": ObjectId(made[0]["id"])}, {"$set": {"expires_at": _utc_now_naive() - timedelta(days=1)}}
    )

    _make(client, regular_user_token)


# Revoking -------------------------------------------------------------------------------------------------------------


def test_revoking_stops_a_token_at_once_and_a_second_revoke_is_safe(client, regular_user_token):
    made = _make(client, regular_user_token, scopes=["pets:read"])
    assert client.get("/api/pets", headers=_bearer(made["token"])).status_code == 200

    first = client.delete(f"/api/me/tokens/{made['id']}", headers=_bearer(regular_user_token))
    assert first.status_code == 200
    assert first.get_json() == {"revoked": True}
    _refused(client.get("/api/pets", headers=_bearer(made["token"])), 401, "token_invalid")

    [revoked_once] = client.get("/api/me/tokens", headers=_bearer(regular_user_token)).get_json()["tokens"]
    again = client.delete(f"/api/me/tokens/{made['id']}", headers=_bearer(regular_user_token))
    assert again.status_code == 200
    [revoked_twice] = client.get("/api/me/tokens", headers=_bearer(regular_user_token)).get_json()["tokens"]
    assert revoked_twice["revoked_at"] == revoked_once["revoked_at"]


def test_another_persons_token_cannot_be_revoked(client, admin_token, regular_user_token):
    made = _make(client, admin_token)

    response = client.delete(f"/api/me/tokens/{made['id']}", headers=_bearer(regular_user_token))

    _refused(response, 404, "personal_token_not_found")
    assert client.get("/api/pets", headers=_bearer(made["token"])).status_code == 200


def test_an_id_that_is_not_one_is_not_found(client, regular_user_token):
    response = client.delete("/api/me/tokens/not-an-id", headers=_bearer(regular_user_token))
    _refused(response, 404, "personal_token_not_found")


# Using a token: the routes it names, with the scope each one needs ----------------------------------------------------


def test_a_token_reads_pets_and_event_types_with_pets_read(client, regular_user_token, test_pet):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]

    pets = client.get("/api/pets", headers=_bearer(token))
    assert pets.status_code == 200
    assert "Test Cat" in pets.get_data(as_text=True)
    assert client.get(f"/api/pets/{test_pet['_id']}", headers=_bearer(token)).status_code == 200
    assert client.get("/api/event-types", headers=_bearer(token)).status_code == 200


def test_a_token_writes_an_event_with_events_write(client, mock_db, regular_user_token, test_pet):
    token = _make(client, regular_user_token, scopes=["events:write"])["token"]

    response = client.post("/api/events", json={**EVENT, "pet_id": str(test_pet["_id"])}, headers=_bearer(token))

    assert response.status_code == 201
    assert mock_db["events"].count_documents({"pet_id": str(test_pet["_id"])}) == 1


def test_a_token_reads_the_timeline_with_history_read(client, regular_user_token, test_pet):
    token = _make(client, regular_user_token, scopes=["history:read"])["token"]

    response = client.get(f"/api/history/timeline?pet_id={test_pet['_id']}", headers=_bearer(token))

    assert response.status_code == 200


def test_a_token_reads_the_medical_card_with_medical_read(client, regular_user_token, test_pet):
    token = _make(client, regular_user_token, scopes=["medical:read"])["token"]

    response = client.get(f"/api/pets/{test_pet['_id']}/medical-card", headers=_bearer(token))

    assert response.status_code == 200


@pytest.mark.parametrize(
    "method, path, with_event",
    [
        ("post", "/api/events", True),
        ("get", "/api/history/timeline?pet_id={pet}", False),
        ("get", "/api/pets/{pet}/medical-card", False),
    ],
)
def test_a_route_asks_for_its_own_scope_and_no_other(client, regular_user_token, test_pet, method, path, with_event):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]
    pet = str(test_pet["_id"])
    body = {**EVENT, "pet_id": pet} if with_event else None

    response = client.open(path.format(pet=pet), method=method.upper(), json=body, headers=_bearer(token))

    _refused(response, 403, "token_scope_missing")


def test_a_token_reaches_no_more_pets_than_its_owner(client, regular_user_token, admin_pet):
    token = _make(client, regular_user_token)["token"]
    owner_view = client.get(f"/api/pets/{admin_pet['_id']}", headers=_bearer(regular_user_token))
    token_view = client.get(f"/api/pets/{admin_pet['_id']}", headers=_bearer(token))

    assert owner_view.status_code != 200
    assert token_view.status_code == owner_view.status_code


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("post", "/api/me/tokens", {"name": "Новый", "scopes": ["pets:read"]}),
        ("get", "/api/me/tokens", None),
        ("delete", "/api/me/tokens/507f1f77bcf86cd799439011", None),
        ("put", "/api/me/password", {"current_password": "user123", "new_password": "another-pass-1"}),
        ("post", "/api/auth/logout", None),
        ("delete", "/api/me/account", {"password": "user123"}),
        ("get", "/api/users", None),
        ("delete", "/api/users/testuser", None),
        ("post", "/api/pets", {"name": "Новый"}),
        ("get", "/api/users/search?q=te", None),
    ],
)
def test_a_route_that_names_no_token_refuses_it_whatever_the_scopes(client, regular_user_token, method, path, body):
    token = _make(client, regular_user_token)["token"]

    response = client.open(path, method=method.upper(), json=body, headers=_bearer(token))

    _refused(response, 403, "token_not_allowed")


def test_a_token_changes_neither_the_password_nor_the_account(client, mock_db, regular_user_token):
    token = _make(client, regular_user_token)["token"]
    before = mock_db["users"].find_one({"username": "testuser"})

    client.put(
        "/api/me/password",
        json={"current_password": "user123", "new_password": "another-pass-1"},
        headers=_bearer(token),
    )
    client.delete("/api/me/account", json={"password": "user123"}, headers=_bearer(token))

    assert mock_db["users"].find_one({"username": "testuser"}) == before


def test_a_token_in_a_cookie_is_not_a_personal_token(client, regular_user_token):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]
    client.set_cookie("access_token", token)

    assert client.get("/api/pets").status_code == 401


# What a token is refused for ------------------------------------------------------------------------------------------


def test_an_expired_token_answers_401(client, mock_db, regular_user_token):
    made = _make(client, regular_user_token, scopes=["pets:read"])
    mock_db["api_tokens"].update_one(
        {"_id": ObjectId(made["id"])}, {"$set": {"expires_at": _utc_now_naive() - timedelta(minutes=1)}}
    )

    _refused(client.get("/api/pets", headers=_bearer(made["token"])), 401, "token_invalid")


def test_a_token_of_a_disabled_account_answers_401(client, regular_user_token, auth_headers):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]
    assert client.get("/api/pets", headers=_bearer(token)).status_code == 200

    assert client.delete("/api/users/testuser", headers=auth_headers).status_code == 200

    _refused(client.get("/api/pets", headers=_bearer(token)), 401, "token_invalid")


def test_a_token_that_was_never_made_answers_401(client):
    _refused(client.get("/api/pets", headers=_bearer(PERSONAL_TOKEN_PREFIX + "x" * 43)), 401, "token_invalid")


# The limit and the log ------------------------------------------------------------------------------------------------


def test_a_token_gets_120_requests_a_minute_then_429(client, regular_user_token):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]
    for attempt in range(1, 121):
        assert client.get("/api/pets", headers=_bearer(token)).status_code == 200, f"request {attempt} refused"

    refused = client.get("/api/pets", headers=_bearer(token))

    assert refused.status_code == 429
    assert refused.get_json()["code"] == "rate_limit_exceeded"
    assert refused.headers["Retry-After"] == "60"


def test_the_limit_belongs_to_each_token_and_a_session_is_not_counted(client, regular_user_token):
    first = _make(client, regular_user_token, scopes=["pets:read"])["token"]
    second = _make(client, regular_user_token, scopes=["pets:read"])["token"]
    for _ in range(120):
        client.get("/api/pets", headers=_bearer(first))
    assert client.get("/api/pets", headers=_bearer(first)).status_code == 429

    assert client.get("/api/pets", headers=_bearer(second)).status_code == 200
    for _ in range(130):
        assert client.get("/api/pets", headers=_bearer(regular_user_token)).status_code == 200


def test_a_session_never_reaches_the_token_limit_with_an_empty_key(client, regular_user_token, caplog):
    """A session is exempt from the token limit before the limiter reads a key. Without that exemption the limiter
    would try the limit with an empty key, skip it, and log an error on every request."""
    caplog.set_level(logging.ERROR)

    for _ in range(5):
        assert client.get("/api/pets", headers=_bearer(regular_user_token)).status_code == 200

    assert not [record for record in caplog.records if "Skipping limit" in record.getMessage()]


def test_each_request_with_a_token_is_logged_by_id_and_never_by_value(client, regular_user_token, caplog):
    made = _make(client, regular_user_token, scopes=["pets:read"])
    caplog.set_level(logging.INFO, logger="web.app")

    response = client.get("/api/pets", headers=_bearer(made["token"]))

    assert response.status_code == 200
    lines = [record.getMessage() for record in caplog.records if "Personal token request" in record.getMessage()]
    assert lines == [f"Personal token request: token={made['id']}, route=GET /api/pets, status=200"]
    assert made["token"] not in caplog.text


def test_the_last_use_is_written_at_most_every_five_minutes(client, mock_db, regular_user_token):
    made = _make(client, regular_user_token, scopes=["pets:read"])

    def last_used():
        return mock_db["api_tokens"].find_one({"_id": ObjectId(made["id"])})["last_used_at"]

    client.get("/api/pets", headers=_bearer(made["token"]))
    first = last_used()
    assert first is not None

    client.get("/api/pets", headers=_bearer(made["token"]))
    assert last_used() == first

    old = _utc_now_naive() - timedelta(minutes=6)
    mock_db["api_tokens"].update_one({"_id": ObjectId(made["id"])}, {"$set": {"last_used_at": old}})
    client.get("/api/pets", headers=_bearer(made["token"]))
    assert last_used() > old


# The account --------------------------------------------------------------------------------------------------------


def test_deleting_the_account_deletes_its_tokens(client, mock_db, regular_user_token):
    made = _make(client, regular_user_token, scopes=["pets:read"])
    _make(client, regular_user_token)

    response = client.delete("/api/me/account", json={"password": "user123"}, headers=_bearer(regular_user_token))

    assert response.status_code == 200
    assert mock_db["api_tokens"].count_documents({"username": "testuser"}) == 0
    _refused(client.get("/api/pets", headers=_bearer(made["token"])), 401, "token_invalid")


# Password change, reset by link, and the administrator's reset -----------------------------------------------------

NEW_PASSWORD = "a-new-password-1"


def test_a_password_change_revokes_the_personal_tokens(client, regular_user_token):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]
    assert client.get("/api/pets", headers=_bearer(token)).status_code == 200

    changed = client.put(
        "/api/me/password",
        json={"current_password": "user123", "new_password": NEW_PASSWORD},
        headers=_bearer(regular_user_token),
    )
    assert changed.status_code == 200

    _refused(client.get("/api/pets", headers=_bearer(token)), 401, "token_invalid")
    # The answer carries a session for this device, and a token made with it works.
    made = _make(client, changed.get_json()["access_token"], scopes=["pets:read"])
    assert client.get("/api/pets", headers=_bearer(made["token"])).status_code == 200


def test_a_reset_by_link_revokes_the_personal_tokens(client, regular_user_token):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]
    link = _new_token("testuser", "reset", timedelta(hours=1))

    reset = client.post("/api/auth/password/reset", json={"token": link, "password": NEW_PASSWORD})
    assert reset.status_code == 200

    _refused(client.get("/api/pets", headers=_bearer(token)), 401, "token_invalid")
    made = _make(client, reset.get_json()["access_token"], scopes=["pets:read"])
    assert client.get("/api/pets", headers=_bearer(made["token"])).status_code == 200


def test_an_administrators_reset_revokes_the_personal_tokens(client, regular_user_token, auth_headers):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]

    reset = client.post("/api/users/testuser/reset-password", json={"password": NEW_PASSWORD}, headers=auth_headers)

    assert reset.status_code == 200
    _refused(client.get("/api/pets", headers=_bearer(token)), 401, "token_invalid")


def test_an_administrators_new_password_revokes_the_personal_tokens(client, regular_user_token, auth_headers):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]

    changed = client.put("/api/users/testuser", json={"password": NEW_PASSWORD}, headers=auth_headers)

    assert changed.status_code == 200
    _refused(client.get("/api/pets", headers=_bearer(token)), 401, "token_invalid")


def test_signing_out_leaves_the_personal_tokens_working(client, regular_user_token):
    token = _make(client, regular_user_token, scopes=["pets:read"])["token"]
    signed_in = client.post("/api/auth/login", json={"username": "testuser", "password": "user123"})
    refresh = signed_in.get_json()["refresh_token"]

    assert client.post("/api/auth/logout", json={"refresh_token": refresh}).status_code == 200

    assert client.get("/api/pets", headers=_bearer(token)).status_code == 200
