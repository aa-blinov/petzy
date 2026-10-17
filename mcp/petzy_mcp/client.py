"""Запросы к API Petzy от имени одного личного доступа и перевод ошибок API в понятный текст.

Токен уходит в заголовке Authorization и только туда. Текст ошибки складывается из фиксированных фраз. Ответ сервера
попадает в него, только когда сервер сам говорит, что не так (422, 409, 404 для типа события), и то без токена.
"""

from typing import Any

import httpx

DEFAULT_API_URL = "https://petzy.duckdns.org"
REQUEST_TIMEOUT_SECONDS = 15.0

AUTH_FAILED = (
    "Доступ не найден, отозван или его срок истёк. Создайте новый в настройках Petzy, раздел «Доступ для ассистентов»"
)
# Галочки под теми же подписями, что в настройках («Доступ для ассистентов»): по тексту ошибки их легко найти.
SCOPE_LABELS = {
    "pets:read": "Читать питомцев",
    "events:write": "Записывать события",
    "history:read": "Читать ленту и историю",
    "medical:read": "Читать медкарту",
}
NOT_ALLOWED = "Этот доступ не работает для такого действия"
NOT_FOUND = "Питомец или запись не найдены"
EVENT_TYPE_NOT_FOUND = "Тип события не найден. Список типов покажет list_event_types"
REJECTED_DATA = "Petzy не принял данные запроса. Проверьте значения и попробуйте снова"
RATE_LIMITED = "Слишком много запросов, подождите минуту"
SERVER_FAILED = "Petzy не смог ответить из-за ошибки на своей стороне. Попробуйте позже"
TIMED_OUT = "Petzy не ответил вовремя. Попробуйте ещё раз немного позже"
UNREACHABLE = "Не удалось связаться с Petzy. Проверьте, что сервис доступен, и попробуйте позже"
BAD_RESPONSE = "Petzy ответил так, что ответ не удалось прочитать"

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


class PetzyError(Exception):
    """Ошибка, текст которой можно показать модели как есть: без токена, без адреса и без трассировки."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def scope_missing(scope: str | None) -> str:
    """Что ответить, когда у доступа нет галочки: по её подписи, как она написана в настройках."""
    label = SCOPE_LABELS.get(scope or "")
    if label is None:
        return "У этого доступа нет нужной галочки. Создайте доступ и отметьте галочку для этого действия"
    return f"У этого доступа нет галочки «{label}». Создайте доступ и отметьте её"


def checked_api_url(value: str) -> str:
    """Адрес API Petzy, проверенный до первого запроса.

    Токен идёт по этому адресу, поэтому без https адрес допускается только для этой машины и для имени сервиса
    внутри сети Docker, например http://web:5000.
    """
    try:
        url = httpx.URL(value.strip())
    except httpx.InvalidURL:
        raise ValueError("адрес не разобран") from None
    if url.scheme not in ("http", "https") or not url.host:
        raise ValueError("адрес должен начинаться с https://")
    if url.scheme == "http" and not _is_local(url.host):
        raise ValueError("без https можно указать только localhost или имя сервиса в Docker, например http://web:5000")
    return str(url).rstrip("/")


def _is_local(host: str) -> bool:
    # Имя без точек внутри сети Docker (web, db) не выходит в интернет.
    return host in _LOCAL_HOSTS or "." not in host


class PetzyClient:
    """Соединение с API Petzy на один вызов инструмента: открывается, отвечает и закрывается.

    Перенаправления не выполняются: иначе заголовок Authorization ушёл бы по адресу, который выбрал не Petzy.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        transport: httpx.AsyncBaseTransport | None = None,
        *,
        scope: str | None = None,
    ) -> None:
        self._token = token
        self._scope = scope
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=False,
            transport=transport,
        )

    async def __aenter__(self) -> "PetzyClient":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self._http.aclose()

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return await self._send("GET", path, params=params)

    async def post(self, path: str, body: dict[str, Any]) -> Any:
        return await self._send("POST", path, json=body)

    async def _send(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._http.request(method, path, **kwargs)
        except httpx.TimeoutException:
            raise PetzyError(TIMED_OUT) from None
        except httpx.RequestError:
            raise PetzyError(UNREACHABLE) from None
        if not response.is_success:
            raise PetzyError(self._error_message(response))
        try:
            return response.json()
        except ValueError:
            raise PetzyError(BAD_RESPONSE) from None

    def _error_message(self, response: httpx.Response) -> str:
        status = response.status_code
        body = _json_body(response)
        code = body.get("code") if isinstance(body, dict) else None
        server_text = self._server_text(body)
        if status == 401:
            return AUTH_FAILED
        if status == 403:
            if code == "token_scope_missing":
                return scope_missing(self._scope)
            if code == "token_not_allowed":
                return NOT_ALLOWED
            return server_text or "У этого доступа не хватает прав на это действие"
        if status == 404:
            return EVENT_TYPE_NOT_FOUND if code == "event_type_not_found" else NOT_FOUND
        if status == 422:
            return server_text or REJECTED_DATA
        if status == 429:
            return RATE_LIMITED
        if status >= 500:
            return SERVER_FAILED
        return server_text or f"Petzy ответил ошибкой (код {status})"

    def _server_text(self, body: Any) -> str | None:
        text = body.get("error") if isinstance(body, dict) else None
        if not isinstance(text, str) or not text.strip():
            return None
        if self._token:
            text = text.replace(self._token, "[скрыто]")
        return text.strip()[:500]


def _json_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None
