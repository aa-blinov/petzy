"""Dockerfile MCP-сервера: не root, без лишних пакетов, слушает все адреса на 8000 и не несёт секретов."""

import re
from pathlib import Path

DOCKERFILE = Path(__file__).resolve().parents[2] / "mcp" / "Dockerfile"


def _text():
    return DOCKERFILE.read_text(encoding="utf-8")


def test_the_container_runs_as_a_user_that_is_not_root():
    users = re.findall(r"^USER\s+(\S+)\s*$", _text(), flags=re.MULTILINE)

    assert users
    assert users[-1] not in ("root", "0")


def test_no_system_packages_are_installed():
    assert "apt-get" not in _text()
    assert "apk add" not in _text()


def test_the_server_listens_on_all_addresses_on_port_8000_and_checks_health_there():
    text = _text()

    assert "EXPOSE 8000" in text
    assert '"--host", "0.0.0.0", "--port", "8000"' in text
    assert "/healthz" in text


def test_no_token_is_written_into_the_image():
    assert "PETZY_TOKEN" not in _text()
