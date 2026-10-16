"""The MCP server on the stand: an assistant's personal token, the five tools over HTTP, and a revoked token.

It goes the way an assistant does. The owner makes a personal access token (POST /api/me/tokens), and the MCP protocol
runs on localhost:3000/mcp, through nginx. The throwaway pet «Тест-М» and the token are removed at the end, also when a
step failed. No line printed here carries the token.
"""

import asyncio
import json
import secrets
from contextlib import asynccontextmanager

import httpx2
from common import BASE, api, async_playwright, check, login, new_page, summary
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = BASE + "/mcp"
SCOPES = ["pets:read", "events:write", "history:read", "medical:read"]
TOOLS = {"list_pets", "list_event_types", "add_event", "get_history", "get_medical_card"}
# The text petzy_mcp answers with when Petzy refuses the token (mcp/petzy_mcp/client.py).
NOT_FOUND = "Доступ не найден"
JSON_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
LIST_TOOLS = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}


@asynccontextmanager
async def mcp_session(token):
    """An MCP session over HTTP, with the token in the Authorization header of every request."""
    async with httpx2.AsyncClient(
        headers={"Authorization": f"Bearer {token}"}, timeout=httpx2.Timeout(30.0, read=120.0)
    ) as http:
        async with streamable_http_client(MCP_URL, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def call(session, name, arguments=None):
    """What a tool answers, as (is an error, text)."""
    result = await session.call_tool(name, arguments or {})
    return result.is_error, result.content[0].text


async def use_the_tools(token, pet_id):
    """The five tools in the order an assistant needs them: the pet, the types, a record, its history, the card."""
    async with mcp_session(token) as session:
        listed = await session.list_tools()
        names = {tool.name for tool in listed.tools}
        check("tools/list offers the five tools", names == TOOLS, ", ".join(sorted(names)))

        is_error, text = await call(session, "list_pets")
        pets = [] if is_error else json.loads(text)["pets"]
        check("list_pets sees the throwaway pet", any(p.get("id") == pet_id for p in pets), f"{len(pets)} pets")

        is_error, text = await call(session, "list_event_types")
        types = [] if is_error else json.loads(text)["event_types"]
        weight = next((t for t in types if t.get("key") == "weight"), {})
        check(
            "list_event_types describes the weight type with its weight field",
            any(field.get("name") == "weight" for field in weight.get("fields", [])),
        )

        is_error, text = await call(
            session,
            "add_event",
            {"pet_id": pet_id, "type": "weight", "date": "2026-10-01", "time": "09:30", "fields": {"weight": 4.2}},
        )
        record_id = "" if is_error else json.loads(text).get("id", "")
        check("add_event writes the weight and answers with its id", bool(record_id), "" if record_id else text[:120])

        is_error, text = await call(session, "get_history", {"pet_id": pet_id})
        items = [] if is_error else json.loads(text)["items"]
        mine = [item for item in items if item.get("id") == record_id]
        check(
            "get_history shows the record with its weight",
            len(mine) == 1
            and mine[0].get("record_type") == "weight"
            and mine[0].get("fields", {}).get("weight") == 4.2,
            f"{len(items)} items",
        )

        is_error, text = await call(session, "get_medical_card", {"pet_id": pet_id})
        card = {} if is_error else json.loads(text)
        check(
            "get_medical_card answers with the card",
            not is_error and isinstance(card.get("card"), dict) and bool(text.strip()),
            f"{len(text)} characters",
        )


async def without_a_token():
    """A request with no Authorization header stops at the front door: 401 with the code token_missing."""
    async with httpx2.AsyncClient(timeout=30) as http:
        response = await http.post(MCP_URL, json=LIST_TOOLS, headers=JSON_HEADERS)
    check(
        "without an Authorization header: 401 token_missing",
        response.status_code == 401 and _code(response) == "token_missing",
        str(response.status_code),
    )


async def unknown_token():
    """A well-formed token Petzy does not know: the server passes it on, and the tool answers in plain Russian."""
    token = "ptz_" + secrets.token_urlsafe(32)
    async with mcp_session(token) as session:
        is_error, text = await call(session, "list_pets")
    check("an unknown token: the tool answers «Доступ не найден»", is_error and NOT_FOUND in text)


async def revoked_token(token):
    """The token that was just revoked gets the same answer as an unknown one."""
    async with mcp_session(token) as session:
        is_error, text = await call(session, "list_pets")
    check("after revoking, the same token gets «Доступ не найден»", is_error and NOT_FOUND in text)


def _code(response):
    body = response.json()
    return body.get("code") if isinstance(body, dict) else None


async def attempt(name, step, token=None):
    """One part of the check. A failure there is a FAIL line and not a crash, so the cleanup below still runs."""
    try:
        await step
    except Exception as exc:
        # The MCP client wraps what went wrong in a task group: the first error inside says what it was.
        cause = exc
        while getattr(cause, "exceptions", None):
            cause = cause.exceptions[0]
        message = f"{type(cause).__name__}: {cause}"
        if token:
            message = message.replace(token, "[скрыто]")
        check(name, False, message[:200])


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        _, pg = await new_page(browser, sw=False)
        await login(pg)
        pet_id = token_id = token = None
        try:
            made = await api(pg, "POST", "/pets", {"name": "Тест-М", "species": "dog", "gender": "male"})
            pet_id = ((made["json"] or {}).get("pet") or {}).get("_id")
            check("a throwaway pet «Тест-М» is made", bool(pet_id), str(made["status"]))

            minted = await api(
                pg, "POST", "/me/tokens", {"name": "Проверка MCP", "scopes": SCOPES, "expires_in_days": 1}
            )
            issued = minted["json"] or {}
            token, token_id = issued.get("token"), issued.get("id")
            check(
                "the owner makes a personal token with the four scopes",
                minted["status"] == 201 and str(token).startswith("ptz_") and issued.get("scopes") == SCOPES,
                str(minted["status"]),
            )

            if pet_id and token:
                await attempt("the five tools answer over HTTP", use_the_tools(token, pet_id), token)
            await attempt("without a token the request is refused", without_a_token())
            await attempt("an unknown token is refused by the tool", unknown_token())
            if token_id:
                revoked = await api(pg, "DELETE", f"/me/tokens/{token_id}")
                check("the owner revokes the token", revoked["status"] == 200, str(revoked["status"]))
                if token:
                    await attempt("a revoked token is refused by the tool", revoked_token(token), token)
        finally:
            if token_id:
                await api(pg, "DELETE", f"/me/tokens/{token_id}")
            if pet_id:
                await api(pg, "DELETE", f"/pets/{pet_id}")
        await browser.close()
    summary("MCP on the stand")


asyncio.run(main())
