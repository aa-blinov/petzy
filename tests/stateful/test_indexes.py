"""Smoke tests for the database-index bootstrapping."""

from unittest.mock import patch

import mongomock
import pytest
from pymongo.errors import DuplicateKeyError

from web.db import HEALTH_RECORD_COLLECTIONS, ensure_indexes


def _patched_db():
    """Return (ctx_manager, mock_db) that swaps ``web.db.db`` for mongomock."""
    mock_db = mongomock.MongoClient()["idx_test"]
    return patch("web.db.db", mock_db), mock_db


def test_ensure_indexes_creates_expected_indexes():
    """ensure_indexes() must declare the indexes the app relies on."""
    cm, mock_db = _patched_db()
    with cm:
        ensure_indexes()

    expected = {
        "pets": ["pets_owner_created", "pets_shared"],
        "medications": ["meds_pet_created", "medications_pet_updated"],
        "medication_intakes": ["intakes_pet_date", "intakes_med_date", "medication_intakes_pet_updated"],
        "users": ["users_username_unique", "users_role"],
        "refresh_tokens": ["refresh_token_jti_unique", "refresh_token_hash_unique", "refresh_token_family"],
        "idempotency_keys": ["idempotency_key_unique", "idempotency_keys_ttl"],
        "events": [
            "events_pet_date",
            "events_pet_type_date",
            "events_local_id_unique",
            "events_deleted_ttl",
            "events_pet_updated",
        ],
        "event_types": ["event_types_key_unique"],
        "documents": ["documents_pet_created", "documents_pet_category_created", "documents_pet_updated"],
        "medical_records": ["medical_records_pet_kind_date", "medical_records_pet_updated"],
        "sync_deletions": ["sync_deletions_viewer", "sync_deletions_ttl"],
        "medical_shares": ["medical_shares_token_unique", "medical_shares_pet_created", "medical_shares_purge"],
        "push_subscriptions": ["push_subscriptions_endpoint_unique", "push_subscriptions_username"],
        "medication_reminders_sent": ["reminders_sent_slot_unique", "reminders_sent_ttl"],
        "document_expiry_reminders_sent": [
            "document_expiry_reminders_sent_unique",
            "document_expiry_reminders_sent_ttl",
        ],
        "medical_due_reminders_sent": [
            "medical_due_reminders_sent_unique",
            "medical_due_reminders_sent_ttl",
        ],
        "login_failures": ["login_failures_ttl"],
        "verification_mail_log": ["verification_mail_log_address", "verification_mail_log_ttl"],
        "api_tokens": ["api_tokens_token_hash_unique", "api_tokens_user_created"],
    }
    for coll_name, idx_names in expected.items():
        info = mock_db[coll_name].index_information()
        for idx in idx_names:
            assert idx in info, f"{coll_name} missing index {idx}; have {list(info.keys())}"

    # Factory-generated health-record collections should all share
    # the same compound pet_id+date_time index.
    for coll_name in HEALTH_RECORD_COLLECTIONS:
        info = mock_db[coll_name].index_information()
        assert f"{coll_name}_pet_date" in info, f"{coll_name} missing pet+date index; have {list(info.keys())}"


def test_the_letter_log_is_indexed_by_address_and_expires_its_rows():
    """Counting an address's letters reads one address's rows, and a row leaves the log a day after its letter."""
    cm, mock_db = _patched_db()
    with cm:
        ensure_indexes()
        info = mock_db.verification_mail_log.index_information()

    assert [tuple(k) for k in info["verification_mail_log_address"]["key"]] == [
        ("address_key", 1),
        ("expires_at", 1),
    ]
    assert [tuple(k) for k in info["verification_mail_log_ttl"]["key"]] == [("expires_at", 1)]
    assert info["verification_mail_log_ttl"]["expireAfterSeconds"] == 0


def test_ensure_indexes_idempotent():
    """Calling ensure_indexes() twice in a row must not raise."""
    cm, _ = _patched_db()
    with cm:
        ensure_indexes()
        # Second call should be a no-op for every collection.
        ensure_indexes()


def test_get_env_raises_when_required_var_missing():
    from web.db import get_env

    try:
        get_env("SOME_VAR_THAT_DEFINITELY_IS_NOT_SET_IN_THIS_PROCESS_XYZ")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "SOME_VAR_THAT_DEFINITELY_IS_NOT_SET_IN_THIS_PROCESS_XYZ" in str(e)


def test_ensure_indexes_drops_legacy_refresh_token_index():
    """The pre-jti unique index on refresh_tokens.token must be dropped
    when present — legacy deploys built it before jti-based uniqueness
    replaced it."""
    from pymongo import ASCENDING

    cm, mock_db = _patched_db()
    with cm:
        mock_db.refresh_tokens.create_index([("token", ASCENDING)], name="refresh_token_unique", unique=True)
        assert "refresh_token_unique" in mock_db.refresh_tokens.index_information()

        ensure_indexes()

        assert "refresh_token_unique" not in mock_db.refresh_tokens.index_information()


