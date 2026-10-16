"""HTTP-приложение: /mcp (streamable HTTP) за проверкой личного доступа и /healthz для проверки контейнера.

Сессий нет: каждый запрос к /mcp несёт свой заголовок Authorization, и сервер не помнит клиента между запросами.
Так токен живёт ровно столько, сколько длится запрос.
"""

import httpx
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .auth import TokenError, personal_token
from .server import build_server

HEALTH_PATH = "/healthz"


async def healthz(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


class RequirePersonalToken:
    """Пускает к приложению только запросы с личным доступом Petzy, проверка до MCP.

    /healthz открыт: контейнеру нужен ответ, а сведений он не отдаёт.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] != HEALTH_PATH:
            try:
                personal_token(Headers(scope=scope).get("authorization"))
            except TokenError as refused:
                response = JSONResponse(
                    {"success": False, "error": refused.message, "code": refused.code},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


def create_app(api_url: str, *, api_transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
    server = build_server(api_url, api_transport=api_transport)
    app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        # SDK сам включает проверку заголовка Host, если сервер слушает localhost, и пускает только localhost:
        # за обратным прокси с публичным именем каждый запрос получил бы 421. Проверка выключена осознанно.
        # Страница, подменившая Host, токена не знает, а без токена сервер ничего не отдаёт.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    app.add_route(HEALTH_PATH, healthz, methods=["GET"])
    app.add_middleware(RequirePersonalToken)
    return app
