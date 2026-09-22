"""Direct unit tests for web.security helpers not otherwise exercised
through an HTTP route (ensure_default_admin, the env-var admin
credential fallback, get_current_user's own unauthenticated contract).
"""

import pytest


@pytest.mark.auth
class TestEnsureDefaultAdmin:
    def test_creates_admin_when_missing(self, mock_db):
        from web.security import ensure_default_admin, ADMIN_USERNAME

        mock_db["users"].delete_many({"username": ADMIN_USERNAME})

        ensure_default_admin()

        admin = mock_db["users"].find_one({"username": ADMIN_USERNAME})
        assert admin is not None
        assert admin["is_admin"] is True

    def test_backfills_is_admin_flag_on_existing_admin(self, mock_db):
        from web.security import ensure_default_admin, ADMIN_USERNAME

        mock_db["users"].update_one({"username": ADMIN_USERNAME}, {"$unset": {"is_admin": ""}})

        ensure_default_admin()

        admin = mock_db["users"].find_one({"username": ADMIN_USERNAME})
        assert admin["is_admin"] is True

    def test_leaves_admin_untouched_when_already_flagged(self, mock_db):
        from web.security import ensure_default_admin, ADMIN_USERNAME

        mock_db["users"].update_one({"username": ADMIN_USERNAME}, {"$set": {"is_admin": True}})

        # Should not raise or alter anything else about the document.
        ensure_default_admin()

        admin = mock_db["users"].find_one({"username": ADMIN_USERNAME})
        assert admin["is_admin"] is True


@pytest.mark.auth
class TestVerifyUserCredentialsEnvFallback:
    def test_falls_back_to_env_admin_hash_when_no_db_user_exists(self, mock_db):
        """Before ensure_default_admin has ever run (or if the admin row
        was somehow removed), login must still work against the
        ADMIN_PASSWORD_HASH env-configured credentials."""
        from web.security import verify_user_credentials, ADMIN_USERNAME

        mock_db["users"].delete_many({"username": ADMIN_USERNAME})

        assert verify_user_credentials(ADMIN_USERNAME, "admin123") is True
        assert verify_user_credentials(ADMIN_USERNAME, "wrongpassword") is False


@pytest.mark.auth
@pytest.mark.auth
class TestModuleLevelAdminHashValidation:
    """ADMIN_PASSWORD_HASH is validated once, at import time — the only
    way to exercise that check is to force a re-import with it unset,
    which is why this isn't reached through any normal call."""

    def test_raises_at_import_when_admin_password_hash_missing(self):
        import importlib
        import web.security
        from web.configs import ADMIN_CONFIG

        original = ADMIN_CONFIG["password_hash"]
        ADMIN_CONFIG["password_hash"] = ""
        try:
            with pytest.raises(RuntimeError, match="ADMIN_PASSWORD_HASH"):
                importlib.reload(web.security)
        finally:
            ADMIN_CONFIG["password_hash"] = original
            importlib.reload(web.security)


@pytest.mark.auth
class TestVerifyUserCredentialsCorruptedAdminHash:
    def test_corrupted_admin_password_hash_fails_cleanly(self, mock_db, monkeypatch):
        """If ADMIN_PASSWORD_HASH itself isn't a valid bcrypt hash (bad
        deploy config, truncated env var, ...), the env-fallback branch
        must fail closed instead of raising out of bcrypt.checkpw."""
        import web.security
        from web.security import verify_user_credentials, ADMIN_USERNAME

        mock_db["users"].delete_many({"username": ADMIN_USERNAME})
        monkeypatch.setattr(web.security, "ADMIN_PASSWORD_HASH", "not-a-real-bcrypt-hash")

        assert verify_user_credentials(ADMIN_USERNAME, "admin123") is False


@pytest.mark.auth
class TestLoginRequiredRefreshEdgeCase:
    def test_freshly_refreshed_token_failing_reverification_is_treated_as_unauthenticated(self):
        """If try_refresh_access_token() hands back a token that then
        immediately fails verify_token() (a same-request inconsistency
        that shouldn't normally happen, but the code guards against
        anyway), login_required must fall through to unauthorized
        rather than trusting a token it couldn't itself verify."""
        from unittest.mock import patch
        from flask import Flask
        import web.security as security_module

        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.route("/_protected")
        @security_module.login_required
        def _protected():
            return "ok"

        with (
            patch.object(security_module, "try_refresh_access_token", return_value="freshly.issued.token"),
            patch.object(security_module, "verify_token", return_value=None),
        ):
            with app.test_client() as c:
                response = c.get("/_protected")

        assert response.status_code == 401


@pytest.mark.auth
class TestGetCurrentUserDirectContract:
    """get_current_user() is normally called after @login_required has
    already set request.current_user, making its own "not set" branch
    unreachable through the HTTP surface — but the function has its own
    contract worth verifying directly."""

    def test_returns_unauthorized_when_current_user_not_set(self):
        from flask import Flask
        from web.security import get_current_user

        app = Flask(__name__)
        with app.test_request_context("/"):
            username, error = get_current_user()

        assert username is None
        assert error is not None
        _, status = error
        assert status == 401
