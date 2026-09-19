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
            JWT_SECRET_KEY, JWT_ALGORITHM, REFRESH_TOKEN_EXPIRE_DAYS,
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

    def test_login_page_get(self, client):
        """Test GET login page."""
        response = client.get("/login")
        assert response.status_code == 200

    def test_login_page_post_success(self, client, mock_db):
        """Test POST login page with valid credentials."""
        response = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)

        # Should redirect to dashboard (302) or return success
        assert response.status_code in [200, 302]
        # Check cookies are set in response headers if redirecting
        if response.status_code == 302:
            set_cookie_headers = [h for h in response.headers.getlist("Set-Cookie")]
            cookie_names = " ".join(set_cookie_headers)
            assert "access_token" in cookie_names

    def test_login_page_post_invalid(self, client, mock_db):
        """Test POST login page with invalid credentials."""
        response = client.post("/login", data={"username": "admin", "password": "wrongpassword"})

        assert response.status_code == 200
        # Should render login page with error

    def test_index_redirects_to_login_when_not_authenticated(self, client):
        """Test index redirects to login when not authenticated."""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_index_redirects_to_dashboard_when_authenticated(self, client, auth_cookies):
        """Test index redirects to dashboard when authenticated."""
        client.set_cookie("access_token", auth_cookies["access_token"])
        client.set_cookie("refresh_token", auth_cookies["refresh_token"])
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 302
        assert "/dashboard" in response.location

    def test_dashboard_requires_authentication(self, client):
        """Test dashboard requires authentication."""
        response = client.get("/dashboard", follow_redirects=False)
        assert response.status_code == 302
        assert "/login" in response.location

    def test_dashboard_accessible_with_token(self, client, auth_headers):
        """Test dashboard is accessible with valid token."""
        response = client.get("/dashboard", headers=auth_headers)
        assert response.status_code == 200

    def test_logout_route(self, client, mock_db, admin_refresh_token):
        """Test logout route."""
        # Store refresh token
        from web.app import db

        db["refresh_tokens"].insert_one(
            {
                "token": admin_refresh_token,
                "username": "admin",
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            }
        )

        client.set_cookie("refresh_token", admin_refresh_token)
        response = client.get("/logout", follow_redirects=False)

        assert response.status_code == 302
        assert "/login" in response.location

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
            JWT_SECRET_KEY, JWT_ALGORITHM,
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

        response = client.get(
            "/dashboard", headers={"Authorization": f"Bearer {expired_token}"}, follow_redirects=False
        )

        assert response.status_code == 302  # Should redirect to login

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
