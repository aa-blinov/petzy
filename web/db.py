"""Database interaction module for the web application."""

import base64
import hashlib
import logging
import os
from datetime import timezone
from functools import lru_cache
from urllib.parse import quote_plus

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from pymongo import ASCENDING, DESCENDING, MongoClient

from web.configs import JWT_CONFIG


def get_env(name: str, default: str = None) -> str:
    """Get environment variable with optional default."""
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Environment variable '{name}' is not set!")
    return value


# MongoDB connection settings. The app signs in with its own account when
# the deploy has made one (MONGO_APP_USER: read and write on this database
# and the rate limiter's, nothing else). MONGO_USER is the root account the
# database was created with: backups and admin work only. Without an app
# account (local runs, CI), root as before.
if os.getenv("MONGO_APP_USER") and os.getenv("MONGO_APP_PASS"):
    MONGO_USER, MONGO_PASS = os.environ["MONGO_APP_USER"], os.environ["MONGO_APP_PASS"]
else:
    MONGO_USER, MONGO_PASS = get_env("MONGO_USER"), get_env("MONGO_PASS")
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


def _index_matches(existing: dict, keys: list, opts: dict) -> bool:
    """True when the index already built under this name is the one the code asks for.

    Only what changes how an index behaves is compared: its keys, uniqueness, TTL and partial filter.
    ``background`` does not change that, so it is left out.
    """
    return (
        [tuple(k) for k in existing["key"]] == [tuple(k) for k in keys]
        and bool(existing.get("unique")) == bool(opts.get("unique"))
        and existing.get("expireAfterSeconds") == opts.get("expireAfterSeconds")
        and existing.get("partialFilterExpression") == opts.get("partialFilterExpression")
    )


def _create_index(coll, keys: list, name: str, opts: dict) -> None:
    """Create an index, replacing a same-named one that was built from another definition.

    Indexes change after their first build (the unique flag and the TTL partial filter were added later for
    some). MongoDB refuses a second index under the same name, so the old one is dropped first. If the new
    definition cannot be built on the data (a unique index over duplicate rows), the old one is built back,
    so the collection is never left without it.
    """
    existing = coll.index_information().get(name)
    if not existing or _index_matches(existing, keys, opts):
        coll.create_index(keys, name=name, background=True, **opts)
        return
    coll.drop_index(name)
    try:
        coll.create_index(keys, name=name, background=True, **opts)
    except Exception:
        restore = ("unique", "expireAfterSeconds", "partialFilterExpression")
        old_opts = {k: existing[k] for k in restore if k in existing}
        coll.create_index(existing["key"], name=name, background=True, **old_opts)
        raise


