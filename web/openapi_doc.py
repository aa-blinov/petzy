"""The published API reference: /api/docs (ReDoc) and /api/openapi.json.

flask_pydantic_spec builds the spec from the routes' schemas; this adds
what it can't know: how to sign in from a native app, the error format,
time conventions, multipart uploads, file responses, which endpoints are
public. Both routes sit under /api/, the only path nginx forwards to the
app (its own /apidoc stays local).
"""

import re

from flask import Blueprint, Response, jsonify

from web.app import api, app
from web.security import PAT_SCOPE_ATTR, PERSONAL_TOKEN_PREFIX

docs_bp = Blueprint("docs", __name__)

# Pinned, with the file's hash: the page runs whatever this URL serves.
REDOC_VERSION = "2.5.4"
REDOC_SRI = "sha384-w447zOpYfw/1Tv/5AK9NfHTlQIqE3RVR6KY62jCyy9zNDgO64cMwGGP1Fj0zJVf5"

DESCRIPTION = """
API дневника здоровья питомцев Petzy: питомцы, записи (кормление, вес и другие типы событий), лекарства и приёмы, документы, общий доступ. Этим же API пользуется веб-приложение.

## Адрес и формат

`https://petzy.duckdns.org`, все пути начинаются с `/api/`. Запросы и ответы в JSON (UTF-8). Исключения: загрузка файлов (`multipart/form-data`) и ответы, которые отдают сам файл.

## Вход из нативного приложения

1. `POST /api/auth/login` с `{"username": "...", "password": "..."}`. Запрос без заголовка `Origin` получает в ответе `access_token` (живёт 15 минут) и `refresh_token` (7 дней).
2. В каждом запросе заголовок `Authorization: Bearer <access_token>`.
3. На ответ 401 отправьте `POST /api/auth/refresh` с `{"refresh_token": "..."}` и повторите запрос с новым `access_token`. Ответ содержит и новый `refresh_token`: сохраните его вместо старого. Старый работает ещё 30 секунд (на случай параллельных запросов), а предъявленный позже считается украденным, и вход на этом устройстве отменяется. Если обновление ответило 401, нужно войти заново.
4. Выход: `POST /api/auth/logout` с `{"refresh_token": "..."}`. Он завершает вход на этом устройстве: его refresh-токены и access-токены. Остальные устройства остаются в системе. `{"refresh_token": "...", "everywhere": true}` завершает входы на всех устройствах сразу.

Храните `refresh_token` в защищённом хранилище (Keychain, EncryptedSharedPreferences). Смена или сброс пароля завершают все остальные сессии, их токены перестают работать сразу.

Веб-приложение входит по httpOnly-кукам `access_token` и `refresh_token`. Браузер всегда присылает `Origin`, и refresh-токен в теле ему не отдаётся; `POST /api/auth/refresh` возвращает в теле только `access_token`.

Аккаунт создаётся через `POST /api/auth/register`. Открыта ли регистрация и работает ли почта, скажет `GET /api/auth/registration`.

## Синхронизация с нативным приложением

Приложение может писать офлайн. Записи и правки уходят на сервер очередью, а чтение всей ленты даёт то, что есть на сервере. Так работает синхронизация:

1. **Свой идентификатор записи.** Создавая запись офлайн, отправьте в `POST /api/events` поле `local_id` (до 64 символов, пробелы по краям не считаются). Пока ответа ещё нет, запись можно править и удалять по этому имени: `PUT` и `DELETE /api/events/local/{local_id}`. Имя при правке не меняется.
2. **Повтор безопасен.** Повтор `POST` с тем же `local_id` не создаёт вторую запись. Ответ `200` содержит `id` уже сохранённой записи. Новые значения в повторе не записываются: остаётся первая запись.
3. **Коды, на которые приложение должно реагировать.** `409 local_id_taken`: имя занято записью другого питомца, придумайте новое. `409 record_deleted`: запись уже удалена (на этом или другом устройстве), уберите её из локальной копии и не повторяйте отправку. `404 record_not_found`: записи с таким `id` или именем нет, или она не ваша, это одно и то же.
4. **Время на сервере.** `updated_at` записи ставит сервер, в UTC, до секунды, например `2026-10-18T08:12:33Z`. Сравнивайте значения как текст, часы телефона для сравнения не годятся. `updated_at` меняется при каждом сохранении и при удалении: у надгробия он равен `deleted_at`.
5. **Изменения с момента.** Приложение хранит момент, до которого у него есть всё, и спрашивает `GET /api/events?pet_id=…&since=<момент>&page_size=500`. В ответе записи, изменённые с этого момента (включительно), и надгробия удалённых, от старых изменений к новым. Если ответ содержит `next_cursor`, передайте его как `after` в следующем запросе, пока курсор не станет `null`. Новый момент для следующего `since` берите из наибольшего `updated_at` (или `deleted_at`) полученных записей, и только после того, как ответ разобран. Записи с тем же моментом могут прийти повторно: пропускайте их по `_id`.
6. **Полное чтение и удаления.** Полная лента: `GET /api/events?pet_id=…&with_deleted=1&page_size=500` (или `GET /api/history/timeline` с теми же параметрами), страницы по `next_cursor` через `before`. Удалённая запись сразу уходит из обычных ответов. С `with_deleted=1` и в `since` она приходит как надгробие: `is_deleted: true` и `deleted_at`, и приложение убирает её у себя. Надгробие хранится 30 дней, потом база его удаляет. Если приложение не выходило в сеть дольше 30 дней, пусть прочитает всю ленту без `since` и заменит локальную копию: записи, которых нет в ответе, удалены. Чтение по номеру страницы (`page`) предназначено для экрана веб-приложения.
7. **Конфликт.** Сервер не сливает записи: он отдаёт текущую запись и её `updated_at`. Если запись изменилась на сервере, пока у приложения есть свои несохранённые правки, приложение само сравнивает поля. Поля, которые приложение не меняло, берутся с сервера. Поля, которые поменяли обе стороны, приложение решает сам, например спрашивает человека.

## Картинки

Фото питомца (`photo_url`) и картинки документов (`file_url`) приходят готовыми адресами: абсолютными, с подписью. Такой адрес открывается без заголовков входа, поэтому его можно отдать в `AsyncImage` (SwiftUI) или в `<img>`.

- Адрес выдан конкретному человеку и открывает картинку, только пока у этого человека есть доступ к питомцу. Отозвали доступ или отключили аккаунт, адрес перестаёт работать сразу.
- Адрес меняется раз в час и действует от одного до двух часов. Внутри часа он один и тот же, поэтому картинка берётся из кэша.
- Если адрес отвечает 401 `picture_link_invalid`, обновите список питомцев или документов и возьмите новый адрес.
- Размер меняется параметрами `w` и `h`, как и раньше: подпись от размера не зависит.
- Сканы и PDF адреса не получают. Их открывайте с заголовком `Authorization: Bearer` или с сессией, как раньше.

## Личные доступы

Для скриптов и ассистентов есть долгоживущий доступ, личный токен `ptz_…`. Его делает владелец аккаунта: в веб-приложении, в настройках «Доступ для ассистентов», или `POST /api/me/tokens` со входом по логину. Полный токен показывается один раз.

- Токен передаётся как `Authorization: Bearer ptz_…`. Каждый маршрут, который он открывает, пишет в описании свою область: `pets:read`, `events:write`, `history:read` или `medical:read`. Другая область отвечает 403 `token_scope_missing`.
- Срок от 1 до 365 дней, по умолчанию 90. Не больше 10 действующих доступов на одного человека.
- Отзыв: `DELETE /api/me/tokens/{id}`. Отозванный доступ остаётся в списке, пока его не удалили: повторный `DELETE` по нему убирает запись насовсем, и после этого он отвечает 404 `personal_token_not_found`.
- Доступ не расширяет права владельца: питомец, которого аккаунт не видит, по токену тоже не открывается.
- Больше 120 запросов в минуту с одним токеном не пускают: 429 с `rate_limit_exceeded`. Вход по логину этим ограничением не считается.
- Остальные маршруты отвечают 403 `token_not_allowed`, как бы ни был передан токен. Так устроены смена пароля, выход, удаление аккаунта, управление доступами и администрирование: их можно вызвать только входом по логину.
- Отозванный или истёкший доступ, а также доступ отключённого аккаунта, отвечают 401 `token_invalid`. Смена пароля, сброс по ссылке, сброс администратором и отключение аккаунта отзывают все личные доступы: после включения аккаунта их создают заново. Выход из аккаунта их не трогает.

## Персональные данные

- Регистрация требует `full_name`, `email` (когда `mail_enabled`) и `"privacy_consent": true`: покажите пользователю галочку со ссылками на согласие (`https://petzy.duckdns.org/consent`) и политику (`https://petzy.duckdns.org/privacy`). Без неё ответ 422 `privacy_consent_required`.
- `GET /api/me/account` отвечает `privacy_consent_needed: true`, если человек ещё не согласился с текущей редакцией (аккаунт создан администратором или политика изменилась). Спросите согласие и отправьте `POST /api/me/privacy-consent` с `version` из `GET /api/legal`.
- Удаление аккаунта: `GET /api/me/account/deletion` покажет, какие питомцы удалятся, какие перейдут другим людям и к каким пропадёт доступ. `DELETE /api/me/account` с `{"password": "..."}` удаляет насовсем, все токены перестают работать.

## Ошибки

Тело ошибки: `{"success": false, "error": "текст для человека", "code": "машинный_код"}`. Показывайте пользователю `error`, а решения принимайте по `code`. Ошибка проверки схемы (422, `code: "validation_error"`) добавляет `details`: список `{"field": "comment", "type": "string_too_long"}`, чтобы подсветить нужное поле. Проверки, которые делает сам обработчик (значения полей события, дата вместе со временем), приходят с тем же кодом, но без `details`: причина только в `error`.

| Статус | Значит |
|---|---|
| 401 | нет токена или он истёк |
| 403 | нет прав (например, действие только для владельца питомца) |
| 404 | не найдено, в том числе чужая запись |
| 422 | неверные данные |
| 413 | тело запроса слишком большое. Приложение отвечает так на тело больше 16 МБ, но прокси сервера может остановить уже тело больше 10 МБ, и тогда ответ не JSON |
| 429 | слишком много запросов. Поле `retry_after` и заголовок `Retry-After` дают длину окна ограничения в секундах: повторить можно не позже, чем через столько. У 429 `too_many_pending_uploads` (незавершённые загрузки сканов) их нет |
| 503 | не настроена часть сервиса (почта, хранилище файлов) или письмо не удалось отправить (`mail_send_failed`). Push без ключей VAPID отвечает иначе: 422 `push_not_configured` |

## Даты и время

Дата `YYYY-MM-DD`, время `HH:MM`, вместе `YYYY-MM-DD HH:MM`. Это время на часах того, кто его ввёл: присылайте его так, как видит человек. Записи событий, приёмы лекарств и документы (кроме сканов) принимают ещё `tz`, IANA-имя зоны устройства (`Asia/Almaty`), и хранят его рядом со временем: так приложение и выгрузка показывают время на часах того, кто смотрит. Без `tz`, или с неизвестным именем зоны (его молча отбрасывают), время ни к какой зоне не привязано. Эндпоинты, которым нужно «сегодня», принимают текущие дату и время устройства (`client_date`, `client_datetime`), а медкарта и её записи принимают `tz`. Без них, и при неизвестной зоне, сервер считает по UTC.

## Списки

По страницам (`page` с 1 и `page_size`, в ответе `page`, `page_size` и `total`) отдаются лента событий, история, документы и приёмы лекарств. Остальные списки (питомцы, приглашения, курсы, поиск людей) приходят целиком. Список пользователей у администратора берёт только `page`: страница в 20 аккаунтов, в ответе `per_page`.

## Ограничения

- Вход: 10 неверных паролей в минуту с одного адреса, верный пароль не считается. Регистрация: 5 созданных аккаунтов и 30 попыток в час с одного адреса. Письма подтверждения: не больше 3 на одну почту за сутки, с какого бы адреса ни пришёл запрос.
- Документ файлом до 10 МБ. Сканы и архивы до 500 МБ загружаются прямо в хранилище, см. ниже.
- На владельца питомцев 2 ГБ под документы (сервер может задать другой размер). Начатая загрузка скана занимает место сразу, до подтверждения. У администратора ограничения нет.
- Тело запроса не больше 10 МБ (на этом месте его может остановить прокси сервера): всё, что больше, загружается как скан.

## Сканы и архивы

1. `POST /api/documents/scans` с `{"pet_id", "filename", "size"}` вернёт `upload_url`, `upload_id` и `content_type`.
2. `PUT` файла на `upload_url` с заголовками `Content-Type: <content_type>` и точным `Content-Length`. Ссылка живёт от 15 минут до часа, в зависимости от размера.
3. `POST /api/documents/scans/{upload_id}/complete` с `{"title", "note", "expires_at"}` создаёт документ.

`GET /api/documents/{id}/file` для скана отвечает редиректом 302 на временную ссылку хранилища.

## Общий доступ

`POST /api/pets/{pet_id}/share` отправляет приглашение. Приглашённый видит его в `GET /api/pets/invites` и принимает (`/invite/accept`) или отклоняет (`/invite/decline`). Выйти из чужого питомца: `POST /api/pets/{pet_id}/leave`.

## Уведомления

Напоминания о лекарствах и документах сейчас приходят только как Web Push в браузер (`/api/push/*`, ключи VAPID). Для пушей в нативное приложение (APNs, FCM) серверу нужна доработка.
""".strip()

