"""Generic event-type registry and events CRUD.

Replaces the old per-type hand-rolled collections (asthma_attacks,
defecations, litter_changes, weights, feedings, eye_drops, tooth_brushing,
ear_cleaning) and their duplicated schemas/routes/messages/export specs with
one ``event_types`` registry (builtin + user-defined) and one ``events``
collection. Adding a type — builtin or user-created — is a document, not code.

Medications keep their own module: courses, doses, and inventory are a
different domain (scheduled, stateful) from a point-in-time event log.
"""

import math
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Optional
from uuid import uuid4

from flask import Blueprint, g, jsonify, request
from flask_pydantic_spec import Request, Response

import web.app as app  # use app.db and app.logger so test patches are visible
from web.app import api
from web.configs import PUSH_CONFIG
from web.decorators import pat_allowed, require_pet_access, require_record_access
from web.errors import error_response
from web.helpers import (
    LIVE_EVENT_FILTER,
    check_pet_access,
    parse_event_datetime_safe,
    ru_dose_unit,
    utc_iso,
    valid_tz,
    zoned_iso,
)
from web.messages import get_message
from web.push_delivery import get_pet_push_subscriptions, send_push_to_subscriptions
from web.trend_alerts import detect_anomaly
from web.schemas import (
    EventItem,
    UsedEventTypesResponse,
    ErrorResponse,
    EventCreate,
    EventListQuery,
    EventListResponse,
    EventTypeCreate,
    EventTypeItem,
    EventTypeListResponse,
    EventTypeUpdate,
    EventUpdate,
    HealthStatsQuery,
    HealthStatsResponse,
    PetIdQuery,
    SuccessResponse,
    TimelineQuery,
    TimelineResponse,
)
from web.builtin_event_types import BUILTIN_TYPE_ORDER, HARD_BOUNDS
from web.security import get_current_user, is_admin, login_required
from web.idempotency import idempotent
from web.save_lock import acquire, release
from web.offline import conflict_answer, is_stale, next_stamp, version_guard
from web.sync import log_deletion


events_bp = Blueprint("events", __name__)

EVENTS_COLLECTION = "events"
EVENT_TYPES_COLLECTION = "event_types"

DUPLICATE_EVENT_WINDOW = timedelta(minutes=5)
"""How long after saving a record the very same request is still the same record. A request whose
answer never arrived says nothing about whether the record was written, so the person presses
«Создать» again, and the diary must not answer that with a second entry."""


# ---------------------------------------------------------------------------
# Event type registry
# ---------------------------------------------------------------------------


def _serialize_event_type(doc: dict) -> dict:
    return {
        "key": doc["key"],
        "label": doc["label"],
        "icon": doc["icon"],
        "color": doc["color"],
        "is_builtin": doc.get("is_builtin", False),
        "category": doc.get("category"),
        "created_by": doc.get("created_by"),
        "fields": doc.get("fields", []),
        "chart": doc.get("chart") or {"kind": "count"},
    }


def _household(username: str) -> set[str]:
    """The user and everyone they share a pet with, either way round."""
    people = {username}
    for pet in app.db.pets.find(
        {"$or": [{"owner": username}, {"shared_with": username}]}, {"owner": 1, "shared_with": 1}
    ):
        people.add(pet.get("owner"))
        people.update(pet.get("shared_with") or [])
    people.discard(None)
    return people


def _visible_types_query(username: str) -> dict:
    """Builtin types, plus custom ones made in the user's household.

    Custom types used to be one list for the whole server: every user saw
    every other household's type names. A household (the people sharing
    pets) still sees one another's, or a shared pet's records of the
    owner's type would have nothing to render them by.
    """
    return {"$or": [{"is_builtin": True}, {"created_by": {"$in": sorted(_household(username))}}]}


def _find_visible_type(key: str, username: str) -> Optional[dict]:
    return app.db[EVENT_TYPES_COLLECTION].find_one({"$and": [{"key": key}, _visible_types_query(username)]})


def _same_label(text: str) -> str:
    """What makes two names one: the case and the spaces do not count."""
    return " ".join((text or "").split()).casefold()


# What a re-save of a field keeps when the payload says nothing about it: the range a number is checked against and
# how far it may drift before it counts as a trend anomaly. A form that has no inputs for these sends them as absent,
# and a plain overwrite dropped them: renaming a built-in type silently turned a weight capped at 100 into any float.
NUMERIC_FIELD_SETTINGS = ("max", "step", "deviation_threshold")


def _keep_numeric_settings(new_fields: list[dict], stored_fields: list[dict]) -> list[dict]:
    """Carry over the stored bounds of the fields the update still has, by name.

    Only what the payload leaves out is carried over, so a field that is
    explicitly given a bound gets the one that was asked for.
    """
    stored = {f.get("name"): f for f in stored_fields or [] if f.get("name")}
    kept: list[dict] = []
    for field in new_fields:
        previous = stored.get(field.get("name"))
        if previous:
            for setting in NUMERIC_FIELD_SETTINGS:
                if field.get(setting) is None and previous.get(setting) is not None:
                    field[setting] = previous[setting]
        kept.append(field)
    return kept


def _label_is_taken(label: str, username: str, own_key: Optional[str] = None) -> bool:
    """A type with this name is already among the ones the user sees (built-in or the household's): two tiles of one name
    cannot be told apart in the sheet that adds a record and in the filter of the history."""
    wanted = _same_label(label)
    return any(
        doc["key"] != own_key and _same_label(doc.get("label", "")) == wanted
        for doc in app.db[EVENT_TYPES_COLLECTION].find(_visible_types_query(username), {"key": 1, "label": 1})
    )


def _generate_event_type_key() -> str:
    """A stable, opaque id for a custom type — the label is free text (any
    language/characters) and only used for display, so the key is generated
    rather than slugified from it."""
    return f"custom_{uuid4().hex[:10]}"


@events_bp.route("/api/event-types", methods=["GET"])
@login_required
@pat_allowed("pets:read")
@api.validate(resp=Response(HTTP_200=EventTypeListResponse), tags=["events"])
def list_event_types():
    """List the event types this user can use: builtin, and their household's.

    Built-in types are the same for everyone and are renamed only by an administrator. A household's own types are visible to everyone you share any pet with, either way round. Only the person who made a custom type may change or remove it; removing a type that has records takes ``?with_events=true`` and deletes those records too.
    """
    username, _ = get_current_user()
    docs = list(app.db[EVENT_TYPES_COLLECTION].find(_visible_types_query(username)))
    docs.sort(key=_registry_order)
    return jsonify({"event_types": [_serialize_event_type(d) for d in docs]})


