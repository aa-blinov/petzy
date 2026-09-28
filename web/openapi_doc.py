"""The published API reference: /api/docs (ReDoc) and /api/openapi.json.

flask_pydantic_spec builds the spec from the routes' schemas; this adds
what it can't know: how to sign in from a native app, the error format,
time conventions, multipart uploads, file responses, which endpoints are
public. Both routes sit under /api/, the only path nginx forwards to the
app (its own /apidoc stays local).
"""

from flask import Blueprint, Response, jsonify

from web.app import api

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
4. Выход: `POST /api/auth/logout` с `{"refresh_token": "..."}`. Он завершает все сессии пользователя.

Храните `refresh_token` в защищённом хранилище (Keychain, EncryptedSharedPreferences). Смена или сброс пароля завершают все остальные сессии, их токены перестают работать сразу.

Веб-приложение входит по httpOnly-кукам `access_token` и `refresh_token`. Браузер всегда присылает `Origin`, и токены в теле ответа ему не отдаются.

Аккаунт создаётся через `POST /api/auth/register`. Открыта ли регистрация и работает ли почта, скажет `GET /api/auth/registration`.

## Персональные данные

- Регистрация требует `full_name`, `email` (когда `mail_enabled`) и `"privacy_consent": true`: покажите пользователю галочку со ссылками на согласие (`https://petzy.duckdns.org/consent`) и политику (`https://petzy.duckdns.org/privacy`). Без неё ответ 422 `privacy_consent_required`.
- `GET /api/me/account` отвечает `privacy_consent_needed: true`, если человек ещё не согласился с текущей редакцией (аккаунт создан администратором или политика изменилась). Спросите согласие и отправьте `POST /api/me/privacy-consent` с `version` из `GET /api/legal`.
- Удаление аккаунта: `GET /api/me/account/deletion` покажет, какие питомцы удалятся, какие перейдут другим людям и к каким пропадёт доступ. `DELETE /api/me/account` с `{"password": "..."}` удаляет насовсем, все токены перестают работать.

## Ошибки

Тело ошибки: `{"success": false, "error": "текст для человека", "code": "машинный_код"}`. Показывайте пользователю `error`, а решения принимайте по `code`. Ошибка проверки данных (422, `code: "validation_error"`) приходит в том же виде и добавляет `details`: список `{"field": "comment", "type": "string_too_long"}`, чтобы подсветить нужное поле.

| Статус | Значит |
|---|---|
| 401 | нет токена или он истёк |
| 403 | нет прав (например, действие только для владельца питомца) |
| 404 | не найдено, в том числе чужая запись |
| 422 | неверные данные |
| 429 | слишком много запросов, повторите позже |
| 503 | не настроена часть сервиса (почта, хранилище файлов) |

## Даты и время

Дата `YYYY-MM-DD`, время `HH:MM`, вместе `YYYY-MM-DD HH:MM`. Это местное время пользователя: часовой пояс не передаётся и не хранится, присылайте время так, как его видит человек. Эндпоинты, которым нужно «сегодня», принимают текущие дату и время устройства (`client_date`, `client_datetime`). Без них сервер считает по UTC.

## Списки

Параметры `page` (с 1) и `page_size`. В ответе `page`, `page_size` и `total`.

## Ограничения

- Вход: 5 попыток в минуту с одного адреса. Регистрация: 5 аккаунтов в час.
- Документ файлом до 10 МБ. Сканы и архивы до 500 МБ загружаются прямо в хранилище, см. ниже.
- На владельца питомцев 2 ГБ под документы.

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
    {"name": "push", "x-displayName": "Уведомления", "description": "Подписка браузера на Web Push"},
    {
        "name": "users",
        "x-displayName": "Пользователи",
        "description": "Пользователи: поиск для общего доступа, профиль, настройки форм; управление аккаунтами только для администратора",
    },
]

# No session needed for these.
PUBLIC = {
    ("post", "/api/auth/login"),
    ("post", "/api/auth/register"),
    ("get", "/api/auth/registration"),
    ("post", "/api/auth/refresh"),
    ("post", "/api/auth/logout"),
    ("post", "/api/auth/password/forgot"),
    ("post", "/api/auth/password/reset"),
    ("post", "/api/auth/email/verify"),
    ("get", "/api/legal"),
}

_BINARY = {"type": "string", "format": "binary"}


def _multipart(properties: dict, required: list) -> dict:
    return {"multipart/form-data": {"schema": {"type": "object", "properties": properties, "required": required}}}


PET_FORM = {
    "name": {"type": "string", "maxLength": 100},
    "species": {"type": "string", "description": "cat, dog, rabbit, ferret, … (как в веб-приложении)"},
    "breed": {"type": "string"},
    "birth_date": {"type": "string", "format": "date"},
    "gender": {"type": "string"},
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
            "description": "access_token из /api/auth/login (нативное приложение)",
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
    for path, operations in paths.items():
        for method, operation in operations.items():
            if (method, path) in PUBLIC:
                operation["security"] = []

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
                    "file": {**_BINARY, "description": "JPEG, PNG, WebP, HEIC или PDF, до 10 МБ"},
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

    # Endpoints that answer with the file itself.
    photo = op("get", "/api/pets/{pet_id}/photo")
    if photo:
        photo["responses"]["200"] = {
            "description": "Фото (WebP). ?w= и ?h= дают уменьшенную копию",
            "content": {"image/webp": {"schema": _BINARY}},
        }
    document_file = op("get", "/api/documents/{id}/file")
    if document_file:
        document_file["responses"]["200"] = {
            "description": "Файл документа",
            "content": {
                "image/webp": {"schema": _BINARY},
                "image/jpeg": {"schema": _BINARY},
                "application/pdf": {"schema": _BINARY},
            },
        }
        document_file["responses"]["302"] = {"description": "Скан: редирект на временную ссылку хранилища"}
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
    return spec


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