TAGS = [
    {"name": "auth", "x-displayName": "Вход", "description": "Вход, регистрация, обновление токена, выход"},
    {
        "name": "account",
        "x-displayName": "Аккаунт",
        "description": "Свой аккаунт: почта, пароль, восстановление по почте, удаление, согласие на обработку данных",
    },
    {"name": "pets", "x-displayName": "Питомцы", "description": "Питомцы, фото, общий доступ и приглашения"},
    {
        "name": "events",
        "x-displayName": "Записи",
        "description": "Записи и типы событий (кормление, вес, свои типы), лента, статистика",
    },
    {"name": "stats", "x-displayName": "Графики", "description": "Данные для графиков"},
    {
        "name": "medications",
        "x-displayName": "Лекарства",
        "description": "Курсы лекарств, приёмы, остатки, ближайшие дозы",
    },
    {"name": "documents", "x-displayName": "Документы", "description": "Документы и сканы"},
    {
        "name": "export",
        "x-displayName": "Выгрузка",
        "description": "Выгрузка записей в CSV, TSV, HTML, Markdown или ZIP",
    },
    {
        "name": "medical-records",
        "x-displayName": "Медкарта",
        "description": "Записи, из которых собирается медкарта: прививки, обработки от паразитов, визиты и операции",
    },
    {"name": "push", "x-displayName": "Уведомления", "description": "Подписка браузера на Web Push"},
    {
        "name": "tokens",
        "x-displayName": "Личные доступы",
        "description": "Личные токены для скриптов и ассистентов: создание, список и отзыв",
    },
    {
        "name": "users",
        "x-displayName": "Пользователи",
        "description": "Пользователи: поиск для общего доступа, профиль, настройки форм; управление аккаунтами только для администратора",
    },
]

