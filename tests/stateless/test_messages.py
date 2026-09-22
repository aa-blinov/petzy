"""Tests for get_message's fallback paths — the happy path (known key,
correct kwargs) is already exercised indirectly by every route that
calls it; these cover the two defensive branches that aren't."""

import pytest


@pytest.mark.unit
class TestGetMessageFallbacks:

    def test_unknown_key_returns_generic_success_message(self):
        from flask import Flask
        from web.messages import get_message

        app = Flask(__name__)
        with app.test_request_context("/"):
            response, status = get_message("this_key_does_not_exist")
            body = response.get_json()

        assert status == 200
        assert body["success"] is True
        assert "this_key_does_not_exist" in body["message"]

    def test_missing_placeholder_kwarg_leaves_message_unformatted(self):
        """pet_shared's template needs `username` — passing some *other*
        kwarg (so the format() call actually runs, unlike passing none
        at all) but not that one must not crash the response, just
        leave the placeholder unfilled."""
        from flask import Flask
        from web.messages import get_message

        app = Flask(__name__)
        with app.test_request_context("/"):
            response, status = get_message("pet_shared", unrelated_kwarg="x")
            body = response.get_json()

        assert status == 200
        assert body["message"] == "Доступ предоставлен пользователю {username}"
