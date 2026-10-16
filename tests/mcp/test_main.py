"""Запуск сервера: что проверяется до старта. Сами серверы в тестах не поднимаются."""

import pytest

from petzy_mcp.__main__ import main

SECRET_LOOKALIKE = "eyJhbGciOiJIUzI1NiJ9.secret.part"


def test_stdio_without_a_personal_token_stops_and_says_which_variable(capsys):
    assert main(["--stdio"], environ={}) == 2

    assert "PETZY_TOKEN" in capsys.readouterr().err


def test_a_token_that_is_not_personal_is_refused_and_never_printed(capsys):
    assert main(["--stdio"], environ={"PETZY_TOKEN": SECRET_LOOKALIKE}) == 2

    captured = capsys.readouterr()
    assert SECRET_LOOKALIKE not in captured.out + captured.err


@pytest.mark.parametrize("url", ["http://petzy.duckdns.org", "ftp://web:5000"])
def test_an_api_address_that_would_send_the_token_in_the_clear_stops_the_server(capsys, url):
    assert main([], environ={"PETZY_API_URL": url}) == 2

    assert "PETZY_API_URL" in capsys.readouterr().err


def test_an_empty_api_address_means_the_default_not_an_error(capsys):
    assert main(["--stdio"], environ={"PETZY_API_URL": ""}) == 2

    captured = capsys.readouterr()
    assert "PETZY_API_URL" not in captured.err
    assert "PETZY_TOKEN" in captured.err