# No session needed for these. Everything else answers 401 without a token, and
# the spec has to say so: it said so on eight operations out of a hundred, so a
# reader had no way to tell which calls need a token at all.
# Three were missing here and the published spec said the opposite: a vet opens
# a shared card by its link with no account at all, and the reset check is what
# the page behind the emailed link asks.
PUBLIC = {
    ("post", "/api/auth/login"),
    ("post", "/api/auth/register"),
    ("get", "/api/auth/registration"),
    ("post", "/api/auth/refresh"),
    ("post", "/api/auth/logout"),
    ("post", "/api/auth/password/forgot"),
    ("post", "/api/auth/password/reset"),
    ("get", "/api/auth/password/reset/check"),
    ("post", "/api/auth/email/verify"),
    ("post", "/api/auth/password/common"),
    ("get", "/api/legal"),
    ("get", "/api/version"),
    ("get", "/api/shared/medical-card/{token}"),
    ("get", "/api/shared/medical-card/{token}/pdf"),
}

# What a person can ask for before the answer is 429, in the words of the limit. The numbers
# come from the @limiter.limit above each view, and from RATE_LIMIT_CONFIG for the ones that read
# it at run time (sign-up, sign-in and search). Only one operation said so before.
RATE_LIMITS = {
    ("post", "/api/auth/login"): "10 неверных паролей в минуту с одного адреса",
    ("post", "/api/auth/register"): "5 созданных аккаунтов и 30 попыток в час с одного адреса, "
    "и 3 письма подтверждения на одну почту за сутки (`register_letter_limit`)",
    ("post", "/api/auth/password/forgot"): "5 запросов в час с одного адреса",
    ("post", "/api/auth/password/reset"): "20 попыток в час с одного адреса",
    ("get", "/api/auth/password/reset/check"): "30 проверок в час с одного адреса",
    ("post", "/api/auth/email/verify"): "30 проверок в час с одного адреса",
    ("post", "/api/auth/password/common"): "60 проверок пароля в час с одного адреса",
    ("put", "/api/me/email"): "10 в час с одного адреса, и 3 письма подтверждения на одну почту за сутки "
    "(`register_letter_limit`)",
    ("post", "/api/me/email/resend"): "5 в час с одного адреса, и 3 письма подтверждения на одну почту за сутки "
    "(`register_letter_limit`)",
    ("put", "/api/me/password"): "10 в час с одного адреса",
    ("delete", "/api/me/account"): "10 в час с одного адреса",
    ("post", "/api/images/preview"): "120 в час с одного адреса",
    ("get", "/api/shared/medical-card/{token}"): "60 в минуту с одного адреса",
    ("get", "/api/shared/medical-card/{token}/pdf"): "60 в минуту с одного адреса",
    ("get", "/api/users/search"): "30 в минуту на одного пользователя",
}

