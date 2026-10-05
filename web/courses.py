"""When a medication course is running: one rule for everyone who asks.

A course has a flag (``is_active``, turned off by «Завершить курс» and on again by «Возобновить курс») and,
optionally, dates (``started_on``, ``ended_on``, both ``YYYY-MM-DD`` of the
owner's calendar). The list, the upcoming doses, the push reminders and the
medical card all read them through here, so a course that ended yesterday
stops being offered, reminded and shown as current in the same moment, and a
course that starts next week isn't reminded about until it does.

A course without dates (every one made before they existed) is bounded by
the flag alone, as it always was. Dates are compared as text, which is
correct for ``YYYY-MM-DD``.

This module imports nothing from the app, so the reminder sender and the
tests can use it freely.
"""

from typing import Optional

ACTIVE = "active"
PLANNED = "planned"
ENDED = "ended"


def _day(value) -> Optional[str]:
    text = str(value)[:10] if value else ""
    return text or None


def course_covers(med: dict, day: str) -> bool:
    """Does the course take in this day (``YYYY-MM-DD``)? The flag is the
    caller's to check (a query does it); this is about the dates."""
    started, ended = _day(med.get("started_on")), _day(med.get("ended_on"))
    if started and day < started:
        return False
    if ended and day > ended:
        return False
    return True


def course_status(med: dict, today: str) -> str:
    """``ended``: switched off, or its end date has passed. ``planned``: still
    to begin. Otherwise ``active``."""
    if med.get("is_active") is False:
        return ENDED
    ended = _day(med.get("ended_on"))
    if ended and ended < today:
        return ENDED
    started = _day(med.get("started_on"))
    if started and started > today:
        return PLANNED
    return ACTIVE
