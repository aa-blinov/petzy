"""MCP-сервер Petzy: пять инструментов и личный доступ, с которым каждый из них обращается к API.

Инструмент отвечает CallToolResult, а не исключением. Модель получает русский текст ошибки без служебного префикса
SDK, а журнал не получает трассировок на ожидаемые ошибки.
"""

import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Annotated, Any

import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent
from pydantic import Field

from . import __version__, tools
from .auth import MISSING_TOKEN_TEXT, TokenError, personal_token
from .client import PetzyClient, PetzyError

INSTRUCTIONS = (
    "Дневник питомца Petzy. Работайте по порядку. 1) list_pets: найдите питомца по имени, которое назвал "
    "пользователь, и возьмите его id. Если имя не совпадает ни с одним или совпадает с двумя, спросите пользователя. "
    "2) list_event_types: ключ типа (key) и имена полей (fields) для add_event берите только оттуда. "
    "Обязательные поля (required), которых пользователь не назвал, спросите у пользователя. "
    "3) add_event: одна запись за один вызов. Дату «сегодня» берите из контекста, если там есть текущая дата, "
    "иначе спросите. Время не выдумывайте: если его не назвали, спросите. Пояс (tz) тоже не выдумывайте: "
    "спросите, если его не знаете. "
    "Инструменты не меняют и не удаляют записи: правку скажите сделать в приложении Petzy."
)

LIST_PETS = (
    "Питомцы, к которым есть доступ у этого ключа: номер (id), имя и вид (dog, cat и т. д.). "
    "Начните с этого инструмента: номер питомца нужен всем остальным. Ничего не меняет."
)
LIST_EVENT_TYPES = (
    "Типы записей дневника, которые можно добавить через add_event, и поля каждого типа. Вызовите его перед "
    "add_event: ключ типа (key) и имена полей (fields) берутся отсюда. У поля есть required, type (number, text, "
    "select, textarea), min, max, step и options (value отправляется, text показывается). Единица измерения "
    "написана в подписи поля, например «Вес корма (г)». Список одинаков для всех питомцев. Ничего не меняет."
)
ADD_EVENT = (
    "Добавляет одну запись в дневник питомца: вес, кормление, приём лекарства и другие типы из list_event_types. "
    "Перед вызовом получите ключ типа и поля через list_event_types. Ключ type тот же, что record_type в истории. "
    "Дата ГГГГ-ММ-ДД, время ЧЧ:ММ, tz пояс (IANA-имя, например Asia/Almaty), fields словарь «имя поля: значение». "
    "Если Petzy ответил «Такая запись уже "
    "сохранена», запись уже есть: не записывайте её снова. Инструмент только добавляет запись: изменить или удалить "
    "существующую он не может."
)
GET_HISTORY = (
    "Последние записи дневника питомца, новые сверху: события и приёмы лекарств. В каждой записи есть id, "
    "record_type (ключ типа события или medications для приёма), date_time (ГГГГ-ММ-ДД ЧЧ:ММ), fields и comment. "
    "У приёма есть medication_name, dose_taken, dose_unit, а skipped означает пропущенный приём. В ответе total: "
    "всего записей. Чтобы увидеть больше, увеличьте limit (до 100). Ничего не меняет."
)
GET_MEDICAL_CARD = (
    "Медицинская карта питомца: профиль (аллергии, группа крови), вес, текущие и прошедшие курсы лекарств, "
    "прививки, записи и последние документы. Только чтение. Пустые строки и null не выводятся. Если карта не "
    "помещается в 30 000 символов, в ответе будет пометка «ответ обрезан» и список разделов, которых в нём нет."
)


def token_for_call(ctx: Context, stdio_token: str | None) -> str:
    """Личный доступ для одного вызова.

    Вызов по HTTP несёт свой заголовок Authorization, и токен берётся только из него: запасной токен сервера в такой
    вызов не подставляется. У вызова через stdio заголовков нет, и его токен задан при запуске (PETZY_TOKEN).
    """
    headers = _headers(ctx)
    if headers is None:
        if stdio_token is None:
            raise PetzyError(MISSING_TOKEN_TEXT)
        return stdio_token
    try:
        return personal_token(headers.get("authorization"))
    except TokenError as exc:
        raise PetzyError(exc.message) from None


