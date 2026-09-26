"""Object storage (S3-compatible, Backblaze B2 in production) for every file.

Pet photos, documents, their thumbnails and scans all live in one private
bucket; MongoDB keeps only the records that point at them. Files used to
sit in GridFS, which put them in the daily database dumps (a week of
retention on a few GB of disk) and made the database the file server.

Separation between users
    The bucket is private and the app's key never leaves the server. Every
    read and write goes through an authenticated request that checks
    access to the pet first; the browser only ever gets a short-lived URL
    signed for one exact object. Keys are namespaced by the pet's owner:

        users/<owner user id>/pets/<pet id>/<kind>/<uuid><ext>
        users/<...>/<uuid>.webp.thumbs/<w>x<h>.webp      (thumbnails)

    so one user's objects can be listed, exported or removed together.

Scans (MRI/CT/X-ray archives, up to 500 MB) don't pass through the server
at all: the client gets a signed PUT URL, uploads straight to the bucket
(the host proxy in front of the stack caps bodies at 10 MB), and we check
the object's size and first bytes before a document exists.

Configured by S3_ENDPOINT, S3_REGION, S3_BUCKET, S3_KEY_ID, S3_SECRET_KEY.
S3_PREFIX (empty in production) puts every key under a namespace: local
runs (scripts/dev_local.py) share the production bucket under "dev/".
"""

import hashlib
import os
import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional
from uuid import uuid4

MAX_SCAN_BYTES = 500 * 1024 * 1024
UPLOAD_URL_TTL_SECONDS = 2 * 60 * 60  # long enough for 500 MB on a slow link
DOWNLOAD_URL_TTL_SECONDS = 10 * 60
# Scan upload slots never confirmed (tab closed, upload failed) are removed
# together with whatever reached the bucket after this long.
ABANDONED_UPLOAD_AFTER = timedelta(hours=6)

# Origins allowed to PUT scans straight to the bucket and read signed URLs.
CORS_ORIGINS = ["https://petzy.duckdns.org", "http://localhost:5173", "http://localhost:4173"]

# Extension -> (content type stored with the object, format family checked
# against the file's first bytes).
SCAN_FORMATS: dict[str, tuple[str, str]] = {
    ".zip": ("application/zip", "zip"),
    ".7z": ("application/x-7z-compressed", "7z"),
    ".rar": ("application/vnd.rar", "rar"),
    ".tar": ("application/x-tar", "tar"),
    ".tar.gz": ("application/gzip", "gzip"),
    ".tgz": ("application/gzip", "gzip"),
    ".gz": ("application/gzip", "gzip"),
    ".dcm": ("application/dicom", "dicom"),
    ".iso": ("application/x-iso9660-image", "iso"),
}
SCAN_CONTENT_TYPES = {content_type for content_type, _ in SCAN_FORMATS.values()}

# Enough of the file to see every signature below (ISO's sits at 32 KB).
SNIFF_BYTES = 32 * 1024 + 8


class StorageNotConfigured(RuntimeError):
    """S3_* settings are missing; files can't be stored or read."""


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def storage_configured() -> bool:
    return all(_env(n) for n in ("S3_ENDPOINT", "S3_BUCKET", "S3_KEY_ID", "S3_SECRET_KEY"))


