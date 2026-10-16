"""The mcp service in docker-compose.yml: reached only through nginx, and holding no secrets.

A published port would let the MCP server answer around nginx. An env_file would hand it the app's secrets, which a
request from an assistant has no use for. The file is read as text: CI installs no YAML parser for these tests.
"""

import re
from pathlib import Path

COMPOSE = (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text(encoding="utf-8")


def _block(name):
    """The lines of one service: from its key to the first line that is not indented under it."""
    lines = COMPOSE.splitlines()
    start = lines.index(f"  {name}:")
    body = []
    for line in lines[start + 1 :]:
        if line and not line.startswith("    "):
            break
        body.append(line)
    return "\n".join(body)


def test_the_service_publishes_no_port_on_the_host():
    assert "ports:" not in _block("mcp")


def test_it_takes_no_env_file_and_only_the_address_of_the_app():
    block = _block("mcp")

    assert "env_file" not in block
    assert re.findall(r"- ([A-Z_]+)=", block) == ["PETZY_API_URL"]


def test_the_address_names_the_port_the_app_listens_on():
    web_port = re.search(r'"[\d.]+:\d+:(\d+)"', _block("web")).group(1)

    assert f"- PETZY_API_URL=http://web:{web_port}" in _block("mcp")


def test_it_is_built_from_its_folder_restarts_with_the_rest_and_waits_for_the_app():
    block = _block("mcp")

    assert "build: ./mcp" in block
    assert "restart: unless-stopped" in block
    assert "    depends_on:\n      - web" in block
    assert "logging: *default-logging" in block
