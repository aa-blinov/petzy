"""Клиент к API Petzy: токен только в заголовке, ошибки API в понятном тексте, без токена и без трассировки."""

import asyncio
import logging

import httpx
import pytest

from petzy_mcp.client import (
    AUTH_FAILED,
    BAD_RESPONSE,
    EVENT_TYPE_NOT_FOUND,
    NOT_ALLOWED,
    NOT_FOUND,
    RATE_LIMITED,
    REJECTED_DATA,
    SCOPE_MISSING,
    SERVER_FAILED,
    TIMED_OUT,
    UNREACHABLE,
    PetzyClient,
    PetzyError,
    checked_api_url,
)
from tests.mcp.fake_petzy import BASE_URL, PET_ID, TOKEN, FakePetzy


def _get(transport, path="/api/pets", base_url=BASE_URL):
    async def go():
        async with PetzyClient(base_url, TOKEN, transport) as api:
            return await api.get(path)

    return asyncio.run(go())


def test_the_token_goes_in_the_authorization_header_and_never_in_the_address():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", body={"pets": []})

    _get(petzy.transport)

    [sent] = petzy.requests
    assert sent.headers["authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in str(sent.url)


def test_the_api_path_joins_the_base_address_without_a_double_slash():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", body={"pets": []})

    _get(petzy.transport, base_url="https://petzy.example/")

    assert str(petzy.requests[0].url) == "https://petzy.example/api/pets"


@pytest.mark.parametrize(
    "status, body, expected",
    [
        (401, {"success": False, "code": "token_invalid", "error": "Доступ не найден"}, AUTH_FAILED),
        (401, None, AUTH_FAILED),
        (403, {"success": False, "code": "token_scope_missing", "error": "x"}, SCOPE_MISSING),
        (403, {"success": False, "code": "token_not_allowed", "error": "x"}, NOT_ALLOWED),
        (
            403,
            {"success": False, "code": "forbidden", "error": "Нет доступа к этому ресурсу"},
            "Нет доступа к этому ресурсу",
        ),
        (404, {"success": False, "code": "pet_not_found", "error": "Питомец не найден"}, NOT_FOUND),
        (
            404,
            {"success": False, "code": "event_type_not_found", "error": "Тип события не найден"},
            EVENT_TYPE_NOT_FOUND,
        ),
        (
            422,
            {"success": False, "code": "validation_error", "error": "Неверный формат времени"},
            "Неверный формат времени",
        ),
        (422, {"success": False, "code": "validation_error"}, REJECTED_DATA),
        (429, {"success": False, "code": "rate_limit_exceeded", "error": "Слишком много попыток"}, RATE_LIMITED),
        (500, {"success": False, "code": "internal_error", "error": "Внутренняя ошибка сервера"}, SERVER_FAILED),
        (
            409,
            {"success": False, "code": "duplicate_event", "error": "Такая запись уже сохранена на 09:30"},
            "Такая запись уже сохранена на 09:30",
        ),
    ],
)
def test_each_api_error_becomes_its_russian_text(status, body, expected):
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", status=status, body=body)

    with pytest.raises(PetzyError) as refused:
        _get(petzy.transport)

    assert refused.value.message == expected


def test_a_token_echoed_by_the_server_is_removed_from_the_error_text():
    petzy = FakePetzy()
    petzy.answer("POST", "/api/events", status=422, body={"success": False, "error": f"плохо: {TOKEN}"})

    async def go():
        async with PetzyClient(BASE_URL, TOKEN, petzy.transport) as api:
            return await api.post("/api/events", {})

    with pytest.raises(PetzyError) as refused:
        asyncio.run(go())

    assert TOKEN not in refused.value.message
    assert "плохо:" in refused.value.message


def test_a_server_failure_does_not_show_what_it_said():
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", status=500, body={"success": False, "error": "секретная трасса"})

    with pytest.raises(PetzyError) as refused:
        _get(petzy.transport)

    assert refused.value.message == SERVER_FAILED


@pytest.mark.parametrize(
    "failure, expected",
    [
        (httpx.ReadTimeout(f"таймаут с {TOKEN}"), TIMED_OUT),
        (httpx.ConnectError(f"нет соединения с {TOKEN}"), UNREACHABLE),
    ],
)
def test_timeouts_and_network_errors_are_plain_text(failure, expected):
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", body=failure)

    with pytest.raises(PetzyError) as refused:
        _get(petzy.transport)

    assert refused.value.message == expected
    assert TOKEN not in refused.value.message
    assert refused.value.__suppress_context__


def test_a_redirect_is_not_followed_so_the_token_never_leaves_for_another_address():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://elsewhere.example/api/pets"})

    with pytest.raises(PetzyError) as refused:
        _get(httpx.MockTransport(handler))

    assert len(seen) == 1
    assert refused.value.message == "Petzy ответил ошибкой (код 302)"


def test_an_answer_that_is_not_json_is_refused_plainly():
    def handler(request):
        return httpx.Response(
            200,
            content="<html>ошибка прокси</html>".encode("utf-8"),
            headers={"content-type": "text/html"},
        )

    with pytest.raises(PetzyError) as refused:
        _get(httpx.MockTransport(handler))

    assert refused.value.message == BAD_RESPONSE


def test_the_token_is_not_written_to_the_log(caplog):
    caplog.set_level(logging.DEBUG)
    petzy = FakePetzy()
    petzy.answer("GET", "/api/pets", status=403, body={"code": "token_scope_missing", "error": "x"})
    petzy.answer("GET", f"/api/pets/{PET_ID}/medical-card", body={"card": {}})

    with pytest.raises(PetzyError):
        _get(petzy.transport)
    _get(petzy.transport, path=f"/api/pets/{PET_ID}/medical-card")

    assert TOKEN not in caplog.text


@pytest.mark.parametrize(
    "value, expected",
    [
        ("https://petzy.duckdns.org", "https://petzy.duckdns.org"),
        ("https://petzy.duckdns.org/", "https://petzy.duckdns.org"),
        ("http://web:5000", "http://web:5000"),
        ("http://localhost:5000", "http://localhost:5000"),
        ("http://127.0.0.1:5000", "http://127.0.0.1:5000"),
    ],
)
def test_the_api_address_is_accepted_when_the_token_stays_safe(value, expected):
    assert checked_api_url(value) == expected


@pytest.mark.parametrize(
    "value",
    ["http://petzy.duckdns.org", "ftp://web:5000", "petzy.duckdns.org", "", "https://"],
)
def test_an_address_that_would_send_the_token_in_the_clear_is_refused(value):
    with pytest.raises(ValueError):
        checked_api_url(value)
