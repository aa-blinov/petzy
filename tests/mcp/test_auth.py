"""Личный доступ в заголовке: что считается доступом Petzy, как читается схема Bearer и почему запрос отказан."""

import pytest

from petzy_mcp.auth import MALFORMED_TOKEN_TEXT, MISSING_TOKEN_TEXT, TokenError, bearer_value, is_token, personal_token
from tests.mcp.fake_petzy import TOKEN


@pytest.mark.parametrize("value", [TOKEN, "ptz_" + "a" * 43, "ptz_abc-DEF_123"])
def test_a_personal_token_is_recognised(value):
    assert is_token(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "ptz_",
        "ptz_ab cd",
        "ptz_ab\n",
        " ptz_abc",
        "PTZ_abc",
        "Bearer ptz_abc",
        "eyJhbGciOiJIUzI1NiJ9.e30.signature",
    ],
)
def test_anything_else_is_not_a_personal_token(value):
    assert not is_token(value)


@pytest.mark.parametrize("header", ["Bearer ptz_abc", "bearer ptz_abc", "BEARER ptz_abc"])
def test_the_bearer_scheme_is_read_without_regard_to_case(header):
    assert bearer_value(header) == "ptz_abc"


@pytest.mark.parametrize("header", [None, "", "Basic dXNlcjpwYXNz"])
def test_no_header_or_another_scheme_has_no_bearer_value(header):
    assert bearer_value(header) is None


def test_a_good_header_gives_the_token():
    assert personal_token(f"Bearer {TOKEN}") == TOKEN


@pytest.mark.parametrize(
    "header, code, message",
    [
        (None, "token_missing", MISSING_TOKEN_TEXT),
        ("Basic dXNlcjpwYXNz", "token_missing", MISSING_TOKEN_TEXT),
        ("Bearer", "token_malformed", MALFORMED_TOKEN_TEXT),
        ("Bearer ", "token_malformed", MALFORMED_TOKEN_TEXT),
        ("Bearer eyJhbGciOiJIUzI1NiJ9.e30.signature", "token_malformed", MALFORMED_TOKEN_TEXT),
    ],
)
def test_a_header_that_is_not_a_personal_token_is_refused_with_a_reason(header, code, message):
    with pytest.raises(TokenError) as refused:
        personal_token(header)
    assert (refused.value.code, refused.value.message) == (code, message)
