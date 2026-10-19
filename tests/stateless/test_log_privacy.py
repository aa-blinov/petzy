"""What the public CI logs and the nginx access log may show.

The diagnostic workflows print the web and nginx logs through a mask() shell function. These tests run
that function, as written in the workflow files, on log lines whose tokens and usernames are invented.
The access log is read from nginx/nginx.conf and from gunicorn.conf.py, the app behind it; nginx's
local copy is checked by test_local_stand_nginx.
"""

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = [
    ROOT / ".github" / "workflows" / "inspect_db.yaml",
    ROOT / ".github" / "workflows" / "server_diagnose.yaml",
]
NGINX = ROOT / "nginx" / "nginx.conf"
GUNICORN = ROOT / "gunicorn.conf.py"

# Invented values, shaped like the real ones. None of them is a secret.
LOG_LINES = "\n".join(
    [
        '203.0.113.7 - - [t] "GET /api/shared/medical-card/FAKE-LINK/pdf HTTP/1.1" 200 1 "-" "UA" 1',
        '203.0.113.7 - - [t] "GET /api/x HTTP/1.1" 200 1 "https://petzy.test/share/medical/FAKE-LINK" "UA" 1',
        '203.0.113.7 - - [t] "GET /api/auth/reset-password?token=FAKE-RESET HTTP/1.1" 200 1 "-" "UA" 1',
        '203.0.113.7 - - [t] "GET /api/x?refresh_token=FAKE-REFRESH&pet_id=PET-1 HTTP/1.1" 200 1 "-" "UA" 1',
        '203.0.113.7 - - [t] "GET /api/x?reset_token=FAKE-RESET2&w=10 HTTP/1.1" 200 1 "-" "UA" 1',
        '203.0.113.7 - - [t] "DELETE /api/pets/PET-1/share/FAKE-USER HTTP/1.1" 200 1 "-" "UA" 1',
        '203.0.113.7 - - [t] "GET /api/users/FAKE-USER/profile HTTP/1.1" 200 1 "-" "UA" 1',
        '203.0.113.7 - - [t] "DELETE /api/pets/PET-1/medical-card/shares/SHARE-1 HTTP/1.1" 200 1 "-" "UA" 1',
        '203.0.113.7 - - [t] "GET /api/x?mytoken=keep-me HTTP/1.1" 200 1 "-" "UA" 1',
        '203.0.113.7 - - [t] "GET /api/token-refresh HTTP/1.1" 200 1 "-" "UA" 1',
        "user=admin mail a.b@example.com",
    ]
)

# Must not survive masking: a rule that stops working shows up here.
SECRETS = ["FAKE-LINK", "FAKE-RESET", "FAKE-REFRESH", "FAKE-USER", "203.0.113.7", "a.b@example.com"]
# Must survive masking: the masks replace what they should and nothing more.
KEPT = [
    "/api/shared/medical-card/*** HTTP/1.1",
    "/share/medical/***",
    "reset-password?token=*** HTTP/1.1",
    "refresh_token=***&pet_id=***",
    "reset_token=***&w=10",
    "/api/pets/PET-1/share/*** HTTP/1.1",
    "/api/users/***/profile HTTP/1.1",
    "/api/pets/PET-1/medical-card/shares/SHARE-1 HTTP/1.1",
    "mytoken=keep-me",
    "/api/token-refresh HTTP/1.1",
    "x.x.x.x",
    "***@***",
    "user=***",
]


def mask_function(path: Path) -> str:
    match = re.search(r"^ *mask\(\) \{\n.*?^ *\}$", path.read_text(encoding="utf-8"), re.S | re.M)
    assert match, f"no mask() in {path.name}"
    return match.group(0)


def mask_problems(function_text: str) -> list[str]:
    out = subprocess.run(
        ["bash", "-c", f"{function_text}\nmask"],
        input=LOG_LINES,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [f"visible after masking: {s}" for s in SECRETS if s in out] + [
        f"missing from the output: {s}" for s in KEPT if s not in out
    ]


def access_log_problems(text: str) -> list[str]:
    fmt = re.search(r"^log_format no_query (.*?);$", text, re.S | re.M)
    if fmt is None:
        return ["log_format no_query is missing"]
    body = fmt.group(1)
    problems = []
    if not body.startswith("'$remote_addr - "):
        problems.append("the client address is no longer the first field (server_diagnose reads field 3)")
    if "$log_path" not in body:
        problems.append("the log does not write $log_path")
    if re.search(r"\$(request|request_uri|uri|http_referer)\b", body):
        problems.append("the log format names $request, $request_uri, $uri or $http_referer")
    if not re.search(r"map \$request_uri \$log_path \{\s*~\^\(\[\^\?\]\*\) \$1;\s*\}", text):
        problems.append("$log_path is not the requested path cut at the query string")
    if "access_log /var/log/nginx/access.log no_query if=$loggable;" not in text:
        problems.append("the access log does not skip the medical card links")
    if not re.search(r"map \$uri \$loggable \{[^}]*~\^/api/shared/\s+0;", text):
        problems.append("/api/shared/ is not excluded from the access log")
    share = re.search(r"location \^~ /share/ \{(.*?)\n    \}", text, re.S)
    if share is None or "access_log off;" not in share.group(1):
        problems.append("/share/ writes to the access log")
    return problems


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_the_workflow_mask_hides_link_tokens_and_usernames(path):
    assert mask_problems(mask_function(path)) == []


def test_both_workflows_carry_the_same_mask():
    assert mask_function(WORKFLOWS[0]) == mask_function(WORKFLOWS[1])


def test_the_access_log_keeps_the_route_without_query_or_referer():
    assert access_log_problems(NGINX.read_text(encoding="utf-8")) == []


def test_the_map_cuts_the_query_and_keeps_the_route():
    found = re.search(r"map \$request_uri \$log_path \{\s*~(\^\(\[\^\?\]\*\)) \$1;", NGINX.read_text(encoding="utf-8"))
    assert found, "map $request_uri $log_path has changed"
    cut = re.compile(found.group(1))
    assert cut.match("/reset-password?token=FAKE-RESET").group(1) == "/reset-password"
    assert cut.match("/api/pets/PET-1?page=2").group(1) == "/api/pets/PET-1"
    assert cut.match("/login").group(1) == "/login"


def gunicorn_format() -> str:
    found = re.search(r"^access_log_format = (.*)$", GUNICORN.read_text(encoding="utf-8"), re.M)
    assert found, "gunicorn.conf.py has no access_log_format"
    return found.group(1)


def test_the_gunicorn_access_log_keeps_the_route_without_query():
    """The app must not undo what nginx does: %(r)s is the whole request line, query and all.

    nginx already writes no_query, so the token in the query has to stop here too, or it lands in
    the container log that the workflows collect.
    """
    fmt = gunicorn_format()
    assert "%(r)s" not in fmt, "the gunicorn access log writes the whole request line, query included"
    assert "%(U)s" in fmt, "the gunicorn access log no longer writes the path alone"
    for field in ("%(m)s", "%(H)s", "%(s)s", "%(b)s", "%(f)s", "%(a)s"):
        assert field in fmt, f"the gunicorn access log lost {field}"
