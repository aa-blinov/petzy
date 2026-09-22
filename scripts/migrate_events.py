"""One-time migration: fold the eight legacy health-record collections into
the unified ``events`` collection, and seed the ``event_types`` registry.

The old collections (asthma_attacks, defecations, litter_changes, weights,
feedings, eye_drops, tooth_brushing, ear_cleaning) are read, never written
to or deleted — they stay as an untouched backup after this runs. Re-running
is safe: a migrated document carries its source id in ``_migrated_from_id``,
so an already-migrated row is skipped on a second pass.

Usage:
    python -m scripts.migrate_events            # apply
    python -m scripts.migrate_events --dry-run  # report counts only, write nothing
"""

import argparse
import logging

from web.builtin_event_types import LEGACY_COLLECTION_MAP, seed_builtin_event_types

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger("migrate_events")


def migrate(db, dry_run: bool = False) -> dict[str, int]:
    """Copy every legacy collection's documents into ``events``.

    ``db`` is taken as a parameter (rather than imported at module level)
    so tests can pass a mongomock database directly.

    Returns ``{old_collection_name: migrated_count}``.
    """
    inserted_types = seed_builtin_event_types(db)
    logger.info("Seeded %d builtin event type(s) (already-present ones left alone).", inserted_types)

    counts: dict[str, int] = {}
    for collection_name, mapping in LEGACY_COLLECTION_MAP.items():
        event_type = mapping["type"]
        field_names = mapping["fields"]

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
            fields = {
                name: doc[name]
                for name in field_names
                if doc.get(name) not in (None, "")
            }
            to_insert.append(
                {
                    "pet_id": doc.get("pet_id"),
                    "type": event_type,
                    "date_time": doc.get("date_time"),
                    "fields": fields,
                    "comment": doc.get("comment", "") or "",
                    "username": doc.get("username", "") or "",
                    "_migrated_from_id": str(doc["_id"]),
                }
            )

        counts[collection_name] = len(to_insert)
        if to_insert and not dry_run:
            db.events.insert_many(to_insert)
        logger.info(
            "%s -> events (type=%s): %d document(s) %s",
            collection_name,
            event_type,
            len(to_insert),
            "would be migrated (dry run)" if dry_run else "migrated",
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