def refresh_token_hash(token: str) -> str:
    """How a refresh token is kept in ``refresh_tokens``: its sha256 in hex.

    The token itself is never written to the database, so a read of the collection hands out no session. A session is
    found by this value, and only the one who holds the token can produce it.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


PLAIN_JWT_PREFIX = "eyJ"  # every JWT starts with the base64 of its header, which opens with `{"`


@lru_cache(maxsize=4)
def _successor_cipher(secret: str) -> Fernet:
    """The cipher that seals a spent session's successor, keyed from the JWT secret.

    That secret lives in the server's environment, not in the database, so a dump of the collection opens nothing.
    """
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"petzy refresh successor").derive(
        secret.encode("utf-8")
    )
    return Fernet(base64.urlsafe_b64encode(key))


def seal_refresh_successor(token: str) -> str:
    """How the successor of a spent refresh token is kept in ``replaced_by``: sealed, never as a token."""
    return _successor_cipher(JWT_CONFIG["secret_key"]).encrypt(token.encode("utf-8")).decode("ascii")


def open_refresh_successor(sealed: object) -> str | None:
    """The token that ``seal_refresh_successor`` sealed, or None when it does not open: a plain token, damage, or a
    secret that has changed. The caller then treats the sign-in as ended.
    """
    if not isinstance(sealed, str):
        return None
    try:
        return _successor_cipher(JWT_CONFIG["secret_key"]).decrypt(sealed.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def migrate_refresh_successors() -> int:
    """Seal the successors that spent sessions kept as plain tokens (``replaced_by`` starting with ``eyJ``).

    Returns how many rows changed. A sealed value never starts with ``eyJ``, so a second run changes nothing.
    """
    rows = list(db.refresh_tokens.find({"replaced_by": {"$regex": f"^{PLAIN_JWT_PREFIX}"}}, {"replaced_by": 1}))
    changed = 0
    for row in rows:
        plain = row["replaced_by"]
        # Compare-and-set: a row that another worker changed meanwhile is not overwritten.
        result = db.refresh_tokens.update_one(
            {"_id": row["_id"], "replaced_by": plain},
            {"$set": {"replaced_by": seal_refresh_successor(plain)}},
        )
        changed += result.modified_count
    return changed


def migrate_refresh_token_hashes() -> int:
    """Move the sessions written before the hash from ``token`` to ``token_hash``. Returns how many rows changed.

    The token keeps its value, so an old session still works: only the way it is kept changes. The token is removed in
    the same write that stores its hash. A second run changes nothing, and an empty collection is no error.
    """
    rows = list(db.refresh_tokens.find({"token": {"$exists": True}, "token_hash": {"$exists": False}}, {"token": 1}))
    changed = 0
    for row in rows:
        token = row.get("token")
        change = {"$unset": {"token": ""}}
        if isinstance(token, str) and token:
            change["$set"] = {"token_hash": refresh_token_hash(token)}
        # The filter repeats "no hash yet", so a second worker starting at the same moment changes nothing.
        result = db.refresh_tokens.update_one({"_id": row["_id"], "token_hash": {"$exists": False}}, change)
        changed += result.modified_count
    return changed


CHANGE_STAMPED = ("pets", "documents", "medications", "medication_intakes", "medical_records")


def backfill_updated_at() -> int:
    """Give a record saved before the sync feed its change moment: its creation, the last change it had.

    The feed (web/sync.py) reads updated_at only, so a record without it would never reach a device. Runs at
    startup and does nothing once every record has the field. Returns how many records got it.
    """
    done = 0
    for name in CHANGE_STAMPED:
        for row in list(db[name].find({"updated_at": {"$exists": False}}, {"created_at": 1})):
            moment = row.get("created_at") or row["_id"].generation_time
            if moment.tzinfo is not None:
                moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
            db[name].update_one({"_id": row["_id"], "updated_at": {"$exists": False}}, {"$set": {"updated_at": moment}})
            done += 1
    return done


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
                          slot_key unique sparse (a slot is closed once; the key is
                          course + day + minutes of the slot time, written only by
                          a mark that names its slot and was not forced)
      events              pet_id + date_time (timeline per pet)
                          pet_id + type + date_time (per-type list/chart)
      event_types         key unique         (registry lookup by type)
      documents           pet_id + created_at (document list for a pet)
      medical_records     pet_id + kind + date (the medical card's records of one kind)
      medical_shares      token_hash (a link opens by it; unique), pet_id + created_at (a pet's links),
                          purge_at (the database drops a link a month after its end)
                          pet_id + category + created_at (category filter)
      users               username unique (login lookup)
                          role             (admin queries)
      refresh_tokens      jti unique        (RFC 7519 JWT ID; replaces
                                              the older `token`-unique
                                              index, which collided when
                                              two logins landed in the
                                              same wall-clock second)
                          token_hash unique (sha256 of the token: the
                                              token itself is not stored)
                          family            (a sign-in: ended as a whole)
      idempotency_keys    username + path + key unique (a retried create gets its first answer)
                          expires_at        (the database drops a key a day after it was taken)
      push_subscriptions  endpoint unique   (upsert on re-subscribe)
                          username          (list a user's own devices)
      api_tokens          token_hash unique (sha256 of a personal access token: the token
                                              itself is not stored)
                          username + created_at (a person's tokens, newest first)
      medication_reminders_sent
                          medication_id + date + time unique (dedupe: one
                                              reminder per scheduled slot)
                          expires_at TTL    (auto-prune after 30 days)
      document_expiry_reminders_sent
                          document_id + expires_at unique (dedupe: one
                                              reminder per document expiry date)
                          purge_at TTL      (auto-prune after 90 days)
      medical_due_reminders_sent
                          record_id + next_due + stage unique (dedupe: one
                                              «скоро» and one «просрочено»
                                              push per repeat date)
                          purge_at TTL      (auto-prune after 90 days)
      image_thumbnails    source_file_id    (drop a file's variants with it)
      document_uploads    created_at        (sweep abandoned scan uploads)
      deleted_accounts   username unique  (a repeat delete after a broken answer
                                           answers instead of «wrong password»)
      login_failures      expires_at TTL    (wrong-password count per login, _id is the
                                           login: gone when its window or its lock ends)
      verification_mail_log
                          address_key + expires_at (letters to one address in the last day,
                                           keyed by an HMAC: the address is not stored)
                          expires_at TTL    (a row goes a day after its letter)
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

    # Sessions written before the hash kept the token in `token`. Each one moves to `token_hash` here, so it keeps
    # working and no token is left in plain text. A failure is logged, not raised: the startup goes on.
    try:
        moved = migrate_refresh_token_hashes()
        if moved:
            logger.info("Moved %d refresh tokens from token to token_hash", moved)
    except Exception:  # pragma: no cover — defensive
        logger.exception("Could not move refresh tokens to token_hash")

    # Spent sessions kept their successor as a plain token (`replaced_by`). Startup seals those values the same way.
    try:
        sealed = migrate_refresh_successors()
        if sealed:
            logger.info("Sealed %d refresh successors kept as plain tokens", sealed)
    except Exception:  # pragma: no cover — defensive
        logger.exception("Could not seal refresh successors")

    declarations = [
        (db.pets, [("owner", ASCENDING), ("created_at", DESCENDING)], "pets_owner_created"),
        (db.pets, [("shared_with", ASCENDING)], "pets_shared"),
        (db.medications, [("pet_id", ASCENDING), ("created_at", DESCENDING)], "meds_pet_created"),
        (db.medication_intakes, [("pet_id", ASCENDING), ("date_time", DESCENDING)], "intakes_pet_date"),
        (db.medication_intakes, [("medication_id", ASCENDING), ("date_time", DESCENDING)], "intakes_med_date"),
        (
            db.medication_intakes,
            [("slot_key", ASCENDING)],
            "intakes_slot_unique",
            {
                "unique": True,
                # The last line of defence for a slot closed twice: the check in log_intake reads the
                # day's intakes and then writes, so two phones marking the same 08:00 dose at the
                # same moment both saw it open and both wrote it, taking the stock twice.
                # The key is written only by a mark that names the slot it closed, and a forced mark
                # leaves it out, so it stays out of the index. A sparse unique index is used rather
                # than a partial one because Mongo refuses a partial filter that excludes a field
                # ("Expression not supported in partial index: $not").
                "sparse": True,
            },
        ),
        (db.events, [("pet_id", ASCENDING), ("date_time", DESCENDING)], "events_pet_date"),
        (db.events, [("pet_id", ASCENDING), ("type", ASCENDING), ("date_time", DESCENDING)], "events_pet_type_date"),
        (db.events, [("local_id", ASCENDING)], "events_local_id_unique", {"unique": True, "sparse": True}),
        # The name a device gives a record it made offline (web/offline.py): one record per name in each section.
        (db.medications, [("local_id", ASCENDING)], "medications_local_id_unique", {"unique": True, "sparse": True}),
        (
            db.medical_records,
            [("local_id", ASCENDING)],
            "medical_records_local_id_unique",
            {"unique": True, "sparse": True},
        ),
        (db.pets, [("local_id", ASCENDING)], "pets_local_id_unique", {"unique": True, "sparse": True}),
        (
            db.medication_intakes,
            [("local_id", ASCENDING)],
            "medication_intakes_local_id_unique",
            {"unique": True, "sparse": True},
        ),
        (db.events, [("pet_id", ASCENDING), ("updated_at", ASCENDING)], "events_pet_updated"),
        # A tombstone is kept for 30 days, then the database removes it.
        (db.events, [("deleted_at", ASCENDING)], "events_deleted_ttl", {"expireAfterSeconds": 30 * 24 * 60 * 60}),
        (db.event_types, [("key", ASCENDING)], "event_types_key_unique", {"unique": True}),
        (db.documents, [("pet_id", ASCENDING), ("created_at", DESCENDING)], "documents_pet_created"),
        (
            db.medical_records,
            [("pet_id", ASCENDING), ("kind", ASCENDING), ("date", DESCENDING)],
            "medical_records_pet_kind_date",
        ),
        (
            db.documents,
            [("pet_id", ASCENDING), ("category", ASCENDING), ("created_at", DESCENDING)],
            "documents_pet_category_created",
        ),
        (db.medical_shares, [("token_hash", ASCENDING)], "medical_shares_token_unique", {"unique": True}),
        (db.medical_shares, [("pet_id", ASCENDING), ("created_at", DESCENDING)], "medical_shares_pet_created"),
        (db.medical_shares, [("purge_at", ASCENDING)], "medical_shares_purge", {"expireAfterSeconds": 0}),
        (db.image_thumbnails, [("source_file_id", ASCENDING)], "image_thumbnails_source"),
        # Scan upload slots, swept by created_at (web/storage.py).
        (db.document_uploads, [("created_at", ASCENDING)], "document_uploads_created"),
        (db.deleted_accounts, [("username", ASCENDING)], "deleted_accounts_username", {"unique": True}),
        (db.users, [("username", ASCENDING)], "users_username_unique", {"unique": True}),
        # Links from letters (web/account.py): looked up by hash, gone when expired.
        (db.account_tokens, [("token_hash", ASCENDING)], "account_tokens_hash_unique", {"unique": True}),
        (db.account_tokens, [("expires_at", ASCENDING)], "account_tokens_ttl", {"expireAfterSeconds": 0}),
        # Personal access tokens (web/personal_tokens.py): found by the hash of the token on each request made with one.
        (db.api_tokens, [("token_hash", ASCENDING)], "api_tokens_token_hash_unique", {"unique": True}),
        # A person's tokens, newest first: their list, and the count of working ones.
        (db.api_tokens, [("username", ASCENDING), ("created_at", DESCENDING)], "api_tokens_user_created"),
        # Wrong-password count per login (web/login_lockout.py): the row goes when its window or its lock ends.
        (db.login_failures, [("expires_at", ASCENDING)], "login_failures_ttl", {"expireAfterSeconds": 0}),
        # Confirmation letters counted per address for a day (web/account.py): keyed by an HMAC, not the address.
        (
            db.verification_mail_log,
            [("address_key", ASCENDING), ("expires_at", ASCENDING)],
            "verification_mail_log_address",
        ),
        (db.verification_mail_log, [("expires_at", ASCENDING)], "verification_mail_log_ttl", {"expireAfterSeconds": 0}),
        (db.refresh_tokens, [("family", ASCENDING)], "refresh_token_family"),
        (
            db.idempotency_keys,
            [("username", ASCENDING), ("path", ASCENDING), ("key", ASCENDING)],
            "idempotency_key_unique",
            {"unique": True},
        ),
        (db.idempotency_keys, [("expires_at", ASCENDING)], "idempotency_keys_ttl", {"expireAfterSeconds": 0}),
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
        (
            db.refresh_tokens,
            [("token_hash", ASCENDING)],
            "refresh_token_hash_unique",
            {
                "unique": True,
                # Only rows that carry a hash. After the migration above, a row without one holds no token at all, and
                # such rows would all collide on a null value.
                "partialFilterExpression": {"token_hash": {"$exists": True}},
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
        (
            db.medical_due_reminders_sent,
            [("record_id", ASCENDING), ("next_due", ASCENDING), ("stage", ASCENDING)],
            "medical_due_reminders_sent_unique",
            {"unique": True},
        ),
        (
            db.medical_due_reminders_sent,
            [("purge_at", ASCENDING)],
            "medical_due_reminders_sent_ttl",
            {"expireAfterSeconds": 0},
        ),
    ]
    for coll_name in HEALTH_RECORD_COLLECTIONS:
        coll = db[coll_name]
        declarations.append((coll, [("pet_id", ASCENDING), ("date_time", DESCENDING)], f"{coll_name}_pet_date"))

    for coll_name in ("documents", "medications", "medication_intakes", "medical_records"):
        declarations.append(
            (db[coll_name], [("pet_id", ASCENDING), ("updated_at", ASCENDING)], f"{coll_name}_pet_updated")
        )
    # The sync feed (web/sync.py): who can see a gone record, and when the record is dropped.
    declarations.append(
        (
            db.sync_deletions,
            [("viewers", ASCENDING), ("kind", ASCENDING), ("deleted_at", ASCENDING)],
            "sync_deletions_viewer",
        )
    )
    declarations.append(
        (db.sync_deletions, [("expires_at", ASCENDING)], "sync_deletions_ttl", {"expireAfterSeconds": 0})
    )

    for spec in declarations:
        coll = spec[0]
        keys = spec[1]
        name = spec[2]
        opts = spec[3] if len(spec) > 3 else {}
        try:
            _create_index(coll, keys, name, opts)
        except Exception as exc:  # pragma: no cover — defensive
            # Don't fail startup on an index that cannot be built (a unique
            # index over duplicate rows); log and move on.
            logger.warning("Could not create index %s on %s: %s", name, coll.name, exc)

    try:
        backfill_updated_at()
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning("Could not backfill updated_at: %s", exc)


# Export mongo_uri for use in Flask-Limiter
__all__ = ["db", "client", "mongo_uri", "ensure_indexes", "HEALTH_RECORD_COLLECTIONS"]
