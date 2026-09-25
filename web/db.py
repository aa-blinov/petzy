"""Database interaction module for the web application."""

import logging
import os
from urllib.parse import quote_plus

from pymongo import ASCENDING, DESCENDING, MongoClient


def get_env(name: str, default: str = None) -> str:
    """Get environment variable with optional default."""
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Environment variable '{name}' is not set!")
    return value


# MongoDB connection settings
MONGO_USER = get_env("MONGO_USER")
MONGO_PASS = get_env("MONGO_PASS")
MONGO_HOST = get_env("MONGO_HOST", "db")
MONGO_PORT = get_env("MONGO_PORT", "27017")
MONGO_DB = get_env("MONGO_DB")

# Build MongoDB URI
mongo_user = quote_plus(MONGO_USER)
mongo_pass = quote_plus(MONGO_PASS)
mongo_uri: str = f"mongodb://{mongo_user}:{mongo_pass}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}?authSource=admin"

# MongoDB connection pool settings
MONGO_POOL_CONFIG = {
    "maxPoolSize": 50,  # Maximum number of connections in the pool
    "minPoolSize": 5,  # Minimum number of connections to maintain
    "maxIdleTimeMS": 30000,  # Close idle connections after 30 seconds
    "serverSelectionTimeoutMS": 5000,  # Timeout for server selection (5 seconds)
    "connectTimeoutMS": 10000,  # Timeout for initial connection (10 seconds)
    "socketTimeoutMS": 30000,  # Timeout for socket operations (30 seconds)
    "retryWrites": True,  # Enable automatic retry for write operations
    "retryReads": True,  # Enable automatic retry for read operations
}

# Create MongoDB client and database connection with pool configuration
client: MongoClient = MongoClient(mongo_uri, **MONGO_POOL_CONFIG)
db = client[MONGO_DB]

logger = logging.getLogger(__name__)

# Collections that need a {pet_id, date_time/-created_at} compound index
# for the timeline / list-by-pet queries. The factory-generated health
# record endpoints all funnel into these.
HEALTH_RECORD_COLLECTIONS = (
    "asthma_attacks",
    "defecations",
    "litter_changes",
    "weights",
    "feedings",
    "eye_drops",
    "tooth_brushing",
    "ear_cleaning",
)


