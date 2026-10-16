"""MCP-сервер: пять инструментов по-русски и токен, с которым уходит каждый вызов."""

import asyncio
import json
import re
from types import SimpleNamespace

import pytest

from petzy_mcp.auth import MALFORMED_TOKEN_TEXT, MISSING_TOKEN_TEXT
from petzy_mcp.client import SCOPE_MISSING, PetzyError
from petzy_mcp.server import build_server, token_for_call
from petzy_mcp.tools import BAD_DATE
from tests.mcp.fake_petzy import BASE_URL, PET_ID, TOKEN, FakePetzy

TOOL_NAMES = {"list_pets", "list_event_types", "add_event", "get_history", "get_medical_card"}
CYRILLIC = re.compile("[А-Яа-яЁё]")


def _call(server, name, arguments):
    return asyncio.run(server.call_tool(name, arguments))


def _text(result):
    [block] = result.content
    return block.text


def test_the_server_offers_exactly_the_five_tools_with_russian_descriptions():
    offered = asyncio.run(build_server(BASE_URL).list_tools())

    assert {tool.name for tool in offered} == TOOL_NAMES
    for tool in offered:
        assert CYRILLIC.search(tool.description), tool.name


def test_add_event_declares_the_fields_a_record_cannot_do_without():
    [add_event] = [t for t in asyncio.run(build_server(BASE_URL).list_tools()) if t.name == "add_event"]

    assert set(add_event.input_schema["required"]) == {"pet_id", "type", "date", "time", "fields"}


def test_the_stdio_token_goes_to_petzy_in_the_authorization_header():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", body={"pets": [{"_id": PET_ID, "name": "Рекс", "species": "dog"}]})
    server = build_server(BASE_URL, api_transport=petzy.transport, stdio_token=TOKEN)

    result = _call(server, "list_pets", {})

    assert result.is_error is False
    assert petzy.requests[0].headers["authorization"] == f"Bearer {TOKEN}"
    assert json.loads(_text(result)) == {"pets": [{"id": PET_ID, "name": "Рекс", "species": "dog"}]}
    assert "Рекс" in _text(result), "Cyrillic stays readable, not escaped"


def test_without_any_token_the_tool_says_so_and_sends_nothing():
    petzy = FakePetzy()
    server = build_server(BASE_URL, api_transport=petzy.transport)

    result = _call(server, "list_pets", {})

    assert result.is_error is True
    assert _text(result) == MISSING_TOKEN_TEXT
    assert petzy.requests == []


def test_a_refused_scope_reaches_the_model_as_the_plain_russian_text():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", status=403, body={"success": False, "code": "token_scope_missing", "error": "x"})
    server = build_server(BASE_URL, api_transport=petzy.transport, stdio_token=TOKEN)

    result = _call(server, "list_pets", {})

    assert result.is_error is True
    assert _text(result) == SCOPE_MISSING
    assert TOKEN not in _text(result)


def test_a_bad_date_is_refused_by_the_tool_before_any_request():
    petzy = FakePetzy()
    server = build_server(BASE_URL, api_transport=petzy.transport, stdio_token=TOKEN)

    result = _call(
        server,
        "add_event",
        {"pet_id": PET_ID, "type": "weight", "date": "2026-02-30", "time": "09:30", "fields": {}},
    )

    assert result.is_error is True
    assert _text(result) == BAD_DATE
    assert petzy.requests == []


def test_the_http_token_comes_only_from_the_header_and_never_from_the_fallback():
    with pytest.raises(PetzyError) as refused:
        token_for_call(SimpleNamespace(headers={}), stdio_token=TOKEN)

    assert refused.value.message == MISSING_TOKEN_TEXT


def test_a_header_token_wins_over_the_fallback_and_a_bad_header_is_refused():
    fallback = "ptz_other_token_0000000000"
    assert token_for_call(SimpleNamespace(headers={"authorization": f"Bearer {TOKEN}"}), stdio_token=fallback) == TOKEN

    with pytest.raises(PetzyError) as refused:
        token_for_call(SimpleNamespace(headers={"authorization": "Bearer не-токен"}), stdio_token=fallback)
    assert refused.value.message == MALFORMED_TOKEN_TEXT


def test_a_call_without_a_request_uses_the_stdio_token():
    assert token_for_call(SimpleNamespace(headers=None), stdio_token=TOKEN) == TOKEN
