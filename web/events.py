"""Generic event-type registry and events CRUD.

Replaces the old per-type hand-rolled collections (asthma_attacks,
defecations, litter_changes, weights, feedings, eye_drops, tooth_brushing,
ear_cleaning) and their duplicated schemas/routes/messages/export specs with
one ``event_types`` registry (builtin + user-defined) and one ``events``
collection. Adding a type — builtin or user-created — is a document, not code.

Medications keep their own module: courses, doses, and inventory are a
different domain (scheduled, stateful) from a point-in-time event log.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from flask import Blueprint, g, jsonify, request
from flask_pydantic_spec import Request, Response

import web.app as app  # use app.db and app.logger so test patches are visible
from web.app import api
from web.decorators import require_pet_access, require_record_access
from web.errors import error_response
from web.helpers import apply_pagination, parse_event_datetime_safe
from web.messages import get_message
from web.schemas import (
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
    SuccessResponse,
    TimelineQuery,
    TimelineResponse,
)
from web.security import get_current_user, login_required


events_bp = Blueprint("events", __name__)

EVENTS_COLLECTION = "events"
EVENT_TYPES_COLLECTION = "event_types"


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
        "fields": doc.get("fields", []),
        "chart": doc.get("chart") or {"kind": "count"},
    }


def _generate_event_type_key() -> str:
    """A stable, opaque id for a custom type — the label is free text (any
    language/characters) and only used for display, so the key is generated
    rather than slugified from it."""
    return f"custom_{uuid4().hex[:10]}"


@events_bp.route("/api/event-types", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=EventTypeListResponse), tags=["events"])
def list_event_types():
    """List every event type (builtin + custom)."""
    docs = app.db[EVENT_TYPES_COLLECTION].find({}).sort([("is_builtin", -1), ("label", 1)])
    return jsonify({"event_types": [_serialize_event_type(d) for d in docs]})


@events_bp.route("/api/event-types", methods=["POST"])
@api.validate(
    body=Request(EventTypeCreate),
    resp=Response(HTTP_201=EventTypeItem, HTTP_422=ErrorResponse),
    tags=["events"],
)
@login_required
def create_event_type():
    """Create a custom event type."""
    # @login_required already guarantees request.current_user is set.
    username, _ = get_current_user()

    data = request.context.body  # type: ignore[attr-defined]
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
@api.validate(
    body=Request(EventTypeUpdate),
    resp=Response(HTTP_200=EventTypeItem, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["events"],
)
@login_required
def update_event_type(key):
    """Update an event type's label/icon/color/fields/chart.

    Builtin types are editable too (only the ``key`` itself is immutable) —
    once everything is data-driven there's no reason to special-case them
    beyond protecting them from deletion below.
    """
    # @login_required already guarantees request.current_user is set.
    username, _ = get_current_user()

    existing = app.db[EVENT_TYPES_COLLECTION].find_one({"key": key})
    if not existing:
        return error_response("event_type_not_found")

    data = request.context.body  # type: ignore[attr-defined]
    update_data: dict[str, Any] = {}
    if data.label is not None:
        update_data["label"] = data.label
    if data.icon is not None:
        update_data["icon"] = data.icon
    if data.color is not None:
        update_data["color"] = data.color
    if data.fields is not None:
        update_data["fields"] = [f.model_dump() for f in data.fields]
    if data.chart is not None:
        update_data["chart"] = data.chart.model_dump()

    if update_data:
        app.db[EVENT_TYPES_COLLECTION].update_one({"key": key}, {"$set": update_data})
        existing.update(update_data)

    app.logger.info(f"Event type updated: key={key}, user={username}")
    return jsonify(_serialize_event_type(existing)), 200


@events_bp.route("/api/event-types/<key>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["events"],
)
@login_required
def delete_event_type(key):
    """Delete a custom event type.

    Builtin types can't be deleted, and a custom type with existing events
    can't either — its history would otherwise lose its field labels and
    rendering.
    """
    # @login_required already guarantees request.current_user is set.
    username, _ = get_current_user()

    existing = app.db[EVENT_TYPES_COLLECTION].find_one({"key": key})
    if not existing:
        return error_response("event_type_not_found")
    if existing.get("is_builtin"):
        return error_response("event_type_builtin_immutable")
    if app.db[EVENTS_COLLECTION].count_documents({"type": key}) > 0:
        return error_response("event_type_has_events")

    app.db[EVENT_TYPES_COLLECTION].delete_one({"key": key})
    app.logger.info(f"Event type deleted: key={key}, user={username}")
    return get_message("event_type_deleted")


# ---------------------------------------------------------------------------
# Events CRUD
# ---------------------------------------------------------------------------


def _validate_event_fields(raw_fields: dict, field_defs: list) -> tuple[Optional[dict], Optional[str]]:
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
            try:
                value = float(value)
            except (TypeError, ValueError):
                return None, f"Поле «{field_def['label']}» должно быть числом"
            field_min = field_def.get("min")
            field_max = field_def.get("max")
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


def _serialize_event(record: dict) -> dict:
    """Convert an internal Mongo event doc into the JSON-friendly shape."""
    record["_id"] = str(record["_id"])
    record["pet_id"] = str(record.get("pet_id", ""))
    record["username"] = record.get("username", "")
    record["fields"] = record.get("fields", {})
    if isinstance(record.get("date_time"), datetime):
        record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")
    return record


@events_bp.route("/api/events", methods=["POST"])
@api.validate(
    body=Request(EventCreate),
    resp=Response(
        HTTP_201=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["events"],
)
@require_pet_access
def create_event():
    """Create a new event of any registered type."""
    data = request.context.body  # type: ignore[attr-defined]
    pet_id = g.pet_id
    username = g.username

    event_type = app.db[EVENT_TYPES_COLLECTION].find_one({"key": data.type})
    if not event_type:
        return error_response("event_type_not_found")

    cleaned_fields, field_error = _validate_event_fields(data.fields, event_type.get("fields", []))
    if field_error:
        return error_response("validation_error", field_error)

    event_dt, dt_error = parse_event_datetime_safe(data.date, data.time, event_type["label"], pet_id, username)
    if dt_error:
        return dt_error[0], dt_error[1]

    doc = {
        "pet_id": pet_id,
        "type": data.type,
        "date_time": event_dt,
        "fields": cleaned_fields,
        "comment": data.comment or "",
        "username": username,
    }
    app.db[EVENTS_COLLECTION].insert_one(doc)
    app.logger.info(f"Event recorded: type={data.type}, pet_id={pet_id}, user={username}")
    return get_message("event_created", status=201, label=event_type["label"])


@events_bp.route("/api/events", methods=["GET"])
@api.validate(
    query=EventListQuery,
    resp=Response(HTTP_200=EventListResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["events"],
)
@require_pet_access
def list_events():
    """List events for the current pet, optionally filtered by type."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = g.pet_id
    page = query_params.page
    page_size = query_params.page_size

    mongo_query: dict[str, Any] = {"pet_id": pet_id}
    if query_params.type:
        mongo_query["type"] = query_params.type

    total = app.db[EVENTS_COLLECTION].count_documents(mongo_query)
    base_query = app.db[EVENTS_COLLECTION].find(mongo_query).sort("date_time", -1)
    paginated_query, _ = apply_pagination(base_query, page, page_size)
    items = [_serialize_event(r) for r in paginated_query]

    return jsonify({"items": items, "page": page, "page_size": page_size, "total": total})


