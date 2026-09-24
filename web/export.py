"""Data export routes (CSV/TSV/HTML/Markdown) for events + medications.

Export specs for the eight (or more, once custom types exist) event types
are built from the ``event_types`` registry at request time rather than
declared statically — a custom type is exportable the moment it's created,
no code change needed. ``medications`` keeps its own static spec since it
isn't part of the registry.

The special export type ``all`` returns a ZIP holding one file per type
that has records. Types are not merged into a single table on purpose:
their column sets genuinely differ (feeding has "Вес корма", defecation
has "Тип стула"/"Цвет стула"), so a combined sheet would be either lossy
or mostly empty cells. One file per type keeps each schema intact while
still being a single download.
"""

import csv
import io
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import quote

from flask import Blueprint, g, make_response
from flask_pydantic_spec import Response

import web.app as app  # access db, logger
from web.app import api
from web.decorators import require_pet_access
from web.errors import error_response
from web.schemas import ErrorResponse, PetIdQuery


export_bp = Blueprint("export", __name__)


FieldSpec = tuple[str, str]  # (db_field, ru_header)


@dataclass(frozen=True)
class ExportSpec:
    collection_name: str
    title: str
    fields: list[FieldSpec]
    extra_query: dict = field(default_factory=dict)
    """Extra filter merged into the ``{"pet_id": pet_id}`` base query
    (e.g. ``{"type": "defecation"}`` for an events-backed spec)."""

    enrich: Optional[Callable[[dict, list[dict]], None]] = None
    """Per-row hook invoked with ``(record, all_records)`` before serialisation.
    Used for denormalising lookups (e.g. medication names) and flattening
    an event's ``fields`` dict onto the record."""


def _enrich_medication_names(_record: dict, records: list[dict]) -> None:
    """Annotate medication_intakes rows with the human-readable name.

    Looks up names once and writes them onto each row in ``records``.
    """
    from bson import ObjectId

    med_ids = list({r["medication_id"] for r in records if r.get("medication_id")})
    if not med_ids:
        return
    meds = {
        str(m["_id"]): m.get("name", "Unknown")
        for m in app.db.medications.find({"_id": {"$in": [ObjectId(mid) for mid in med_ids]}})
    }
    for r in records:
        r["medication_name"] = meds.get(r.get("medication_id"), "Unknown")


def _replace_skip_blank(value, replacement: str = "-") -> str:
    """Treat empty / 'Пропустить' as the replacement placeholder."""
    if isinstance(value, str) and value.strip() in ("", "Пропустить"):
        return replacement
    return value or ""


MEDICATIONS_EXPORT_SPEC = ExportSpec(
    collection_name="medication_intakes",
    title="Приём препаратов",
    fields=[
        ("date_time", "Дата и время"),
        ("username", "Пользователь"),
        ("medication_name", "Препарат"),
        ("dose_taken", "Доза"),
        ("comment", "Комментарий"),
    ],
    enrich=_enrich_medication_names,
)


def _humanize_select_values(event_fields: dict, field_defs: list) -> dict:
    """Map a ``select`` field's stored value to its display text.

    Event field values are stored raw (e.g. ``inhalation: "true"``) so the
    edit form can re-select the right option; export is display-only, so
    it shows the option's label (e.g. "Да") instead.
    """
    out = dict(event_fields)
    for fd in field_defs:
        if fd.get("type") == "select" and fd["name"] in out:
            match = next(
                (opt for opt in (fd.get("options") or []) if opt["value"] == out[fd["name"]]),
                None,
            )
            if match:
                out[fd["name"]] = match["text"]
    return out


