"""Daily database backups to the bucket (scripts/backup_to_s3.py).

mongodump/mongorestore are replaced by a fake ``run``; the bucket is
moto's (conftest.s3_storage).
"""

import os
import stat
from datetime import datetime, timedelta, timezone

import pytest

from scripts import backup_to_s3 as backup
from web import storage

BUCKET = "petzy-test"


def _keys(s3, prefix=""):
    return sorted(o["Key"] for o in s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix).get("Contents", []))


class FakeMongoTools:
    """Stands in for mongodump/mongorestore: records calls, writes an archive."""

    def __init__(self, archive=b"\x1f\x8b" + b"x" * 100, fail=None):
        self.archive, self.fail, self.calls = archive, fail, []

    def __call__(self, cmd, check):
        self.calls.append(cmd)
        tool = cmd[0]
        if tool == self.fail:
            raise RuntimeError(f"{tool} failed")
        if tool == "mongodump":
            path = next(a.split("=", 1)[1] for a in cmd if a.startswith("--archive="))
            with open(path, "wb") as f:
                f.write(self.archive)
            config = next(a.split("=", 1)[1] for a in cmd if a.startswith("--config="))
            self.config_mode = stat.S_IMODE(os.stat(config).st_mode)
            with open(config) as f:
                self.config = f.read()


@pytest.fixture(autouse=True)
def mongo_env(monkeypatch):
    monkeypatch.setenv("MONGO_DB", "petzy")
    monkeypatch.setenv("MONGO_USER", "root")
    monkeypatch.setenv("MONGO_PASS", 's3cr"et')


def _at(day, hour=0):
    return datetime(2026, 9, day, hour, 0, tzinfo=timezone.utc)


class TestBackupOnce:
    def test_dumps_verifies_and_uploads_into_the_backups_folder(self, s3_storage):
        tools = FakeMongoTools()

        key = backup.backup_once(storage, keep=3, now=_at(26), run=tools)

        assert key == "backups/mongo/petzy-20260926-000000.archive.gz"
        assert _keys(s3_storage) == [key]
        assert s3_storage.get_object(Bucket=BUCKET, Key=key)["Body"].read() == tools.archive
        assert [c[0] for c in tools.calls] == ["mongodump", "mongorestore"]
        assert "--dryRun" in tools.calls[1]
        assert "--db=petzy" in tools.calls[0]

    def test_the_password_never_reaches_the_command_line(self, s3_storage):
        tools = FakeMongoTools()

        backup.backup_once(storage, keep=3, now=_at(26), run=tools)

        assert not any("s3cr" in arg for call in tools.calls for arg in call)
        assert tools.config == 'password: "s3cr\\"et"\n'
        assert tools.config_mode == 0o600

    def test_keeps_the_newest_three(self, s3_storage):
        for day in range(20, 26):
            backup.backup_once(storage, keep=3, now=_at(day), run=FakeMongoTools())

        assert _keys(s3_storage, "backups/") == [
            "backups/mongo/petzy-20260923-000000.archive.gz",
            "backups/mongo/petzy-20260924-000000.archive.gz",
            "backups/mongo/petzy-20260925-000000.archive.gz",
        ]

    def test_rotation_removes_every_version(self, s3_storage):
        s3_storage.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
        for day in range(20, 25):
            backup.backup_once(storage, keep=3, now=_at(day), run=FakeMongoTools())

        versions = s3_storage.list_object_versions(Bucket=BUCKET, Prefix="backups/")
        keys = {v["Key"] for v in versions.get("Versions", [])}
        assert len(keys) == 3 and not versions.get("DeleteMarkers")

    def test_only_the_backups_folder_is_rotated(self, s3_storage):
        others = ["users/u1/pets/p1/photos/a.webp", "dev/users/u1/x", "backups/mongo/notes.txt"]
        for key in others:
            s3_storage.put_object(Bucket=BUCKET, Key=key, Body=b"x")

        for day in range(20, 25):
            backup.backup_once(storage, keep=1, now=_at(day), run=FakeMongoTools())

        assert set(others) <= set(_keys(s3_storage))

    @pytest.mark.parametrize("failing", ["mongodump", "mongorestore"])
    def test_a_failed_dump_or_check_keeps_the_old_backups(self, s3_storage, failing):
        for day in (20, 21, 22):
            backup.backup_once(storage, keep=3, now=_at(day), run=FakeMongoTools())

        with pytest.raises(RuntimeError):
            backup.backup_once(storage, keep=3, now=_at(23), run=FakeMongoTools(fail=failing))

        assert len(_keys(s3_storage, "backups/")) == 3
        assert "backups/mongo/petzy-20260923-000000.archive.gz" not in _keys(s3_storage)

    def test_an_empty_dump_is_not_uploaded(self, s3_storage):
        with pytest.raises(RuntimeError):
            backup.backup_once(storage, keep=3, now=_at(26), run=FakeMongoTools(archive=b""))

        assert _keys(s3_storage) == []

    def test_an_upload_of_the_wrong_size_is_removed_and_nothing_rotates(self, s3_storage, monkeypatch):
        for day in (20, 21, 22):
            backup.backup_once(storage, keep=3, now=_at(day), run=FakeMongoTools())
        monkeypatch.setattr(storage, "object_size", lambda key: 1)

        with pytest.raises(RuntimeError):
            backup.backup_once(storage, keep=3, now=_at(23), run=FakeMongoTools())

        assert _keys(s3_storage, "backups/") == [
            "backups/mongo/petzy-20260920-000000.archive.gz",
            "backups/mongo/petzy-20260921-000000.archive.gz",
            "backups/mongo/petzy-20260922-000000.archive.gz",
        ]

    def test_keep_must_be_at_least_one(self, s3_storage):
        with pytest.raises(ValueError):
            backup.rotate(storage, keep=0)


class TestSchedule:
    def test_next_run_is_today_if_the_hour_is_ahead(self):
        assert backup.seconds_until_next(datetime(2026, 9, 26, 1, 30, tzinfo=timezone.utc), 3) == 90 * 60

    def test_next_run_is_tomorrow_once_the_hour_has_passed(self):
        now = datetime(2026, 9, 26, 3, 0, tzinfo=timezone.utc)
        assert backup.seconds_until_next(now, 3) == 24 * 3600

    def test_due_with_no_backups(self, s3_storage):
        assert backup.is_due(storage, datetime.now(timezone.utc))

    def test_not_due_right_after_a_backup(self, s3_storage):
        backup.backup_once(storage, keep=3, run=FakeMongoTools())
        assert not backup.is_due(storage, datetime.now(timezone.utc))

    def test_due_when_the_newest_is_over_a_day_old(self, s3_storage):
        backup.backup_once(storage, keep=3, run=FakeMongoTools())
        assert backup.is_due(storage, datetime.now(timezone.utc) + timedelta(hours=25))