@lru_cache(maxsize=1)
def _client():
    if not storage_configured():
        raise StorageNotConfigured("S3_ENDPOINT, S3_BUCKET, S3_KEY_ID and S3_SECRET_KEY must be set")
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=_env("S3_ENDPOINT"),
        region_name=_env("S3_REGION") or None,
        aws_access_key_id=_env("S3_KEY_ID"),
        aws_secret_access_key=_env("S3_SECRET_KEY"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def reset_client() -> None:
    """Forget the cached client (tests switch endpoints and credentials)."""
    _client.cache_clear()


def _bucket() -> str:
    return _env("S3_BUCKET")


# ---------------------------------------------------------------- keys


_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def is_storage_key(ref: Optional[str]) -> bool:
    """True for an object key; False for a legacy GridFS id (24 hex chars)."""
    return bool(ref) and "/" in str(ref)


def owner_id(db, username: str) -> str:
    """Stable id for a user's key prefix (their user _id, not the username)."""
    user = db.users.find_one({"username": username}, {"_id": 1})
    return str(user["_id"]) if user else "u-" + _SAFE.sub("_", username or "unknown")


def key_prefix() -> str:
    """Namespace in front of every key: "" in production, "dev/" locally."""
    prefix = _env("S3_PREFIX").strip("/")
    return f"{prefix}/" if prefix else ""


def pet_prefix(db, owner_username: str, pet_id) -> str:
    """Everything stored for one pet: users/<owner id>/pets/<pet id>/."""
    return f"{key_prefix()}users/{owner_id(db, owner_username)}/pets/{_SAFE.sub('_', str(pet_id))}/"


def new_key(db, owner_username: str, pet_id, kind: str, ext: str) -> str:
    """A fresh key under the pet's prefix: users/<id>/pets/<pet>/<kind>/<uuid><ext>."""
    ext = ext if re.fullmatch(r"(\.[a-z0-9]{1,5}){1,2}", ext or "") else ""
    return f"{pet_prefix(db, owner_username, pet_id)}{kind}/{uuid4().hex}{ext}"


def file_version(ref) -> str:
    """Opaque token for a stored file, for ETags and cache-busting URLs.

    Changes whenever the file does, without handing the key (and with it
    the owner's id and the bucket layout) to the client.
    """
    return hashlib.sha1(str(ref).encode()).hexdigest()[:16]


def thumb_prefix(key: str) -> str:
    return f"{key}.thumbs/"


def thumb_key(key: str, width: Optional[int], height: Optional[int]) -> str:
    return f"{thumb_prefix(key)}{width or 0}x{height or 0}.webp"


# ---------------------------------------------------------------- objects


def put_bytes(key: str, data: bytes, content_type: str) -> None:
    _client().put_object(Bucket=_bucket(), Key=key, Body=data, ContentType=content_type)


def put_file(key: str, path: str, content_type: str) -> None:
    """Upload a file from disk (multipart for big ones, e.g. backups)."""
    _client().upload_file(path, _bucket(), key, ExtraArgs={"ContentType": content_type})


def list_objects(prefix: str) -> list[dict]:
    """Current objects under ``prefix``: [{"key", "size", "modified"}]."""
    client = _client()
    kwargs = {"Bucket": _bucket(), "Prefix": prefix}
    found = []
    while True:
        page = client.list_objects_v2(**kwargs)
        for obj in page.get("Contents", []):
            found.append({"key": obj["Key"], "size": obj["Size"], "modified": obj["LastModified"]})
        if not page.get("IsTruncated"):
            return found
        kwargs["ContinuationToken"] = page["NextContinuationToken"]


def get_bytes(key: str) -> tuple[bytes, str]:
    obj = _client().get_object(Bucket=_bucket(), Key=key)
    body = obj["Body"]
    try:
        return body.read(), obj.get("ContentType") or "application/octet-stream"
    finally:
        body.close()


def _is_missing(error) -> bool:
    return error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound")


def get_bytes_if_exists(key: str) -> Optional[tuple[bytes, str]]:
    from botocore.exceptions import ClientError

    try:
        return get_bytes(key)
    except ClientError as e:
        if _is_missing(e):
            return None
        raise


def object_size(key: str) -> Optional[int]:
    """Size of the stored object, or None when it isn't there."""
    from botocore.exceptions import ClientError

    try:
        return int(_client().head_object(Bucket=_bucket(), Key=key)["ContentLength"])
    except ClientError as e:
        if _is_missing(e):
            return None
        raise


def read_head(key: str) -> bytes:
    body = _client().get_object(Bucket=_bucket(), Key=key, Range=f"bytes=0-{SNIFF_BYTES - 1}")["Body"]
    try:
        return body.read()
    finally:
        body.close()


def _versions(prefix: str):
    """Every stored version (and delete marker) under ``prefix``.

    The production bucket keeps all versions, where a plain DeleteObject
    only adds a marker that hides the file and the bytes stay. Deleting a
    user's document has to actually remove it, so deletes go version by
    version.
    """
    client = _client()
    kwargs = {"Bucket": _bucket(), "Prefix": prefix}
    while True:
        page = client.list_object_versions(**kwargs)
        for v in page.get("Versions", []) + page.get("DeleteMarkers", []):
            yield {"Key": v["Key"], "VersionId": v["VersionId"]}
        if not page.get("IsTruncated"):
            return
        kwargs["KeyMarker"] = page.get("NextKeyMarker")
        kwargs["VersionIdMarker"] = page.get("NextVersionIdMarker")


def _delete_versions(objects: list) -> None:
    client = _client()
    for i in range(0, len(objects), 1000):
        client.delete_objects(Bucket=_bucket(), Delete={"Objects": objects[i : i + 1000], "Quiet": True})


def delete_object(key: str) -> None:
    """Remove ``key`` for good: every version, not just the latest."""
    objects = [v for v in _versions(key) if v["Key"] == key]
    if objects:
        _delete_versions(objects)
    else:
        _client().delete_object(Bucket=_bucket(), Key=key)


def delete_prefix(prefix: str) -> int:
    """Remove every object (all versions) under ``prefix``. Returns how many keys."""
    objects = list(_versions(prefix))
    _delete_versions(objects)
    return len({o["Key"] for o in objects})


# ---------------------------------------------------------------- signed URLs


def upload_url(key: str, content_type: str, size: int) -> str:
    """A signed PUT URL for one exact key, content type and size.

    Content-Length is one of the signed headers, so the bucket refuses a
    body of any other size: nobody can park more than they declared (and
    we checked against MAX_SCAN_BYTES) behind a slot.
    """
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": _bucket(), "Key": key, "ContentType": content_type, "ContentLength": size},
        ExpiresIn=UPLOAD_URL_TTL_SECONDS,
    )


