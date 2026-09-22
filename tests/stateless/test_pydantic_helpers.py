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

def test_json_body_of_literal_null_returns_validation_error(flask_app):
    """A syntactically valid JSON body that parses to None (the literal
    `null`) must produce a clean validation_error rather than crashing
    on model_validate(None). A body that isn't valid JSON at all, or has
    no JSON content-type, raises inside request.get_json() itself and
    is caught by the generic except further down instead — this is
    specifically the "parsed successfully to nothing" case.
    """
    with flask_app.test_request_context("/x", method="POST", data="null", content_type="application/json"):
        data, err = validate_request_data(request, _Payload, context="ctx")
    assert data is None
    body, status = err
    assert status == 422


def test_unexpected_exception_during_validation_is_caught(flask_app, monkeypatch):
    """Something other than pydantic's own ValidationError raised during
    model_validate (a bug in a custom validator, e.g.) must still come
    back as a clean validation_error instead of propagating as a 500."""

    class _Explodes(BaseModel):
        name: str

        @classmethod
        def model_validate(cls, *_a, **_kw):
            raise RuntimeError("unexpected bug in a custom validator")

    with flask_app.test_request_context("/x", method="POST", json={"name": "x"}):
        data, err = validate_request_data(request, _Explodes, context="ctx")

    assert data is None
    body, status = err
    assert status == 422
    assert "unexpected bug" in body.get_json()["error"]


def test_validation_error_with_no_error_entries_falls_back_to_str(flask_app):
    """Pydantic's ValidationError always carries at least one entry in
    practice, but the code defensively handles an empty list too —
    verified directly since Pydantic itself won't naturally produce one."""
    from pydantic import ValidationError

    class _Empty(BaseModel):
        name: str

        @classmethod
        def model_validate(cls, *_a, **_kw):
            raise ValidationError.from_exception_data(cls.__name__, [])

    with flask_app.test_request_context("/x", method="POST", json={"name": "x"}):
        data, err = validate_request_data(request, _Empty, context="ctx")

    assert data is None
    body, status = err
    assert status == 422
