"""What changed since a device last looked, for its offline copy: pets, documents, medications, intakes, medical records
and events.

The feed carries markers, not the records. A marker says which record changed (``kind``, ``id``), its pet, when it
changed (``updated_at``), and whether it is gone (``deleted``). The device fetches the records it wants through the list
and detail endpoints, and drops the ones a marker says are gone. A pet's marker covers what is under the pet: when a
pet is gone, the device takes the pet and everything it had off the device. A type of the records is no one's pet and is
shared by a whole household, so its marker names the type and leaves the pet empty.

A device asks with ``since`` (the moment it last looked, inclusive) and follows ``next_cursor`` through the pages. The
order is by change moment, then kind, then id, so each page starts just after the one before, and no change is lost or
repeated. A device that was away for longer than gone records are kept (30 days) gets ``reset``: it drops its copy and
starts again from the beginning.
"""

from datetime import datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, jsonify, request
from flask_pydantic_spec import Response

import web.app as app
from web.app import api
from web.helpers import utc_iso
from web.schemas import ErrorResponse, SyncQuery, SyncResponse
from web.security import login_required

sync_bp = Blueprint("sync", __name__)

KINDS = ("document", "event", "medical_record", "medication", "medication_intake", "pet")
# Gone records of these kinds are noted in DELETIONS. An event leaves a tombstone of its own (is_deleted), kept as long, and
# only comes here when it was erased with the type it belonged to: there was no document left to mark. An event type is
# named by its key, belongs to no pet, and has no document of its own to leave a tombstone in: it is only ever a deletion.
LOGGED_KINDS = ("document", "event", "event_type", "medical_record", "medication", "medication_intake", "pet")
# The collection each kind lives in, and the field that names its pet (none for a pet, which is its own pet).
LIVE = {
    "document": ("documents", "pet_id"),
    "event": ("events", "pet_id"),
    "medical_record": ("medical_records", "pet_id"),
    "medication": ("medications", "pet_id"),
    "medication_intake": ("medication_intakes", "pet_id"),
    "pet": ("pets", None),
}
DELETIONS = "sync_deletions"
KEEP_DELETIONS = timedelta(days=30)
EPOCH = datetime(1970, 1, 1)


