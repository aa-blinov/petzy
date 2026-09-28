"""Request validation failures in words a person can act on.

pydantic reports «String should have at most 100 characters» and the like;
flask-pydantic-spec used to send that list to the client as is, so the app
showed a generic «Не удалось сохранить» and a native client got English.
Every validation failure now answers in the one error shape:

    {"success": false, "code": "validation_error",
     "error": "Слишком длинный текст: не больше 100 символов",
     "details": [{"field": "name", "type": "string_too_long"}]}

`error` is for the person, `details` for code (which field, which rule).
"""

import json
import re

from flask import Response

CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def _plural_chars(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "символов"
    if n % 10 == 1 and n % 100 != 11:
        return "символа"
    return "символов"


def message_for(errors: list) -> str:
    """The first problem, in Russian."""
    if not errors:
        return "Проверьте введённые данные"
    first = errors[0] if isinstance(errors[0], dict) else {}
    kind = str(first.get("type", ""))
    ctx = first.get("ctx") or {}
    msg = str(first.get("msg", ""))

    # Our own validators (schemas.py) already speak Russian.
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, ") :]
    if CYRILLIC.search(msg):
        return msg

    if kind == "string_too_long":
        limit = ctx.get("max_length")
        return f"Слишком длинный текст: не больше {limit} {_plural_chars(limit)}"
    if kind == "string_too_short":
        limit = ctx.get("min_length")
        if limit in (None, 1):
            return "Заполните обязательные поля"
        return f"Слишком короткий текст: не меньше {limit} {_plural_chars(limit)}"
    if kind == "missing":
        return "Заполните обязательные поля"
    if kind == "too_long":
        return "Слишком много значений"
    if kind.startswith(("greater_than", "less_than")):
        bound = next((ctx[k] for k in ("gt", "ge", "lt", "le") if k in ctx), None)
        return f"Число вне допустимых пределов ({bound})" if bound is not None else "Число вне допустимых пределов"
    if kind in ("int_parsing", "int_type", "float_parsing", "float_type", "decimal_parsing", "int_from_float"):
        return "Введите число"
    if kind.startswith(("date", "datetime", "time")):
        return "Проверьте дату и время"
    if kind in ("literal_error", "enum"):
        return "Выберите значение из списка"
    if kind == "string_pattern_mismatch":
        return "Неверный формат значения"
    if kind in ("bool_parsing", "bool_type"):
        return "Неверное значение переключателя"
    return "Проверьте введённые данные"


def details_for(errors: list) -> list:
    out = []
    for e in errors:
        if not isinstance(e, dict):
            continue
        loc = [str(part) for part in (e.get("loc") or ()) if part not in ("body", "query")]
        out.append({"field": ".".join(loc), "type": str(e.get("type", ""))})
    return out


def body_for(errors: list) -> dict:
    return {
        "success": False,
        "error": message_for(errors),
        "code": "validation_error",
        "details": details_for(errors),
    }


def before_request_validation(req, resp: Response, req_validation_error, instance) -> None:
    """flask-pydantic-spec's `before` hook: rewrite its raw error list."""
    if req_validation_error is None or resp is None:
        return
    try:
        errors = json.loads(req_validation_error.json())
    except Exception:
        errors = []
    resp.set_data(json.dumps(body_for(errors), ensure_ascii=False))
    resp.mimetype = "application/json"
