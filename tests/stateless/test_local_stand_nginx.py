"""The local stand's nginx is the production config plus one storage route, and nothing else.

Production never mounts the local file. This keeps the copy from drifting: if nginx/nginx.conf changes, the local copy
must be regenerated from it, not edited apart. The stand's compose file mounts the copy in place of the production one.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROD = (ROOT / "nginx" / "nginx.conf").read_text(encoding="utf-8")
LOCAL = (ROOT / "nginx" / "local-storage.conf").read_text(encoding="utf-8")
ANCHOR = "    location ^~ /api/ {"


def test_the_local_copy_is_the_production_config_plus_the_storage_route_only():
    assert PROD.count(ANCHOR) == 1
    head, tail = LOCAL.split("    # Local stand only:", 1)
    route, rest = tail.split(ANCHOR, 1)
    assert head + ANCHOR + rest == PROD.replace(ANCHOR, ANCHOR, 1)
    assert "location ^~ /petzy-local/ {" in route
    # The storage signs the Host header, so the route hands on the host the browser used: a second stand on another
    # port then uploads just as the first one does. A fixed port here would break the second stand.
    assert "proxy_set_header Host $http_host;" in route
    assert "localhost:3000" not in route


def test_the_stand_mounts_the_local_copy_and_production_never_does():
    compose = (ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")
    assert "./nginx/local-storage.conf:/etc/nginx/conf.d/default.conf:ro" in compose
    production = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "local-storage.conf" not in production