def download_url(key: str, content_disposition: str) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": key, "ResponseContentDisposition": content_disposition},
        ExpiresIn=DOWNLOAD_URL_TTL_SECONDS,
    )


def ensure_bucket_cors(logger=None) -> bool:
    """Allow the app's origins to PUT scans and GET signed URLs directly.

    Best effort at startup: the upload of anything else never needs it.
    Returns whether the rules are in place.
    """
    rules = [
        {
            "AllowedOrigins": CORS_ORIGINS,
            "AllowedMethods": ["PUT", "GET", "HEAD"],
            "AllowedHeaders": ["content-type", "content-length"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3600,
        }
    ]
    try:
        client = _client()
        try:
            current = client.get_bucket_cors(Bucket=_bucket()).get("CORSRules", [])
        except Exception:
            current = []
        if _same_rules(current, rules):
            return True
        client.put_bucket_cors(Bucket=_bucket(), CORSConfiguration={"CORSRules": rules})
        if logger:
            logger.info("Bucket CORS rules set for scan uploads")
        return True
    except Exception as e:  # pragma: no cover - depends on the key's rights
        if logger:
            logger.warning(f"Could not set bucket CORS rules (scan uploads from the browser need them): {e}")
        return False


def _same_rules(current: list, wanted: list) -> bool:
    # Header names are case-insensitive, and B2 hands them back lowercased
    # ("ETag" comes back as "etag"); origins and methods are compared as sets.
    def norm(rule):
        return {
            k: sorted(x.lower() if k.endswith("Headers") else x for x in v) if isinstance(v, list) else v
            for k, v in rule.items()
            if k != "ID"
        }

    return [norm(r) for r in current] == [norm(r) for r in wanted]


# ---------------------------------------------------------------- scans


def scan_format(filename: str) -> Optional[tuple[str, str, str]]:
    """(extension, content type, family) for an accepted scan filename."""
    lower = (filename or "").lower()
    for ext in sorted(SCAN_FORMATS, key=len, reverse=True):  # ".tar.gz" before ".gz"
        if lower.endswith(ext):
            content_type, family = SCAN_FORMATS[ext]
            return ext, content_type, family
    return None


def matches_family(head: bytes, family: str) -> bool:
    """Whether the file's first bytes are what its extension claims."""
    if family == "zip":
        return head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    if family == "7z":
        return head.startswith(b"7z\xbc\xaf\x27\x1c")
    if family == "rar":
        return head.startswith(b"Rar!\x1a\x07")
    if family == "gzip":
        return head.startswith(b"\x1f\x8b")
    if family == "tar":
        return head[257:262] == b"ustar"
    if family == "dicom":
        return head[128:132] == b"DICM"
    if family == "iso":
        return head[32769:32774] == b"CD001"
    return False


def cleanup_abandoned_uploads(db, now: Optional[datetime] = None) -> int:
    """Drop scan upload slots never confirmed within ABANDONED_UPLOAD_AFTER.

    Called from the reminders worker's loop, the app's one periodic
    process. Returns how many were removed.
    """
    if not storage_configured():
        return 0
    cutoff = (now or datetime.now(timezone.utc)) - ABANDONED_UPLOAD_AFTER
    removed = 0
    for slot in db.document_uploads.find({"created_at": {"$lt": cutoff}}):
        try:
            delete_object(slot["key"])
        except Exception:
            continue  # try again on the next pass rather than leak the object
        db.document_uploads.delete_one({"_id": slot["_id"]})
        removed += 1
    return removed
