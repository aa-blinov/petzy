"""What a device that writes offline needs from the stand: a name for a record it made, and the version it edited.

A native client keeps its writes in a queue and sends them later, so the same request can arrive twice and an edit can
arrive hours after the record changed somewhere else. The two answers to that live here, shared by every section.

``local_id`` is the name the device gave a record before the stand had given it an id. One record per name: a create
sent again is answered with the record it already made, and the record can be changed or removed by that name.

``base_version`` is the ``updated_at`` of the record as the device last read it. A change made from an older copy is
refused with 409 ``conflict`` and the record as it is now, because the stand does not merge: the device compares the
fields itself. Without ``base_version`` the change is applied as it always was.
"""

from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable, Optional

from bson.errors import InvalidId
from flask import g, jsonify

import web.app as app
from web.errors import error_response
from web.helpers import check_pet_access, utc_iso
from web.security import get_current_user, login_required
from web.sync import DELETIONS, _object_id

LOCAL_ID_MAX = 64


def clean_local_id(value: Optional[str]) -> Optional[str]:
    """The name as the device sent it, without spaces around it: an empty one names nothing."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        raise ValueError("Идентификатор записи не может быть пустым")
    return value


def record_version(record: dict) -> str:
    """The version of a record: when it last changed, as the API writes every timestamp.

    A record from before ``updated_at`` existed has its creation as the last change it had. A course keeps its own
    ``edited_at``: the stock moves with every dose and every pack (``updated_at``, which the feed reports), but it is not
    an edit of the course, and a device editing the course must not be told «изменили» because a dose was marked.
    """
    changed = record.get("edited_at") or record.get("updated_at") or record.get("created_at")
    if isinstance(changed, datetime):
        return utc_iso(changed)
    # Already written the API's way (a record that has been through its serializer).
    return changed if isinstance(changed, str) else ""


def next_stamp(record: dict) -> datetime:
    """The moment to write as a record's new ``updated_at``: now, but never within the second of its last change.

    The version is that moment to the second (a Swift client refuses a fraction), so two edits in one second would leave
    the version as it was, and an edit made from the old copy would pass for a current one. Every write of a record
    that is versioned moves the version on by at least a second: the stamp may run a second or two ahead of the clock
    while a record is edited in bursts, which nothing reads as a time of day.
    """
    now = datetime.now(timezone.utc).replace(microsecond=0)
    previous = record.get("edited_at") or record.get("updated_at") or record.get("created_at")
    if isinstance(previous, str):
        try:
            previous = datetime.fromisoformat(previous.replace("Z", "+00:00"))
        except ValueError:
            previous = None
    if isinstance(previous, datetime):
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        floor = previous.replace(microsecond=0) + timedelta(seconds=1)
        if now < floor:
            return floor
    return now


def is_stale(base_version: Optional[str], record: dict) -> bool:
    """Whether the device edited an older copy. Not sent: nothing to compare, and the change goes through."""
    return base_version is not None and base_version != record_version(record)


def conflict_answer(current: Any):
    """409 ``conflict`` with the record as it is now, so the client can show it and let the person choose."""
    response, status = error_response("conflict", "Запись изменили, пока вы её правили")
    body = response.get_json()
    body["record"] = current
    return jsonify(body), status


def version_guard(record: dict, base_version: Optional[str]) -> dict:
    """The part of an update's filter that makes the version check hold up to the write.

    The check above the write reads the record and the write comes later, so two edits in the same instant both pass
    it. With ``base_version`` the write names the ``updated_at`` it was checked against, and only one of them finds it.
    """
    if base_version is None:
        return {}
    field = "edited_at" if record.get("edited_at") is not None else "updated_at"
    return {field: record.get(field)}


def _tombstone(kind: str, username: str, **match) -> Optional[dict]:
    """The note that a record of this kind is gone, if the person could see it. Notes are kept for thirty days."""
    return app.db[DELETIONS].find_one({"kind": kind, "viewers": username, **match})


def deleted_by_id_answer(kind: str, record_id: str, username: str):
    """409 ``record_deleted`` when the id names a record that was deleted and the person could see it, else None.

    A record that is gone and one that never was look alike to everyone who could not see it, so only people who
    could answer differently: 404 stays for the rest.
    """
    try:
        entity = _object_id(record_id)
    except (InvalidId, TypeError):
        return None
    if _tombstone(kind, username, entity_id={"$in": [entity, str(record_id)]}):
        return error_response("record_deleted")
    return None


def deleted_by_local_id_answer(kind: str, local_id: str, username: str):
    """The same for a record the device names by its ``local_id``."""
    if local_id and _tombstone(kind, username, local_id=local_id):
        return error_response("record_deleted")
    return None


def tombstone_for_name(kind: str, local_id: str, pet_id: Optional[str] = None) -> Optional[dict]:
    """A record of this kind that was deleted under this name (for a create that repeats after the delete)."""
    match: dict[str, Any] = {"kind": kind, "local_id": local_id}
    if pet_id is not None:
        match["pet_id"] = {"$in": [_object_id(pet_id), str(pet_id)]}
    return app.db[DELETIONS].find_one(match)


def require_local_record_access(
    collection: str, kind: str, *, owner_only: bool = False, tell_deleted: bool = True, extra_filter=None
):
    """The access check of ``require_record_access`` for a record the device names by ``local_id`` in the path.

    An unknown name and a record of a pet the caller cannot see answer alike: 404 ``record_not_found``. A name that
    belonged to a record that was deleted answers 409 ``record_deleted``, for a person who could see that record.
    A delete does not ask for the news (``tell_deleted=False``): a record that is gone is not there to delete, as in the
    feed. ``owner_only`` is for pets, where the owner alone may change the record. Sets ``g.username``, ``g.record``,
    ``g.pet_id``, as the access check by id does.
    """

    def decorator(view: Callable):
        @login_required
        @wraps(view)
        def decorated(*args, **kwargs):
            username, auth_error = get_current_user()
            if auth_error:
                return auth_error[0], auth_error[1]
            local_id = kwargs.get("local_id")
            record = app.db[collection].find_one({"local_id": local_id, **(extra_filter or {})}) if local_id else None
            if record is None:
                gone = deleted_by_local_id_answer(kind, local_id, username) if tell_deleted else None
                return gone or error_response("record_not_found")
            pet_id = record["_id"] if collection == "pets" else record.get("pet_id")
            if not pet_id or not check_pet_access(pet_id, username):
                return error_response("record_not_found")
            if owner_only and record.get("owner") != username:
                return error_response("owner_action_forbidden")
            g.username = username
            g.record = record
            g.pet_id = str(pet_id)
            return view(*args, **kwargs)

        return decorated

    return decorator


__all__ = [
    "LOCAL_ID_MAX",
    "clean_local_id",
    "conflict_answer",
    "deleted_by_id_answer",
    "deleted_by_local_id_answer",
    "is_stale",
    "record_version",
    "require_local_record_access",
    "tombstone_for_name",
    "version_guard",
]
