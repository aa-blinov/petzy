"""The life history (анамнез жизни): everything the medical card knows about a
pet, without the card's «last ten» limits, and in the order a vet reads a history.

The card is a summary for an appointment; this is the whole record: every
vaccination, treatment, visit and procedure from the pet's birth on, every
medication course, the full weight curve, how much the diary holds of each
kind of event, and the documents. It is a PDF and is built on request from the
same records; nothing is stored.
"""

from datetime import date, datetime
import web.app as app
from web.medical_card import _as_date_str, _courses, _weight, build_medical_card
from web.medical_records import pet_records

# A kind of event whose own section says more than a count does (the weight curve).
EVENTS_SHOWN_ELSEWHERE = {"weight"}


def _documents(pet_id: str) -> list[dict]:
    """Every document of the pet, newest first: its title, what it is, when added, how long valid."""
    rows = []
    for doc in app.db.documents.find({"pet_id": pet_id}).sort("created_at", -1):
        rows.append(
            {
                "id": str(doc["_id"]),
                "title": doc.get("title", ""),
                "category": doc.get("category", ""),
                "added": _as_date_str(doc.get("created_at")) or "",
                "expires_at": _as_date_str(doc.get("expires_at")),
            }
        )
    return rows


def _event_summary(pet_id: str) -> list[dict]:
    """What the diary holds, per kind of event: how many, the first and the last, and how many each year.

    Counted in one pass over the pet's events (only their type and date are read).
    """
    labels = {t["key"]: t.get("label", t["key"]) for t in app.db.event_types.find({})}
    stats: dict[str, dict] = {}
    for event in app.db.events.find({"pet_id": pet_id}, {"type": 1, "date_time": 1}):
        kind, moment = event.get("type"), event.get("date_time")
        if not kind or kind in EVENTS_SHOWN_ELSEWHERE or not isinstance(moment, datetime):
            continue
        row = stats.setdefault(kind, {"total": 0, "first": moment, "last": moment, "years": {}})
        row["total"] += 1
        row["first"] = min(row["first"], moment)
        row["last"] = max(row["last"], moment)
        row["years"][moment.year] = row["years"].get(moment.year, 0) + 1
    summary = [
        {
            "key": kind,
            "label": labels.get(kind, kind),
            "total": row["total"],
            "first": row["first"].strftime("%Y-%m-%d"),
            "last": row["last"].strftime("%Y-%m-%d"),
            "years": dict(sorted(row["years"].items())),
        }
        for kind, row in stats.items()
    ]
    # The ones with the most entries first, by name among equals.
    summary.sort(key=lambda r: (-r["total"], r["label"]))
    return summary


def build_anamnesis(pet: dict, username: str, today: date) -> dict:
    """The card's data with its limits lifted, plus what only a full history has."""
    pet_id = str(pet["_id"])
    card = build_medical_card(pet, username, today)
    current, past = _courses(pet_id, today, past_limit=None)
    # Oldest first: a history reads from the birth onwards.
    records = sorted(pet_records(pet_id, today), key=lambda r: (r["date"], r["_id"]))
    card.update(
        {
            "records": {kind: [r for r in records if r["kind"] == kind] for kind in card["records"]},
            "timeline_records": records,
            "medications": current,
            "past_courses": past,
            "weight": _weight(pet_id, limit=None),
            "documents": _documents(pet_id),
            "event_summary": _event_summary(pet_id),
        }
    )
    return card
