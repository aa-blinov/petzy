"""Flags a newly-logged numeric reading that looks abnormal for a pet —
compared to that pet's own recent history for the same field, not a
manually-configured "normal range" (nothing to set up, works the same for
every numeric event type, including a future custom one).

Deliberately simple for v1: a short rolling average rather than anything
statistical (std-dev, seasonality, etc.) — good enough to catch an obvious
jump (a scale misread, a sudden real change worth a second look) without
asking the user to define anything, and it adapts to a genuine gradual
trend (a growing kitten, steady weight loss on a diet) within a few
readings rather than flagging every step of it forever.
"""

from typing import Optional

# Need at least this many prior readings before judging a new one — with
# fewer, "average" is too noisy to mean anything (e.g. a single prior
# reading would flag literally any different second reading).
MIN_HISTORY_FOR_BASELINE = 3

# How many of the most recent prior readings make up the baseline. Short on
# purpose: a long window would treat a real, sustained trend (weight
# steadily climbing) as "abnormal" for months after it started, instead of
# adapting to the new normal within a few readings.
ROLLING_WINDOW = 5

# Fraction away from the rolling average that counts as worth a push. 15%
# catches a genuinely large swing (a misread scale, a real sudden change)
# without firing on ordinary day-to-day noise in something like a feeding
# portion.
DEVIATION_THRESHOLD = 0.15


def detect_anomaly(db, pet_id: str, event_type: str, field_name: str, new_value: float) -> Optional[dict]:
    """None if there's not enough history yet, the average is degenerate
    (zero), or `new_value` is within DEVIATION_THRESHOLD of the average of
    the pet's last ROLLING_WINDOW readings for this (event_type,
    field_name) — otherwise ``{"average": float, "deviation": float}``.

    Must be called with `new_value` NOT YET inserted into the events
    collection — the caller's own about-to-be-saved value has to stay out
    of its own baseline, or a single big jump would just average itself in
    and quietly fail to look abnormal.
    """
    history_cursor = (
        db.events.find({"pet_id": pet_id, "type": event_type, f"fields.{field_name}": {"$exists": True}})
        .sort("date_time", -1)
        .limit(ROLLING_WINDOW)
    )
    values = [
        doc["fields"][field_name]
        for doc in history_cursor
        if isinstance(doc.get("fields", {}).get(field_name), (int, float))
    ]
    if len(values) < MIN_HISTORY_FOR_BASELINE:
        return None

    average = sum(values) / len(values)
    if average == 0:
        return None

    deviation = abs(new_value - average) / average
    if deviation < DEVIATION_THRESHOLD:
        return None

    return {"average": round(average, 2), "deviation": deviation}
