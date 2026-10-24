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

from pymongo.errors import DuplicateKeyError

from bson import ObjectId
from flask import Blueprint, g, jsonify, request
from flask_pydantic_spec import Request, Response

import web.app as app
from web.security import login_required
from web.app import api
from web.decorators import require_pet_access, require_record_access
from web.errors import error_response
from web.helpers import valid_tz
from web.vaccines import GROUP_LABELS, effective_protects
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
from web.idempotency import idempotent
from web.save_lock import single_flight
from web.offline import (
    conflict_answer,
    is_stale,
    next_stamp,
    record_version,
    require_local_record_access,
    tombstone_for_name,
    version_guard,
)
from web.sync import log_deletion

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


def group_key(record: dict) -> tuple:
    """What makes two records one line of the card: a newer one replaces an older one with the same key.

    A vaccination is the same by what it is against (a change of brand is not a new vaccine), a treatment by what it is for;
    when that is not known, by the name."""
    kind = record["kind"]
    protects = effective_protects(record)
    if kind == "vaccination" and protects:
        return (kind, "protects", protects)
    if kind == "parasite" and record.get("target"):
        return (kind, "target", record["target"])
    return (kind, "title", normalize_title(record.get("title", "")))


def record_states(records: list[dict], today: date) -> dict[str, dict]:
    """For every record: its status, days to the repeat, and whether a newer one replaced it."""
    latest: dict[tuple, dict] = {}
    for record in records:
        if record.get("kind") not in REPEATING_KINDS:
            continue
        key = group_key(record)
        if key not in latest or _latest_key(record) > _latest_key(latest[key]):
            latest[key] = record
    # A treatment against both fleas/ticks and worms also covers each of them: a newer «both» replaces an older
    # «fleas_ticks» and an older «worms», or the old one would stay overdue and keep sending alerts.
    both = latest.get(("parasite", "target", "both"))

    def covered_by_both(record: dict) -> bool:
        return (
            both is not None
            and record.get("kind") == "parasite"
            and record.get("target") in ("fleas_ticks", "worms")
            and _latest_key(both) > _latest_key(record)
        )

    states = {}
    for record in records:
        rid = str(record["_id"])
        kind = record.get("kind")
        if kind in REPEATING_KINDS and (latest[group_key(record)]["_id"] != record["_id"] or covered_by_both(record)):
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


def serialize_records(records: list[dict], today: date, with_version: bool = False) -> list[dict]:
    """Newest first, each with its state and the titles of its documents.

    ``with_version`` adds what a device that writes offline reads: the version of the record (``updated_at``) and the name
    it gave the record (``local_id``). The medical card, which is also shown to a vet, leaves them out.
    """
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
                "protects": effective_protects(r),
                "protects_label": GROUP_LABELS.get(effective_protects(r) or ""),
                "complaint": r.get("complaint"),
                "diagnosis": r.get("diagnosis"),
                "recommendations": r.get("recommendations"),
                "weight_event_id": r.get("weight_event_id"),
                "documents": [docs[d] for d in r.get("document_ids") or [] if d in docs],
                **({"updated_at": record_version(r) or None, "local_id": r.get("local_id")} if with_version else {}),
            }
        )
    return out


def pet_records(pet_id: str, today: date, with_version: bool = False) -> list[dict]:
    return serialize_records(list(app.db.medical_records.find({"pet_id": pet_id})), today, with_version)


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


def document_records(pet_id: str) -> dict[str, list[dict]]:
    """For each document some record points at: those records, newest first, with what a person searches by (the title, the
    day, the diagnosis, the clinic), so that Documents can say where a file came from and be searched by it."""
    refs: dict[str, list[dict]] = {}
    cursor = app.db.medical_records.find(
        {"pet_id": pet_id, "document_ids": {"$exists": True, "$ne": []}},
        {"document_ids": 1, "kind": 1, "title": 1, "date": 1, "diagnosis": 1, "clinic": 1},
    ).sort("date", -1)
    for record in cursor:
        ref = {
            "id": str(record["_id"]),
            "kind": record.get("kind"),
            "title": record.get("title", ""),
            "date": record.get("date"),
            "diagnosis": record.get("diagnosis"),
            "clinic": record.get("clinic"),
        }
        for doc_id in record.get("document_ids") or []:
            refs.setdefault(doc_id, []).append(ref)
    return refs


