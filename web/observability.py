"""Errors, traces, profiles and logs to Sentry, for every process: the API,
the reminder sender and the backup job.

Off unless SENTRY_DSN is set (local runs and tests send nothing). The DSN
comes from the environment, never from this repository: in production the
deploy writes it from the SENTRY_DSN repository secret.

send_default_pii is on (the user and their address are what makes an error
traceable), but what must never leave the server is taken out before an
event is sent: cookies, the Authorization header, and any password or
token in a request body or query string.
"""

import os
import re

# Keys whose values never go to Sentry, wherever they appear in a request.
SECRET_KEYS = {
    "password",
    "current_password",
    "new_password",
    "token",
    "access_token",
    "refresh_token",
    "keys",  # a push subscription's p256dh/auth
    "p256dh",
    "auth",
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}
FILTERED = "[Filtered]"

# A link to a pet's medical card carries its secret in the address (web/medical_share.py): the address of a request, a page or
# a breadcrumb must not take it to Sentry.
_LINK_SECRET = re.compile(r"(/shared/medical-card/|/share/medical/)[^/?#\s]+")


def _scrub_link(value):
    return _LINK_SECRET.sub(lambda m: m.group(1) + FILTERED, value) if isinstance(value, str) else value


def _scrub_value(value):
    if isinstance(value, dict):
        return {k: (FILTERED if str(k).lower() in SECRET_KEYS else _scrub_value(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_value(v) for v in value]
    return value


def _scrub_frames(event) -> None:
    """A crash inside, say, login has the password in a local variable of
    its frame; Sentry sends frame variables."""
    for exception in (event.get("exception") or {}).get("values") or []:
        for frame in (exception.get("stacktrace") or {}).get("frames") or []:
            if isinstance(frame.get("vars"), dict):
                frame["vars"] = _scrub_value(frame["vars"])
    for thread in (event.get("threads") or {}).get("values") or []:
        for frame in (thread.get("stacktrace") or {}).get("frames") or []:
            if isinstance(frame.get("vars"), dict):
                frame["vars"] = _scrub_value(frame["vars"])


def scrub_event(event, _hint=None):
    """before_send / before_send_transaction: drop cookies and secrets."""
    _scrub_frames(event)
    if isinstance(event.get("extra"), dict):
        event["extra"] = _scrub_value(event["extra"])
    for crumb in (event.get("breadcrumbs") or {}).get("values") or []:
        if isinstance(crumb.get("data"), dict):
            crumb["data"] = {k: _scrub_link(v) for k, v in _scrub_value(crumb["data"]).items()}
        if "message" in crumb:
            crumb["message"] = _scrub_link(crumb["message"])
    if "transaction" in event:
        event["transaction"] = _scrub_link(event["transaction"])
    request = event.get("request")
    if isinstance(request, dict):
        if "url" in request:
            request["url"] = _scrub_link(request["url"])
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            request["headers"] = {k: (FILTERED if k.lower() in SECRET_KEYS else v) for k, v in headers.items()}
        if "data" in request:
            request["data"] = _scrub_value(request["data"])
        query = request.get("query_string")
        if isinstance(query, str) and any(f"{key}=" in query.lower() for key in ("token", "password")):
            request["query_string"] = FILTERED
    return event


def init_sentry(component: str) -> bool:
    """Start reporting for this process; True when Sentry is on.

    ``component`` («web», «reminders», «backup») becomes a tag, so one
    project tells the processes apart.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        release=os.getenv("SENTRY_RELEASE") or None,
        send_default_pii=True,
        enable_logs=True,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")),
        profile_session_sample_rate=float(os.getenv("SENTRY_PROFILE_SAMPLE_RATE", "1.0")),
        profile_lifecycle="trace",
        before_send=scrub_event,
        before_send_transaction=scrub_event,
    )
    sentry_sdk.set_tag("component", component)
    return True


def set_user(username) -> None:
    """Tie the current request's events to the signed-in login."""
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - the backup image has no Flask app
        return
    sentry_sdk.set_user({"username": username} if username else None)
