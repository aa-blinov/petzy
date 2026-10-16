"""HTTP-приложение: доступ проверяется до MCP, /healthz открыт, личный доступ доходит до API Petzy и не выходит обратно."""

import asyncio
import logging

import httpx
import pytest

from petzy_mcp.auth import MALFORMED_TOKEN_TEXT, MISSING_TOKEN_TEXT
from petzy_mcp.client import SCOPE_MISSING, TIMED_OUT
from petzy_mcp.http_app import create_app
from tests.mcp.fake_petzy import BASE_URL, PET_ID, TOKEN, FakePetzy

LIST_TOOLS = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
CALL_LIST_PETS = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_pets", "arguments": {}}}


async def _post(client, body, authorization, host=None):
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    if authorization is not None:
        headers["Authorization"] = authorization
    if host is not None:
        headers["Host"] = host
    return await client.post("/mcp", headers=headers, json=body)


def _session(petzy, check):
    """Запускает приложение с его жизненным циклом (сессии MCP) и даёт check клиента."""

    async def main():
        app = create_app(BASE_URL, api_transport=petzy.transport)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://petzy-mcp.example") as client:
                return await check(client)

    return asyncio.run(main())


def test_healthz_answers_ok_without_any_token():
    response = _session(FakePetzy(), lambda client: client.get("/healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_a_request_without_a_token_is_refused_in_russian_and_reaches_nothing():
    petzy = FakePetzy()

    response = _session(petzy, lambda client: _post(client, LIST_TOOLS, None))

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"success": False, "error": MISSING_TOKEN_TEXT, "code": "token_missing"}
    assert petzy.requests == []


@pytest.mark.parametrize(
    "authorization, code, message",
    [
        ("Basic dXNlcjpwYXNz", "token_missing", MISSING_TOKEN_TEXT),
        ("Bearer eyJhbGciOiJIUzI1NiJ9.e30.signature", "token_malformed", MALFORMED_TOKEN_TEXT),
    ],
)
def test_a_login_token_or_another_scheme_is_refused_before_mcp(authorization, code, message):
    petzy = FakePetzy()

    response = _session(petzy, lambda client: _post(client, CALL_LIST_PETS, authorization))

    assert response.status_code == 401
    assert response.json() == {"success": False, "error": message, "code": code}
    assert petzy.requests == []


def test_the_token_reaches_petzy_only_in_the_header_and_never_comes_back_in_the_answer():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", body={"pets": [{"_id": PET_ID, "name": "Рекс", "species": "dog"}]})

    response = _session(petzy, lambda client: _post(client, CALL_LIST_PETS, f"Bearer {TOKEN}"))

    assert response.status_code == 200
    [sent] = petzy.requests
    assert sent.headers["authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(sent.url)
    result = response.json()["result"]
    assert result["isError"] is False
    assert "Рекс" in result["content"][0]["text"]
    assert TOKEN not in response.text


def test_the_server_offers_the_five_tools_over_mcp():
    response = _session(FakePetzy(), lambda client: _post(client, LIST_TOOLS, f"Bearer {TOKEN}"))

    names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert names == {"list_pets", "list_event_types", "add_event", "get_history", "get_medical_card"}


def test_a_refused_scope_comes_back_to_the_model_as_the_plain_text():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", status=403, body={"success": False, "code": "token_scope_missing", "error": "x"})

    response = _session(petzy, lambda client: _post(client, CALL_LIST_PETS, f"Bearer {TOKEN}"))

    result = response.json()["result"]
    assert response.status_code == 200
    assert result["isError"] is True
    assert result["content"][0]["text"] == SCOPE_MISSING
    assert TOKEN not in response.text


def test_a_petzy_timeout_is_a_tool_error_and_not_a_server_error():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", body=httpx.ReadTimeout("таймаут"))

    response = _session(petzy, lambda client: _post(client, CALL_LIST_PETS, f"Bearer {TOKEN}"))

    assert response.status_code == 200
    assert response.json()["result"]["content"][0]["text"] == TIMED_OUT


def test_the_app_answers_under_the_public_host_name_behind_the_proxy():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", body={"pets": []})

    response = _session(
        petzy, lambda client: _post(client, CALL_LIST_PETS, f"Bearer {TOKEN}", host="mcp.petzy.example")
    )

    assert response.status_code == 200


def test_the_token_stays_out_of_the_log_on_both_the_good_and_the_refused_path(caplog):
    caplog.set_level(logging.DEBUG)
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", status=403, body={"code": "token_scope_missing", "error": "x"})

    _session(petzy, lambda client: _post(client, CALL_LIST_PETS, f"Bearer {TOKEN}"))
    _session(petzy, lambda client: _post(client, CALL_LIST_PETS, None))

    assert TOKEN not in caplog.text