def linked_document_ids(pet_id: str) -> set[str]:
    """Documents some record already points at (a certificate that has become a record)."""
    return set(document_links(pet_id))


def repeating_document_ids(pet_id: str, db=None) -> set[str]:
    """Documents linked to a vaccination or treatment record that has a repeat date: that record's reminder
    covers them. A record with no repeat date reminds about nothing, so a certificate attached to it keeps
    its own «скоро истекает»: the date the person typed must not go quiet because of a record."""
    covered: set[str] = set()
    cursor = (db or app.db).medical_records.find(
        {"pet_id": pet_id, "kind": {"$in": list(REPEATING_KINDS)}, "next_due": {"$nin": [None, ""]}},
        {"document_ids": 1},
    )
    for record in cursor:
        covered.update(record.get("document_ids") or [])
    return covered


def _own_documents(pet_id: str, ids: list[str]) -> bool:
    """Every id is a document of this pet: a record can't reach into somebody else's files."""
    if not ids:
        return True
    return app.db.documents.count_documents({"_id": {"$in": [ObjectId(i) for i in ids]}, "pet_id": pet_id}) == len(
        set(ids)
    )


def _own_weight(pet_id: str, event_id: Optional[str]) -> bool:
    """The weight a visit points at is a weighing of this pet: a record can't point into another pet's diary."""
    if not event_id:
        return True
    return app.db.events.count_documents({"_id": ObjectId(event_id), "pet_id": pet_id, "type": "weight"}, limit=1) == 1


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
        "protects": data.get("protects") if kind == "vaccination" else None,
        "complaint": data.get("complaint") if kind == "visit" else None,
        "diagnosis": data.get("diagnosis") if kind == "visit" else None,
        "recommendations": data.get("recommendations") if kind == "visit" else None,
        "weight_event_id": data.get("weight_event_id") if kind == "visit" else None,
    }
    return doc


def _record_named(local_id: str) -> Optional[dict]:
    """The record the device named with ``local_id``. A name is unique on the stand, so there is at most one."""
    return app.db.medical_records.find_one({"local_id": local_id})


def _saved_answer(record_id, local_id: Optional[str], status: int):
    named = {"local_id": local_id} if local_id else {}
    return jsonify({"message": "Запись добавлена", "success": True, "id": str(record_id), **named}), status


def _answer_for_record_name(existing: Optional[dict], pet_id: str, kind: str, local_id: str):
    """The answer to a create that names a record: the one already there (200), or why the name cannot be used.

    The same pet and kind: answered as saved, and nothing is written. Another pet's record, or another kind, holds the
    name: 409 ``local_id_taken``. No record, but a deleted one had the name: 409 ``record_deleted``.
    """
    if existing is None:
        if tombstone_for_name("medical_record", local_id, pet_id):
            return error_response("record_deleted")
        return None
    if str(existing.get("pet_id")) != str(pet_id) or existing.get("kind") != kind:
        return error_response("local_id_taken")
    return _saved_answer(existing["_id"], local_id, 200)