def _build_event_export_spec(event_type: dict) -> ExportSpec:
    """Build an ``ExportSpec`` for one event-type-registry entry."""
    field_defs = event_type.get("fields", [])
    columns: list[FieldSpec] = [("date_time", "Дата и время"), ("username", "Пользователь")]
    columns += [(f["name"], f["label"]) for f in field_defs]
    columns += [("comment", "Комментарий")]

    def _enrich(record: dict, _records: list[dict], _field_defs=field_defs) -> None:
        record.update(_humanize_select_values(record.pop("fields", {}), _field_defs))

    return ExportSpec(
        collection_name="events",
        title=event_type["label"],
        fields=columns,
        extra_query={"type": event_type["key"]},
        enrich=_enrich,
    )


def _build_export_specs() -> dict[str, ExportSpec]:
    """All currently exportable types: every registered event type, plus
    the static ``medications`` spec. Built fresh per request so a custom
    type created a moment ago is immediately exportable."""
    specs: dict[str, ExportSpec] = {"medications": MEDICATIONS_EXPORT_SPEC}
    for event_type in app.db.event_types.find({}):
        specs[event_type["key"]] = _build_event_export_spec(event_type)
    return specs


# ---------------------------------------------------------------------------
# Serialisers — one per format, all return ``(bytes, mimetype, filename_suffix)``.
# ---------------------------------------------------------------------------


def _serialize_csv(records: list[dict], fields: list[FieldSpec]) -> tuple[bytes, str, str]:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([ru for _, ru in fields])
    for r in records:
        writer.writerow([str(r.get(en, "") or "") for en, _ in fields])
    return output.getvalue().encode("utf-8-sig"), "text/csv", "csv"


def _serialize_tsv(records: list[dict], fields: list[FieldSpec]) -> tuple[bytes, str, str]:
    output = io.StringIO()
    writer = csv.writer(output, delimiter="\t")
    writer.writerow([ru for _, ru in fields])
    for r in records:
        writer.writerow([str(r.get(en, "") or "") for en, _ in fields])
    return output.getvalue().encode("utf-8"), "text/tab-separated-values", "tsv"


def _serialize_html(title: str, records: list[dict], fields: list[FieldSpec]) -> tuple[bytes, str, str]:
    parts: list[str] = [
        '<!DOCTYPE html><html lang="ru"><head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>{title}</title>",
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
        "padding:20px;background:#000;color:#fff}"
        "table{width:100%;border-collapse:collapse;background:#1c1c1e;border-radius:10px;overflow:hidden}"
        "th{background:#2c2c2e;padding:12px;text-align:left;font-weight:600;border-bottom:1px solid #38383a}"
        "td{padding:12px;border-bottom:1px solid #38383a}"
        "tr:last-child td{border-bottom:none}"
        "tr:hover{background:#2c2c2e}"
        "</style></head><body>",
        f"<h1>{title}</h1><table><thead><tr>",
    ]
    for _, ru in fields:
        parts.append(f"<th>{ru}</th>")
    parts.append("</tr></thead><tbody>")
    for r in records:
        parts.append("<tr>")
        for en, _ in fields:
            value = str(r.get(en, "") or "").replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f"<td>{value}</td>")
        parts.append("</tr>")
    parts.append("</tbody></table></body></html>")
    return "".join(parts).encode("utf-8"), "text/html", "html"


def _serialize_md(title: str, records: list[dict], fields: list[FieldSpec]) -> tuple[bytes, str, str]:
    lines: list[str] = [f"# {title}", ""]
    lines.append("| " + " | ".join(ru for _, ru in fields) + " |")
    lines.append("|" + "---|" * len(fields))
    for r in records:
        lines.append("| " + " | ".join(str(r.get(en, "") or "").replace("|", "\\|") for en, _ in fields) + " |")
    return ("\n".join(lines) + "\n").encode("utf-8"), "text/markdown", "md"


SERIALIZERS = {
    "csv": _serialize_csv,
    "tsv": _serialize_tsv,
    "html": _serialize_html,
    "md": _serialize_md,
}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


ALL_TYPES = "all"