_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

_BINARY = {"type": "string", "format": "binary"}


def _multipart(properties: dict, required: list) -> dict:
    return {"multipart/form-data": {"schema": {"type": "object", "properties": properties, "required": required}}}


PET_FORM = {
    "name": {"type": "string", "maxLength": 100},
    "species": {"type": "string", "maxLength": 50, "description": "cat, dog, rabbit, ferret, … (как в веб-приложении)"},
    "breed": {"type": "string", "maxLength": 100},
    "birth_date": {"type": "string", "format": "date", "description": "Не в будущем и не раньше чем 50 лет назад"},
    "gender": {"type": "string", "maxLength": 20},
    "is_neutered": {"type": "string", "enum": ["true", "false"]},
    "health_notes": {"type": "string", "maxLength": 1000},
    "tiles_settings": {"type": "string", "description": 'JSON: {"order": [...], "visible": {...}}'},
    "photo_file": {**_BINARY, "description": "Фото: JPEG, PNG, WebP или HEIC. Хранится как WebP до 1920 px"},
}


def finish_spec(spec: dict) -> dict:
    """Complete the generated spec in place (and return it)."""
    spec["info"] = {"title": "Petzy API", "version": "1.0", "description": DESCRIPTION}
    spec["servers"] = [{"url": "https://petzy.duckdns.org", "description": "Рабочий сервер"}]
    spec["tags"] = TAGS
    components = spec.setdefault("components", {})
    components["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": f"access_token из /api/auth/login (нативное приложение), или личный доступ "
            f"`{PERSONAL_TOKEN_PREFIX}…` (раздел «Личные доступы»)",
        },
        "cookieAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "access_token",
            "description": "httpOnly-кука веб-приложения",
        },
    }
    spec["security"] = [{"bearerAuth": []}, {"cookieAuth": []}]

    paths = spec.get("paths", {})
    error_schema = {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}}
    for path, operations in paths.items():
        for method, operation in operations.items():
            if method not in _METHODS:
                continue
            if (method, path) in PUBLIC:
                operation["security"] = []
            else:
                # What a client sees first on every route outside PUBLIC, whether the token was
                # forgotten, expired or stolen.
                operation.setdefault("responses", {}).setdefault(
                    "401", {"description": "Нет токена или он истёк", **error_schema}
                )
            limit = RATE_LIMITS.get((method, path))
            if limit:
                operation.setdefault("responses", {}).setdefault(
                    "429", {"description": f"Ограничение: {limit}", **error_schema}
                )

    def op(method: str, path: str) -> dict:
        return paths.get(path, {}).get(method, {})

    # Uploads are multipart (the JSON form of these two stays documented too).
    documents = op("post", "/api/documents")
    if documents:
        documents["requestBody"] = {
            "required": True,
            "content": _multipart(
                {
                    "pet_id": {"type": "string"},
                    "category": {"type": "string", "description": "Категория (vaccination, lab_result, …)"},
                    "title": {"type": "string", "maxLength": 100},
                    "note": {"type": "string", "maxLength": 500},
                    "expires_at": {"type": "string", "format": "date"},
                    "tz": {"type": "string", "description": "IANA-зона устройства (Asia/Almaty)"},
                    "upload_id": {"type": "string", "description": "32 hex: по нему загрузку можно отменить"},
                    "file": {**_BINARY, "description": "JPEG, PNG, WebP, HEIC/HEIF или PDF, до 10 МБ"},
                },
                ["pet_id", "category", "title", "file"],
            ),
        }
    for method, required, extra in (
        ("post", ["name"], {}),
        ("put", [], {"remove_photo": {"type": "string", "enum": ["true"], "description": "Удалить текущее фото"}}),
    ):
        path = "/api/pets" if method == "post" else "/api/pets/{pet_id}"
        pets = op(method, path)
        if pets and "requestBody" in pets:
            pets["requestBody"]["content"].update(_multipart({**PET_FORM, **extra}, required))

    # A native app has no cookie: it signs out with its refresh token in the body. The web app sends nothing,
    # so the body stays optional and is not a pydantic model (that would refuse the empty request).
    logout = op("post", "/api/auth/logout")
    if logout:
        logout["requestBody"] = {
            "required": False,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "refresh_token": {
                                "type": "string",
                                "description": "Нативное приложение: refresh_token этого устройства. Веб-приложение тело не шлёт",
                            },
                            "everywhere": {
                                "type": "boolean",
                                "description": "true: завершить входы на всех устройствах, а не только на этом",
                            },
                        },
                    },
                    "example": {"refresh_token": "eyJhbGciOiJIUzI1NiIs..."},
                }
            },
        }
    replace_file = op("put", "/api/documents/{id}/file")
    if replace_file:
        replace_file["requestBody"] = {
            "required": True,
            "content": _multipart(
                {
                    "file": {
                        **_BINARY,
                        "description": "JPEG, PNG, WebP, HEIC или PDF, до 10 МБ; проверяется как при создании",
                    }
                },
                ["file"],
            ),
        }

    # Endpoints that answer with the file itself.
    photo = op("get", "/api/pets/{pet_id}/photo")
    if photo:
        photo["responses"]["200"] = {
            "description": "Фото (WebP; у старых JPEG, PNG или GIF). ?w= и ?h= дают уменьшенную копию",
            "content": {
                "image/webp": {"schema": _BINARY},
                "image/jpeg": {"schema": _BINARY},
                "image/png": {"schema": _BINARY},
                "image/gif": {"schema": _BINARY},
                "application/octet-stream": {"schema": _BINARY},
            },
        }
    document_file = op("get", "/api/documents/{id}/file")
    if document_file:
        document_file["responses"]["200"] = {
            "description": "Файл документа",
            "content": {
                "image/webp": {"schema": _BINARY},
                "image/jpeg": {"schema": _BINARY},
                "image/png": {"schema": _BINARY},
                "image/heic": {"schema": _BINARY},
                "image/heif": {"schema": _BINARY},
                "application/pdf": {"schema": _BINARY},
            },
        }
        document_file["responses"]["302"] = {"description": "Скан: редирект на временную ссылку хранилища"}
    for path in ("/api/pets/{pet_id}/medical-card/pdf", "/api/shared/medical-card/{token}/pdf"):
        pdf = op("get", path)
        if pdf:
            pdf["responses"]["200"] = {
                "description": "Медкарта одним файлом PDF",
                "content": {"application/pdf": {"schema": _BINARY}},
            }
    export = op("get", "/api/export/{export_type}/{format_type}")
    if export:
        export["responses"]["200"] = {
            "description": "Файл выгрузки; export_type=all и любой формат дают ZIP",
            "content": {
                "text/csv": {"schema": _BINARY},
                "text/tab-separated-values": {"schema": _BINARY},
                "text/html": {"schema": _BINARY},
                "text/markdown": {"schema": _BINARY},
                "application/zip": {"schema": _BINARY},
            },
        }
    # The picture a browser cannot draw, made drawable. Nothing here is a pydantic model: the file comes from the
    # form and the answer is the file, so the generator leaves the route out and it is written in by hand.
    preview = op("post", "/api/images/preview")
    if not preview:
        paths["/api/images/preview"] = {"post": {}}
        preview = paths["/api/images/preview"]["post"]
    preview["tags"] = ["documents"]
    preview["operationId"] = "previewImage"
    preview["summary"] = "A picture the browser cannot draw, as WebP, without storing it."
    preview["description"] = (
        "Фото, которое браузер не рисует (HEIC с телефона: Safari показывает, Chrome нет), приходит сюда "
        "и уходит картинкой WebP до 1600 px, которую уже видно в форме. Ничего не сохраняется: при "
        "сохранении формы отправляется исходный файл, и тогда он переводится на сервере. PDF не принимается. "
        "Ограничение 120 запросов в час с одного адреса; тело больше 16 МБ останавливается на 413."
    )
    preview["parameters"] = []
    preview["requestBody"] = {
        "required": True,
        "content": _multipart(
            {"file": {**_BINARY, "description": "JPEG, PNG, WebP, HEIC или HEIF, до 10 МБ"}},
            ["file"],
        ),
    }
    preview["responses"] = {
        "200": {"description": "Картинка WebP до 1600 px", "content": {"image/webp": {"schema": _BINARY}}},
        "401": {
            "description": "Нет токена",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
        },
        "422": {
            "description": "Файл не подходит: нет поля file, тип не тот, не тот формат или слишком большой",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
        },
        "429": {
            "description": "Ограничение: 120 запросов в час с одного адреса",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
        },
    }

    # A personal access token reaches only the operations that name it (pat_allowed in the views). Each one
    # says which scope opens it.
    for (method, path), scope in _personal_token_operations().items():
        operation = op(method, path)
        if operation:
            operation["description"] = (
                operation.get("description", "")
                + f" A personal access token with the `{scope}` scope opens it; another scope answers 403 "
                "`token_scope_missing`."
            )
            operation.setdefault("responses", {}).setdefault(
                "429", {"description": "Ограничение: 120 запросов в минуту на один личный доступ", **error_schema}
            )

    _say_what_errors_mean(paths, op, error_schema)
    _name_the_params_views_read(op, error_schema)
    return spec


