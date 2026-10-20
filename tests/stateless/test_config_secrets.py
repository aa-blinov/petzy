"""The configuration that leaves the server in a log is masked, and the app's own account wins over the general one.

``get_config_json`` is the one place where the whole configuration is written out as text, so it is
the place where a secret can leak into a log, a terminal or a support chat. Everything that is
really a secret goes out as «***MASKED***», and what is not a secret (an empty value, the built-in
development key) stays as it is: masking it would only hide that nothing was set.
"""

import json

from web.configs import get_config_json, load_config

MASKED = "***MASKED***"
DEV_SECRET = "dev-secret-key-change-in-production"


def _json(monkeypatch):
    return json.loads(get_config_json())


def test_the_admin_password_hash_is_masked_when_there_is_one(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "hash-of-the-admin")
    assert _json(monkeypatch)["admin"]["password_hash"] == MASKED


def test_no_admin_password_hash_is_left_alone(monkeypatch):
    """There is nothing to hide when the administrator has no password set."""
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
    assert _json(monkeypatch)["admin"]["password_hash"] is None


def test_the_secret_keys_are_masked_when_they_are_set(monkeypatch):
    monkeypatch.setenv("FLASK_SECRET_KEY", "a-real-flask-secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-real-jwt-secret")
    config = _json(monkeypatch)
    assert config["flask"]["secret_key"] == MASKED
    assert config["jwt"]["secret_key"] == MASKED


def test_the_built_in_development_keys_are_not_masked(monkeypatch):
    """The development key is published in the code: hiding it would say nothing about the server."""
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    config = _json(monkeypatch)
    assert config["flask"]["secret_key"] == DEV_SECRET
    assert config["jwt"]["secret_key"] == DEV_SECRET


def test_an_empty_mongo_password_is_left_alone(monkeypatch):
    monkeypatch.setenv("MONGO_PASS", "")
    assert _json(monkeypatch)["mongodb"]["pass"] == ""


def test_the_push_private_key_is_masked_when_it_is_set(monkeypatch):
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "private-key-of-the-push-server")
    assert _json(monkeypatch)["push"]["vapid_private_key"] == MASKED


def test_the_apps_own_account_wins_over_the_general_one(monkeypatch):
    """The app keeps its own database account; the general one is only a fallback."""
    monkeypatch.setenv("MONGO_APP_USER", "app_user")
    monkeypatch.setenv("MONGO_APP_PASS", "app_pass")
    monkeypatch.setenv("MONGO_USER", "general_user")
    monkeypatch.setenv("MONGO_PASS", "general_pass")

    config = load_config()

    assert config["mongodb"]["user"] == "app_user"
    assert config["mongodb"]["pass"] == "app_pass"
    assert "app_user:app_pass@" in config["mongodb"]["uri"]


def test_a_half_of_the_apps_own_account_falls_back_to_the_general_one(monkeypatch):
    """One half is not an account: the general one is used instead."""
    monkeypatch.setenv("MONGO_APP_USER", "app_user")
    monkeypatch.delenv("MONGO_APP_PASS", raising=False)
    monkeypatch.setenv("MONGO_USER", "general_user")
    monkeypatch.setenv("MONGO_PASS", "general_pass")

    config = load_config()

    assert config["mongodb"]["user"] == "general_user"
    assert config["mongodb"]["pass"] == "general_pass"


def test_the_credentials_in_the_address_are_encoded(monkeypatch):
    """A password with a sign in it would break the address of the database."""
    monkeypatch.setenv("MONGO_USER", "user name")
    monkeypatch.setenv("MONGO_PASS", "p@ss/word")

    uri = load_config()["mongodb"]["uri"]

    assert "user+name" in uri
    assert "p%40ss%2Fword" in uri


def test_the_allowed_origins_are_read_as_a_list_of_the_ones_written(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.example, , https://b.example")
    assert load_config()["cors"]["allowed_origins"] == ["https://a.example", "https://b.example"]
