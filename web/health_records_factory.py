"""Generic CRUD factory for health record endpoints.

Each record type (asthma, defecation, weight, feeding, litter, eye drops,
tooth brushing, ear cleaning) used to be a hand-rolled set of 5 routes with
~80% duplicated boilerplate. This module collapses the duplication into a
single ``register_record_crud`` function plus a per-record ``HealthRecordSpec``.

Adding a new record type is now a matter of declaring a spec.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from flask import Blueprint, g, jsonify, request
from flask_pydantic_spec import Request, Response
from pydantic import BaseModel

import web.app as app  # use app.db and app.logger so test patches are visible
from web.app import api
from web.decorators import require_pet_access, require_record_access
from web.errors import error_response
from web.helpers import apply_pagination, parse_event_datetime_safe
from web.messages import get_message
from web.schemas import ErrorResponse, PetIdPaginationQuery, SuccessResponse


# Type alias for the per-record document builder.
BuildDocFn = Callable[[BaseModel, str, str, datetime], dict]


@dataclass(frozen=True)
class HealthRecordSpec:
    """Declaration of a single health record type's CRUD endpoints."""

    endpoint: str
    """URL slug for the collection (e.g. ``asthma``)."""

    collection: str
    """MongoDB collection name (e.g. ``asthma_attacks``)."""

    log_name: str
    """Human-readable name used in log/error messages (e.g. ``asthma attack``)."""

    msg_prefix: str
    """Prefix for ``get_message`` keys: ``{prefix}_created``, ``_updated``, ``_deleted``."""

    create_schema: type[BaseModel]
    update_schema: type[BaseModel]
    item_schema: type[BaseModel]
    list_response_schema: type[BaseModel]

    list_field_name: str
    """Attribute name on the list response (e.g. ``attacks``, ``defecations``)."""

    build_doc: BuildDocFn
    """Construct the MongoDB document from a create-schema instance."""


def _serialize_record(record: dict) -> dict:
    """Convert an internal Mongo record dict into the JSON-friendly shape.

    All endpoints shared this exact transformation, so it lives here once.
    """
    record["_id"] = str(record["_id"])
    record["pet_id"] = str(record.get("pet_id", ""))
    record["username"] = record.get("username", "")
    if isinstance(record.get("date_time"), datetime):
        record["date_time"] = record["date_time"].strftime("%Y-%m-%d %H:%M")
    return record


