"""Pictures on a signed address: no sign-in headers needed, and the address opens only for the person it was made for.

A native app shows a picture from a plain URL (SwiftUI's AsyncImage takes no headers), so the address carries its own
proof: a signature over what it opens (a pet's photo or a document's picture, at the file's version), the person it
was made for, and an expiry.

The address changes once an hour and stays valid for one to two hours, so a list shown again within the hour gets the
same address and the picture comes from the cache. The picture size (``w``, ``h``) is not part of the signature: a
size changes nothing about who may see the picture.

Using the address checks two things every time: the signature, and that the person still sees the pet. Taking the
sharing away, or deactivating the account, ends the address at once, not at its expiry.
"""

import base64
import hashlib
import hmac
import os
import time
from functools import wraps
from typing import Callable, Optional

from bson import ObjectId
from bson.errors import InvalidId
from flask import g, request

import web.app as app
from web import storage
from web.configs import JWT_CONFIG
from web.errors import error_response
from web.helpers import check_pet_access

HOUR = 3600
# Made in hour k, the address is valid until the end of hour k+1 (so one to two hours): the same address for the hour.
VALID_HOURS_AFTER = 2
DEFAULT_BASE = "https://petzy.duckdns.org"  # the same default the letters use for their links (web/mail.py)


def _now() -> int:
    return int(time.time())


def _expiry(now: int) -> int:
    return (now // HOUR + VALID_HOURS_AFTER) * HOUR


def _signing_key() -> bytes:
    """The app's secret with a purpose of its own, so the same secret signs nothing else as this."""
    return hmac.new(JWT_CONFIG["secret_key"].encode(), b"petzy picture links v1", hashlib.sha256).digest()


def _signature(kind: str, resource_id: str, version: str, user_id: str, exp: int) -> str:
    message = "\n".join((kind, resource_id, version, user_id, str(exp))).encode()
    digest = hmac.new(_signing_key(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _object_id(value) -> Optional[ObjectId]:
    # ObjectId(None) would make a new id, so a missing value is no id at all.
    if value is None:
        return None
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


def viewer_id() -> Optional[str]:
    """The id of the person the request is for, read once per request."""
    if not hasattr(g, "picture_viewer_id"):
        username = getattr(request, "current_user", None)
        user = app.db["users"].find_one({"username": username}, {"_id": 1}) if username else None
        g.picture_viewer_id = str(user["_id"]) if user else None
    return g.picture_viewer_id


def signed_picture_url(path: str, kind: str, resource_id: str, version: str, query: str = "") -> Optional[str]:
    """The absolute address of a picture for the person asking now. None when nobody is asking: a picture is only
    ever given to someone."""
    user_id = viewer_id()
    if user_id is None:
        return None
    exp = _expiry(_now())
    parts = [query] if query else []
    parts += [f"uid={user_id}", f"exp={exp}", f"sig={_signature(kind, resource_id, version, user_id, exp)}"]
    base = os.getenv("APP_BASE_URL", DEFAULT_BASE).rstrip("/")
    return f"{base}{path}?{'&'.join(parts)}"


def _open_with_signature(kind: str, kwargs: dict):
    """Checks a signed address for its route. None when the picture may be served, with the person set for the route;
    otherwise the answer that refuses it."""
    args = request.args
    try:
        exp = int(args.get("exp", ""))
    except ValueError:
        return error_response("picture_link_invalid")
    now = _now()
    if exp < now or exp > now + VALID_HOURS_AFTER * HOUR:
        return error_response("picture_link_invalid")

    user_id = _object_id(args.get("uid"))
    user = app.db["users"].find_one({"_id": user_id}, {"username": 1, "is_active": 1}) if user_id else None
    if not user or user.get("is_active") is False:
        return error_response("picture_link_invalid")

    if kind == "pet-photo":
        record = app.db["pets"].find_one({"_id": _object_id(kwargs.get("pet_id"))})
        ref = (record or {}).get("photo_file_id")
        if not ref:
            return error_response("photo_not_found")
    else:
        record = app.db["documents"].find_one({"_id": _object_id(kwargs.get("id"))})
        ref = None if not record or record.get("scan") else record.get("file_id")
        if not ref:
            return error_response("record_not_found")

    expected = _signature(kind, str(record["_id"]), storage.file_version(ref), str(user_id), exp)
    # Bytes on both sides: compare_digest refuses text with characters outside ASCII.
    if not hmac.compare_digest(expected.encode(), args.get("sig", "").encode("utf-8", "replace")):
        return error_response("picture_link_invalid")

    username = user["username"]
    if kind == "document-file":
        # A document's picture also needs the pet to be seen by the person the address was made for, now.
        if not check_pet_access(record["pet_id"], username):
            return error_response("record_not_found")
        g.record = record
        g.pet_id = record["pet_id"]
    # The pet's picture checks the pet's sharing itself, in its route, as it does for a session.
    setattr(request, "current_user", username)
    g.current_user = username
    g.username = username
    return None


def picture_route(kind: str, session_guard: Callable) -> Callable:
    """Put on a picture route above its query validation: a signed address opens the picture, and every other request
    goes through the session check the route had before (``session_guard``)."""

    def decorator(view):
        guarded = session_guard(view)

        @wraps(view)
        def wrapper(*args, **kwargs):
            if "sig" not in request.args:
                return guarded(*args, **kwargs)
            refusal = _open_with_signature(kind, kwargs)
            if refusal is not None:
                return refusal
            return view(*args, **kwargs)

        return wrapper

    return decorator