def test_ensure_indexes_replaces_index_built_from_an_older_definition():
    """refresh_token_ttl was first built without its partial filter. A database that still holds that index gets
    the current one, instead of keeping the old one and warning on every start."""
    from pymongo import ASCENDING

    cm, mock_db = _patched_db()
    with cm:
        mock_db.refresh_tokens.create_index([("expires_at", ASCENDING)], name="refresh_token_ttl", expireAfterSeconds=0)

        ensure_indexes()

        info = mock_db.refresh_tokens.index_information()["refresh_token_ttl"]
        assert info["partialFilterExpression"] == {"expires_at": {"$exists": True}}
        assert info["expireAfterSeconds"] == 0


def test_ensure_indexes_makes_deleted_account_username_unique():
    """A repeat delete of one account must hit the unique index. An index built before the unique flag existed is
    replaced, not left in place."""
    from pymongo import ASCENDING

    cm, mock_db = _patched_db()
    with cm:
        mock_db.deleted_accounts.create_index([("username", ASCENDING)], name="deleted_accounts_username")

        ensure_indexes()

        assert mock_db.deleted_accounts.index_information()["deleted_accounts_username"].get("unique") is True


def test_ensure_indexes_keeps_old_index_when_new_one_cannot_be_built():
    """Duplicate rows block the unique index. The old index must be built back, not left dropped."""
    from pymongo import ASCENDING

    cm, mock_db = _patched_db()
    with cm:
        mock_db.deleted_accounts.create_index([("username", ASCENDING)], name="deleted_accounts_username")
        mock_db.deleted_accounts.insert_many([{"username": "same"}, {"username": "same"}])

        ensure_indexes()

        info = mock_db.deleted_accounts.index_information()["deleted_accounts_username"]
        assert not info.get("unique")


def test_ensure_indexes_makes_a_refresh_token_hash_unique():
    """One hash is one session: a second row with the same hash is refused."""
    cm, mock_db = _patched_db()
    with cm:
        ensure_indexes()

        info = mock_db.refresh_tokens.index_information()["refresh_token_hash_unique"]
        assert info.get("unique") is True
        assert info["partialFilterExpression"] == {"token_hash": {"$exists": True}}
        mock_db.refresh_tokens.insert_one({"token_hash": "f" * 64, "username": "a"})
        with pytest.raises(DuplicateKeyError):
            mock_db.refresh_tokens.insert_one({"token_hash": "f" * 64, "username": "b"})


def test_login_failures_expire_with_their_window_or_lock():
    """A login's count of wrong passwords is swept when its window or its lock ends (web/login_lockout.py)."""
    cm, mock_db = _patched_db()
    with cm:
        ensure_indexes()

        info = mock_db.login_failures.index_information()["login_failures_ttl"]
        assert info["key"] == [("expires_at", 1)]
        assert info["expireAfterSeconds"] == 0


def test_a_personal_token_hash_is_unique():
    """One hash is one personal token: a second row with the same hash is refused, and a request finds its token by it."""
    cm, mock_db = _patched_db()
    with cm:
        ensure_indexes()

        info = mock_db.api_tokens.index_information()["api_tokens_token_hash_unique"]
        assert info.get("unique") is True
        assert info["key"] == [("token_hash", 1)]
        mock_db.api_tokens.insert_one({"token_hash": "a" * 64, "username": "a"})
        with pytest.raises(DuplicateKeyError):
            mock_db.api_tokens.insert_one({"token_hash": "a" * 64, "username": "b"})


def test_ensure_indexes_makes_a_local_id_unique_and_sparse():
    """A name the device gave is one record on the stand. A record without a name is left out of that index."""
    from pymongo.errors import DuplicateKeyError

    cm, mock_db = _patched_db()
    with cm:
        ensure_indexes()

        info = mock_db.events.index_information()["events_local_id_unique"]
        assert info.get("unique") is True
        assert info.get("sparse") is True
        mock_db.events.insert_one({"pet_id": "p", "type": "weight"})
        mock_db.events.insert_one({"pet_id": "p", "type": "weight"})
        mock_db.events.insert_one({"pet_id": "p", "type": "weight", "local_id": "same"})
        with pytest.raises(DuplicateKeyError):
            mock_db.events.insert_one({"pet_id": "q", "type": "weight", "local_id": "same"})


def test_ensure_indexes_removes_a_deleted_event_after_thirty_days():
    """A tombstone is kept for thirty days after its deletion, then the database removes it. A live event has no
    deleted_at, so the index leaves it alone."""
    cm, mock_db = _patched_db()
    with cm:
        ensure_indexes()

        info = mock_db.events.index_information()["events_deleted_ttl"]
        assert info.get("expireAfterSeconds") == 30 * 24 * 60 * 60
        mock_db.events.insert_one({"pet_id": "p", "type": "weight"})