def _personal_token_operations() -> dict:
    """``{(method, path): scope}`` for every operation a personal access token may call: the views marked pat_allowed."""
    found = {}
    for rule in app.url_map.iter_rules():
        scope = getattr(app.view_functions.get(rule.endpoint), PAT_SCOPE_ATTR, None)
        if scope is None:
            continue
        path = re.sub(r"<(?:[^:>]+:)?([^>]+)>", r"{\1}", rule.rule)
        for method in {m.lower() for m in rule.methods} & set(_METHODS):
            found[(method, path)] = scope
    return found


def _param(name: str, where: str, schema: dict, description: str, required: bool = False) -> dict:
    return {"name": name, "in": where, "required": required, "schema": schema, "description": description}


def _name_the_params_views_read(op, error_schema: dict) -> None:
    """Query values a view reads itself, outside a pydantic model, so the generator never saw them."""
    adds = {
        ("get", "/api/auth/password/reset/check"): [
            _param("token", "query", {"type": "string"}, "Токен из ссылки в письме")
        ],
        ("get", "/api/users"): [
            _param("q", "query", {"type": "string"}, "Часть логина или имени, без учёта регистра"),
            _param(
                "page",
                "query",
                {"type": "integer", "default": 1},
                "Страница, по 20 аккаунтов; неверное значение читается как 1",
            ),
        ],
        ("get", "/api/users/search"): [
            _param("q", "query", {"type": "string"}, "Начало логина или логин целиком; короче 2 знаков: пустой список")
        ],
        ("delete", "/api/event-types/{key}"): [
            _param(
                "preview",
                "query",
                {"type": "boolean"},
                "Только посчитать записи типа, ничего не удаляя (true, 1, yes или on)",
            ),
            _param(
                "with_events",
                "query",
                {"type": "boolean"},
                "Удалить тип вместе со всеми его записями (true, 1, yes или on)",
            ),
        ],
        ("get", "/api/medical-records/{id}"): [
            _param("tz", "query", {"type": "string"}, "IANA-зона устройства: по ней считается «сегодня» для статуса")
        ],
    }
    for (method, path), params in adds.items():
        operation = op(method, path)
        if operation:
            known = {x.get("name") for x in operation.get("parameters", [])}
            operation.setdefault("parameters", []).extend(x for x in params if x["name"] not in known)

    export = op("get", "/api/export/{export_type}/{format_type}")
    for parameter in export.get("parameters", []) if export else []:
        if parameter.get("name") == "export_type":
            parameter["description"] = "Ключ типа события, medications или all (все типы одним ZIP)"
        elif parameter.get("name") == "format_type":
            parameter["schema"] = {"type": "string", "enum": ["csv", "tsv", "html", "md"]}

    for path in ("/api/pets/{pet_id}/medical-card/pdf", "/api/shared/medical-card/{token}/pdf"):
        if op("get", path):
            op("get", path)["responses"]["500"] = {
                "description": "Не удалось собрать PDF (`internal_error`)",
                **error_schema,
            }
    for path, what in (
        ("/api/pets/{pet_id}/medical-profile", "profile"),
        ("/api/pets/{pet_id}/visit-prep", "visit_prep"),
        ("/api/pets/{pet_id}/look", "look"),
    ):
        operation = op("put", path)
        if operation and "409" in operation.get("responses", {}):
            operation["responses"]["409"] = {
                "description": f"Сохранение сделано со старой копии: `base_version` не совпал. В ответе `{what}` как он есть сейчас",
                **error_schema,
            }


