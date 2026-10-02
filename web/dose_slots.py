"""Which of a day's scheduled doses are already handled.

A schedule says «08:00, 20:00». An intake says when it was logged, which is rarely
the same minute. The first version of this counted the day's intakes and treated the
earliest N slots as given, and that broke in three ways: adding an early time to the
schedule turned a dose already given into a «пропущена», a dose given late for the
morning closed the evening slot, and after midnight a dose for yesterday's evening
closed today's morning.

Now an intake belongs to a slot. One logged from the dose widget carries the slot it
was for (``slot_date`` and ``slot_time``), and closes exactly that. One without it
(an older record, a dose marked from the list) closes the nearest slot of its day that
nothing else claims. Skipped intakes close their slot too: it is handled, nothing was given.
"""

from datetime import datetime
from typing import Iterable, Optional

# A slot left open this long after its time is carried over past midnight, so a dose
# forgotten at 23:30 is still offered at 00:10 and not lost with the day.
CARRY_OVER_HOURS = 6

# Two doses of the same course this close are one dose marked twice: asked about, not recorded silently.
DUPLICATE_WINDOW_MINUTES = 30


def minutes_of_day(value: str) -> Optional[int]:
    try:
        hour, minute = value.split(":")
        return int(hour) * 60 + int(minute)
    except (ValueError, AttributeError):
        return None


def intake_day(intake: dict) -> Optional[str]:
    """The day an intake counts for: the day of its slot when it carries one, else the day it was logged."""
    if intake.get("slot_date"):
        return intake["slot_date"]
    moment = intake.get("date_time")
    return moment.strftime("%Y-%m-%d") if isinstance(moment, datetime) else None


def group_by_day(intakes: Iterable[dict]) -> dict:
    """(medication_id, 'YYYY-MM-DD') -> that day's intakes."""
    grouped: dict = {}
    for intake in intakes:
        day = intake_day(intake)
        if day is None:
            continue
        grouped.setdefault((intake.get("medication_id"), day), []).append(intake)
    return grouped


def closed_slots(slot_times: list[str], intakes: list[dict]) -> set[str]:
    """The times (of ``slot_times``) that the day's intakes close."""
    slots = sorted(set(slot_times))
    closed: set[str] = set()
    loose: list[dict] = []
    for intake in intakes:
        explicit = intake.get("slot_time")
        if explicit in slots and explicit not in closed:
            closed.add(explicit)
        else:
            loose.append(intake)
    # What carries no slot, in the order it happened: each closes the nearest slot nobody has.
    for intake in sorted(loose, key=lambda i: i.get("date_time") or datetime.min):
        moment = intake.get("date_time")
        if not isinstance(moment, datetime):
            continue
        at = moment.hour * 60 + moment.minute
        free = [(abs((minutes_of_day(t) or 0) - at), minutes_of_day(t) or 0, t) for t in slots if t not in closed]
        if free:
            closed.add(min(free)[2])
    return closed


def open_slots(slot_times: list[str], intakes: list[dict]) -> list[str]:
    """The day's slots nothing has closed yet, in time order."""
    closed = closed_slots(slot_times, intakes)
    return [t for t in sorted(set(slot_times)) if t not in closed]
