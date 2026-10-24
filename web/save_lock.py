"""A short lock for a save whose duplicate check is «look, then write».

A check like «is this record already there?» followed by an insert lets two identical requests that arrive at the same
instant both pass the check before either has written. Here the request first takes a lock in ``recent_saves``: a row
whose ``_id`` is a hash of what makes the save the same one, inserted with ``insert_one``, so the database lets exactly
one request take it (a second insert is a ``DuplicateKeyError``). The holder runs its check and its write and then
frees the lock. A request that finds the lock held waits for it to be freed and then runs its own check, which now sees
what the holder wrote, so the answer is the one a repeat gets today. Nothing is remembered after the save, so a record
repeated on purpose later is not touched.

A holder that died is not waited for: a lock has a lease, and after it the row is taken over (and the database
drops the row itself a little later, see the TTL index in ``web/db.py``).
"""

import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import request
from pymongo.errors import DuplicateKeyError

import web.app as app
from web.errors import error_response

COLLECTION = "recent_saves"
LEASE = timedelta(seconds=30)
WAIT_SECONDS = 5.0
_POLL_SECONDS = 0.02


def _now() -> datetime:
    """Naive UTC, as the database keeps moments."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _lock_id(parts: tuple) -> str:
    return hashlib.sha256(repr(parts).encode("utf-8")).hexdigest()


def acquire(parts: tuple, wait: float = WAIT_SECONDS) -> "str | None":
    """Take the lock named by ``parts``: a token for ``release``, or None when it stayed held for ``wait`` seconds."""
    rows = app.db[COLLECTION]
    lock_id = _lock_id(parts)
    token = uuid.uuid4().hex
    deadline = time.monotonic() + wait
    while True:
        now = _now()
        try:
            rows.insert_one({"_id": lock_id, "token": token, "expires_at": now + LEASE})
            return token
        except DuplicateKeyError:
            pass
        # A holder that died left its row behind: whoever comes first after the lease takes it over.
        taken = rows.update_one(
            {"_id": lock_id, "expires_at": {"$lte": now}}, {"$set": {"token": token, "expires_at": now + LEASE}}
        )
        if taken.modified_count == 1:
            return token
        if time.monotonic() >= deadline:
            return None
        time.sleep(_POLL_SECONDS)


def release(parts: tuple, token: "str | None") -> None:
    """Free the lock, unless it was taken over from this holder meanwhile."""
    if token is not None:
        app.db[COLLECTION].delete_one({"_id": _lock_id(parts), "token": token})


def single_flight(view):
    """Put this under the route's validation and login: while a request is running, an identical one (same person,
    same path, same body) that arrives at the same instant is told to wait, 409 ``idempotency_in_progress``, instead of
    being run in parallel and saving a second record. A request with an ``Idempotency-Key`` is left to ``@idempotent``,
    and once the first request has finished nothing is held, so a deliberate repeat is a new request."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.headers.get("Idempotency-Key") is not None:
            return view(*args, **kwargs)
        digest = hashlib.sha256(request.get_data(cache=True)).hexdigest()
        parts = ("flight", request.current_user, request.method, request.path, digest)
        token = acquire(parts, wait=0)
        if token is None:
            return error_response("idempotency_in_progress")
        try:
            return view(*args, **kwargs)
        finally:
            release(parts, token)

    return wrapper