# Operations with nothing to validate: no body, no query, no path value the schema checks. The generator still
# promised them a 422, which never comes.
NOTHING_TO_VALIDATE = {
    ("get", "/api/auth/check-admin"),
    ("get", "/api/auth/registration"),
    ("get", "/api/auth/session"),
    ("get", "/api/me/account"),
    ("get", "/api/me/account/deletion"),
    ("get", "/api/legal"),
    ("get", "/api/version"),
    ("get", "/api/event-types"),
    ("get", "/api/vaccines/catalog"),
    ("get", "/api/pets"),
    ("get", "/api/me/tokens"),
    ("delete", "/api/me/tokens/{token_id}"),
    ("get", "/api/pets/invites"),
    ("get", "/api/users/search"),
    ("get", "/api/users/{username}/profile"),
    ("post", "/api/pets/{pet_id}/invite/accept"),
    ("post", "/api/pets/{pet_id}/invite/decline"),
    ("post", "/api/pets/{pet_id}/leave"),
    ("post", "/api/auth/logout"),
    ("get", "/api/auth/password/reset/check"),
    ("get", "/api/users"),
    ("get", "/api/users/{username}"),
    ("post", "/api/documents/uploads/{upload_id}/cancel"),
    ("get", "/api/documents/storage"),
}

