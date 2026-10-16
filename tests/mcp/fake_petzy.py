"""Имитация API Petzy для тестов MCP: записывает каждый запрос и отвечает заранее заданным.

Ни один тест не ходит в сеть: клиент получает MockTransport. Маршрут без ответа даёт 500, чтобы тест не прошёл
молча на пустом месте.
"""

from typing import Any

import httpx

BASE_URL = "https://petzy.example"
TOKEN = "ptz_test_token_for_mcp_0123456789"
PET_ID = "507f1f77bcf86cd799439011"


class FakePetzy:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self._answers: dict[tuple[str, str], tuple[int, Any]] = {}

    def answer(self, method: str, path: str, status: int = 200, body: Any = None) -> None:
        """Ответ на метод и путь (без query). Исключение в body бросается вместо ответа, как сетевая ошибка."""
        self._answers[(method, path)] = (status, body)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self._answers.get(
            (request.method, request.url.path),
            (500, {"success": False, "error": "Нет ответа в тесте"}),
        )
        if isinstance(body, Exception):
            raise body
        return httpx.Response(status, json=body)
