"""Запуск MCP-сервера Petzy.

python -m petzy_mcp              HTTP на /mcp, адрес и порт из --host и --port (по умолчанию 127.0.0.1:8000)
python -m petzy_mcp --stdio      через stdin и stdout, личный доступ из PETZY_TOKEN

Адрес API берётся из PETZY_API_URL (по умолчанию https://petzy.duckdns.org). Значение токена нигде не печатается.
"""

import argparse
import os
import sys
from collections.abc import Mapping, Sequence

import uvicorn

from .auth import is_token
from .client import DEFAULT_API_URL, checked_api_url
from .http_app import create_app
from .server import build_server

ENV_API_URL = "PETZY_API_URL"
ENV_TOKEN = "PETZY_TOKEN"


def main(argv: Sequence[str] | None = None, environ: Mapping[str, str] | None = None) -> int:
    args = _parser().parse_args(argv)
    env = os.environ if environ is None else environ
    try:
        api_url = checked_api_url(env.get(ENV_API_URL) or DEFAULT_API_URL)
    except ValueError as problem:
        print(f"{ENV_API_URL}: {problem}", file=sys.stderr)
        return 2
    if args.stdio:
        token = env.get(ENV_TOKEN, "")
        if not is_token(token):
            print(f"{ENV_TOKEN}: задайте личный доступ Petzy, он начинается с ptz_", file=sys.stderr)
            return 2
        build_server(api_url, stdio_token=token).run("stdio")
        return 0
    uvicorn.run(create_app(api_url), host=args.host, port=args.port, log_level="info")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m petzy_mcp",
        description="MCP-сервер Petzy: дневник питомца для ассистентов.",
    )
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="работать через stdin и stdout, личный доступ берётся из PETZY_TOKEN",
    )
    parser.add_argument("--host", default="127.0.0.1", help="адрес для HTTP, по умолчанию только этот компьютер")
    parser.add_argument("--port", type=int, default=8000, help="порт для HTTP")
    return parser


if __name__ == "__main__":
    sys.exit(main())