@medical_records_bp.route("/api/medical-records", methods=["POST"])
@login_required
@api.validate(
    body=Request(MedicalRecordCreate),
    resp=Response(HTTP_201=SuccessResponse, HTTP_404=ErrorResponse, HTTP_409=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["medical-records"],
)
@require_pet_access
@single_flight
@idempotent
def create_medical_record():
    """Add a vaccination, treatment, visit or procedure to a pet's medical card.

    One of the four kinds the card is built from. The repeat date is what makes the card answer later, and only documents belonging to this pet may be attached. ``date`` is at most a day ahead and at most 50 years back; ``next_due`` is not before ``date`` and at most 10 years ahead. A parasite treatment needs ``target``. Fields that do not belong to the kind are dropped (``batch`` and ``protects`` are a vaccination's, ``target`` a parasite treatment's, ``complaint``, ``diagnosis``, ``recommendations`` and ``weight_event_id`` a visit's; the last names the weighing in the feed that was said at the visit, and it has to be this pet's). Any member of the pet may add, change or delete any of its records. A ``local_id`` the device gives makes the request repeatable: sent again, it is answered with the record it already made (200) and nothing is written twice; a name that belongs to another pet's record is 409 ``local_id_taken``, and a name of a record that was deleted is 409 ``record_deleted``.
    """
    data = request.context.body  # type: ignore[attr-defined]
    if data.local_id:
        answer = _answer_for_record_name(_record_named(data.local_id), g.pet_id, data.kind, data.local_id)
        if answer:
            return answer
    fields = data.model_dump()
    if not _own_documents(g.pet_id, fields["document_ids"]):
        return error_response("validation_error", "Документ не найден среди документов этого питомца")
    if not _own_weight(g.pet_id, fields.get("weight_event_id")):
        return error_response("validation_error", "Запись веса не найдена среди записей этого питомца")
    now = datetime.now(timezone.utc)
    doc = {
        "pet_id": g.pet_id,
        "kind": data.kind,
        **_stored(fields, data.kind),
        "username": g.username,
        "created_at": now,
        "updated_at": now,
    }
    if data.local_id:
        doc["local_id"] = data.local_id
    try:
        result = app.db.medical_records.insert_one(doc)
    except DuplicateKeyError:
        # Two requests naming one record at the same moment: the second one finds what the first one wrote.
        answer = _answer_for_record_name(_record_named(data.local_id or ""), g.pet_id, data.kind, data.local_id or "")
        if not data.local_id or not answer:
            raise
        return answer
    app.logger.info(f"Medical record added: kind={data.kind}, pet_id={g.pet_id}, user={g.username}")
    return _saved_answer(result.inserted_id, data.local_id, 201)


@medical_records_bp.route("/api/medical-records", methods=["GET"])
@login_required
@api.validate(
    query=MedicalRecordListQuery,
    resp=Response(HTTP_404=ErrorResponse, HTTP_200=MedicalRecordListResponse, HTTP_422=ErrorResponse),
    tags=["medical-records"],
)
@require_pet_access
def list_medical_records():
    """A pet's medical records, newest first, each with its status.

    Vaccinations, parasite treatments, visits and procedures, with what each one's repeat date says today: late, close (within 14 days for a vaccination, 7 for a parasite treatment), in time, or no repeat asked for. Only vaccinations and parasite treatments get a status; visits and procedures are always ``none``. A newer record against the same thing (the same protection, the same target, otherwise the same name) is the one that counts; the older one stays in the list as history. ``tz`` decides which day 'today' is.
    """
    query = request.context.query  # type: ignore[attr-defined]
    if query.kind and query.kind not in MEDICAL_KINDS:
        return error_response("validation_error", "Неизвестный вид записи")
    records = pet_records(g.pet_id, _today(query.tz), with_version=True)
    if query.kind:
        records = [r for r in records if r["kind"] == query.kind]
    return jsonify({"records": records})


@medical_records_bp.route("/api/medical-records/<id>", methods=["GET"])
@api.validate(
    resp=Response(HTTP_200=MedicalRecordResponse, HTTP_404=ErrorResponse),
    tags=["medical-records"],
)
@require_record_access("medical_records")
def get_medical_record(id):
    """One record.

    As the card reads it, with the same status (``tz`` in the query decides which day 'today' is). A record of a pet the caller cannot see answers like a missing one; a malformed id answers 422 ``invalid_record_id``.
    """
    mine = [r for r in pet_records(g.pet_id, _today(request.args.get("tz")), with_version=True) if r["_id"] == id]
    return jsonify({"record": mine[0]})


@medical_records_bp.route("/api/medical-records/<id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(MedicalRecordUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_409=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["medical-records"],
)
@require_record_access("medical_records", deleted_kind="medical_record")
def update_medical_record(id):
    """Replace a record's contents; its pet and kind stay.

    A full replace: everything in the record can change except which pet it belongs to and what kind of thing it is, and a field left out is cleared, ``document_ids`` included (sent without it, the record lets go of its documents). The rules of creation apply (``target`` for a parasite treatment, fields of another kind dropped). A new repeat date on a vaccination puts the card's answer back to in time, or to close if it is within two weeks, when that date is still ahead and no newer record replaces this one. ``base_version`` is the ``updated_at`` the device last read: a record changed since answers 409 ``conflict`` with the record as it is now in ``record``; without it the change is applied. A record that was deleted answers 409 ``record_deleted``.
    """
    return _update_record(g.record)


@medical_records_bp.route("/api/medical-records/local/<local_id>", methods=["PUT"])
@login_required
@api.validate(
    body=Request(MedicalRecordUpdate),
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse, HTTP_409=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["medical-records"],
)
@require_local_record_access("medical_records", "medical_record")
def update_medical_record_by_local_id(local_id):
    """Replace a record by the ``local_id`` the device gave it, for when the device has not got the record's id.

    The same replace as by id, with the same ``base_version`` check. The name stays as it was created.
    """
    return _update_record(g.record)


def _current(record: dict) -> Optional[dict]:
    """The record as the card reads it now (what a rejected edit brings back as ``record``)."""
    mine = [
        r for r in pet_records(str(record["pet_id"]), _today(None), with_version=True) if r["_id"] == str(record["_id"])
    ]
    return mine[0] if mine else None


def _update_record(record: dict):
    """The update of one record found by the access check, by its id or by the local_id the device named."""
    data = request.context.body  # type: ignore[attr-defined]
    if is_stale(data.base_version, record):
        return conflict_answer(_current(record))
    kind = record["kind"]
    fields = data.model_dump(exclude={"base_version"})
    if kind == "parasite" and not fields.get("target"):
        return error_response("validation_error", "Выберите, от чего обработка")
    if not _own_documents(g.pet_id, fields["document_ids"]):
        return error_response("validation_error", "Документ не найден среди документов этого питомца")
    if not _own_weight(g.pet_id, fields.get("weight_event_id")):
        return error_response("validation_error", "Запись веса не найдена среди записей этого питомца")
    changes = {**_stored(fields, kind), "updated_at": next_stamp(record)}
    result = app.db.medical_records.update_one(
        {"_id": record["_id"], **version_guard(record, data.base_version)}, {"$set": changes}
    )
    if result.matched_count == 0:
        latest = app.db.medical_records.find_one({"_id": record["_id"]})
        if latest is None:
            return error_response("record_deleted")
        # Saved by someone else between the check above and the write.
        return conflict_answer(_current(latest))
    return jsonify({"message": "Запись сохранена", "success": True})


@medical_records_bp.route("/api/medical-records/<id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse),
    tags=["medical-records"],
)
@require_record_access("medical_records")
def delete_medical_record(id):
    """Delete a record.

    It leaves the card, the PDF and the overdue dot at once. Documents attached to it are not deleted with it: they belong to the pet, not to the record.
    """
    return _delete_record(g.record)


@medical_records_bp.route("/api/medical-records/local/<local_id>", methods=["DELETE"])
@api.validate(
    resp=Response(HTTP_200=SuccessResponse, HTTP_404=ErrorResponse),
    tags=["medical-records"],
)
@require_local_record_access("medical_records", "medical_record", tell_deleted=False)
def delete_medical_record_by_local_id(local_id):
    """Delete a record by the ``local_id`` the device gave it, for when the device has not got the record's id.

    The same delete as by id. An unknown name, a deleted record and someone else's record answer 404 ``record_not_found``.
    """
    return _delete_record(g.record)


def _delete_record(record: dict):
    """The delete of one record found by the access check, by its id or by the local_id the device named."""
    app.db.medical_records.delete_one({"_id": record["_id"]})
    log_deletion("medical_record", record["_id"], g.pet_id, local_id=record.get("local_id"))
    app.logger.info(f"Medical record deleted: id={record['_id']}, pet_id={g.pet_id}, user={g.username}")
    return jsonify({"message": "Запись удалена", "success": True})
