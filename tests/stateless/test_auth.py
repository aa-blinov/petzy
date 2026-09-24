"""Tests for authentication endpoints."""

import pytest
from datetime import datetime, timedelta, timezone
import jwt
from web.security import JWT_SECRET_KEY, JWT_ALGORITHM


@pytest.mark.auth
class TestAuthentication:
    """Test authentication endpoints."""

    def test_api_login_success(self, client, mock_db):
        """Test successful API login."""
        response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "access_token" in data
        assert "refresh_token" in data

        # Check cookies are set in response headers
        set_cookie_headers = [h for h in response.headers.getlist("Set-Cookie")]
        cookie_names = [h.split("=")[0] for h in set_cookie_headers]
        assert "access_token" in " ".join(cookie_names)
        assert "refresh_token" in " ".join(cookie_names)

    def test_two_logins_produce_distinct_refresh_token_jtis(self, client, mock_db):
        """Regression: two back-to-back logins must not collide on the
        refresh-token unique index. Each refresh token now carries a
        fresh UUID4 `jti` (RFC 7519 §4.1.7) so even identical
        ``{username, exp}`` payloads produce distinct documents.

        Before this fix, both tokens decoded to the same JWT string when
        issued in the same wall-clock second, tripping the unique index
        on ``refresh_tokens.token`` and crashing the second login with
        DuplicateKeyError — visible as a flake on the CI pytest job.

        The HTTP-200 on the second login is itself the proof — before
        the fix the index raised inside the view function and Flask
        surfaced it as a 500. We additionally assert the two tokens
        carry distinct ``jti`` claims, which is what makes the DB-side
        uniqueness work.
        """
        r1 = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        r2 = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

        assert r1.status_code == 200
        assert r2.status_code == 200

        t1 = r1.get_json()["refresh_token"]
        t2 = r2.get_json()["refresh_token"]

        # Different JWT strings (jti is part of the signed payload).
        assert t1 != t2

        # Both tokens carry a `jti` claim and they are distinct.
        p1 = jwt.decode(t1, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        p2 = jwt.decode(t2, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert "jti" in p1 and "jti" in p2
        assert p1["jti"] != p2["jti"]

    def test_api_login_invalid_credentials(self, client, mock_db):
        """Test login with invalid credentials."""
        response = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_api_login_missing_fields(self, client):
        """Test login with missing fields."""
        response = client.post("/api/auth/login", json={"username": "admin"})

        assert response.status_code == 422
        data = response.get_json()
        assert isinstance(data, list) and "missing" in str(data)

    def test_api_login_rate_limiting(self, client, mock_db):
        """Test rate limiting on login attempts."""
        # Make multiple failed attempts
        for _ in range(6):
            response = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})

        # Should be rate limited
        assert response.status_code == 429
        data = response.get_json()
        assert "error" in data
        assert "Превышен лимит" in data["error"] or "rate limit" in data["error"].lower() or "Too many" in data["error"]

    def test_api_refresh_token_success(self, client, mock_db, admin_refresh_token):
        """Test successful token refresh.

        ``admin_refresh_token`` fixture already persisted the token with
        the matching ``jti`` claim — no need to re-insert here.
        """
        client.set_cookie("refresh_token", admin_refresh_token)
        response = client.post("/api/auth/refresh")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "access_token" in data

    def test_api_refresh_token_invalid(self, client):
        """Test refresh with invalid token."""
        client.set_cookie("refresh_token", "invalid_token")
        response = client.post("/api/auth/refresh")

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_api_refresh_token_missing(self, client):
        """Test refresh without token."""
        response = client.post("/api/auth/refresh", json={})

        assert response.status_code == 401
        data = response.get_json()
        assert "error" in data

    def test_api_logout(self, client, mock_db, admin_refresh_token):
        """Test logout removes the user's refresh token (and only theirs).

        Also covers the "logout invalidates every device" invariant: a
        second refresh token for the same user must be dropped together
        with the cookie token.
        """
        from uuid import uuid4
        from web.app import db
        from web.security import (
            JWT_SECRET_KEY,
            JWT_ALGORITHM,
            REFRESH_TOKEN_EXPIRE_DAYS,
        )

        # Ensure cookie token exists (fixture already does this).
        existing = db["refresh_tokens"].find_one({"token": admin_refresh_token})
        if not existing:
            db["refresh_tokens"].insert_one(
                {
                    "jti": uuid4().hex,
                    "token": admin_refresh_token,
                    "username": "admin",
                    "created_at": datetime.now(timezone.utc),
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
                }
            )

        # Insert a SECOND refresh token for the same user (simulates an
        # older device/session). Logout must drop both.
        other_jti = uuid4().hex
        other_token = jwt.encode(
            {
                "username": "admin",
                "exp": datetime.now(timezone.utc) + timedelta(days=7),
                "type": "refresh",
                "jti": other_jti,
            },
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
        db["refresh_tokens"].insert_one(
            {
                "jti": other_jti,
                "token": other_token,
                "username": "admin",
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            }
        )

        # And one for a DIFFERENT user — must NOT be dropped.
        from tests.conftest import _mock_db  # noqa: F401 — ensures conftest imported

        db["refresh_tokens"].insert_one(
            {
                "jti": uuid4().hex,
                "token": "other-user-token",
                "username": "someone-else",
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            }
        )

        client.set_cookie("refresh_token", admin_refresh_token)
        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Cookie token gone
        assert db["refresh_tokens"].find_one({"token": admin_refresh_token}) is None
        # Other admin token also gone (logout is "sign out of everything")
        assert db["refresh_tokens"].find_one({"token": other_token}) is None
        # Other user untouched
        assert db["refresh_tokens"].find_one({"token": "other-user-token"}) is not None

        # Should render login page with error

    def test_token_verification(self, client, admin_token):
        """Test token verification."""
        payload = jwt.decode(admin_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        assert payload["username"] == "admin"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_expired_refresh_token_is_dropped_on_use(self, client, mock_db):
        """A refresh token whose stored `expires_at` is in the past must
        not only be rejected but actively deleted by try_refresh_access_token
        — otherwise the TTL monitor is the only line of defence and a
        stolen-but-revoked token could keep minting access tokens during
        the ~60 s gap between expiry and the sweep.
        """
        from uuid import uuid4
        from web.app import db
        from web.security import (
            JWT_SECRET_KEY,
            JWT_ALGORITHM,
        )

        # Mint a refresh token whose stored expires_at is yesterday, but
        # whose JWT signature itself is still valid (the JWT's `exp` is
        # one second from now — the document expires_at is what we read).
        jti = uuid4().hex
        token = jwt.encode(
            {
                "username": "admin",
                "exp": datetime.now(timezone.utc) + timedelta(seconds=10),
                "type": "refresh",
                "jti": jti,
            },
            JWT_SECRET_KEY,
            algorithm=JWT_ALGORITHM,
        )
        db["refresh_tokens"].insert_one(
            {
                "jti": jti,
                "token": token,
                "username": "admin",
                "created_at": datetime.now(timezone.utc) - timedelta(days=2),
                "expires_at": datetime.now(timezone.utc) - timedelta(days=1),
            }
        )

        client.set_cookie("refresh_token", token)
        response = client.post("/api/auth/refresh")

        # The /api/auth/refresh endpoint should reject and try_refresh
        # should have already deleted the row.
        assert response.status_code in (401, 403), response.get_json()
        assert db["refresh_tokens"].find_one({"token": token}) is None

    def test_expired_token_rejection(self, client):
        """Test that expired tokens are rejected."""
        # Create expired token
        expired_payload = {
            "username": "admin",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "type": "access",
        }
        expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        response = client.get("/api/auth/session", headers={"Authorization": f"Bearer {expired_token}"})

        assert response.status_code == 401

    def test_check_admin_requires_authentication(self, client):
        """Test that check-admin requires authentication."""
        response = client.get("/api/auth/check-admin")
        assert response.status_code == 401

    def test_check_admin_returns_true_for_admin(self, client, mock_db, admin_token):
        """Test that check-admin returns true for admin user."""
        # Ensure admin user has is_admin flag
        from web.app import db

        db["users"].update_one({"username": "admin"}, {"$set": {"is_admin": True}})

        response = client.get("/api/auth/check-admin", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["is_admin"] is True

    def test_check_admin_returns_false_for_regular_user(self, client, mock_db, regular_user_token):
        """Test that check-admin returns false for regular user."""
        response = client.get("/api/auth/check-admin", headers={"Authorization": f"Bearer {regular_user_token}"})
        assert response.status_code == 200
        data = response.get_json()
        assert data["is_admin"] is False


@pytest.mark.auth
class TestSessionProbe:
    """Tests for GET /api/auth/session — the SPA's single auth probe."""

    def test_session_requires_authentication(self, client):
        """No cookies, no token -> 401.

        The SPA treats a 401 here (and only a 401) as "signed out", so
        this status is load-bearing: it is the single signal that sends
        the user to /login.
        """
        response = client.get("/api/auth/session")
        assert response.status_code == 401

    def test_session_returns_identity_for_admin(self, client, mock_db, admin_token):
        response = client.get("/api/auth/session", headers={"Authorization": f"Bearer {admin_token}"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["username"] == "admin"
        assert data["is_admin"] is True

    def test_session_returns_identity_for_regular_user(self, client, mock_db, regular_user_token):
        response = client.get("/api/auth/session", headers={"Authorization": f"Bearer {regular_user_token}"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["username"] == "testuser"
        assert data["is_admin"] is False

    def test_session_renews_access_cookie_from_refresh_token(self, client, mock_db, admin_refresh_token):
        """The silent refresh must hand the renewed cookie back.

        ``login_required`` refreshes an expired access token
        mid-request and attaches the new one as a cookie. It guards
        that on the shape of the view's return value, so the guard is
        sensitive to decorator order: if the renewal is ever skipped,
        the browser's 15-minute access_token cookie stays expired and
        every request has to fall back to refresh_token, which turns
        any hiccup with refresh_token into a whole-app 401.

        Here there is no access_token at all, only a valid
        refresh_token, so the request can only succeed via the silent
        refresh — and the renewed cookie must come back with it. This
        route returns a ``(body, status)`` tuple, so it also pins the
        tuple-shaped path.
        """
        client.set_cookie("refresh_token", admin_refresh_token)

        response = client.get("/api/auth/session")

        assert response.status_code == 200
        assert response.get_json()["username"] == "admin"

        set_cookies = " ".join(response.headers.getlist("Set-Cookie"))
        assert "access_token=" in set_cookies

    def test_session_401_when_refresh_token_is_unknown(self, client, mock_db):
        """A refresh_token with no DB row (e.g. after a service restart
        wiped the collection) must read as signed out, not as a crash."""
        from web.security import create_refresh_token

        token = create_refresh_token("admin")
        mock_db["refresh_tokens"].delete_many({})
        client.set_cookie("refresh_token", token)

        response = client.get("/api/auth/session")
        assert response.status_code == 401

    def test_logout_deletes_refresh_token_by_raw_value_when_undecodable(self, client, mock_db):
        """A refresh_token cookie holding garbage (not a valid JWT at all)
        can't be decoded to find its jti, so logout falls back to
        deleting by the raw token string — otherwise an unparseable
        cookie would leave whatever row matches it (if any) behind
        forever."""
        garbage_token = "not-a-real-jwt"
        mock_db["refresh_tokens"].insert_one({"token": garbage_token, "username": "admin"})
        client.set_cookie("refresh_token", garbage_token)

        response = client.post("/api/auth/logout")

        assert response.status_code == 200
        assert mock_db["refresh_tokens"].find_one({"token": garbage_token}) is None

    def test_login_with_corrupted_password_hash_fails_cleanly(self, client, mock_db):
        """A stored password_hash that isn't valid bcrypt output (data
        corruption, a bad migration) must fail the check, not crash it.

        Calls verify_user_credentials directly rather than through
        /api/auth/login — that endpoint's rate limiter uses real-time
        in-memory state shared across this whole test file, and an
        earlier test in this class already exhausts it.
        """
        from web.security import verify_user_credentials

        mock_db["users"].insert_one(
            {
                "username": "corrupted",
                "password_hash": "not-a-real-bcrypt-hash",
                "is_active": True,
            }
        )

        assert verify_user_credentials("corrupted", "anything") is False

    def test_refresh_token_rejected_when_used_as_access_token(self, client, mock_db, admin_refresh_token):
        """A refresh token presented where an access token is expected
        must be rejected — verify_token checks the `type` claim, not
        just the signature."""
        response = client.get(
            "/api/auth/session",
            headers={"Authorization": f"Bearer {admin_refresh_token}"},
        )

        assert response.status_code == 401

    def test_check_admin_returns_false_on_unexpected_error(self, client, mock_db, admin_token):
        from unittest.mock import patch

        with patch("web.security.is_admin", side_effect=RuntimeError("boom")):
            response = client.get("/api/auth/check-admin", headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 200
        assert response.get_json()["is_admin"] is False
