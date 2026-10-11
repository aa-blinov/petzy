"""How the app is served: the docs address, the health check, and what nginx says about itself.

Three things here were wrong at once and none of them raised an error, which is why they need a
check rather than a glance. `/docs` answered 200 with the app itself, because the SPA fallback
catches every path that is not the API: a page that opens and is not the documentation. The health
check answered for `/health/anything`, so a check that passes on nonsense is not a check. And nginx
named its version on every error page it wrote itself.

The redirect is the subtle one. Written the obvious way, `return 301 /api/docs`, nginx builds an
absolute Location from its own scheme, and this nginx sits behind the host's TLS terminator, so it
sends the visitor to http first and back to https afterwards. It also drops the port on the local
stand. The Location has to stay relative.

HTTP only, no browser: these are nginx answers, not things a page renders.
"""

import urllib.error
import urllib.request

from common import BASE, check, summary


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Look at the redirect instead of following it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def ask(path: str, follow: bool = False):
    """Status, headers and a little of the body for one path."""
    opener = urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(BASE + path, timeout=15) as answer:
            return answer.status, dict(answer.headers), answer.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read(400).decode("utf-8", "replace")


def main() -> int:
    status, headers, _ = ask("/docs")
    location = headers.get("Location", "")
    check(
        "/docs redirects rather than answering with the app", status == 301, f"статус {status}, Location {location!r}"
    )
    check(
        "the redirect is relative, so https and the port survive it", location == "/api/docs", f"Location {location!r}"
    )

    if status == 301:
        status, headers, body = ask(location, follow=True)
        check(
            "and it arrives at the reference",
            status == 200 and "Petzy API" in body,
            f"статус {status}, заголовок страницы: {body[body.find('<title>') : body.find('</title>') + 8][:60]!r}",
        )

    # The health check answers for itself and for nothing else. Before the exact match, anything
    # under /health/ answered "healthy" too, which is how a check passes on a path nobody meant.
    health, _, body = ask("/health")
    check("/health answers", health == 200 and "healthy" in body, f"статус {health}")
    junk, _, junk_body = ask("/health/junk")
    check(
        "/health/junk is not healthy",
        "healthy" not in junk_body,
        f"статус {junk}, тело начинается с {junk_body[:30]!r}",
    )

    _, headers, _ = ask("/assets/definitely-not-here.js")
    server = headers.get("Server", "")
    check("nginx does not name its version", "/" not in server, f"Server: {server!r}")

    # The app still answers everywhere it used to: the redirect is one exact path and must not
    # have swallowed the SPA fallback or the static files.
    for path, want in (("/", 200), ("/login", 200), ("/help", 200), ("/assets/definitely-not-here.js", 404)):
        got, _, _ = ask(path)
        check(f"{path} still answers {want}", got == want, f"статус {got}")

    summary("how the app is served")


main()
