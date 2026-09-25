"""Move files still in GridFS into object storage (web/storage.py).

Pet photos and document files used to be GridFS files, referenced by their
24-hex id in ``pets.photo_file_id`` / ``documents.file_id``. This copies
each one to the bucket under its owner's prefix, checks the stored size,
repoints the record at the new key and only then deletes the GridFS file,
so an interrupted run loses nothing and a rerun skips what's done. The
old Mongo thumbnail cache is dropped (thumbnails regenerate in storage).

Runs on every deploy (.github/workflows/deploy.yaml):

    python -m scripts.migrate_files_to_s3            # migrate
    python -m scripts.migrate_files_to_s3 --dry-run  # only report
"""

import argparse
import logging
import sys

from bson import ObjectId

logger = logging.getLogger("migrate_files_to_s3")


def _ext(filename: str, content_type: str) -> str:
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    return {"image/webp": ".webp", "image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}.get(
        content_type, ""
    )


def _move(db, fs, storage, ref: str, owner: str, pet_id, kind: str, dry_run: bool):
    """Copy one GridFS file to storage; returns the new key (None when dry-run or missing)."""
    try:
        grid_file = fs.get(ObjectId(ref))
    except Exception as e:
        logger.warning(f"GridFS file {ref} is missing ({type(e).__name__}); leaving the record as it is")
        return None
    data = grid_file.read()
    content_type = grid_file.content_type or "application/octet-stream"
    if dry_run:
        return None
    key = storage.new_key(db, owner, pet_id, kind, _ext(getattr(grid_file, "filename", "") or "", content_type))
    storage.put_bytes(key, data, content_type)
    if storage.object_size(key) != len(data):
        storage.delete_object(key)
        raise RuntimeError(f"size check failed for {ref} -> {key}")
    return key


def migrate(db, fs, storage, dry_run: bool = False) -> dict:
    stats = {"photos": 0, "documents": 0, "missing": 0, "pending": 0}

    for pet in db.pets.find({"photo_file_id": {"$nin": [None, ""]}}):
        ref = str(pet["photo_file_id"])
        if storage.is_storage_key(ref):
            continue
        stats["pending"] += 1
        key = _move(db, fs, storage, ref, pet.get("owner") or "", pet["_id"], "photos", dry_run)
        if dry_run:
            continue
        if key is None:
            stats["missing"] += 1
            continue
        # Conditional on the old ref: a photo replaced meanwhile wins.
        if db.pets.update_one(
            {"_id": pet["_id"], "photo_file_id": pet["photo_file_id"]}, {"$set": {"photo_file_id": key}}
        ).modified_count:
            fs.delete(ObjectId(ref))
            stats["photos"] += 1
        else:
            storage.delete_object(key)

    for doc in db.documents.find({"file_id": {"$nin": [None, ""]}}):
        ref = str(doc["file_id"])
        if storage.is_storage_key(ref):
            continue
        stats["pending"] += 1
        pet = db.pets.find_one({"_id": ObjectId(doc["pet_id"])}) if ObjectId.is_valid(str(doc.get("pet_id"))) else None
        owner = (pet or {}).get("owner") or doc.get("username") or ""
        key = _move(db, fs, storage, ref, owner, doc.get("pet_id"), "documents", dry_run)
        if dry_run:
            continue
        if key is None:
            stats["missing"] += 1
            continue
        if db.documents.update_one(
            {"_id": doc["_id"], "file_id": doc["file_id"]}, {"$set": {"file_id": key}}
        ).modified_count:
            fs.delete(ObjectId(ref))
            stats["documents"] += 1
        else:
            storage.delete_object(key)

    if not dry_run:
        stats["thumbnails_dropped"] = db.image_thumbnails.delete_many({}).deleted_count
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="report what would move, change nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    from web import storage

    if not storage.storage_configured():
        logger.info("Object storage is not configured; nothing to migrate to.")
        return 0

    from web.app import db, fs

    stats = migrate(db, fs, storage, dry_run=args.dry_run)
    left = db["fs.files"].count_documents({})
    logger.info(f"{'Would move' if args.dry_run else 'Moved'}: {stats}; GridFS files left: {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
