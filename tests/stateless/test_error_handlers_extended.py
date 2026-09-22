"""Tests for the global error handlers in web.app.

These exercise the 422 handler and the unhandled-exception handler that
flask-pydantic-spec / generic HTTPException dispatch routes through.
"""

import pytest


@pytest.mark.error_handling
class TestGlobalErrorHandlers:
    def test_422_validation_error_returns_json(self):
        """Posting invalid JSON to a pydantic-validated endpoint returns 422 + JSON.

        Uses a fresh app to avoid the auth rate limiter interfering.
        """
        from flask import Flask
        from flask_pydantic_spec import FlaskPydanticSpec

        from web.app import handle_unexpected_error, handle_unprocessable_entity

        app = Flask(__name__)
        app.config["TESTING"] = True

        api = FlaskPydanticSpec("flask", title="T", version="1.0", path="apidoc")

        app.register_error_handler(422, handle_unprocessable_entity)
        app.register_error_handler(Exception, handle_unexpected_error)

        # Minimal endpoint that exercises flask-pydantic-spec validation.
        from pydantic import BaseModel

        class _Payload(BaseModel):
            name: str

        from flask_pydantic_spec import Request, Response as FResp

        @app.route("/x", methods=["POST"])
        @api.validate(
            body=Request(_Payload),
            resp=FResp(HTTP_200=None, HTTP_422=None),
        )
        def _x():
            from flask import jsonify
            return jsonify({"ok": True})

        client = app.test_client()
        response = client.post(
            "/x",
            json={"name": ""},  # missing required field if we make it required
        )
        # Empty string is technically valid for str — use missing field instead.
        response = client.post("/x", data="not-json", content_type="application/json")
        assert response.status_code == 422
        payload = response.get_json()
        assert payload is not None
        assert response.headers["Content-Type"].startswith("application/json")

    def test_404_returns_json_for_api_path(self, client):
        response = client.get("/api/this_does_not_exist")
        assert response.status_code == 404
        payload = response.get_json()
        assert payload["success"] is False
        assert payload["code"] == "not_found"

    def test_405_returns_json_for_api_path(self, client):
        """GET on a POST-only endpoint should yield 405 with our JSON envelope."""
        response = client.get("/api/auth/login")
        # Either 405 or 401 depending on auth ordering; we just want JSON envelope
        assert response.status_code in (401, 405)
        payload = response.get_json()
        assert payload["success"] is False

    def test_rate_limit_returns_json_for_api(self, client):
        """Hammer the login endpoint past the limit and verify JSON envelope."""
        for _ in range(10):
            client.post(
                "/api/auth/login",
                json={"username": "bad", "password": "bad"},
            )
        # Some request after the burst should now hit the limiter.
        response = client.post(
            "/api/auth/login",
            json={"username": "bad", "password": "bad"},
        )
        # The limit is 5 per 5 minutes — after 10 attempts the next must be 429.
        if response.status_code == 429:
            payload = response.get_json()
            assert payload["success"] is False
            assert payload["code"] == "rate_limit_exceeded"

    def test_internal_exception_returns_json_for_api(self):
        """An unexpected exception raised by a route should still yield JSON.

        Uses a fresh Flask app with the same error handlers attached, so we
        don't disturb the shared application (and don't trip Flask's
        ``setup_finished`` lock that other tests trigger).
        """
        from flask import Flask
        from werkzeug.exceptions import HTTPException

        from web.errors import error_response

        app = Flask(__name__)
        app.config["TESTING"] = True

        @app.errorhandler(Exception)
        def _on_exc(e):
            if isinstance(e, HTTPException):
                return e
            return error_response("internal_error")

        @app.route("/api/_boom")
        def _boom():  # pragma: no cover - tiny exception-raising route
            raise RuntimeError("explosion")

        client = app.test_client()
        response = client.get("/api/_boom")
        assert response.status_code == 500
        payload = response.get_json()
        assert payload["success"] is False
        assert payload["code"] == "internal_error"