# Bodies above 16 MB stop at the server before the view (MAX_CONTENT_LENGTH): 413, not the view's own 422.
TOO_LARGE = {
    ("post", "/api/documents"),
    ("put", "/api/documents/{id}/file"),
    ("post", "/api/pets"),
    ("put", "/api/pets/{pet_id}"),
    ("post", "/api/images/preview"),
}

# Where a file is written to or read from object storage, which a deploy may leave unconfigured.
NEEDS_STORAGE = {
    ("post", "/api/documents"),
    ("put", "/api/documents/{id}/file"),
    ("get", "/api/documents/{id}/file"),
    ("post", "/api/documents/scans/{upload_id}/complete"),
    ("post", "/api/pets"),
    ("put", "/api/pets/{pet_id}"),
}


def _say_what_errors_mean(paths: dict, op, error_schema: dict) -> None:
    """Replace the generator's bare status names with what the error means here, and add the ones it cannot see."""

    def answer(text: str) -> dict:
        return {"description": text, **error_schema}

    for path, operations in paths.items():
        for method, operation in operations.items():
            if method not in _METHODS:
                continue
            responses = operation.setdefault("responses", {})
            key = (method, path)
            if key in NOTHING_TO_VALIDATE:
                responses.pop("422", None)
            elif key == ("post", "/api/me/email/resend"):
                responses["422"] = answer("Нет новой почты, ждущей подтверждения (`account_no_pending_email`)")
            elif responses.get("422", {}).get("description") in ("Validation Error", "Unprocessable Entity"):
                responses["422"] = answer(
                    "Неверные данные. `code` называет причину; ошибка проверки схемы (`validation_error`) "
                    "добавляет `details` с полями"
                )
            if responses.get("404", {}).get("description") == "Not Found":
                if path.startswith("/api/users"):
                    text = "Нет такого пользователя (`user_not_found`)"
                elif path.startswith("/api/shared/"):
                    text = "Ссылки нет: неверная, истекла или отозвана (`not_found`)"
                elif path.startswith("/api/me/tokens"):
                    text = "Доступа нет, или он не ваш (`personal_token_not_found`)"
                elif path.startswith("/api/event-types/"):
                    text = (
                        "Такого типа нет среди встроенных и типов вашего круга, людей, с которыми у вас общий питомец "
                        "(`event_type_not_found`)"
                    )
                else:
                    text = (
                        "Питомца или записи нет, или к ним нет доступа: чужое отвечает так же, как несуществующее "
                        "(`pet_not_found`, `record_not_found` и подобные)"
                    )
                responses["404"] = answer(text)
            if responses.get("403", {}).get("description") == "Forbidden":
                if path.startswith("/api/users"):
                    text = "Только для администратора (`forbidden_admin_only`): это встроенный аккаунт ADMIN_USERNAME"
                elif path == "/api/auth/register":
                    text = "Регистрация закрыта (`registration_closed`)"
                elif path.startswith("/api/event-types/") and method == "delete":
                    text = "Чужой тип удалить нельзя (`event_type_not_yours`)"
                elif path.startswith("/api/event-types/"):
                    text = (
                        "Встроенный тип меняет только администратор (`event_type_builtin_admin_only`), "
                        "чужой тип менять нельзя (`event_type_not_yours`)"
                    )
                else:
                    text = "Только для владельца питомца (`owner_action_forbidden`)"
                responses["403"] = answer(text)
            if responses.get("401", {}).get("description") == "Unauthorized":
                responses["401"] = answer("Нет токена или он истёк")
            if key == ("delete", "/api/me/account") and "500" in responses:
                responses["500"] = answer(
                    "Не удалось удалить (`account_delete_failed`): аккаунт остался, часть данных могла уже уйти, повторите позже"
                )
            elif responses.get("500", {}).get("description") == "Internal Server Error":
                responses["500"] = answer("Сбой на сервере (`internal_error`), повторите позже")
            if key == ("delete", "/api/pets/{pet_id}") and "503" in responses:
                responses["503"] = answer(
                    "Не удалось удалить (`pet_delete_failed`): питомец остался, повторите удаление"
                )
            if responses.get("503", {}).get("description") == "Service Unavailable":
                if path.startswith(("/api/me/email", "/api/auth")):
                    responses["503"] = answer(
                        "Почта не настроена (`mail_not_configured`) или письмо не удалось отправить (`mail_send_failed`)"
                    )
                else:
                    responses["503"] = answer("Хранилище файлов не настроено (`storage_not_configured`)")
            if key in TOO_LARGE:
                responses["413"] = answer(
                    "Тело слишком большое: больше 16 МБ (`request_too_large`), а прокси сервера может остановить его уже после 10 МБ"
                )
            if key in NEEDS_STORAGE:
                responses.setdefault("503", answer("Хранилище файлов не настроено (`storage_not_configured`)"))

    for path, text in (
        ("/api/auth/login", "Неверный логин или пароль, или аккаунт отключён"),
        ("/api/auth/refresh", "refresh-токен недействителен, истёк или отозван: войдите заново"),
        ("/api/auth/session", "Сессии нет: и access-, и refresh-токен недействительны"),
    ):
        method = "get" if path.endswith("session") else "post"
        if "401" in op(method, path).get("responses", {}):
            op(method, path)["responses"]["401"] = answer(text)

    # Files sent with an ETag: a repeated request with If-None-Match gets an empty 304.
    for path in ("/api/pets/{pet_id}/photo", "/api/documents/{id}/file"):
        if op("get", path):
            op("get", path)["responses"]["304"] = {"description": "Файл не изменился (совпал If-None-Match)"}
            op("get", path)["responses"]["404"] = answer(
                "Питомца, документа или файла нет, к ним нет доступа, или сохранённый файл не удалось прочитать "
                "(`upload_error`)"
            )

    duplicate = op("post", "/api/events")
    if duplicate:
        duplicate["responses"]["409"] = answer(
            "Тот же человек прислал ту же запись (питомец, тип, время до минуты, поля и комментарий) в течение "
            "5 минут (`duplicate_event`). В ответе `existing`: `id`, `date`, `time`, `username`, `own`. С `local_id`, занятым другой записью: 409 `local_id_taken`"
        )
        duplicate["responses"]["200"] = answer(
            "Запись с этим `local_id` уже сохранена этим питомцем с тем же типом: отдаётся она (`id`), новая не пишется"
        )
    scans = op("post", "/api/documents/scans")
    if scans:
        scans["responses"]["429"] = answer(
            "Уже 3 незавершённые загрузки, начатые за последний час (`too_many_pending_uploads`): дождитесь их"
        )
    intake = op("post", "/api/medications/{id}/log")
    if intake:
        intake["responses"]["409"] = answer(
            "Приём уже отмечен (`duplicate_intake`, в ответе `existing`; повторите с `force: true`, чтобы записать "
            "всё равно), или остаток не удалось списать с трёх попыток (`conflict`)"
        )


