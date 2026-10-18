"""Binds the records saved before a zone was kept to the zone of the person who saved them.

An event or an intake saved before its zone was stored has no tz, so it reads on the UTC offset (see
web/helpers.zoned_iso). Its clock is the local clock of the device it was saved on, as the app kept it then. That
device's zone is the one most of its author's own records name: a record of that author with no zone takes it, and its
clock stays as entered. When the author names no zone, or two zones equally, the record stays as it is.

    python -m web.zone_backfill          counts only: what --apply would write
    python -m web.zone_backfill --apply  writes the zones; a second run writes nothing

Only a record with no zone is touched, and only with a zone the zone database knows.
"""

import argparse
from collections import Counter
from zoneinfo import ZoneInfo

COLLECTIONS = ("events", "medication_intakes")
NO_ZONE = {"$or": [{"tz": {"$exists": False}}, {"tz": None}]}


def _known_zone(name):
    if not isinstance(name, str) or not name:
        return None
    try:
        ZoneInfo(name)
    except (KeyError, ValueError):
        return None
    return name


def _author_zones(database) -> dict:
    """The zone each author's records name, when one zone is named most: two zones named equally name none."""
    named: dict = {}
    for collection in COLLECTIONS:
        for row in database[collection].find({"tz": {"$ne": None}}, {"username": 1, "tz": 1}):
            zone = _known_zone(row["tz"])
            if zone and row.get("username"):
                named.setdefault(row["username"], Counter())[zone] += 1
    zones = {}
    for author, counts in named.items():
        ranked = counts.most_common(2)
        if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
            zones[author] = ranked[0][0]
    return zones


def backfill_zones(database, apply: bool = False) -> dict:
    """Counts the records without a zone and, with apply, writes their author's zone into them."""
    zones = _author_zones(database)
    report = {}
    for collection in COLLECTIONS:
        counts = {"without_zone": 0, "bindable": 0, "unbound": 0, "written": 0}
        rows = list(database[collection].find(NO_ZONE, {"username": 1}))
        for row in rows:
            counts["without_zone"] += 1
            zone = zones.get(row.get("username"))
            if not zone:
                counts["unbound"] += 1
                continue
            counts["bindable"] += 1
            if apply:
                result = database[collection].update_one({"_id": row["_id"], **NO_ZONE}, {"$set": {"tz": zone}})
                counts["written"] += result.modified_count
        report[collection] = counts
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Gives the records without a zone the zone of their author.")
    parser.add_argument("--apply", action="store_true", help="write the zones (without it, only the counts)")
    args = parser.parse_args()

    from web.db import db  # the same database connection the web process uses

    report = backfill_zones(db, apply=args.apply)
    for collection, counts in report.items():
        line = (
            f"{collection}: без пояса {counts['without_zone']}, пояс автора есть {counts['bindable']}, "
            f"не привязать {counts['unbound']}"
        )
        if args.apply:
            line += f", записано {counts['written']}"
        print(line)
    if not args.apply:
        print("Ничего не записано. Чтобы записать, запустите с --apply.")


if __name__ == "__main__":
    main()