def _headers(ctx: Context) -> Mapping[str, str] | None:
    try:
        return ctx.headers
    except ValueError:  # вызов сделан прямо в коде, не из запроса: заголовков нет
        return None


def _result(text: str, *, is_error: bool = False) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)], is_error=is_error)


def build_server(
    api_url: str,
    *,
    api_transport: httpx.AsyncBaseTransport | None = None,
    stdio_token: str | None = None,
) -> MCPServer:
    """MCP-сервер с пятью инструментами. Для HTTP stdio_token не задают: каждый запрос несёт свой доступ."""
    server = MCPServer("petzy", instructions=INSTRUCTIONS, version=__version__)

    async def run_tool(ctx: Context, call: Callable[[PetzyClient], Awaitable[Any]], scope: str) -> CallToolResult:
        try:
            token = token_for_call(ctx, stdio_token)
            async with PetzyClient(api_url, token, api_transport, scope=scope) as api:
                data = await call(api)
        except PetzyError as exc:
            return _result(exc.message, is_error=True)
        return _result(json.dumps(data, ensure_ascii=False, separators=(",", ":")))

    @server.tool(description=LIST_PETS, structured_output=False)
    async def list_pets(ctx: Context) -> CallToolResult:
        return await run_tool(ctx, tools.list_pets, "pets:read")

    @server.tool(description=LIST_EVENT_TYPES, structured_output=False)
    async def list_event_types(ctx: Context) -> CallToolResult:
        return await run_tool(ctx, tools.list_event_types, "pets:read")

    @server.tool(description=ADD_EVENT, structured_output=False)
    async def add_event(
        ctx: Context,
        pet_id: Annotated[str, Field(description="Номер питомца из list_pets, 24 символа")],
        type: Annotated[str, Field(description="Ключ типа записи из list_event_types, например weight")],
        date: Annotated[
            str,
            Field(
                description="Дата в формате ГГГГ-ММ-ДД. «Сегодня» берите из контекста, если там есть текущая дата, "
                "иначе спросите"
            ),
        ],
        time: Annotated[
            str,
            Field(description="Время в формате ЧЧ:ММ. Если пользователь его не назвал, спросите: не выдумывайте"),
        ],
        fields: Annotated[
            dict[str, Any],
            Field(
                description="Значения полей: имя поля и значение, имена берутся из list_event_types. "
                "Число передавайте числом без единиц: 50, а не «50 г»"
            ),
        ],
        tz: Annotated[
            str,
            Field(
                description="IANA-имя пояса, в котором введено время, например Asia/Almaty. Обязательно: без пояса "
                "время не сохраняется. Пояс пользователя, если не знаете, спросите"
            ),
        ],
        comment: Annotated[str, Field(description="Комментарий, до 500 символов, можно пустой")] = "",
    ) -> CallToolResult:
        return await run_tool(
            ctx,
            lambda api: tools.add_event(
                api, pet_id=pet_id, type=type, date=date, time=time, fields=fields, comment=comment, tz=tz
            ),
            "events:write",
        )

    @server.tool(description=GET_HISTORY, structured_output=False)
    async def get_history(
        ctx: Context,
        pet_id: Annotated[str, Field(description="Номер питомца из list_pets, 24 символа")],
        limit: Annotated[int, Field(description="Сколько записей показать, от 1 до 100, по умолчанию 20")] = (
            tools.HISTORY_LIMIT_DEFAULT
        ),
    ) -> CallToolResult:
        return await run_tool(ctx, lambda api: tools.get_history(api, pet_id=pet_id, limit=limit), "history:read")

    @server.tool(description=GET_MEDICAL_CARD, structured_output=False)
    async def get_medical_card(
        ctx: Context,
        pet_id: Annotated[str, Field(description="Номер питомца из list_pets, 24 символа")],
    ) -> CallToolResult:
        return await run_tool(ctx, lambda api: tools.get_medical_card(api, pet_id=pet_id), "medical:read")

    return server
