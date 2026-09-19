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
    "maxPoolSize": 50,           # Maximum number of connections in the pool
    "minPoolSize": 5,            # Minimum number of connections to maintain
    "maxIdleTimeMS": 30000,      # Close idle connections after 30 seconds
    "serverSelectionTimeoutMS": 5000,  # Timeout for server selection (5 seconds)
    "connectTimeoutMS": 10000,   # Timeout for initial connection (10 seconds)
    "socketTimeoutMS": 30000,    # Timeout for socket operations (30 seconds)
    "retryWrites": True,         # Enable automatic retry for write operations
    "retryReads": True,          # Enable automatic retry for read operations
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
      users               username unique (login lookup)
                          role             (admin queries)
      refresh_tokens      token unique      (token refresh lookup)
      <each health_*>     pet_id + date_time (per-type timelines)
    """
    declarations = [
        (db.pets, [("owner", ASCENDING), ("created_at", DESCENDING)], "pets_owner_created"),
        (db.pets, [("shared_with", ASCENDING)], "pets_shared"),
        (db.medications, [("pet_id", ASCENDING), ("created_at", DESCENDING)], "meds_pet_created"),
        (db.medication_intakes, [("pet_id", ASCENDING), ("date_time", DESCENDING)], "intakes_pet_date"),
        (db.medication_intakes, [("medication_id", ASCENDING), ("date_time", DESCENDING)], "intakes_med_date"),
        (db.users, [("username", ASCENDING)], "users_username_unique", {"unique": True}),
        (db.users, [("role", ASCENDING)], "users_role"),
        (db.refresh_tokens, [("token", ASCENDING)], "refresh_token_unique", {"unique": True}),
    ]
    for coll_name in HEALTH_RECORD_COLLECTIONS:
        coll = db[coll_name]
        declarations.append(
            (coll, [("pet_id", ASCENDING), ("date_time", DESCENDING)], f"{coll_name}_pet_date")
        )

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