def _render_export(spec: ExportSpec, pet_id, format_type, serializer):
    """Serialise one export type.

    Returns ``(content, mimetype, suffix)``, or ``(None, None, None)`` when
    the pet has no records of that type — the caller decides whether that
    is an error (single-type export) or simply a file to omit (the ZIP).
    """
    query = {"pet_id": pet_id, **spec.extra_query}
    records = list(app.db[spec.collection_name].find(query).sort([("date_time", -1)]))
    if not records:
        return None, None, None

    # Optional denormalisation pass (e.g. medication names, event field
    # flattening + select-value humanising).
    if spec.enrich is not None:
        for r in records:
            spec.enrich(r, records)

    # Common per-row cleanup shared by every export format.
    for r in records:
        dt = r.get("date_time")
        r["date_time"] = dt.strftime("%d.%m.%Y %H:%M") if isinstance(dt, datetime) else str(dt or "")
        if not r.get("username"):
            r["username"] = "-"
        r["comment"] = _replace_skip_blank(r.get("comment", ""))
        r["food"] = _replace_skip_blank(r.get("food", ""))

    # Some serializers need the title (html/md); csv/tsv ignore it.
    if format_type in ("html", "md"):
        return serializer(spec.title, records, spec.fields)
    return serializer(records, spec.fields)


def _render_all_types_zip(pet_id, format_type, serializer, specs: dict[str, ExportSpec]):
    """Bundle every type that has records into a single ZIP.

    Each entry keeps its own column set, named after the type's title, so
    the archive is the "separate exports" the UI offers — just delivered
    as one download instead of several.

    Returns ``(zip_bytes, included_titles)``; an empty list means the pet
    has no records at all.
    """
    buffer = io.BytesIO()
    included = []

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for spec in specs.values():
            content, _mimetype, suffix = _render_export(spec, pet_id, format_type, serializer)
            if content is None:
                # Nothing logged for this type — leave it out rather than
                # shipping an empty file with only a header row.
                continue
            entry_name = f"{spec.title.replace(' ', '_').lower()}.{suffix}"
            archive.writestr(entry_name, content)
            included.append(spec.title)

    return buffer.getvalue(), included


@export_bp.route("/api/export/<export_type>/<format_type>", methods=["GET"])
@api.validate(
    query=PetIdQuery,
    resp=Response(
        HTTP_200=None,
        HTTP_422=ErrorResponse,
        HTTP_401=ErrorResponse,
        HTTP_403=ErrorResponse,
        HTTP_500=ErrorResponse,
    ),
    tags=["export"],
)
@require_pet_access
def export_data(export_type, format_type):
    """Export data in various formats."""
    try:
        pet_id = g.pet_id  # Provided by @require_pet_access
        username = g.username  # Provided by @require_pet_access

        specs = _build_export_specs()

        if export_type != ALL_TYPES and export_type not in specs:
            return error_response("export_invalid_type")

        serializer = SERIALIZERS.get(format_type)
        if serializer is None:
            return error_response("export_invalid_format")

        if export_type == ALL_TYPES:
            content, included = _render_all_types_zip(pet_id, format_type, serializer, specs)
            if not included:
                return error_response("no_data_for_export")
            mimetype = "application/zip"
            title, suffix = "все_записи", "zip"
        else:
            spec = specs[export_type]
            content, mimetype, suffix = _render_export(spec, pet_id, format_type, serializer)
            if content is None:
                return error_response("no_data_for_export")
            title, included = spec.title, [spec.title]

        filename_base = f"{title.replace(' ', '_').lower()}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
        filename = f"{filename_base}.{suffix}"
        encoded_filename = quote(filename)

        response = make_response(content)
        response.headers["Content-Type"] = mimetype
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}"
        response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
        app.logger.info(
            f"Data exported: type={export_type}, format={format_type}, "
            f"pet_id={pet_id}, user={username}, sections={len(included)}"
        )
        return response

    except ValueError as e:
        app.logger.warning(
            f"Invalid input data for export: type={export_type}, format={format_type}, "
            f"pet_id={pet_id}, user={username}, error={e}"
        )
        return error_response("validation_error", str(e))
