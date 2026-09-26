"""One-time migration: fold the eight legacy health-record collections into
the unified ``events`` collection, and seed the ``event_types`` registry.

The old collections (asthma_attacks, defecations, litter_changes, weights,
feedings, eye_drops, tooth_brushing, ear_cleaning) are read, never written
to or deleted — they stay as an untouched backup after this runs. Re-running
is safe: a migrated document carries its source id in ``_migrated_from_id``,
so an already-migrated row is skipped on a second pass.

Values are brought into the shape the event engine validates on every
save (web/events.py), or a migrated record couldn't be edited:

- numbers stored as strings ("4.5", "4,5") or Int64 become floats;
- select fields take the type's option values: True/False become
  "true"/"false", and a known old label maps to its option;
- a value that fits no option (asthma durations were free text: "5 минут")
  isn't guessed: the field stays empty and the original goes into the
  comment ("Длительность: 5 минут"), so nothing is lost;
- records of a pet that no longer exists are skipped (nowhere to show
  them); they stay in the legacy collection.

Usage:
    python -m scripts.migrate_events            # apply
    python -m scripts.migrate_events --dry-run  # report counts only, write nothing
"""

import argparse
import logging

from web.builtin_event_types import LEGACY_COLLECTION_MAP, seed_builtin_event_types

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("migrate_events")


# Old labels whose option is certain. Bristol type 4 is the normal stool.
SELECT_ALIASES: dict[tuple[str, str], dict[str, str]] = {
    ("defecation", "stool_type"): {"Тип 4 (Нормальный)": "Обычный"},
}


def normalize_fields(event_type: str, field_specs: dict, raw: dict) -> tuple[dict, list[str]]:
    """Legacy values -> what web/events.py accepts. Returns (fields, notes):
    notes are "Label: value" for anything that had to leave its field."""
    fields, notes = {}, []
    for name, value in raw.items():
        spec = field_specs.get(name, {})
        label = spec.get("label", name)
        kind = spec.get("type")
        if kind == "number":
            try:
                fields[name] = float(str(value).replace(",", "."))
            except ValueError:
                notes.append(f"{label}: {value}")
        elif kind == "select":
            allowed = {str(o["value"]) for o in spec.get("options") or []}
            candidate = str(value).lower() if isinstance(value, bool) else str(value)
            candidate = SELECT_ALIASES.get((event_type, name), {}).get(candidate, candidate)
            if candidate in allowed:
                fields[name] = candidate
            else:
                notes.append(f"{label}: {value}")
        else:
            fields[name] = str(value)[:500]
    return fields, notes


def migrate(db, dry_run: bool = False) -> dict[str, int]:
    """Copy every legacy collection's documents into ``events``.

    ``db`` is taken as a parameter (rather than imported at module level)
    so tests can pass a mongomock database directly.

    Returns ``{old_collection_name: migrated_count}``.
    """
    inserted_types = seed_builtin_event_types(db)
    logger.info("Seeded %d builtin event type(s) (already-present ones left alone).", inserted_types)

    pet_ids = {str(p["_id"]) for p in db.pets.find({}, {"_id": 1})}
    counts: dict[str, int] = {}
    for collection_name, mapping in LEGACY_COLLECTION_MAP.items():
        event_type = mapping["type"]
        field_names = mapping["fields"]
        type_doc = db.event_types.find_one({"key": event_type}) or {}
        field_specs = {f["name"]: f for f in type_doc.get("fields", [])}
        orphaned = moved_to_comment = 0

        already_migrated = {
            doc["_migrated_from_id"]
            for doc in db.events.find(
                {"type": event_type, "_migrated_from_id": {"$exists": True}},
                {"_migrated_from_id": 1},
            )
        }

        to_insert = []
        for doc in db[collection_name].find({}):
            if str(doc["_id"]) in already_migrated:
                continue
            if str(doc.get("pet_id")) not in pet_ids:
                orphaned += 1
                continue
            raw = {name: doc[name] for name in field_names if doc.get(name) not in (None, "")}
            fields, notes = normalize_fields(event_type, field_specs, raw)
            moved_to_comment += len(notes)
            comment = "\n".join(part for part in [(doc.get("comment", "") or "").strip(), *notes] if part)
            to_insert.append(
                {
                    "pet_id": doc.get("pet_id"),
                    "type": event_type,
                    "date_time": doc.get("date_time"),
                    "fields": fields,
                    "comment": comment,
                    "username": doc.get("username", "") or "",
                    "_migrated_from_id": str(doc["_id"]),
                }
            )

        counts[collection_name] = len(to_insert)
        if to_insert and not dry_run:
            db.events.insert_many(to_insert)
        logger.info(
            "%s -> events (type=%s): %d document(s) %s; %d of a deleted pet skipped; %d value(s) moved to comments",
            collection_name,
            event_type,
            len(to_insert),
            "would be migrated (dry run)" if dry_run else "migrated",
            orphaned,
            moved_to_comment,
        )

    return counts


if __name__ == "__main__":
    from web.db import db as real_db

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing anything")
    args = parser.parse_args()

    result = migrate(real_db, dry_run=args.dry_run)
    total = sum(result.values())
    logger.info(
        "Done. %d total document(s) %s.",
        total,
        "would be migrated" if args.dry_run else "migrated",
    )
