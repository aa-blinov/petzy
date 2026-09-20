"""Data export routes (CSV/TSV/HTML/Markdown) for health records.

The list of supported export types lives in :data:`EXPORT_SPECS`. Adding a
new export type is one entry in that mapping plus, if needed, a record-level
transform function for denormalised lookups (see the ``medications`` case).

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
from dataclasses import dataclass
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


# ---------------------------------------------------------------------------
# Export specs
# ---------------------------------------------------------------------------
#
# ``collection_name`` is looked up at request time against ``app.db``, so
# tests that patch ``web.app.db`` see the same collection the route does.


FieldSpec = tuple[str, str]  # (db_field, ru_header)


@dataclass(frozen=True)
class ExportSpec:
    collection_name: str
    title: str
    fields: list[FieldSpec]
    enrich: Optional[Callable[[dict, list[dict]], None]] = None
    """Per-row hook invoked with ``(record, all_records)`` before serialisation.
    Used for denormalising lookups (e.g. medication names) and one-off
    field conversions (e.g. ``inhalation`` boolean → Russian word)."""


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
        for m in app.db.medications.find(
            {"_id": {"$in": [ObjectId(mid) for mid in med_ids]}}
        )
    }
    for r in records:
        r["medication_name"] = meds.get(r.get("medication_id"), "Unknown")


def _replace_skip_blank(value, replacement: str = "-") -> str:
    """Treat empty / 'Пропустить' as the replacement placeholder."""
    if isinstance(value, str) and value.strip() in ("", "Пропустить"):
        return replacement
    return value or ""


def _localize_inhalation(record: dict, _records: list[dict]) -> None:
    """Convert the boolean ``inhalation`` field to a Russian word for export."""
    inh = record.get("inhalation")
    if inh is True:
        record["inhalation"] = "Да"
    elif inh is False:
        record["inhalation"] = "Нет"
    else:
        record["inhalation"] = "-"


EXPORT_SPECS: dict[str, ExportSpec] = {
    "feeding": ExportSpec(
        collection_name="feedings",
        title="Дневные порции корма",
        fields=[
            ("date_time", "Дата и время"),
            ("username", "Пользователь"),
            ("food_weight", "Вес корма (г)"),
            ("comment", "Комментарий"),
        ],
    ),
    "asthma": ExportSpec(
        collection_name="asthma_attacks",
        title="Приступы астмы",
        fields=[
            ("date_time", "Дата и время"),
            ("username", "Пользователь"),
            ("duration", "Длительность"),
            ("reason", "Причина"),
            ("inhalation", "Ингаляция"),
            ("comment", "Комментарий"),
        ],
        enrich=_localize_inhalation,
    ),
    "defecation": ExportSpec(
        collection_name="defecations",
        title="Дефекации",
        fields=[
            ("date_time", "Дата и время"),
            ("username", "Пользователь"),
            ("stool_type", "Тип стула"),
            ("color", "Цвет стула"),
            ("food", "Корм"),
            ("comment", "Комментарий"),
        ],
    ),
    "litter": ExportSpec(
        collection_name="litter_changes",
        title="Смена лотка",
        fields=[
            ("date_time", "Дата и время"),
            ("username", "Пользователь"),
            ("comment", "Комментарий"),
        ],
    ),
    "weight": ExportSpec(
        collection_name="weights",
        title="Вес",
        fields=[
            ("date_time", "Дата и время"),
            ("username", "Пользователь"),
            ("weight", "Вес (кг)"),
            ("food", "Корм"),
            ("comment", "Комментарий"),
        ],
    ),
    "eye_drops": ExportSpec(
        collection_name="eye_drops",
        title="Закапывание глаз",
        fields=[
            ("date_time", "Дата и время"),
            ("username", "Пользователь"),
            ("drops_type", "Тип капель"),
            ("comment", "Комментарий"),
        ],
    ),
    "tooth_brushing": ExportSpec(
        collection_name="tooth_brushing",
        title="Чистка зубов",
        fields=[
            ("date_time", "Дата и время"),
            ("username", "Пользователь"),
            ("brushing_type", "Способ чистки"),
            ("comment", "Комментарий"),
        ],
    ),
    "ear_cleaning": ExportSpec(
        collection_name="ear_cleaning",
        title="Чистка ушей",
        fields=[
            ("date_time", "Дата и время"),
            ("username", "Пользователь"),
            ("cleaning_type", "Способ чистки"),
            ("comment", "Комментарий"),
        ],
    ),
    "medications": ExportSpec(
        collection_name="medication_intakes",
        title="Прием препаратов",
        fields=[
            ("date_time", "Дата и время"),
            ("username", "Пользователь"),
            ("medication_name", "Препарат"),
            ("dose_taken", "Доза"),
            ("comment", "Комментарий"),
        ],
        enrich=_enrich_medication_names,
    ),
}


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
        "<!DOCTYPE html><html lang=\"ru\"><head>",
        "<meta charset=\"UTF-8\">",
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
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
        lines.append(
            "| "
            + " | ".join(
                str(r.get(en, "") or "").replace("|", "\\|") for en, _ in fields
            )
            + " |"
        )
    return ("\n".join(lines) + "\n").encode("utf-8"), "text/markdown", "md"


SERIALIZERS = {
    "csv": _serialize_csv,
    "tsv": _serialize_tsv,
    "html": _serialize_html,
    "md": _serialize_md,
}


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


ALL_TYPES = "all"


def _render_export(spec, pet_id, format_type, serializer):
    """Serialise one export type.

    Returns ``(content, mimetype, suffix)``, or ``(None, None, None)`` when
    the pet has no records of that type — the caller decides whether that
    is an error (single-type export) or simply a file to omit (the ZIP).
    """
    records = list(
        app.db[spec.collection_name]
        .find({"pet_id": pet_id})
        .sort([("date_time", -1)])
    )
    if not records:
        return None, None, None

    # Optional denormalisation pass (e.g. medication names).
    if spec.enrich is not None:
        for r in records:
            spec.enrich(r, records)

    # Common per-row cleanup shared by every export format.
    for r in records:
        dt = r.get("date_time")
        r["date_time"] = (
            dt.strftime("%d.%m.%Y %H:%M") if isinstance(dt, datetime) else str(dt or "")
        )
        if not r.get("username"):
            r["username"] = "-"
        r["comment"] = _replace_skip_blank(r.get("comment", ""))
        r["food"] = _replace_skip_blank(r.get("food", ""))

    # Some serializers need the title (html/md); csv/tsv ignore it.
    if format_type in ("html", "md"):
        return serializer(spec.title, records, spec.fields)
    return serializer(records, spec.fields)


def _render_all_types_zip(pet_id, format_type, serializer):
    """Bundle every type that has records into a single ZIP.

    Each entry keeps its own column set, named after the type's title, so
    the archive is the "separate exports" the UI offers — just delivered
    as one download instead of nine.

    Returns ``(zip_bytes, included_titles)``; an empty list means the pet
    has no records at all.
    """
    buffer = io.BytesIO()
    included = []

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for export_type, spec in EXPORT_SPECS.items():
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

        if export_type != ALL_TYPES and export_type not in EXPORT_SPECS:
            return error_response("export_invalid_type")

        serializer = SERIALIZERS.get(format_type)
        if serializer is None:
            return error_response("export_invalid_format")

        if export_type == ALL_TYPES:
            content, included = _render_all_types_zip(pet_id, format_type, serializer)
            if not included:
                return error_response("no_data_for_export")
            mimetype = "application/zip"
            title, suffix = "все_записи", "zip"
        else:
            spec = EXPORT_SPECS[export_type]
            content, mimetype, suffix = _render_export(spec, pet_id, format_type, serializer)
            if content is None:
                return error_response("no_data_for_export")
            title, included = spec.title, [spec.title]

        filename_base = (
            f"{title.replace(' ', '_').lower()}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
        )
        filename = f"{filename_base}.{suffix}"
        encoded_filename = quote(filename)

        response = make_response(content)
        response.headers["Content-Type"] = mimetype
        response.headers["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{encoded_filename}"
        )
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