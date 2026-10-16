"""Locks a login after too many wrong passwords, from whichever addresses they come.

The per-address limit on sign-in (web/configs.py) stops one machine, not a guesser with several
addresses. So each login also counts its own wrong passwords. The count is kept for a login that
exists and for one that does not, so the answer never says which it is: after FAILURES_ALLOWED wrong
passwords within FAILURE_WINDOW the login is locked for LOCK_FOR, and while it is locked even the
right password gets the answer a wrong one gets. A right password before the lock clears the count.
Nothing lifts a lock by hand: each row carries its end in ``expires_at``, which the TTL index on the
collection (web/db.py) uses to remove it.
"""

from datetime import datetime, timedelta, timezone

import web.app as app

FAILURES_ALLOWED = 10
FAILURE_WINDOW = timedelta(minutes=15)
LOCK_FOR = timedelta(minutes=15)


def login_key(username: str) -> str:
    """The login as the count keeps it: no spaces around it and no capitals, so 'Vera' and 'vera' share a count."""
    return username.strip().lower()


def _utc(moment: datetime) -> datetime:
    """PyMongo returns BSON dates as naive UTC; compare them as UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def is_locked(username: str) -> bool:
    """Whether this login is locked now: its count has reached the limit and the lock has not ended."""
    row = app.db.login_failures.find_one({"_id": login_key(username)})
    if row is None:
        return False
    return row["count"] >= FAILURES_ALLOWED and _utc(row["expires_at"]) > datetime.now(timezone.utc)


def record_failure(username: str) -> None:
    """Count one wrong password. A count whose window or lock is over starts again at one."""
    key = login_key(username)
    now = datetime.now(timezone.utc)
    row = app.db.login_failures.find_one({"_id": key})
    if row is None or _utc(row["expires_at"]) <= now:
        count, expires_at = 1, now + FAILURE_WINDOW
    else:
        count, expires_at = row["count"] + 1, row["expires_at"]
        if count == FAILURES_ALLOWED:
            expires_at = now + LOCK_FOR
    app.db.login_failures.replace_one(
        {"_id": key},
        {"_id": key, "count": count, "expires_at": expires_at},
        upsert=True,
    )


def clear_failures(username: str) -> None:
    """Forget the count for this login: after a right password, and when its account is deleted."""
    app.db.login_failures.delete_one({"_id": login_key(username)})
