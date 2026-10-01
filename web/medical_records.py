"""Medical records: vaccinations, parasite treatments, vet visits, procedures.

One record is one fact with a date (no time: «12 мая», not «12 мая в 14:30»)
and, for vaccinations and treatments, when to repeat it. They live in their
own collection rather than among the feed's events: the events engine has no
date-only record, no date fields, no way to keep a type out of the tiles and
the trend charts, and these records have none of that in common with a meal
or a weight. They don't appear in the feed; they are the medical card.

«Replaced by a newer one»: among the records of one kind with the same title,
only the latest counts for «when is it due». An earlier rabies shot with
next_due last year is history once this year's is entered, not an overdue
one. The card and the reminders read this through ``record_states``.
"""

from datetime import date, datetime, timezone
from typing import Optional

from bson import ObjectId
from flask import Blueprint, g, jsonify, request
from flask_pydantic_spec import Request, Response

import web.app as app
from web.app import api
from web.decorators import require_pet_access, require_record_access
from web.errors import error_response
from web.helpers import valid_tz
from web.schemas import (
    MEDICAL_KINDS,
    ErrorResponse,
    MedicalRecordCreate,
    MedicalRecordListQuery,
    MedicalRecordListResponse,
    MedicalRecordResponse,
    MedicalRecordUpdate,
    SuccessResponse,
)
from zoneinfo import ZoneInfo

medical_records_bp = Blueprint("medical_records", __name__)

# How many days before a repeat it counts as «скоро», by kind. A vaccination
# is the same 14 days as the push for an expiring document; a treatment is
# repeated more often and noticed a week ahead.
SOON_DAYS = {"vaccination": 14, "parasite": 7}
# Kinds for which «when to repeat» means something and a newer record replaces an older.
REPEATING_KINDS = tuple(SOON_DAYS)


def normalize_title(title: str) -> str:
    """«Нобивак  DHPPi» and «нобивак dhppi» are one vaccine."""
    return " ".join((title or "").casefold().split())


def _today(tz_name: Optional[str]) -> date:
    zone = valid_tz(tz_name)
    return datetime.now(ZoneInfo(zone) if zone else timezone.utc).date()


def due_status(kind: str, next_due: Optional[str], today: date) -> tuple[str, Optional[int]]:
    if not next_due or kind not in SOON_DAYS:
        return "none", None
    try:
        due = datetime.strptime(next_due[:10], "%Y-%m-%d").date()
    except ValueError:
        return "none", None
    days_left = (due - today).days
    if days_left < 0:
        return "overdue", days_left
    return ("soon" if days_left <= SOON_DAYS[kind] else "ok"), days_left


def _latest_key(record: dict):
    return (record.get("date") or "", str(record.get("created_at") or ""), str(record["_id"]))


def record_states(records: list[dict], today: date) -> dict[str, dict]:
    """For every record: its status, days to the repeat, and whether a newer one replaced it."""
    latest: dict[tuple, dict] = {}
    for record in records:
        if record.get("kind") not in REPEATING_KINDS:
            continue
        key = (record["kind"], normalize_title(record.get("title", "")))
        if key not in latest or _latest_key(record) > _latest_key(latest[key]):
            latest[key] = record
    states = {}
    for record in records:
        rid = str(record["_id"])
        kind = record.get("kind")
        if kind in REPEATING_KINDS and latest[(kind, normalize_title(record.get("title", "")))]["_id"] != record["_id"]:
            states[rid] = {"status": "none", "days_left": None, "superseded": True}
            continue
        status, days_left = due_status(kind, record.get("next_due"), today)
        states[rid] = {"status": status, "days_left": days_left, "superseded": False}
    return states


def _documents_by_id(records: list[dict]) -> dict[str, dict]:
    ids = {d for r in records for d in r.get("document_ids") or []}
    if not ids:
        return {}
    found = app.db.documents.find({"_id": {"$in": [ObjectId(i) for i in ids]}})
    return {str(d["_id"]): {"id": str(d["_id"]), "title": d.get("title", "")} for d in found}


def serialize_records(records: list[dict], today: date) -> list[dict]:
    """Newest first, each with its state and the titles of its documents."""
    states = record_states(records, today)
    docs = _documents_by_id(records)
    out = []
    for r in sorted(records, key=_latest_key, reverse=True):
        rid = str(r["_id"])
        out.append(
            {
                "_id": rid,
                "pet_id": str(r.get("pet_id", "")),
                "kind": r.get("kind"),
                "date": r.get("date"),
                "title": r.get("title", ""),
                "next_due": r.get("next_due"),
                **states[rid],
                "clinic": r.get("clinic"),
                "vet": r.get("vet"),
                "note": r.get("note"),
                "batch": r.get("batch"),
                "target": r.get("target"),
                "complaint": r.get("complaint"),
                "diagnosis": r.get("diagnosis"),
                "recommendations": r.get("recommendations"),
                "documents": [docs[d] for d in r.get("document_ids") or [] if d in docs],
            }
        )
    return out


def pet_records(pet_id: str, today: date) -> list[dict]:
    return serialize_records(list(app.db.medical_records.find({"pet_id": pet_id})), today)