def ensure_indexes() -> None:
    """Create the indexes the application relies on.

    Safe to call repeatedly — MongoDB makes ``create_index`` a no-op when
    an identical index already exists. ``background=True`` so production
    index builds don't lock the database during startup; mongomock
    ignores the flag but still works.

    Indexes:

      pets                owner + created_at (list owner's pets, newest first)
                          shared_with       (list pets shared with user)
      medications         pet_id + created_at (medication list for a pet)
      medication_intakes  pet_id + date_time (intakes timeline per pet)
                          medication_id + date_time (last intake / count today)
      events              pet_id + date_time (timeline per pet)
                          pet_id + type + date_time (per-type list/chart)
      event_types         key unique         (registry lookup by type)
      documents           pet_id + created_at (document list for a pet)
                          pet_id + category + created_at (category filter)
      users               username unique (login lookup)
                          role             (admin queries)
      refresh_tokens      jti unique        (RFC 7519 JWT ID; replaces
                                              the older `token`-unique
                                              index, which collided when
                                              two logins landed in the
                                              same wall-clock second)
      push_subscriptions  endpoint unique   (upsert on re-subscribe)
                          username          (list a user's own devices)
      medication_reminders_sent
                          medication_id + date + time unique (dedupe: one
                                              reminder per scheduled slot)
                          expires_at TTL    (auto-prune after 30 days)
      document_expiry_reminders_sent
                          document_id + expires_at unique (dedupe: one
                                              reminder per document expiry date)
                          purge_at TTL      (auto-prune after 90 days)
      image_thumbnails    source_file_id    (drop a file's variants with it)
      document_uploads    created_at        (sweep abandoned scan uploads)
      <each health_*>     pet_id + date_time (per-type timelines)
    """
    # Migration: drop the obsolete `refresh_token_unique` on `token` if it
    # exists from a previous deploy. After this, refresh-token uniqueness
    # is enforced on `jti` (UUID4), which is collision-proof regardless of
    # clock alignment. Existing refresh_tokens without a `jti` become
    # useless — users simply re-login.
    try:
        db.refresh_tokens.drop_index("refresh_token_unique")
        logger.info("Dropped legacy refresh_token_unique index on refresh_tokens.token")
    except Exception:
        # mongomock and first-time prod: index doesn't exist yet, that's fine.
        pass

    declarations = [
        (db.pets, [("owner", ASCENDING), ("created_at", DESCENDING)], "pets_owner_created"),
        (db.pets, [("shared_with", ASCENDING)], "pets_shared"),
        (db.medications, [("pet_id", ASCENDING), ("created_at", DESCENDING)], "meds_pet_created"),
        (db.medication_intakes, [("pet_id", ASCENDING), ("date_time", DESCENDING)], "intakes_pet_date"),
        (db.medication_intakes, [("medication_id", ASCENDING), ("date_time", DESCENDING)], "intakes_med_date"),
        (db.events, [("pet_id", ASCENDING), ("date_time", DESCENDING)], "events_pet_date"),
        (db.events, [("pet_id", ASCENDING), ("type", ASCENDING), ("date_time", DESCENDING)], "events_pet_type_date"),
        (db.event_types, [("key", ASCENDING)], "event_types_key_unique", {"unique": True}),
        (db.documents, [("pet_id", ASCENDING), ("created_at", DESCENDING)], "documents_pet_created"),
        (
            db.documents,
            [("pet_id", ASCENDING), ("category", ASCENDING), ("created_at", DESCENDING)],
            "documents_pet_category_created",
        ),
        (db.image_thumbnails, [("source_file_id", ASCENDING)], "image_thumbnails_source"),
        # Scan upload slots, swept by created_at (web/storage.py).
        (db.document_uploads, [("created_at", ASCENDING)], "document_uploads_created"),
        (db.users, [("username", ASCENDING)], "users_username_unique", {"unique": True}),
        (db.users, [("role", ASCENDING)], "users_role"),
        (
            db.refresh_tokens,
            [("jti", ASCENDING)],
            "refresh_token_jti_unique",
            {
                "unique": True,
                # Only enforce uniqueness on rows that actually have a
                # jti. Legacy rows from before the jti fix carry
                # `jti: null` and several of them would collide on the
                # index — a partial filter makes the constraint
                # permissive enough that the index can be created
                # against a pre-existing legacy collection, while
                # still preventing any future duplicate.
                "partialFilterExpression": {"jti": {"$exists": True}},
            },
        ),
        # TTL index — MongoDB's background TTL monitor sweeps every ~60s
        # and drops any document whose `expires_at` is in the past. This
        # is the right answer for "no application-level cleanup needed":
        # the field is already authoritative (we set it from the JWT
        # payload in create_refresh_token), and PyMongo encodes Python
        # datetimes as BSON Date, which is what TTL requires.
        #
        # Documented caveat: rows created before this migration may have
        # `expires_at` missing or as a non-Date type. The TTL monitor
        # silently ignores such rows (no type error — it just doesn't
        # match the index), so existing tokens keep working until they
        # naturally get used-and-replaced. A one-shot deleteMany is run
        # via the `inspect_db` workflow to prune legacy rows.
        (
            db.refresh_tokens,
            [("expires_at", ASCENDING)],
            "refresh_token_ttl",
            {
                "expireAfterSeconds": 0,
                # Same partial filter story — legacy rows without
                # expires_at shouldn't appear "in the past" to TTL.
                "partialFilterExpression": {"expires_at": {"$exists": True}},
            },
        ),
        (db.push_subscriptions, [("endpoint", ASCENDING)], "push_subscriptions_endpoint_unique", {"unique": True}),
        (db.push_subscriptions, [("username", ASCENDING)], "push_subscriptions_username"),
        (
            db.medication_reminders_sent,
            [("medication_id", ASCENDING), ("date", ASCENDING), ("time", ASCENDING)],
            "reminders_sent_slot_unique",
            {"unique": True},
        ),
        # TTL — a sent-reminder row only exists to stop the ~60s poll from
        # re-sending the same slot; nothing ever reads it again after the
        # day it was written, so it can expire like refresh_tokens above.
        (
            db.medication_reminders_sent,
            [("expires_at", ASCENDING)],
            "reminders_sent_ttl",
            {"expireAfterSeconds": 0},
        ),
        (
            db.document_expiry_reminders_sent,
            [("document_id", ASCENDING), ("expires_at", ASCENDING)],
            "document_expiry_reminders_sent_unique",
            {"unique": True},
        ),
        # Field is named purge_at, not expires_at — this collection's own
        # "expires_at" already means the document's expiry date (part of
        # the dedupe key above), so the TTL trigger needed a name of its own.
        (
            db.document_expiry_reminders_sent,
            [("purge_at", ASCENDING)],
            "document_expiry_reminders_sent_ttl",
            {"expireAfterSeconds": 0},
        ),
    ]
    for coll_name in HEALTH_RECORD_COLLECTIONS:
        coll = db[coll_name]
        declarations.append((coll, [("pet_id", ASCENDING), ("date_time", DESCENDING)], f"{coll_name}_pet_date"))

    for spec in declarations:
        coll = spec[0]
        keys = spec[1]
        name = spec[2]
        opts = spec[3] if len(spec) > 3 else {}
        try:
            coll.create_index(keys, name=name, background=True, **opts)
        except Exception as exc:  # pragma: no cover — defensive
            # Don't fail startup if an index already exists under a
            # different name with conflicting options; log and move on.
            logger.warning("Could not create index %s on %s: %s", name, coll.name, exc)


# Export mongo_uri for use in Flask-Limiter
__all__ = ["db", "client", "mongo_uri", "ensure_indexes", "HEALTH_RECORD_COLLECTIONS"]
