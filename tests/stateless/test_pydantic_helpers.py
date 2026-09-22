"""Tests for web.pydantic_helpers.validate_request_data."""

import json

import pytest
from flask import Flask, request
from pydantic import BaseModel, Field

from web.errors import error_response
from web.pydantic_helpers import validate_request_data


class _Payload(BaseModel):
    name: str = Field(..., min_length=1)
    age: int = Field(..., ge=0)


@pytest.fixture
def flask_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    return app


def test_validates_json_body(flask_app):
    with flask_app.test_request_context("/x", method="POST", json={"name": "Kit", "age": 4}):
        data, err = validate_request_data(request, _Payload, context="ctx")
    assert err is None
    assert data is not None
    assert data.name == "Kit"
    assert data.age == 4


def test_returns_error_when_json_missing(flask_app):
    with flask_app.test_request_context("/x", method="POST"):
        data, err = validate_request_data(request, _Payload)
    assert data is None
    assert err is not None
    body, status = err
    assert status == 422


def test_returns_error_on_validation_failure(flask_app):
    with flask_app.test_request_context("/x", method="POST", json={"name": "", "age": -1}):
        data, err = validate_request_data(request, _Payload, context="test")
    assert data is None
    body, status = err
    assert status == 422
    payload = body.get_json()
    assert payload["success"] is False


def test_parses_json_strings_inside_form(flask_app):
    # Multipart form where one field is a JSON-encoded object string.
    with flask_app.test_request_context(
        "/x",
        method="POST",
        content_type="multipart/form-data",
        data={"name": "Kit", "age": 4, "tiles_settings": json.dumps({"a": 1})},
    ):
        # werkzeug test_request_context with `data=` puts values in form
        data, err = validate_request_data(request, _Payload)
    # age is expected as int; ensure parse falls back cleanly
    assert err is None
    assert data.name == "Kit"


def test_keeps_unparseable_json_string_as_string(flask_app):
    class _WithExtra(BaseModel):
        name: str
        age: int
        note: str = ""

    with flask_app.test_request_context(
        "/x",
        method="POST",
        content_type="multipart/form-data",
        data={"name": "Kit", "age": 4, "note": "{not-json"},
    ):
        data, err = validate_request_data(request, _WithExtra)
    assert err is None
    assert data.note == "{not-json"


def test_unexpected_exception_returns_validation_error(flask_app, monkeypatch):
    """If Pydantic raises something other than ValidationError we still return 422."""

    class _Boom(BaseModel):
        name: str

    def _raise(_):
        raise RuntimeError("explode")

    monkeypatch.setattr(_Boom, "model_validate", _raise)

    with flask_app.test_request_context("/x", method="POST", json={"name": "Kit"}):
        data, err = validate_request_data(request, _Boom, context="boom")
    assert data is None
    body, status = err
    assert status == 422
    assert "explode" in body.get_json()["error"]


def test_strips_value_error_prefix(flask_app):
    """Errors raised with 'Value error, ...' should drop the prefix in the message."""

    class _Strict(BaseModel):
        name: str

        @classmethod
        def model_validate(cls, *_a, **_kw):
            from pydantic import ValidationError

            raise ValidationError.from_exception_data(
                cls.__name__,
                [
                    {
                        "type": "value_error",
                        "loc": ("name",),
                        "input": "",
                        "ctx": {"error": ValueError("bad name")},
                    }
                ],
            )

    with flask_app.test_request_context("/x", method="POST", json={"name": ""}):
        data, err = validate_request_data(request, _Strict)
    assert data is None
    body, status = err
    assert status == 422
    assert "bad name" in body.get_json()["error"]
    assert not body.get_json()["error"].startswith("Value error")


def test_no_context_omits_logging(flask_app, monkeypatch):
    """Without context, validate_request_data still works (no log line is fatal)."""
    warnings: list[str] = []

    class _FakeLogger:
        def warning(self, msg, *a, **kw):
            warnings.append(msg)

    monkeypatch.setattr("web.app.logger", _FakeLogger())
    with flask_app.test_request_context("/x", method="POST", json={"name": ""}):
        data, err = validate_request_data(request, _Payload, context="")
    assert data is None
    assert err is not None
    # When context is empty we shouldn't have logged anything.
    assert warnings == []


def test_error_response_helper_unknown_key(monkeypatch, flask_app):
    """Unknown error keys should still produce a 500 response (graceful fallback)."""
    monkeypatch.setattr("web.errors.ERRORS", {})  # force unknown-key path
    with flask_app.app_context():
        body, status = error_response("nope_does_not_exist")
    assert status == 500
    payload = body.get_json()
    assert payload["success"] is False
    assert payload["code"] == "nope_does_not_exist"