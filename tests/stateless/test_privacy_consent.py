"""Consent to the privacy policy: given at sign-up, asked again on a new version."""

import itertools

import pytest

from web import legal
from web.security import create_access_token

_addresses = itertools.count(1)


def _register(client, **body):
    who = {"X-Forwarded-For": f"198.18.0.{next(_addresses) % 250 + 1}"}
    return client.post(
        "/api/auth/register",
        json={"username": "vera", "password": "kotik-2026", "full_name": "Вера", **body},
        headers=who,
    )


def test_no_account_without_consent(client, mock_db):
    for body in ({}, {"privacy_consent": False}):
        response = _register(client, **body)
        assert response.status_code == 422
        assert response.get_json()["code"] == "privacy_consent_required"
    assert mock_db["users"].find_one({"username": "vera"}) is None


def test_sign_up_records_which_version_was_agreed_to(client, mock_db):
    assert _register(client, privacy_consent=True).status_code == 201
    consent = mock_db["users"].find_one({"username": "vera"})["privacy_consent"]
    assert consent["version"] == legal.PRIVACY_POLICY_VERSION and consent["accepted_at"]
    assert client.get("/api/me/account").get_json()["privacy_consent_needed"] is False


def test_an_account_without_consent_is_asked_and_can_agree(client, regular_user):
    headers = {"Authorization": f"Bearer {create_access_token('testuser')}"}
    assert client.get("/api/me/account", headers=headers).get_json()["privacy_consent_needed"] is True

    stale = client.post("/api/me/privacy-consent", json={"version": "2000-01-01"}, headers=headers)
    assert stale.status_code == 422 and stale.get_json()["code"] == "privacy_version_outdated"

    ok = client.post("/api/me/privacy-consent", json={"version": legal.PRIVACY_POLICY_VERSION}, headers=headers)
    assert ok.status_code == 200
    assert client.get("/api/me/account", headers=headers).get_json()["privacy_consent_needed"] is False


def test_a_new_policy_version_asks_again(client, regular_user, monkeypatch):
    headers = {"Authorization": f"Bearer {create_access_token('testuser')}"}
    client.post("/api/me/privacy-consent", json={"version": legal.PRIVACY_POLICY_VERSION}, headers=headers)
    monkeypatch.setattr(legal, "PRIVACY_POLICY_VERSION", "2099-01-01")
    assert client.get("/api/me/account", headers=headers).get_json()["privacy_consent_needed"] is True


@pytest.mark.parametrize("configured", [True, False])
def test_the_policy_facts_come_from_the_environment(client, monkeypatch, configured):
    if configured:
        monkeypatch.setenv("PRIVACY_OPERATOR", "Иванов Иван Иванович")
        monkeypatch.setenv("PRIVACY_CONTACT_EMAIL", "privacy@example.com")
        monkeypatch.setenv("PRIVACY_SERVER_LOCATION", "Россия")
    else:
        for name in ("PRIVACY_OPERATOR", "PRIVACY_CONTACT_EMAIL", "PRIVACY_SERVER_LOCATION"):
            monkeypatch.delenv(name, raising=False)
    body = client.get("/api/legal").get_json()
    assert body["policy_version"] == legal.PRIVACY_POLICY_VERSION
    assert body["backups_kept_days"] >= 1
    assert (body["operator"] == "Иванов Иван Иванович") is configured
    assert (body["contact_email"] == "privacy@example.com") is configured