@docs_bp.route("/api/openapi.json", methods=["GET"])
def openapi_json():
    """The OpenAPI 3.1 document, for code generators and Postman."""
    return jsonify(api.spec)


REDOC_PAGE = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Petzy API</title>
  <style>body {{ margin: 0; padding: 0; }}</style>
</head>
<body>
  <redoc spec-url="/api/openapi.json" hide-download-button="false" required-props-first="true"></redoc>
  <script src="https://cdn.jsdelivr.net/npm/redoc@{REDOC_VERSION}/bundles/redoc.standalone.js"
          integrity="{REDOC_SRI}" crossorigin="anonymous"></script>
</body>
</html>"""

# The API's own CSP (sandbox, nothing loads) would leave this page blank:
# it needs ReDoc's script and its inline styles and workers.
REDOC_CSP = (
    "default-src 'none'; script-src https://cdn.jsdelivr.net; style-src 'unsafe-inline'; "
    "img-src 'self' data: https://cdn.redoc.ly; connect-src 'self'; worker-src blob:; font-src data:; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)


@docs_bp.route("/api/docs", methods=["GET"])
def redoc():
    """Human-readable reference (ReDoc) over /api/openapi.json."""
    response = Response(REDOC_PAGE, mimetype="text/html")
    response.headers["Content-Security-Policy"] = REDOC_CSP
    response.headers["Cache-Control"] = "no-cache"
    return response