def register_record_crud(blueprint: Blueprint, spec: HealthRecordSpec) -> None:
    """Register POST/GET-list/GET-one/PUT/DELETE routes for ``spec``.

    Each generated route delegates to the same closures; per-record differences
    live entirely in ``spec``.
    """
    # Flask keys view functions by their ``__name__``; if all 8 specs registered
    # ``_create`` they would collide. Tag each name with the endpoint slug.
    tag = spec.endpoint.replace(" ", "_")

    def _named(name):
        """Decorator that rewrites ``__name__`` so Flask registers unique endpoints."""
        def deco(fn):
            fn.__name__ = f"{name}_{tag}"
            return fn
        return deco

    # ----- POST (create) ---------------------------------------------------
    @blueprint.route(f"/api/{spec.endpoint}", methods=["POST"])
    @api.validate(
        body=Request(spec.create_schema),
        resp=Response(
            HTTP_201=SuccessResponse,
            HTTP_422=ErrorResponse,
            HTTP_403=ErrorResponse,
            HTTP_500=ErrorResponse,
        ),
        tags=["health-records"],
    )
    @_named("create")
    @require_pet_access
    def _create():
        """Create a new ``spec.log_name`` event."""
        try:
            data = request.context.body  # type: ignore[attr-defined]
            pet_id = g.pet_id
            username = g.username

            event_dt, dt_error = parse_event_datetime_safe(
                data.date, data.time, spec.log_name, pet_id, username
            )
            if dt_error:
                return dt_error[0], dt_error[1]

            doc = spec.build_doc(data, pet_id, username, event_dt)
            app.db[spec.collection].insert_one(doc)
            app.logger.info(
                f"{spec.log_name.capitalize()} recorded: pet_id={pet_id}, user={username}"
            )
            return get_message(f"{spec.msg_prefix}_created", status=201)
        except ValueError as e:
            app.logger.warning(
                f"Invalid input data for {spec.log_name}: pet_id={pet_id}, "
                f"user={username}, error={e}"
            )
            return error_response("validation_error", str(e))

    # ----- GET list --------------------------------------------------------
    @blueprint.route(f"/api/{spec.endpoint}", methods=["GET"])
    @api.validate(
        query=PetIdPaginationQuery,
        resp=Response(
            HTTP_200=spec.list_response_schema,
            HTTP_422=ErrorResponse,
            HTTP_403=ErrorResponse,
        ),
        tags=["health-records"],
    )
    @_named("list")
    @require_pet_access
    def _list():
        """List ``spec.log_name`` events for the current pet (paginated)."""
        query_params = request.context.query  # type: ignore[attr-defined]
        pet_id = g.pet_id
        page = query_params.page
        page_size = query_params.page_size

        total = app.db[spec.collection].count_documents({"pet_id": pet_id})
        base_query = (
            app.db[spec.collection]
            .find({"pet_id": pet_id})
            .sort("date_time", -1)
        )
        paginated_query, _ = apply_pagination(base_query, page, page_size)
        items = [_serialize_record(r) for r in paginated_query]

        return jsonify(
            {
                spec.list_field_name: items,
                "page": page,
                "page_size": page_size,
                "total": total,
            }
        )

    # ----- GET one ---------------------------------------------------------
    @blueprint.route(f"/api/{spec.endpoint}/<record_id>", methods=["GET"])
    @api.validate(
        resp=Response(
            HTTP_200=spec.item_schema,
            HTTP_404=ErrorResponse,
            HTTP_403=ErrorResponse,
        ),
        tags=["health-records"],
    )
    @_named("get_one")
    @require_record_access(spec.collection)
    def _get_one(record_id):
        """Fetch a single ``spec.log_name`` event."""
        try:
            return jsonify(_serialize_record(g.record))
        except Exception as e:
            app.logger.error(f"Error fetching {spec.log_name}: {e}")
            return error_response("internal_error")

    # ----- PUT (update) ----------------------------------------------------
    @blueprint.route(f"/api/{spec.endpoint}/<record_id>", methods=["PUT"])
    @api.validate(
        body=Request(spec.update_schema),
        resp=Response(
            HTTP_200=SuccessResponse,
            HTTP_422=ErrorResponse,
            HTTP_403=ErrorResponse,
            HTTP_404=ErrorResponse,
            HTTP_500=ErrorResponse,
        ),
        tags=["health-records"],
    )
    @_named("update")
    @require_record_access(spec.collection)
    def _update(record_id):
        """Update a ``spec.log_name`` event."""
        from bson import ObjectId  # lazy import to keep this module Mongo-free at import time

        try:
            username = g.username
            pet_id = g.pet_id
            data = request.context.body  # type: ignore[attr-defined]

            event_dt, dt_error = parse_event_datetime_safe(
                data.date, data.time, f"{spec.log_name} update", pet_id, username
            )
            if dt_error:
                return dt_error[0], dt_error[1]

            update_data: dict = {}
            if event_dt is not None:
                update_data["date_time"] = event_dt
            for field in (
                "duration",
                "reason",
                "inhalation",
                "comment",
                "stool_type",
                "color",
                "food",
                "weight",
                "food_weight",
                "drops_type",
                "brushing_type",
                "cleaning_type",
            ):
                value = getattr(data, field, None)
                if value is not None:
                    update_data[field] = value

            result = app.db[spec.collection].update_one(
                {"_id": ObjectId(record_id)}, {"$set": update_data}
            )
            if result.matched_count == 0:
                return error_response("record_not_found")

            app.logger.info(
                f"{spec.log_name.capitalize()} updated: record_id={record_id}, "
                f"pet_id={pet_id}, user={username}"
            )
            return get_message(f"{spec.msg_prefix}_updated")
        except ValueError as e:
            app.logger.warning(
                f"Invalid input data for {spec.log_name} update: "
                f"record_id={record_id}, user={username}, error={e}"
            )
            return error_response("validation_error", str(e))

    # ----- DELETE ----------------------------------------------------------
    @blueprint.route(f"/api/{spec.endpoint}/<record_id>", methods=["DELETE"])
    @api.validate(
        resp=Response(
            HTTP_200=SuccessResponse,
            HTTP_422=ErrorResponse,
            HTTP_403=ErrorResponse,
            HTTP_404=ErrorResponse,
            HTTP_500=ErrorResponse,
        ),
        tags=["health-records"],
    )
    @_named("delete")
    @require_record_access(spec.collection)
    def _delete(record_id):
        """Delete a ``spec.log_name`` event."""
        from bson import ObjectId

        try:
            username = g.username
            pet_id = g.pet_id
            result = app.db[spec.collection].delete_one({"_id": ObjectId(record_id)})
            if result.deleted_count == 0:
                return error_response("record_not_found")
            app.logger.info(
                f"{spec.log_name.capitalize()} deleted: record_id={record_id}, "
                f"pet_id={pet_id}, user={username}"
            )
            return get_message(f"{spec.msg_prefix}_deleted")
        except ValueError as e:
            app.logger.warning(
                f"Invalid record_id for {spec.log_name} deletion: "
                f"record_id={record_id}, user={username}, error={e}"
            )
            return error_response("invalid_record_id")