def _registry_order(doc: dict) -> tuple:
    """Builtin types in BUILTIN_TYPE_ORDER, then custom ones by name."""
    if doc.get("is_builtin"):
        key = doc.get("key")
        rank = BUILTIN_TYPE_ORDER.index(key) if key in BUILTIN_TYPE_ORDER else len(BUILTIN_TYPE_ORDER)
        return (0, rank, doc.get("label", ""))
    return (1, 0, (doc.get("label") or "").lower())


@events_bp.route("/api/event-types", methods=["POST"])
@login_required
@api.validate(
    body=Request(EventTypeCreate),
    resp=Response(HTTP_201=EventTypeItem, HTTP_422=ErrorResponse),
    tags=["events"],
)
@login_required
@idempotent
def create_event_type():
    """Create a custom event type.

    Everyone you share any pet with sees it at once, the person who made it included. The name has to be free among the built-in types and the household's own, case and spaces ignored (422 ``event_type_label_taken``): two types under one name make a record impossible to tell apart later. ``color`` is one of brown, orange, red, green, purple, teal, cyan, yellow, blue, pink, gray; ``icon`` is 1-50 of a-z, 0-9, ``_`` and ``-``. Field names must be unique and cannot be pet_id, date, time, comment, type or fields; a number field with no ``min`` gets ``min: 0``. With ``chart.kind: "value"``, ``value_field`` names a number field of the type.
    """
    # @login_required already guarantees request.current_user is set.
    username, _ = get_current_user()

    data = request.context.body  # type: ignore[attr-defined]
    if _label_is_taken(data.label, username):
        return error_response("event_type_label_taken")
    doc = {
        "key": _generate_event_type_key(),
        "label": data.label,
        "icon": data.icon,
        "color": data.color,
        "is_builtin": False,
        "created_by": username,
        "fields": [f.model_dump() for f in data.fields],
        "chart": data.chart.model_dump(),
        "created_at": datetime.now(timezone.utc),
    }
    app.db[EVENT_TYPES_COLLECTION].insert_one(doc)
    app.logger.info(f"Event type created: key={doc['key']}, user={username}")
    return jsonify(_serialize_event_type(doc)), 201


