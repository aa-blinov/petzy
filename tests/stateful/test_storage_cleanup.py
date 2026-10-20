"""A scan upload that was never confirmed is swept away, and one that cannot be removed waits.

A slot is left behind when the tab was closed halfway through an upload. After six hours it is
swept: the slot and the object go. When the object cannot be removed (the bucket says no), the slot
stays: it is tried again on the next pass, rather than forgotten with the object still in the bucket.
"""

from datetime import datetime, timedelta, timezone

from web import storage


def _slot(mock_db, key, age_hours):
    mock_db["document_uploads"].insert_one(
        {
            "_id": key,
            "key": key,
            "pet_id": "pet-1",
            "username": "testuser",
            "filename": "scan.zip",
            "size": 10,
            "content_type": "application/zip",
            "family": "zip",
            "created_at": datetime.now(timezone.utc) - timedelta(hours=age_hours),
        }
    )


def test_without_the_storage_settings_nothing_is_swept(mock_db, monkeypatch):
    for name in ("S3_ENDPOINT", "S3_BUCKET", "S3_KEY_ID", "S3_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    storage.reset_client()
    _slot(mock_db, "users/a/scan.zip", age_hours=100)

    assert storage.cleanup_abandoned_uploads(mock_db) == 0
    assert mock_db["document_uploads"].count_documents({}) == 1

    storage.reset_client()


def test_an_upload_confirmed_in_time_stays(mock_db, monkeypatch):
    deleted = []
    monkeypatch.setattr(storage, "delete_object", lambda key: deleted.append(key))
    _slot(mock_db, "users/a/fresh.zip", age_hours=1)

    assert storage.cleanup_abandoned_uploads(mock_db) == 0
    assert deleted == []
    assert mock_db["document_uploads"].count_documents({}) == 1


def test_an_upload_left_alone_is_swept(mock_db, monkeypatch):
    deleted = []
    monkeypatch.setattr(storage, "delete_object", lambda key: deleted.append(key))
    _slot(mock_db, "users/a/old.zip", age_hours=7)

    assert storage.cleanup_abandoned_uploads(mock_db) == 1
    assert deleted == ["users/a/old.zip"]
    assert mock_db["document_uploads"].count_documents({}) == 0


def test_an_upload_that_cannot_be_removed_waits_for_the_next_pass(mock_db, monkeypatch):
    def refuse(key):
        raise RuntimeError("the bucket says no")

    monkeypatch.setattr(storage, "delete_object", refuse)
    _slot(mock_db, "users/a/stuck.zip", age_hours=7)

    assert storage.cleanup_abandoned_uploads(mock_db) == 0
    assert mock_db["document_uploads"].count_documents({}) == 1
