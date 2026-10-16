"""The /mcp route in nginx: passed on as it comes, reached by the service's name, and in front of the single-page fallback.

Buffering would hold an answer until a buffer fills, and a route below the fallback would hand the request to the app's
index.html. The access log must not write request headers, where the token travels. The stand's copy is compared with
the production file by test_local_stand_nginx.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROD = (ROOT / "nginx" / "nginx.conf").read_text(encoding="utf-8")
LOCAL = (ROOT / "nginx" / "local-storage.conf").read_text(encoding="utf-8")


def route(text):
    """The /mcp location, from its first line to the closing brace at the location's own indent."""
    found = re.search(r"^    location \^~ /mcp \{\n(.*?)^    \}$", text, re.S | re.M)
    assert found, "nginx has no location ^~ /mcp"
    return found.group(1)


def test_the_answer_is_passed_on_as_it_comes_and_not_cached():
    body = route(PROD)

    for directive in (
        "proxy_buffering off;",
        "proxy_cache off;",
        "proxy_read_timeout 600s;",
        "proxy_http_version 1.1;",
    ):
        assert directive in body, directive


def test_the_service_is_reached_by_name_per_request_so_nginx_starts_without_it():
    body = route(PROD)

    assert "set $mcp http://mcp:8000;" in body
    assert "proxy_pass $mcp;" in body
    assert "proxy_set_header Host $host;" in body
    assert "proxy_set_header X-Forwarded-Proto $forwarded_proto;" in body


def test_the_route_comes_before_the_single_page_fallback_and_is_not_a_file_location():
    assert PROD.index("    location ^~ /mcp {") < PROD.index("    location / {")
    body = route(PROD)

    assert "try_files" not in body
    assert "root " not in body


def test_the_access_log_is_the_api_one_and_writes_no_request_header():
    assert "access_log" not in route(PROD)
    fmt = re.search(r"^log_format no_query (.*?);$", PROD, re.S | re.M)
    assert fmt is not None
    assert re.findall(r"\$http_\w+", fmt.group(1)) == ["$http_user_agent"]


def test_the_stand_has_the_same_route():
    assert route(LOCAL) == route(PROD)