def document_links(pet_id: str, db=None) -> dict[str, list[str]]:
    """For each document some record points at: the kinds of those records.

    A certificate that has become a record is shown as that record, not twice;
    the Documents list says «В медкарте» for it; and when the record repeats
    (a vaccination, a treatment) its own reminder speaks for it, so the
    certificate's «скоро истекает» push is kept back. ``db`` is for the
    reminder sender, which brings its own.
    """
    links: dict[str, list[str]] = {}
    for record in (db or app.db).medical_records.find({"pet_id": pet_id}, {"document_ids": 1, "kind": 1}):
        for doc_id in record.get("document_ids") or []:
            kinds = links.setdefault(doc_id, [])
            if record["kind"] not in kinds:
                kinds.append(record["kind"])
    return links


def linked_document_ids(pet_id: str) -> set[str]:
    """Documents some record already points at (a certificate that has become a record)."""
    return set(document_links(pet_id))


def repeating_document_ids(pet_id: str, db=None) -> set[str]:
    """Documents linked to a vaccination or treatment record: that record's reminder covers them."""
    return {doc_id for doc_id, kinds in document_links(pet_id, db).items() if any(k in REPEATING_KINDS for k in kinds)}


def _own_documents(pet_id: str, ids: list[str]) -> bool:
    """Every id is a document of this pet: a record can't reach into somebody else's files."""
    if not ids:
        return True
    return app.db.documents.count_documents({"_id": {"$in": [ObjectId(i) for i in ids]}, "pet_id": pet_id}) == len(
        set(ids)
    )


def _stored(data: dict, kind: str) -> dict:
    """The fields a record of this kind keeps."""
    doc = {
        "date": data["date"],
        "title": data["title"],
        "next_due": data.get("next_due"),
        "clinic": data.get("clinic"),
        "vet": data.get("vet"),
        "note": data.get("note"),
        "document_ids": list(dict.fromkeys(data.get("document_ids") or [])),
        "batch": data.get("batch") if kind == "vaccination" else None,
        "target": data.get("target") if kind == "parasite" else None,
        "complaint": data.get("complaint") if kind == "visit" else None,
        "diagnosis": data.get("diagnosis") if kind == "visit" else None,
        "recommendations": data.get("recommendations") if kind == "visit" else None,
    }
    return doc


@medical_records_bp.route("/api/medical-records", methods=["POST"])
@api.validate(
    body=Request(MedicalRecordCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["medical-records"],
)
@require_pet_access
def create_medical_record():
    """Add a vaccination, treatment, visit or procedure to a pet's medical card."""
    data = request.context.body  # type: ignore[attr-defined]
    fields = data.model_dump()
    if not _own_documents(g.pet_id, fields["document_ids"]):
        return error_response("validation_error", "Документ не найден среди документов этого питомца")
    now = datetime.now(timezone.utc)
    doc = {
        "pet_id": g.pet_id,
        "kind": data.kind,
        **_stored(fields, data.kind),
        "username": g.username,
        "created_at": now,
        "updated_at": now,
    }
    result = app.db.medical_records.insert_one(doc)
    app.logger.info(f"Medical record added: kind={data.kind}, pet_id={g.pet_id}, user={g.username}")
    return jsonify({"message": "Запись добавлена", "success": True, "id": str(result.inserted_id)}), 201


@medical_records_bp.route("/api/medical-records", methods=["GET"])
@api.validate(
    query=MedicalRecordListQuery,
    resp=Response(HTTP_200=MedicalRecordListResponse, HTTP_403=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["medical-records"],
)
@require_pet_access
def list_medical_records():
    """A pet's medical records, newest first, each with its status."""
    query = request.context.query  # type: ignore[attr-defined]
    if query.kind and query.kind not in MEDICAL_KINDS:
        return error_response("validation_error", "Неизвестный вид записи")
    records = pet_records(g.pet_id, _today(query.tz))
    if query.kind:
        records = [r for r in records if r["kind"] == query.kind]
    return jsonify({"records": records})


@medical_records_bp.route("/api/medical-records/<id>", methods=["GET"])
@api.validate(
    resp=Response(HTTP_200=MedicalRecordResponse, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse),
    tags=["medical-records"],
)
@require_record_access("medical_records")
def get_medical_record(id):
    """One record."""
    mine = [r for r in pet_records(g.pet_id, _today(request.args.get("tz"))) if r["_id"] == id]
    return jsonify({"record": mine[0]})


@medical_records_bp.route("/api/medical-records/<id>", methods=["PUT"])
@api.validate(
    body=Request(MedicalRecordUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["medical-records"],
)
@require_record_access("medical_records")
def update_medical_record(id):
    """Replace a record's contents; its pet and kind stay."""
    data = request.context.body  # type: ignore[attr-defined]
    kind = g.record["kind"]
    fields = data.model_dump()
    if kind == "parasite" and not fields.get("target"):
        return error_response("validation_error", "Укажите, от чего обработка")
    if not _own_documents(g.pet_id, fields["document_ids"]):
        return error_response("validation_error", "Документ не найден среди документов этого питомца")
    changes = {**_stored(fields, kind), "updated_at": datetime.now(timezone.utc)}
    app.db.medical_records.update_one({"_id": g.record["_id"]}, {"$set": changes})
    return jsonify({"message": "Запись сохранена", "success": True})


@medical_records_bp.route("/api/medical-records/<id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse),
    tags=["medical-records"],
)
@require_record_access("medical_records")
def delete_medical_record(id):
    """Delete a record."""
    app.db.medical_records.delete_one({"_id": g.record["_id"]})
    app.logger.info(f"Medical record deleted: id={id}, pet_id={g.pet_id}, user={g.username}")
    return jsonify({"message": "Запись удалена", "success": True})
