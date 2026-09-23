"""Smoke tests for the database-index bootstrapping."""

from unittest.mock import patch

import mongomock

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
        "medications": ["meds_pet_created"],
        "medication_intakes": ["intakes_pet_date", "intakes_med_date"],
        "users": ["users_username_unique", "users_role"],
        "refresh_tokens": ["refresh_token_jti_unique"],
        "events": ["events_pet_date", "events_pet_type_date"],
        "event_types": ["event_types_key_unique"],
        "documents": ["documents_pet_created", "documents_pet_category_created"],
        "push_subscriptions": ["push_subscriptions_endpoint_unique", "push_subscriptions_username"],
        "medication_reminders_sent": ["reminders_sent_slot_unique", "reminders_sent_ttl"],
        "document_expiry_reminders_sent": [
            "document_expiry_reminders_sent_unique",
            "document_expiry_reminders_sent_ttl",
        ],
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