def now_utc() -> datetime:
    """The moment as the database keeps it: UTC, without a zone."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc(moment: datetime) -> datetime:
    if moment.tzinfo is not None:
        return moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _object_id(value):
    """The value as an id the database can order and compare: an ObjectId for a document, and as it is otherwise, since
    an event type is named by its key, which is free text."""
    if not isinstance(value, str):
        return value
    try:
        return ObjectId(value)
    except InvalidId:
        return value


def pet_viewers(pet_id) -> list:
    """Who can see a pet now: its owner and the people it is shared with."""
    pet = app.db.pets.find_one({"_id": _object_id(pet_id)}, {"owner": 1, "shared_with": 1})
    if pet is None:
        return []
    return [pet["owner"], *pet.get("shared_with", [])]


def log_deletion(kind: str, record_id, pet_id, viewers=None, local_id=None) -> None:
    """Note that a record is gone, for the people who could see it.

    ``viewers`` defaults to the pet's owner and viewers now. Name them when the pet is already gone, or when only one
    person lost the pet (a pet taken off someone's list is a deletion for that person alone). ``local_id`` is the name
    the device gave the record: the note keeps it, so a create or an edit that comes by that name later is told the
    record was deleted, not made again or lost.
    """
    moment = now_utc()
    note = {
        "kind": kind,
        "entity_id": _object_id(record_id),
        "pet_id": _object_id(pet_id),
        "viewers": pet_viewers(pet_id) if viewers is None else list(viewers),
        "deleted_at": moment,
        "expires_at": moment + KEEP_DELETIONS,
    }
    if local_id:
        note["local_id"] = local_id
    app.db[DELETIONS].insert_one(note)


def _visible_pet_ids(username: str) -> list:
    """The pets the person can see now, each id in both forms: a pet's records may name it as text or as an ObjectId."""
    ids = [
        pet["_id"] for pet in app.db.pets.find({"$or": [{"owner": username}, {"shared_with": username}]}, {"_id": 1})
    ]
    return ids + [str(pet_id) for pet_id in ids]


def _cursor_text(position: tuple) -> str:
    moment, kind, record_id = position
    return f"{moment.isoformat()},{kind},{record_id}"


def _parse_cursor(text: str) -> tuple:
    """The position a cursor names. SyncQuery checked its shape already."""
    moment_text, kind, record_id = text.split(",", 2)
    return datetime.fromisoformat(moment_text), kind, record_id


def _after(time_field: str, id_field: str, kind: str, cursor: tuple) -> dict:
    """The records of one kind that come after the cursor in the feed's order: a later moment, or the same moment and a
    later id. Within the same moment the kinds are ordered by name, so a kind before the cursor's has nothing left at
    that moment and a kind after it has all of it."""
    moment, cursor_kind, cursor_id = cursor
    if kind < cursor_kind:
        return {time_field: {"$gt": moment}}
    if kind > cursor_kind:
        return {time_field: {"$gte": moment}}
    return {"$or": [{time_field: {"$gt": moment}}, {time_field: moment, id_field: {"$gt": _object_id(cursor_id)}}]}


def _item(kind: str, record_id, pet_id, moment: datetime, deleted: bool) -> dict:
    moment = _naive_utc(moment)
    record_id = str(record_id)
    return {
        "kind": kind,
        "id": record_id,
        "pet_id": str(pet_id),
        "updated_at": utc_iso(moment),
        "deleted": deleted,
        "_position": (moment, kind, record_id),
    }


def _changes(kind: str, username: str, visible_ids: list, since: datetime, cursor, limit: int) -> list:
    collection, _ = LIVE[kind]
    if kind == "pet":
        scope = {"$or": [{"owner": username}, {"shared_with": username}]}
    else:
        scope = {"pet_id": {"$in": visible_ids}}
    clauses = [scope, {"updated_at": {"$gte": since}}]
    if cursor is not None:
        clauses.append(_after("updated_at", "_id", kind, cursor))
    rows = app.db[collection].find({"$and": clauses}).sort([("updated_at", 1), ("_id", 1)]).limit(limit)
    items = []
    for row in rows:
        pet_id = row["_id"] if kind == "pet" else row["pet_id"]
        items.append(_item(kind, row["_id"], pet_id, row["updated_at"], bool(row.get("is_deleted"))))
    return items


def _gone(kind: str, username: str, since: datetime, cursor, limit: int) -> list:
    clauses = [{"kind": kind, "viewers": username}, {"deleted_at": {"$gte": since}}]
    if cursor is not None:
        clauses.append(_after("deleted_at", "entity_id", kind, cursor))
    rows = app.db[DELETIONS].find({"$and": clauses}).sort([("deleted_at", 1), ("entity_id", 1)]).limit(limit)
    return [_item(kind, row["entity_id"], row["pet_id"], row["deleted_at"], True) for row in rows]


@sync_bp.route("/api/sync", methods=["GET"])
@login_required
@api.validate(
    query=SyncQuery,
    resp=Response(HTTP_200=SyncResponse, HTTP_422=ErrorResponse),
    tags=["sync"],
)
def get_sync():
    """The changes since a moment, for a device's offline copy: markers of pets, documents, medications, intakes, medical records and events.

    Each marker has ``kind``, ``id``, ``pet_id``, ``updated_at`` (UTC, to the second) and ``deleted``: a record that is gone comes as ``deleted: true`` and the device drops it. The records themselves come from the list and detail endpoints. A pet that is gone takes its records with it, and the feed sends nothing for them.

    A gone event type comes as one marker of kind ``event_type``: ``id`` is the type's key (what the device stored it under) and ``pet_id`` is empty, because a type belongs to no pet and is shared by a whole household. A marker of a kind the device doesn't know is skipped, not applied: an app that predates ``event_type`` leaves its copy of the types alone and reads ``GET /api/event-types`` again when it next goes online.

    Ask with ``since`` (the moment of the last complete sync, minus a minute, so that nothing written during it is missed; a repeated marker is harmless) and follow ``next_cursor`` while ``has_more`` is true. ``sync_at`` is the server's moment for this answer. ``reset: true`` means the device was away longer than gone records are kept (30 days): it drops its copy and asks again without ``since``.
    """
    query = request.context.query  # type: ignore[attr-defined]
    username = request.current_user
    sync_at = now_utc()
    since = _naive_utc(datetime.fromisoformat(query.since.replace("Z", "+00:00"))) if query.since else EPOCH
    if since > EPOCH and since < sync_at - KEEP_DELETIONS:
        return jsonify(
            {"items": [], "next_cursor": None, "has_more": False, "reset": True, "sync_at": utc_iso(sync_at)}
        )

    cursor = _parse_cursor(query.after) if query.after else None
    limit = query.page_size + 1
    visible_ids = _visible_pet_ids(username)
    items = []
    for kind in KINDS:
        items.extend(_changes(kind, username, visible_ids, since, cursor, limit))
    for kind in LOGGED_KINDS:
        items.extend(_gone(kind, username, since, cursor, limit))
    items.sort(key=lambda item: item["_position"])

    page = items[: query.page_size]
    more = len(items) > query.page_size
    return jsonify(
        {
            "items": [{key: value for key, value in item.items() if key != "_position"} for item in page],
            "next_cursor": _cursor_text(page[-1]["_position"]) if more else None,
            "has_more": more,
            "reset": False,
            "sync_at": utc_iso(sync_at),
        }
    )