@events_bp.route("/api/event-types/<key>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(EventTypeUpdate),
    resp=Response(HTTP_403=ErrorResponse, HTTP_200=EventTypeItem, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["events"],
)
@login_required
def update_event_type(key):
    """Update an event type's label/icon/color/fields/chart.

    A custom type by its author only (403 ``event_type_not_yours``). A builtin type is the same for every
    user, so renaming it renamed it for everyone: an admin's change only (403 ``event_type_builtin_admin_only``).
    The rules of creation apply: a value chart must name a number field of the type as it will be after the change,
    so a chart sent alone is checked against the stored fields and fields sent alone against the stored chart
    (422 ``validation_error``). When ``fields`` is sent again, ``max``, ``step`` and ``deviation_threshold``
    left out of a field are kept from the stored field of the same name.
    """
    # @login_required already guarantees request.current_user is set.
    username, _ = get_current_user()

    existing = _find_visible_type(key, username)
    if not existing:
        return error_response("event_type_not_found")
    if existing.get("is_builtin") and not is_admin(username):
        return error_response("event_type_builtin_admin_only")
    if not existing.get("is_builtin") and existing.get("created_by") != username:
        return error_response("event_type_not_yours")

    data = request.context.body  # type: ignore[attr-defined]
    update_data: dict[str, Any] = {}
    if data.label is not None:
        # An old duplicate may be saved as it is (its colour changed, say): only a name that is new is checked.
        if _same_label(data.label) != _same_label(existing.get("label", "")) and _label_is_taken(
            data.label, username, key
        ):
            return error_response("event_type_label_taken")
        update_data["label"] = data.label
    if data.icon is not None:
        update_data["icon"] = data.icon
    if data.color is not None:
        update_data["color"] = data.color
    if data.fields is not None:
        update_data["fields"] = _keep_numeric_settings(
            [f.model_dump() for f in data.fields], existing.get("fields", [])
        )
    if data.chart is not None:
        update_data["chart"] = data.chart.model_dump()
    # A chart of values must name a number field of the type as it will be after this change, whichever of the
    # two came: a chart sent alone is checked against the stored fields, fields sent alone against the stored chart.
    if data.chart is not None or data.fields is not None:
        chart = update_data.get("chart", existing.get("chart")) or {}
        fields = update_data.get("fields", existing.get("fields", []))
        numbers = {f.get("name") for f in fields if f.get("type") == "number"}
        if chart.get("kind") == "value" and chart.get("value_field") not in numbers:
            return error_response("validation_error", "Для графика значений нужно выбрать числовое поле типа")

    if update_data:
        app.db[EVENT_TYPES_COLLECTION].update_one({"key": key}, {"$set": update_data})
        existing.update(update_data)

    app.logger.info(f"Event type updated: key={key}, user={username}")
    return jsonify(_serialize_event_type(existing)), 200


def _flag(name: str) -> bool:
    """A yes/no query value: ``true``, ``1``, ``yes`` or ``on``, any case. Only ``true`` used to count, and ``1`` asked
    for a preview went on to delete for real."""
    return (request.args.get(name) or "").strip().lower() in ("true", "1", "yes", "on")


@events_bp.route("/api/event-types/<key>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_403=ErrorResponse, HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["events"],
)
@login_required
def delete_event_type(key):
    """Delete a custom event type.

    Builtin types can't be deleted (422 ``event_type_builtin_immutable``), and another person's type
    can't either (403 ``event_type_not_yours``). A type with records answers 422 ``event_type_has_events``
    with ``events_count``; repeated with ``?with_events=true`` it deletes the type together with its records.

    Only records on the pets this person can open are counted and deleted. A type with a record on any other pet
    answers 422 ``event_type_has_events_elsewhere``, the preview too, and nothing is deleted.

    ``?preview=true`` counts the records on the pets this person can open and deletes nothing (the answer carries
    ``events_count``), so the question «удалить тип вместе с записями?» is asked once, with the number in it.
    ``preview`` and ``with_events`` take ``true``, ``1``, ``yes`` or ``on``, any case.

    The deletion is told to the devices that sync (``GET /api/sync``): one marker of kind ``event_type`` for the type, and
    one ``event`` marker for each record erased with it, for everyone in the household.
    """
    # @login_required already guarantees request.current_user is set.
    username, _ = get_current_user()

    existing = _find_visible_type(key, username)
    if not existing:
        return error_response("event_type_not_found")
    if existing.get("is_builtin"):
        return error_response("event_type_builtin_immutable")
    if existing.get("created_by") != username:
        return error_response("event_type_not_yours")
    # The pets this person may open follow the same rule as the pet list (get_pets): their own and the shared ones.
    pets = app.db.pets.find({"$or": [{"owner": username}, {"shared_with": username}]}, {"_id": 1})
    accessible_pet_ids = [str(pet["_id"]) for pet in pets]
    # A record on a pet this person cannot open is someone else's diary entry. Then nothing changes, and the preview
    # refuses too, so no deletion is offered that the delete itself would refuse.
    if app.db[EVENTS_COLLECTION].find_one(
        {"type": key, "pet_id": {"$nin": accessible_pet_ids}, **LIVE_EVENT_FILTER}, {"_id": 1}
    ):
        return error_response("event_type_has_events_elsewhere")
    count = app.db[EVENTS_COLLECTION].count_documents(
        {"type": key, "pet_id": {"$in": accessible_pet_ids}, **LIVE_EVENT_FILTER}
    )
    if _flag("preview"):
        return jsonify({"success": True, "message": "", "events_count": count}), 200
    with_events = _flag("with_events")
    if count > 0 and not with_events:
        # Says how many, so that the client can ask «delete the type with its N records?» instead of refusing flatly.
        response, status = error_response("event_type_has_events")
        body = response.get_json()
        body["events_count"] = count
        return jsonify(body), status
    if count > 0:
        live = {"type": key, "pet_id": {"$in": accessible_pet_ids}, **LIVE_EVENT_FILTER}
        records = list(app.db[EVENTS_COLLECTION].find(live, {"_id": 1, "pet_id": 1}))
        app.db[EVENTS_COLLECTION].delete_many({"type": key, "pet_id": {"$in": accessible_pet_ids}})
        for record in records:
            # A record deleted on its own stays as a tombstone of its own and needs no note here. These are erased, so
            # the devices that keep their own copy are told another way — the same note every other deletion leaves.
            log_deletion("event", record["_id"], record["pet_id"])
        app.logger.info(f"Event type records deleted with it: key={key}, count={count}, user={username}")

    app.db[EVENT_TYPES_COLLECTION].delete_one({"key": key})
    # The type is gone from the registry, and a device that has been offline keeps its own copy of it: without this note
    # it would go on offering a type the server no longer has. Everyone in the household could see it, so everyone in
    # the household is told.
    log_deletion("event_type", key, "", viewers=sorted(_household(username)))
    app.logger.info(f"Event type deleted: key={key}, user={username}")
    return get_message("event_type_deleted")


# ---------------------------------------------------------------------------
# Events CRUD
# ---------------------------------------------------------------------------


def _validate_event_fields(
    raw_fields: dict, field_defs: list, type_key: Optional[str] = None
) -> tuple[Optional[dict], Optional[str]]:
    """Coerce & validate a ``fields`` payload against an event type's schema.

    Keys not declared on the type are silently dropped — the same "process
    only fields defined in the config" convention the frontend form already
    follows (see ``HealthRecordForm.normalizeData``).
    """
    cleaned: dict[str, Any] = {}
    for field_def in field_defs:
        name = field_def["name"]
        value = raw_fields.get(name)
        if value is None or value == "":
            if field_def.get("required"):
                return None, f"Поле «{field_def['label']}» обязательно"
            continue

        field_type = field_def["type"]
        if field_type == "number":
            # bool is an int in Python and float(True) is 1.0: a flag in a number field is refused, not stored as 1.
            if isinstance(value, bool):
                return None, f"Поле «{field_def['label']}» должно быть числом"
            try:
                value = float(value)
            except (TypeError, ValueError, OverflowError):  # OverflowError: an integer too large for a float
                return None, f"Поле «{field_def['label']}» должно быть числом"
            # NaN passes every bound below (comparisons with it are false), and Infinity passes a field with no max.
            if not math.isfinite(value):
                return None, f"Поле «{field_def['label']}» должно быть числом"
            field_min = field_def.get("min")
            field_max = field_def.get("max")
            hard = HARD_BOUNDS.get((type_key, name))
            if hard:
                field_min = hard[0] if field_min is None else max(field_min, hard[0])
                field_max = hard[1] if field_max is None else min(field_max, hard[1])
            if field_min is not None and value < field_min:
                return None, f"Поле «{field_def['label']}» не может быть меньше {field_min:g}"
            if field_max is not None and value > field_max:
                return None, f"Поле «{field_def['label']}» не может быть больше {field_max:g}"
        elif field_type == "select":
            allowed = {opt["value"] for opt in field_def.get("options") or []}
            if str(value) not in allowed:
                return None, f"Недопустимое значение поля «{field_def['label']}»"
            value = str(value)
        else:
            value = str(value)[:500]
        cleaned[name] = value
    return cleaned, None


def _same_record_just_saved(pet_id: str, type_key: str, username: str, event_dt: datetime, comment: str, fields: dict):
    """The same record this person just saved, or None to write a new one.

    Everything the record says has to be the same: its pet, type, time, comment and fields. Only
    this person's own records count, because two people of one household writing the same thing in
    the same minute is something that really happened twice. Records saved before this field
    existed have no ``created_at`` and are never treated as twins.
    """
    return app.db[EVENTS_COLLECTION].find_one(
        {
            "pet_id": pet_id,
            "type": type_key,
            "username": username,
            "date_time": event_dt,
            "comment": comment,
            "fields": fields,
            "created_at": {"$gte": datetime.now(timezone.utc) - DUPLICATE_EVENT_WINDOW},
            **LIVE_EVENT_FILTER,
        },
        sort=[("created_at", -1)],
    )


def _serialize_event(record: dict) -> dict:
    """Convert an internal Mongo event doc into the JSON-friendly shape."""
    record["_id"] = str(record["_id"])
    record["pet_id"] = str(record.get("pet_id", ""))
    record["username"] = record.get("username", "")
    record["fields"] = record.get("fields", {})
    if isinstance(record.get("date_time"), datetime):
        record["date_time"] = zoned_iso(record["date_time"], record.get("tz"))
    # Left as a datetime, this reached the client as «Sat, 03 Oct 2026 07:52:49 GMT», a
    # web-server date nobody else in the API speaks, next to date_time in the project's own
    # format and next to documents and pets, which already format it.
    # A tombstone says so, and when it was deleted: a device removes the record from its copy.
    if record.get("is_deleted"):
        record["is_deleted"] = True
        record["deleted_at"] = utc_iso(record["deleted_at"]) if isinstance(record.get("deleted_at"), datetime) else None
    # When the record last changed, to the second and in UTC. A record saved before the field existed has no
    # updated_at: its creation is the last change it had.
    changed = record.get("updated_at") or record.get("created_at")
    if isinstance(changed, datetime):
        record["updated_at"] = utc_iso(changed)
    if isinstance(record.get("created_at"), datetime):
        record["created_at"] = utc_iso(record["created_at"])
    return record


def _position(record: dict) -> tuple:
    """Where a record stands in the feed: its time, then its id. The feed is newest first, so it is descending by this pair."""
    moment = record.get("date_time")
    return (moment if isinstance(moment, datetime) else datetime.min, record["_id"])


def _cursor_text(position: tuple) -> str:
    """The cursor a page ends with: the position as text, «2026-10-18T09:00:00,64f1…»."""
    moment, record_id = position
    return f"{moment.isoformat()},{record_id}"


def _parse_cursor(text: str) -> tuple:
    """The position a cursor names. The query checked its shape already (see FeedQuery)."""
    from bson import ObjectId  # lazy import, as elsewhere in this module

    moment_text, record_text = text.split(",", 1)
    return datetime.fromisoformat(moment_text), ObjectId(record_text)


def _after_cursor(position: tuple) -> dict:
    """The records further down the feed than a position: an older time, or the same time and an older id."""
    moment, record_id = position
    return {"$or": [{"date_time": {"$lt": moment}}, {"date_time": moment, "_id": {"$lt": record_id}}]}


def _parse_since(text: str) -> datetime:
    """The moment a device last caught up, as the database keeps moments: UTC, without a zone."""
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _change_position(record: dict) -> tuple:
    """Where a record stands in the order of changes: when it last changed, then its id."""
    return (record["updated_at"], record["_id"])


def _after_change(position: tuple) -> dict:
    """The changes further on than a position: a later change moment, or the same moment and a later id."""
    moment, record_id = position
    return {"$or": [{"updated_at": {"$gt": moment}}, {"updated_at": moment, "_id": {"$gt": record_id}}]}


def _changes_since(query_params):
    """What changed since a moment, for a device that keeps its own copy: live records and tombstones alike.

    Oldest change first, each record once. ``since`` is inclusive, so the device may see its last record again;
    ``after`` takes the next page from the ``next_cursor`` of the previous answer.
    """
    page_size = query_params.page_size
    changes: dict[str, Any] = {"pet_id": g.pet_id, "updated_at": {"$gte": _parse_since(query_params.since)}}
    if query_params.type:
        changes["type"] = query_params.type
    total = app.db[EVENTS_COLLECTION].count_documents(changes)
    if query_params.after:
        changes = {**changes, **_after_change(_parse_cursor(query_params.after))}
    records = list(app.db[EVENTS_COLLECTION].find(changes).sort([("updated_at", 1), ("_id", 1)]).limit(page_size + 1))
    has_more = len(records) > page_size
    records = records[:page_size]
    next_cursor = _cursor_text(_change_position(records[-1])) if has_more and records else None
    items = [_serialize_event(r) for r in records]
    return jsonify({"items": items, "page": 1, "page_size": page_size, "total": total, "next_cursor": next_cursor})


def _notify_trend_anomaly(pet: dict, event_type_label: str, field_label: str, new_value, anomaly: dict) -> None:
    """Push the pet's subscribers that a reading looks abnormal compared
    to its own recent history. Never raises — a push failure must not
    turn an already-successfully-saved event into a failed request.

    Takes the pet document itself (the caller already has it from
    @require_pet_access's own lookup) rather than a pet_id, so this
    doesn't repeat a fetch that just happened earlier in the same request.
    """
    try:
        subscriptions = get_pet_push_subscriptions(app.db, pet)
        if not subscriptions:
            return
        payload = {
            "title": f"Необычное значение: {event_type_label}",
            "body": f"{pet.get('name', 'Питомец')}. {field_label}: {new_value} (обычно ~{anomaly['average']})",
            "url": "/history",
        }
        vapid_claims = {"sub": f"mailto:{PUSH_CONFIG.get('vapid_claims_email', 'admin@example.com')}"}
        send_push_to_subscriptions(app.db, subscriptions, payload, PUSH_CONFIG["vapid_private_key"], vapid_claims)
    except Exception:
        app.logger.exception(f"Failed to send trend-anomaly push for pet_id={pet.get('_id')}")


def _record_with_local_id(local_id: str) -> Optional[dict]:
    """The record the device named with ``local_id``. A name is unique on the stand, so there is at most one."""
    return app.db[EVENTS_COLLECTION].find_one({"local_id": local_id})


def _answer_for_local_id(existing: dict, pet_id: str, type_key: str, local_id: str, label: str):
    """The answer to a create request that names a record which is already there.

    The same pet and the same type: that record, answered as saved (200) with its id, and nothing is written. Any
    other record with that name is not this request's record: 409 ``local_id_taken``.
    """
    if str(existing.get("pet_id")) != str(pet_id) or existing.get("type") != type_key:
        return error_response("local_id_taken")
    if existing.get("is_deleted"):
        # The record was deleted: the device must drop its copy, and a repeat must not bring it back.
        return error_response("record_deleted")
    return get_message("event_created", status=200, label=label, id=str(existing["_id"]), local_id=local_id)


@events_bp.route("/api/events", methods=["POST"])
@login_required
@pat_allowed("events:write")
@api.validate(
    body=Request(EventCreate),
    resp=Response(HTTP_404=ErrorResponse, HTTP_201=SuccessResponse, HTTP_422=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["events"],
)
@require_pet_access
@idempotent
def create_event():
    """Create a new event of any registered type.

    The type is checked against what this person may use (404 ``event_type_not_found`` otherwise). A ``local_id`` the device gives makes the request repeatable: sent again, it is answered with the record it already made (200), and nothing is written twice; a name that belongs to another pet's record is 409 ``local_id_taken``. The same
    record sent again by the same person within 5 minutes (pet, type, time to the minute, fields and comment all
    the same) is one record written twice: it is refused with 409 ``duplicate_event``, and ``existing`` says
    which. For a type charted by value, a reading far from the average of the pet's last 5 (at least 3 earlier
    readings; 15% by default, or the field's own ``deviation_threshold``) sends the pet's family a
    Web Push «Необычное значение» (when push is configured). Keys the type does not declare are dropped. A number field becomes a float (a true or false is not a number) and must fit its ``min`` and ``max`` (built-in types also keep fixed limits: weight 0.01-100, feeding ``food_weight`` 0.1-5000, temperature ``temp_c`` 30-45); a choice must be one of its options' ``value``; text is cut to 500 characters. ``date`` with ``time`` is at most a day ahead and at most 50 years back. These answer 422 ``validation_error`` with the reason in ``error``. An unknown or invalid ``tz`` is dropped, and the record is kept without a zone.
    """
    data = request.context.body  # type: ignore[attr-defined]
    pet_id = g.pet_id
    username = g.username

    event_type = _find_visible_type(data.type, username)
    if not event_type:
        return error_response("event_type_not_found")

    cleaned_fields, field_error = _validate_event_fields(
        data.fields, event_type.get("fields", []), event_type.get("key")
    )
    if field_error:
        return error_response("validation_error", field_error)

    event_dt, dt_error = parse_event_datetime_safe(
        data.date, data.time, event_type["label"], pet_id, username, tz=data.tz
    )
    if dt_error:
        return dt_error[0], dt_error[1]

    comment = data.comment or ""
    # Two identical requests at the same instant would both pass the check below before either has written: the
    # lock lets one of them through at a time, and the other runs its check after the first has written.
    lock_parts = ("event", username, pet_id, data.type, event_dt, comment, repr(sorted(cleaned_fields.items())))
    lock_token = None if data.local_id else acquire(lock_parts)
    if lock_token is None and not data.local_id:
        return error_response("idempotency_in_progress")
    try:
        if data.local_id:
            # The device names the record itself, so the name decides, and the guard below does not judge it: the same
            # request sent again is the record that is already there, whatever the guard would make of it.
            existing = _record_with_local_id(data.local_id)
            if existing:
                return _answer_for_local_id(existing, pet_id, data.type, data.local_id, event_type["label"])
            twin = None
        else:
            # The same request sent twice (the answer to the first never came, so the person presses
            # «Создать» again) is the one record, not two: the second request is answered with the
            # record that is already there. The client treats this answer as a saved record.
            twin = _same_record_just_saved(pet_id, data.type, username, event_dt, comment, cleaned_fields)
        if twin:
            app.logger.info(f"Event not written again: type={data.type}, pet_id={pet_id}, user={username}")
            return (
                jsonify(
                    {
                        "success": False,
                        "code": "duplicate_event",
                        "error": f"Такая запись уже сохранена на {event_dt.strftime('%H:%M')}",
                        "existing": {
                            "id": str(twin["_id"]),
                            "date": event_dt.strftime("%Y-%m-%d"),
                            "time": event_dt.strftime("%H:%M"),
                            "username": twin.get("username"),
                            "own": True,
                        },
                    }
                ),
                409,
            )

        # Checked against history BEFORE inserting the new record — the value
        # being judged must never be part of its own baseline. Skipped
        # entirely (no history query at all) when push isn't configured on
        # this deployment — an anomaly here only ever leads to a push, so
        # there's nothing to detect it for.
        chart = event_type.get("chart") or {}
        anomaly = None
        field_def = None
        value_field = chart.get("value_field") if chart.get("kind") == "value" else None
        if value_field is not None and PUSH_CONFIG.get("vapid_private_key"):
            new_value = cleaned_fields.get(value_field)
            if isinstance(new_value, (int, float)):
                field_def = next((f for f in event_type.get("fields", []) if f["name"] == value_field), None)
                anomaly = detect_anomaly(
                    app.db,
                    pet_id,
                    data.type,
                    value_field,
                    new_value,
                    deviation_threshold=(field_def or {}).get("deviation_threshold"),
                )

        now = datetime.now(timezone.utc)
        doc = {
            "pet_id": pet_id,
            "type": data.type,
            "date_time": event_dt,
            "fields": cleaned_fields,
            "comment": comment,
            "username": username,
            # When the record was written down, apart from the time it happened at: it is what says
            # whether a request that comes again is a repeat (see DUPLICATE_EVENT_WINDOW).
            "created_at": now,
            # Stamped again on every save (see _update_event_record): what a device compares with what it last saw.
            "updated_at": now,
        }
        if data.local_id:
            doc["local_id"] = data.local_id
        # The zone the entered clock is in: an export moves the time onto the
        # exporter's clock. Absent for old records and clients that don't say.
        if valid_tz(data.tz):
            doc["tz"] = data.tz
        from pymongo.errors import DuplicateKeyError  # lazy import, as elsewhere in this module

        try:
            inserted = app.db[EVENTS_COLLECTION].insert_one(doc)
        except DuplicateKeyError:
            # Two requests naming one record at the same moment: the second one finds what the first one wrote.
            existing = _record_with_local_id(data.local_id) if data.local_id else None
            if not existing:
                raise
            return _answer_for_local_id(existing, pet_id, data.type, data.local_id, event_type["label"])
        app.logger.info(f"Event recorded: type={data.type}, pet_id={pet_id}, user={username}")

        if anomaly:
            field_label = (field_def or {}).get("label", value_field)
            _notify_trend_anomaly(g.pet, event_type["label"], field_label, cleaned_fields[value_field], anomaly)

        # The id lets the client offer «Отменить» for a record made by mistake.
        # The name the device gave comes back with the id, so the device can match the answer to the record it sent.
        named = {"local_id": data.local_id} if data.local_id else {}
        return get_message(
            "event_created", status=201, label=event_type["label"], id=str(inserted.inserted_id), **named
        )
    finally:
        release(lock_parts, lock_token)


@events_bp.route("/api/events", methods=["GET"])
@login_required
@api.validate(
    query=EventListQuery,
    resp=Response(HTTP_404=ErrorResponse, HTTP_200=EventListResponse, HTTP_422=ErrorResponse),
    tags=["events"],
)
@require_pet_access
def list_events():
    """List events for the current pet, optionally filtered by type.

    Newest first. A page by number (``page``, ``page_size``) is what the web app reads. A device that reads the whole
    diary passes ``before`` with the ``next_cursor`` of the previous answer: the cursor names the last record it has
    seen by its time and its id, so a record written in between moves no page, and no record is read twice or missed.
    ``next_cursor`` is null on the last page. Dates and times are the person's own, kept as they were typed: the zone
    travels with the record (``tz``, the IANA zone it was typed in) and the reading device puts the time on its own clock.
    """
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = g.pet_id
    page = query_params.page
    page_size = query_params.page_size
    if query_params.since:
        return _changes_since(query_params)
    cursor = _parse_cursor(query_params.before) if query_params.before else None

    mongo_query: dict[str, Any] = {"pet_id": pet_id}
    if query_params.type:
        mongo_query["type"] = query_params.type
    if not query_params.with_deleted:
        mongo_query.update(LIVE_EVENT_FILTER)

    total = app.db[EVENTS_COLLECTION].count_documents(mongo_query)
    skip = 0 if cursor else (page - 1) * page_size
    query = {**mongo_query, **_after_cursor(cursor)} if cursor else mongo_query
    # One record more than the page, to know whether there is a next one; read before the records are changed for the answer.
    records = list(
        app.db[EVENTS_COLLECTION].find(query).sort([("date_time", -1), ("_id", -1)]).skip(skip).limit(page_size + 1)
    )
    has_more = len(records) > page_size if cursor else total > skip + page_size
    records = records[:page_size]
    next_cursor = _cursor_text(_position(records[-1])) if has_more and records else None
    items = [_serialize_event(r) for r in records]

    return jsonify({"items": items, "page": page, "page_size": page_size, "total": total, "next_cursor": next_cursor})


@events_bp.route("/api/events/<record_id>", methods=["GET"])
@api.validate(
    resp=Response(HTTP_200=EventItem, HTTP_404=ErrorResponse),
    tags=["events"],
)
@require_record_access(EVENTS_COLLECTION, extra_filter=LIVE_EVENT_FILTER)
def get_event(record_id):
    """Fetch a single event.

    The same check as the list: a record of a pet the caller cannot see answers exactly like a missing one.
    """
    try:
        return jsonify(_serialize_event(g.record))
    except Exception as e:
        app.logger.error(f"Error fetching event: {e}")
        return error_response("internal_error")


def require_local_event_access(view):
    """The same check as ``require_record_access``, for a record the device names by its ``local_id`` in the path.

    An unknown name and a record of a pet the caller cannot see answer alike, as they do by id: 404 ``record_not_found``.
    A record that was deleted is found too, and each action says what it makes of that.
    """

    @login_required
    @wraps(view)
    def decorated_function(*args, **kwargs):
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]
        local_id = kwargs.get("local_id")
        record = app.db[EVENTS_COLLECTION].find_one({"local_id": local_id}) if local_id else None
        if not record or not record.get("pet_id") or not check_pet_access(record["pet_id"], username):
            return error_response("record_not_found")
        g.username = username
        g.record = record
        g.pet_id = record["pet_id"]
        return view(*args, **kwargs)

    return decorated_function


@events_bp.route("/api/events/<record_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(EventUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_409=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["events"],
)
@require_record_access(EVENTS_COLLECTION)
def update_event(record_id):
    """Update an event. The event's type cannot change.

    The type is fixed once written: a different kind of thing belongs in a new record. Any member of the pet may change any of its records, whoever wrote it. Without ``date`` and ``time`` the record keeps its time; one of them sent alone is completed from the stored time. ``fields`` replaces the whole set, it is not merged. Keys the type does not declare are dropped. A number field becomes a float (a true or false is not a number) and must fit its ``min`` and ``max`` (built-in types also keep fixed limits: weight 0.01-100, feeding ``food_weight`` 0.1-5000, temperature ``temp_c`` 30-45); a choice must be one of its options' ``value``; text is cut to 500 characters. ``date`` with ``time`` is at most a day ahead and at most 50 years back. These answer 422 ``validation_error`` with the reason in ``error``. An unknown or invalid ``tz`` is dropped, and the record is kept without a zone. The zone is restamped only when the clock really moved, or an author's time would come back as the editor's. ``base_version`` is the ``updated_at`` the device last read: a record changed since answers 409 ``conflict`` with the record as it is now in ``record``; without it the change is applied. A record that was deleted answers 409 ``record_deleted``.
    """
    return _update_event_record(g.record)


@events_bp.route("/api/events/local/<local_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(EventUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_409=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["events"],
)
@require_local_event_access
def update_event_by_local_id(local_id):
    """Update an event by the ``local_id`` the device gave it, for when the device has not got the record's id.

    The same update as by id, on the same record, with the same ``base_version`` check. The name stays as it was created: an update does not change it.
    """
    return _update_event_record(g.record)


def _update_event_record(record: dict):
    """The update of one record found by the access check, by its id or by the local_id the device named."""
    username = g.username
    pet_id = g.pet_id
    data = request.context.body  # type: ignore[attr-defined]

    if record.get("is_deleted"):
        # Not a missing record: the device made this change on a copy of something that is gone, and it must drop it.
        return error_response("record_deleted")
    if is_stale(data.base_version, record):
        return conflict_answer(_serialize_event(dict(record)))

    event_type = app.db[EVENT_TYPES_COLLECTION].find_one({"key": record["type"]})
    if not event_type:
        return error_response("event_type_not_found")

    # A change that leaves the time out keeps it: a comment edited from another client must not move the
    # record to now. One half sent is completed from the stored time.
    stored_dt = record.get("date_time")
    if data.date is None and data.time is None:
        event_dt, dt_error = None, None
    else:
        date_str = data.date or (stored_dt.strftime("%Y-%m-%d") if isinstance(stored_dt, datetime) else None)
        time_str = data.time or (stored_dt.strftime("%H:%M") if isinstance(stored_dt, datetime) else None)
        event_dt, dt_error = parse_event_datetime_safe(
            date_str, time_str, f"{event_type['label']} update", pet_id, username, tz=data.tz
        )
    if dt_error:
        return dt_error[0], dt_error[1]

    update_data: dict[str, Any] = {}
    if event_dt is not None:
        update_data["date_time"] = event_dt
        # The form sends the whole time back even when only the comment was
        # edited: the zone is re-stamped only when the clock really moved,
        # or an author's time would be read as the editor's.
        if event_dt != record.get("date_time") and valid_tz(data.tz):
            update_data["tz"] = data.tz
        if not valid_tz(data.tz) and not record.get("tz"):
            return error_response("validation_error", "Укажите часовой пояс, в котором введено время")
    if data.comment is not None:
        update_data["comment"] = data.comment
    if data.fields is not None:
        cleaned_fields, field_error = _validate_event_fields(
            data.fields, event_type.get("fields", []), event_type.get("key")
        )
        if field_error:
            return error_response("validation_error", field_error)
        update_data["fields"] = cleaned_fields

    update_data["updated_at"] = next_stamp(record)
    result = app.db[EVENTS_COLLECTION].update_one(
        {"_id": record["_id"], **version_guard(record, data.base_version)}, {"$set": update_data}
    )
    if result.matched_count == 0:
        latest = app.db[EVENTS_COLLECTION].find_one({"_id": record["_id"]})
        if latest is None:
            return error_response("record_not_found")
        if latest.get("is_deleted"):
            return error_response("record_deleted")
        if data.base_version is None:
            return error_response("record_not_found")
        # Saved by someone else between the check above and the write.
        return conflict_answer(_serialize_event(latest))

    app.logger.info(f"Event updated: record_id={record['_id']}, pet_id={pet_id}, user={username}")
    return get_message("event_updated", label=event_type["label"])


@events_bp.route("/api/events/<record_id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_404=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["events"],
)
@require_record_access(EVENTS_COLLECTION, extra_filter=LIVE_EVENT_FILTER)
def delete_event(record_id):
    """Delete an event.

    The record is marked deleted, not erased: it leaves every list, total, chart, card and export, and stays for thirty days as a tombstone that a device reads with ``with_deleted``. Any member of the pet may delete any of its records, whoever wrote it. What was counted from it leaves the counts with it, and the day and the totals it was part of close up again.
    """
    return _delete_event_record(g.record)


@events_bp.route("/api/events/local/<local_id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_422=ErrorResponse, HTTP_404=ErrorResponse, HTTP_500=ErrorResponse),
    tags=["events"],
)
@require_local_event_access
def delete_event_by_local_id(local_id):
    """Delete an event by the ``local_id`` the device gave it, for when the device has not got the record's id.

    The same delete as by id: the record goes. An unknown name or someone else's record answers 404 ``record_not_found``.
    """
    return _delete_event_record(g.record)


def _delete_event_record(record: dict):
    """The delete of one record found by the access check, by its id or by the local_id the device named."""
    username = g.username
    pet_id = g.pet_id
    if record.get("is_deleted"):
        # Found by its name, and already gone: as by id, a record that is not there.
        return error_response("record_not_found")

    deleted_at = datetime.now(timezone.utc)
    # Marked, not erased: the record leaves every ordinary read, and stays as a tombstone for the devices that sync.
    result = app.db[EVENTS_COLLECTION].update_one(
        {"_id": record["_id"]}, {"$set": {"is_deleted": True, "deleted_at": deleted_at, "updated_at": deleted_at}}
    )
    if result.matched_count == 0:
        return error_response("record_not_found")
    app.logger.info(f"Event deleted: record_id={record['_id']}, pet_id={pet_id}, user={username}")
    return get_message("event_deleted")


# ---------------------------------------------------------------------------
# Aggregate endpoints — stats (chart data) + timeline
# ---------------------------------------------------------------------------


@events_bp.route("/api/events/used-types", methods=["GET"])
@login_required
@api.validate(query=PetIdQuery, resp=Response(HTTP_404=ErrorResponse, HTTP_200=UsedEventTypesResponse), tags=["events"])
@require_pet_access
def used_event_types():
    """The types this pet has at least one record of: what a filter of its history has something to show for.

    A filter over a type with nothing behind it would only show an empty list, so the history offers the types that have records.
    """
    types = app.db[EVENTS_COLLECTION].distinct("type", {"pet_id": g.pet_id, **LIVE_EVENT_FILTER})
    return jsonify({"types": sorted(t for t in types if isinstance(t, str))})


@events_bp.route("/api/stats/health", methods=["GET"])
@login_required
@api.validate(
    query=HealthStatsQuery,
    resp=Response(HTTP_404=ErrorResponse, HTTP_200=HealthStatsResponse, HTTP_422=ErrorResponse),
    tags=["stats"],
)
@require_pet_access
def get_health_stats():
    """Get event statistics for charts.

    Records of one type from the last ``days`` days (30 by default, counted back from now in UTC), oldest first, one point each: ``date`` is the record's time, ``value`` is 1 for a counted type or the charted field's value for a type charted by value. ``type=medications`` gives the doses given (skipped ones left out). An unknown type answers 422 ``invalid_type``. ``days`` is from 1 to 3650, and any other value answers 422 ``validation_error``. A record of a value-charted type without that field gives ``value: 0``.
    """
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = g.pet_id
    record_type = query_params.type
    days = query_params.days or 30

    if record_type == "medications":
        collection_name, value_field = "medication_intakes", "count"
    else:
        event_type = app.db[EVENT_TYPES_COLLECTION].find_one({"key": record_type})
        if not event_type:
            return error_response("invalid_type")
        collection_name = EVENTS_COLLECTION
        chart = event_type.get("chart") or {"kind": "count"}
        value_field = chart.get("value_field") if chart.get("kind") == "value" else "count"

    since_date = datetime.now(timezone.utc) - timedelta(days=days)
    mongo_query: dict[str, Any] = {"pet_id": pet_id, "date_time": {"$gte": since_date}}
    # Only what a point is made of: the record's own clock with its zone, and the one field the chart reads. The comment
    # and the fields the chart does not read would otherwise ride along with every record of the window. The window and
    # the order come off the existing indexes (pet_id + type + date_time, pet_id + date_time for doses), so the database
    # answers in order without anything being read to be sorted here.
    projection: dict[str, Any] = {"_id": 0, "date_time": 1, "tz": 1}
    if collection_name == EVENTS_COLLECTION:
        mongo_query["type"] = record_type
        mongo_query.update(LIVE_EVENT_FILTER)
        if value_field != "count":
            projection[f"fields.{value_field}"] = 1
    else:
        # A skipped dose isn't a dose given.
        mongo_query["skipped"] = {"$ne": True}

    records = app.db[collection_name].find(mongo_query, projection).sort("date_time", 1)

    # The loop stays even though the heavy field no longer comes along: a point's date is written in the
    # zone that record was marked in, and the zone is per record, so the days cannot be grouped by the
    # database. What it reads is now three small fields per point.
    stats_data = []
    for record in records:
        dt = record.get("date_time")
        date_str = zoned_iso(dt, record.get("tz")) if isinstance(dt, datetime) else str(dt)

        if value_field == "count":
            value = 1
        else:
            # The only other collection is EVENTS_COLLECTION — medications
            # always uses value_field="count" and hits the branch above,
            # so a non-"count" value_field here can only mean an event's
            # own custom field.
            value = record.get("fields", {}).get(value_field, 0)
        stats_data.append({"date": date_str, "value": value})

    return jsonify({"data": stats_data})


@events_bp.route("/api/history/timeline", methods=["GET"])
@login_required
@pat_allowed("history:read")
@api.validate(
    query=TimelineQuery,
    resp=Response(HTTP_404=ErrorResponse, HTTP_200=TimelineResponse, HTTP_422=ErrorResponse),
    tags=["events"],
)
@require_pet_access
def get_history_timeline():
    """Get an aggregate timeline of events + medication intakes for a pet.

    One page of a pet's records and medication doses, newest first. ``type`` is ``all``, ``medications`` (doses
    only) or the key of an event type; a key that is not known gives an empty list, not an error. Event items carry
    ``record_type`` in place of ``type``. Dose items include skipped ones (``skipped``) and add ``medication_name``
    and ``dose_unit`` while the course still exists.

    A ``before`` cursor (the ``next_cursor`` of the previous answer) takes the feed on from there, as for the event
    list; without it the page is by number. Both kinds of answer carry ``next_cursor``.
    """
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = g.pet_id
    page = query_params.page
    page_size = query_params.page_size
    filter_type = getattr(query_params, "type", "all")
    cursor = _parse_cursor(query_params.before) if query_params.before else None

    include_events = filter_type != "medications"
    include_medications = not filter_type or filter_type in ("all", "medications")

    offset = 0 if cursor else (page - 1) * page_size
    # Each source gives its newest records up to one past the page: enough to merge the feed, and to know there is more.
    fetch_limit = offset + page_size + 1
    rows = []  # (position, item): the merged feed is sorted by the position, newest first
    total = 0

    if include_events:
        events_query: dict[str, Any] = {"pet_id": pet_id}
        if filter_type and filter_type != "all":
            events_query["type"] = filter_type
        if not query_params.with_deleted:
            events_query.update(LIVE_EVENT_FILTER)
        total += app.db[EVENTS_COLLECTION].count_documents(events_query)
        if cursor:
            events_query = {**events_query, **_after_cursor(cursor)}
        for record in (
            app.db[EVENTS_COLLECTION].find(events_query).sort([("date_time", -1), ("_id", -1)]).limit(fetch_limit)
        ):
            position = _position(record)
            item = _serialize_event(record)
            item["record_type"] = item.pop("type")
            rows.append((position, item))

    if include_medications:
        intakes_query: dict[str, Any] = {"pet_id": pet_id}
        total += app.db["medication_intakes"].count_documents(intakes_query)
        if cursor:
            intakes_query = {**intakes_query, **_after_cursor(cursor)}
        intake_records = list(
            app.db["medication_intakes"].find(intakes_query).sort([("date_time", -1), ("_id", -1)]).limit(fetch_limit)
        )

        from bson import ObjectId  # local import keeps module-load cheap

        med_object_ids = []
        for record in intake_records:
            raw_id = record.get("medication_id")
            if raw_id:
                try:
                    med_object_ids.append(ObjectId(raw_id))
                except Exception:
                    pass
        meds = (
            {
                str(med["_id"]): med
                for med in app.db["medications"].find({"_id": {"$in": med_object_ids}}, {"name": 1, "dose_unit": 1})
            }
            if med_object_ids
            else {}
        )

        for record in intake_records:
            position = _position(record)
            record["_id"] = str(record["_id"])
            record["pet_id"] = str(record.get("pet_id", ""))
            record["record_type"] = "medications"
            if isinstance(record.get("date_time"), datetime):
                record["date_time"] = zoned_iso(record["date_time"], record.get("tz"))
            if isinstance(record.get("created_at"), datetime):
                record["created_at"] = utc_iso(record["created_at"])
            med = meds.get(record.get("medication_id"))
            if med:
                record["medication_name"] = med.get("name", "Неизвестный курс")
                # «1 таб», not a bare «1», on the feed. A unit from a script or an older
                # client is read in Russian here; the course keeps what was written.
                record["dose_unit"] = ru_dose_unit(med.get("dose_unit"))
            rows.append((position, record))

    rows.sort(key=lambda row: row[0], reverse=True)
    if cursor:
        page_rows = rows[:page_size]
        has_more = len(rows) > page_size
    else:
        page_rows = rows[offset : offset + page_size]
        has_more = total > offset + page_size
    next_cursor = _cursor_text(page_rows[-1][0]) if has_more and page_rows else None
    items = [item for _, item in page_rows]

    return jsonify(
        {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "next_cursor": next_cursor,
        }
    )
