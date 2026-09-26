"""Daily MongoDB backup to object storage, keeping the newest few.

Runs as its own container (docker-compose's `backup` service, image from
backup/Dockerfile: the mongo image, so mongodump matches the server, plus
Python and boto3). Once a day, at BACKUP_HOUR_UTC, it:

  1. dumps the database with mongodump into one gzipped archive;
  2. checks the archive reads back (mongorestore --dryRun);
  3. uploads it under backups/mongo/ in the bucket and checks the stored
     size;
  4. only then deletes all but the newest BACKUP_KEEP backups, every
     version of them (the bucket keeps versions; a plain delete would
     only hide them).

A failed attempt leaves the older backups alone and is retried in an
hour. On start it backs up at once if the newest backup is more than a
day old (first run, a missed day), so a deploy never leaves the data
without a recent copy.

Backups sit in their own top-level folder, apart from users' files
(users/) and local runs (dev/). Files themselves (photos, documents,
scans) are already in the bucket and aren't part of the dump.

    python scripts/backup_to_s3.py          # the daily loop
    python scripts/backup_to_s3.py --once   # one backup now, then exit

Restoring: see README, "Backups".
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

logger = logging.getLogger("backup")

PREFIX = "backups/mongo/"
SUFFIX = ".archive.gz"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def backup_key(now: datetime) -> str:
    return f"{PREFIX}{_env('MONGO_DB', 'petzy')}-{now.strftime('%Y%m%d-%H%M%S')}{SUFFIX}"


def list_backups(storage) -> list[dict]:
    """Backups in the bucket, newest first: [{key, size, modified}]."""
    found = [b for b in storage.list_objects(PREFIX) if b["key"].endswith(SUFFIX)]
    return sorted(found, key=lambda b: b["key"], reverse=True)  # the key carries the timestamp


def rotate(storage, keep: int) -> list[str]:
    """Delete every backup but the newest ``keep``. Returns the deleted keys."""
    if keep < 1:
        raise ValueError("keep at least one backup")
    stale = [b["key"] for b in list_backups(storage)[keep:]]
    for key in stale:
        storage.delete_object(key)  # all versions
    return stale


def write_credentials(tmp: str) -> str:
    """The password goes in a 0600 config file, not on the command line,
    where the process list and a failed command's error would show it."""
    path = os.path.join(tmp, "mongo.yaml")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"password: {json.dumps(_env('MONGO_PASS'))}\n")  # a JSON string is valid YAML
    return path


def _mongo_args(credentials: str) -> list[str]:
    return [
        f"--host={_env('MONGO_HOST', 'db')}",
        f"--port={_env('MONGO_PORT', '27017')}",
        f"--username={_env('MONGO_USER')}",
        f"--config={credentials}",
        "--authenticationDatabase=admin",
    ]


def dump(path: str, credentials: str, run: Callable = subprocess.run) -> None:
    """mongodump the app's database into one gzipped archive at ``path``."""
    run(
        ["mongodump", *_mongo_args(credentials), f"--db={_env('MONGO_DB')}", f"--archive={path}", "--gzip", "--quiet"],
        check=True,
    )


def verify(path: str, credentials: str, run: Callable = subprocess.run) -> None:
    """Read the whole archive back without writing anything (--dryRun)."""
    run(
        ["mongorestore", *_mongo_args(credentials), f"--archive={path}", "--gzip", "--dryRun", "--quiet"],
        check=True,
    )


def backup_once(storage, keep: int, now: Optional[datetime] = None, run: Callable = subprocess.run) -> str:
    """Dump, verify, upload, check, rotate. Returns the new backup's key."""
    now = now or datetime.now(timezone.utc)
    key = backup_key(now)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "dump.archive.gz")
        credentials = write_credentials(tmp)
        dump(path, credentials, run)
        verify(path, credentials, run)
        size = os.path.getsize(path)
        if size == 0:
            raise RuntimeError("mongodump produced an empty archive")
        storage.put_file(key, path, "application/gzip")
    if storage.object_size(key) != size:
        # Not left behind: it would count as one of the newest and push a
        # good backup out at the next rotation.
        storage.delete_object(key)
        raise RuntimeError(f"stored size of {key} doesn't match the dump ({size} bytes)")
    deleted = rotate(storage, keep)
    logger.info(f"Backup stored: {key} ({size / 1024 / 1024:.1f} MB); removed {len(deleted)} old: {deleted}")
    return key


def seconds_until_next(now: datetime, hour: int) -> float:
    """Seconds until the next HH:00 UTC (tomorrow's, if today's has passed)."""
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


RETRY_AFTER_SECONDS = 60 * 60


def is_due(storage, now: datetime) -> bool:
    """No backup in the last day (first run, or a day was missed)."""
    try:
        backups = list_backups(storage)
    except Exception:
        logger.exception("Could not list backups; backing up to be safe")
        return True
    return not backups or now - backups[0]["modified"] > timedelta(hours=24)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--once", action="store_true", help="make one backup now and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from web import storage

    if not storage.storage_configured():
        logger.error("Object storage is not configured (S3_*); nothing to back up to")
        return 1
    keep = int(_env("BACKUP_KEEP", "3"))
    hour = int(_env("BACKUP_HOUR_UTC", "0"))

    if args.once:
        backup_once(storage, keep)
        return 0

    logger.info(f"Daily backups at {hour:02d}:00 UTC to {PREFIX}, keeping the newest {keep}")
    pending = is_due(storage, datetime.now(timezone.utc))
    while True:
        if pending:
            try:
                backup_once(storage, keep)
                pending = False
            except Exception:
                # The older backups stay untouched; try again in an hour
                # rather than leaving a whole day without a fresh copy.
                logger.exception(f"Backup failed; retrying in {RETRY_AFTER_SECONDS // 60} min")
                time.sleep(RETRY_AFTER_SECONDS)
                continue
        wait = seconds_until_next(datetime.now(timezone.utc), hour)
        logger.info(f"Next backup in {wait / 3600:.1f} h")
        time.sleep(wait)
        pending = True


if __name__ == "__main__":
    sys.exit(main())
