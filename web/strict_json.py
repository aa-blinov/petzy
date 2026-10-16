"""Request JSON read without NaN and Infinity.

Python's json module reads the literals NaN, Infinity and -Infinity, and a number too large for a float (1e400)
becomes Infinity. Such a value was stored wherever no bound of the field refused it (a dose, a number field of an event
type), and the answer then carried NaN, which the browser cannot read as JSON.

NonFiniteNumber is deliberately not a ValueError. flask-pydantic-spec reads a body with get_json(silent=True), which
turns a ValueError into None and then into an empty body, so a dose of NaN would be dropped without a word. Any other
exception reaches the handler in web/app.py, which answers 422 with the message below.
"""

import json
import math

from flask import Request

MESSAGE = "Числа NaN и Infinity не принимаются"


class NonFiniteNumber(Exception):
    """A request holds NaN, Infinity or a number too large for a float."""

    def __init__(self):
        super().__init__(MESSAGE)


def _refuse_constant(_name: str):
    raise NonFiniteNumber()


def _finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise NonFiniteNumber()
    return value


def loads(text):
    """json.loads that refuses NaN, Infinity, -Infinity and a number that overflows to infinity."""
    return json.loads(text, parse_constant=_refuse_constant, parse_float=_finite_float)


class _JSONModule:
    """The json module, with loads replaced by the strict one."""

    loads = staticmethod(loads)

    def __getattr__(self, name):
        return getattr(json, name)


_STRICT_JSON = _JSONModule()


class StrictJSONRequest(Request):
    """A request whose body is read strictly. Responses keep the app's JSON as it is.

    Flask assigns the app's JSON provider to every request (flask/ctx.py), which would hide a class attribute. The
    setter below keeps the strict reader in place. The provider is not made strict itself: flask-pydantic-spec reads
    every response it validates with it, and a stored NaN would then fail a plain GET.
    """

    @property
    def json_module(self):
        return _STRICT_JSON

    @json_module.setter
    def json_module(self, _provider):
        pass


def keep_json_strict() -> None:
    """Read the bodies flask-pydantic-spec reads itself strictly too: a gzip body and a JSON part of a form."""
    from flask_pydantic_spec import flask_backend

    flask_backend.json = _STRICT_JSON