@events_bp.route("/api/events/<record_id>", methods=["GET"])
@api.validate(
    resp=Response(HTTP_200=None, HTTP_404=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["events"],
)
@require_record_access(EVENTS_COLLECTION)
def get_event(record_id):
    """Fetch a single event."""
    try:
        return jsonify(_serialize_event(g.record))
    except Exception as e:
        app.logger.error(f"Error fetching event: {e}")
        return error_response("internal_error")


@events_bp.route("/api/events/<record_id>", methods=["PUT"])
@api.validate(
    body=Request(EventUpdate),
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["events"],
)
@require_record_access(EVENTS_COLLECTION)
def update_event(record_id):
    """Update an event. The event's type cannot change."""
    from bson import ObjectId  # lazy import to keep this module Mongo-free at import time

    username = g.username
    pet_id = g.pet_id
    data = request.context.body  # type: ignore[attr-defined]

    event_type = app.db[EVENT_TYPES_COLLECTION].find_one({"key": g.record["type"]})
    if not event_type:
        return error_response("event_type_not_found")

    event_dt, dt_error = parse_event_datetime_safe(
        data.date, data.time, f"{event_type['label']} update", pet_id, username
    )
    if dt_error:
        return dt_error[0], dt_error[1]

    update_data: dict[str, Any] = {}
    if event_dt is not None:
        update_data["date_time"] = event_dt
    if data.comment is not None:
        update_data["comment"] = data.comment
    if data.fields is not None:
        cleaned_fields, field_error = _validate_event_fields(data.fields, event_type.get("fields", []))
        if field_error:
            return error_response("validation_error", field_error)
        update_data["fields"] = cleaned_fields

    result = app.db[EVENTS_COLLECTION].update_one({"_id": ObjectId(record_id)}, {"$set": update_data})
    if result.matched_count == 0:
        return error_response("record_not_found")

    app.logger.info(f"Event updated: record_id={record_id}, pet_id={pet_id}, user={username}")
    return get_message("event_updated", label=event_type["label"])


@events_bp.route("/api/events/<record_id>", methods=["DELETE"])
@api.validate(
    resp=Response(
        HTTP_200=SuccessResponse,
        HTTP_422=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_404=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["events"],
)
@require_record_access(EVENTS_COLLECTION)
def delete_event(record_id):
    """Delete an event."""
    from bson import ObjectId

    username = g.username
    pet_id = g.pet_id
    event_type = app.db[EVENT_TYPES_COLLECTION].find_one({"key": g.record["type"]})
    label = event_type["label"] if event_type else "Запись"

    result = app.db[EVENTS_COLLECTION].delete_one({"_id": ObjectId(record_id)})
    if result.deleted_count == 0:
        return error_response("record_not_found")
    app.logger.info(f"Event deleted: record_id={record_id}, pet_id={pet_id}, user={username}")
    return get_message("event_deleted", label=label)


# ---------------------------------------------------------------------------
# Aggregate endpoints — stats (chart data) + timeline
# ---------------------------------------------------------------------------


@events_bp.route("/api/stats/health", methods=["GET"])
@api.validate(
    query=HealthStatsQuery,
    resp=Response(HTTP_200=HealthStatsResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["stats"],
)
@require_pet_access
def get_health_stats():
    """Get event statistics for charts."""
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = g.pet_id
    record_type = query_params.type
    days = query_params.days or 30

    if record_type == "medications":
        collection_name, value_field = "medication_intakes", "count"
    else:
        event_type = app.db[EVENT_TYPES_COLLECTION].find_one({"key": record_type})
        if not event_type:
            return error_response("invalid_type", f"Unsupported record type: {record_type}")
        collection_name = EVENTS_COLLECTION
        chart = event_type.get("chart") or {"kind": "count"}
        value_field = chart.get("value_field") if chart.get("kind") == "value" else "count"

    since_date = datetime.now(timezone.utc) - timedelta(days=days)
    mongo_query: dict[str, Any] = {"pet_id": pet_id, "date_time": {"$gte": since_date}}
    if collection_name == EVENTS_COLLECTION:
        mongo_query["type"] = record_type

    records = list(app.db[collection_name].find(mongo_query).sort("date_time", 1))

    stats_data = []
    for record in records:
        dt = record.get("date_time")
        date_str = dt.strftime("%Y-%m-%d %H:%M") if isinstance(dt, datetime) else str(dt)

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
@api.validate(
    query=TimelineQuery,
    resp=Response(HTTP_200=TimelineResponse, HTTP_422=ErrorResponse, HTTP_403=ErrorResponse),
    tags=["events"],
)
@require_pet_access
def get_history_timeline():
    """Get an aggregate timeline of events + medication intakes for a pet.

    Both source collections are indexed on ``{pet_id, date_time}`` — used
    here for a sorted, `limit`-ed fetch from each instead of loading the
    pet's entire history on every call. Fetching the top
    ``offset + page_size`` from each source (rather than everything) is
    still enough to answer this page correctly: any record that belongs
    in the merged page can be at most that far down within its own
    collection, since everything ahead of it globally is also ahead of
    it within its source. Medication names are batch-resolved with one
    `$in` query instead of a `find_one` per intake.
    """
    query_params = request.context.query  # type: ignore[attr-defined]
    pet_id = g.pet_id
    page = query_params.page
    page_size = query_params.page_size
    filter_type = getattr(query_params, "type", "all")

    all_records = []
    total = 0

    include_events = filter_type != "medications"
    include_medications = not filter_type or filter_type in ("all", "medications")

    offset = (page - 1) * page_size
    fetch_limit = offset + page_size

    if include_events:
        events_query: dict[str, Any] = {"pet_id": pet_id}
        if filter_type and filter_type != "all":
            events_query["type"] = filter_type
        total += app.db[EVENTS_COLLECTION].count_documents(events_query)
        cursor = app.db[EVENTS_COLLECTION].find(events_query).sort("date_time", -1).limit(fetch_limit)
        for record in cursor:
            item = _serialize_event(record)
            item["record_type"] = item.pop("type")
            all_records.append(item)

    if include_medications:
        intakes_query = {"pet_id": pet_id}
        total += app.db["medication_intakes"].count_documents(intakes_query)
        intake_records = list(app.db["medication_intakes"].find(intakes_query).sort("date_time", -1).limit(fetch_limit))

        from bson import ObjectId  # local import keeps module-load cheap

        med_object_ids = []
        for record in intake_records:
            raw_id = record.get("medication_id")
            if raw_id:
                try:
                    med_object_ids.append(ObjectId(raw_id))
                except Exception:
                    pass
        med_names = (
            {
                str(med["_id"]): med.get("name", "Unknown")
                for med in app.db["medications"].find({"_id": {"$in": med_object_ids}}, {"name": 1})
            }
            if med_object_ids
            else {}
        )

        for record in intake_records:
            record["_id"] = str(record["_id"])
            record["pet_id"] = str(record.get("pet_id", ""))
            record["record_type"] = "medications"
            if isinstance(record.get("date_time"), datetime):
                record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")
            med_name = med_names.get(record.get("medication_id"))
            if med_name:
                record["medication_name"] = med_name
            all_records.append(record)

    all_records.sort(key=lambda x: x.get("date_time", ""), reverse=True)

    paginated_records = all_records[offset : offset + page_size]

    return jsonify(
        {
            "items": paginated_records,
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )
