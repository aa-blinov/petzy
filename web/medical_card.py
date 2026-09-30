"""A pet's medical card: one read-only page assembled from what the app
already keeps (the pet's profile, weight records, active medications,
vaccination documents, recent results), and the same page as a PDF to give
to a vet.

Nothing here is stored. The card is built on request, so it is never stale
and there is no second copy of anything to keep in step: a weight entered a
minute ago is on it a minute later.
"""

from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, make_response, request
from flask_pydantic_spec import Request, Response

import web.app as app  # db, logger
from web.courses import ACTIVE, ENDED, course_status
from web.app import api
from web.errors import error_response
from web.helpers import get_pet_and_validate, valid_tz
from web.schemas import (
    ErrorResponse,
    MedicalCardQuery,
    MedicalCardResponse,
    MedicalProfile,
    MedicalProfileOut,
    MedicalProfileResponse,
)
from web.security import get_current_user, login_required

medical_card_bp = Blueprint("medical_card", __name__)

# How many days before its end a vaccination counts as «скоро истекает». The
# same window as the push reminder for documents
# (DOCUMENT_EXPIRY_REMINDER_DAYS_BEFORE in scripts/send_medication_reminders.py)
# and the orange badge in the documents list.
EXPIRY_SOON_DAYS = 14

WEIGHT_POINTS = 12
RECENT_DOCUMENTS = 5
PAST_COURSES = 10
# Documents a vet reads: results and conclusions. Scans are big and
# insurance is paperwork; both stay in «Документы».
RECENT_DOCUMENT_CATEGORIES = ("lab_result", "conclusion")
WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

# A pet stores a code for the species and the gender; the card shows words
# (frontend/src/utils/species.ts and constants.ts). An old free-text value
# («Кот», «Мужской») is shown as it was typed.
SPECIES_LABELS = {
    "cat": "Кот",
    "dog": "Собака",
    "rabbit": "Кролик",
    "ferret": "Хорёк",
    "guinea_pig": "Морская свинка",
    "chinchilla": "Шиншилла",
    "rat": "Крыса",
    "hamster": "Хомяк",
    "bird": "Птица",
    "fish": "Рыбка",
    "turtle": "Черепаха",
    "reptile": "Ящерица или змея",
    "other": "Другой питомец",
}
GENDER_LABELS = {"male": "Мальчик", "female": "Девочка", "Мужской": "Мальчик", "Женский": "Девочка"}


def _plural(n: int, one: str, few: str, many: str) -> str:
    mod10, mod100 = n % 10, n % 100
    if mod10 == 1 and mod100 != 11:
        return one
    if 2 <= mod10 <= 4 and not 12 <= mod100 <= 14:
        return few
    return many


def age_text(birth_date: Optional[str], today: date) -> Optional[str]:
    """«5 лет», «8 месяцев», «3 недели»: the same wording as the app's pet card."""
    if not birth_date:
        return None
    try:
        born = datetime.strptime(str(birth_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    months = (today.year - born.year) * 12 + today.month - born.month
    if today.day < born.day:
        months -= 1
    if months < 0:
        return None
    if months < 1:
        days = max(0, (today - born).days)
        if days < 7:
            return f"{days} {_plural(days, 'день', 'дня', 'дней')}"
        weeks = days // 7
        return f"{weeks} {_plural(weeks, 'неделя', 'недели', 'недель')}"
    if months < 12:
        return f"{months} {_plural(months, 'месяц', 'месяца', 'месяцев')}"
    years = months // 12
    return f"{years} {_plural(years, 'год', 'года', 'лет')}"


def _number(value) -> str:
    """1.0 -> «1», 0.5 -> «0,5»."""
    text = f"{float(value):g}"
    return text.replace(".", ",")


def schedule_text(schedule: dict) -> str:
    days = sorted(set(schedule.get("days") or []))
    times = ", ".join(sorted(schedule.get("times") or []))
    when = f"в {times}" if times else ""
    if len(days) == 7:
        return f"Ежедневно {when}".strip()
    names = ", ".join(WEEKDAYS[d] for d in days if 0 <= d < 7)
    return f"По {names} {when}".strip() if names else when


def _today(tz_name: Optional[str]) -> date:
    zone = valid_tz(tz_name)
    return datetime.now(ZoneInfo(zone) if zone else timezone.utc).date()


def neutered_text(is_neutered, gender) -> Optional[str]:
    """«кастрирован» for a male, «стерилизована» for a female, both when the gender isn't set."""
    if is_neutered is None:
        return None
    not_ = "" if is_neutered else "не "
    if gender in ("male", "Мужской"):
        return f"{not_}кастрирован"
    if gender in ("female", "Женский"):
        return f"{not_}стерилизована"
    return "кастрация или стерилизация: " + ("да" if is_neutered else "нет")


def _as_date_str(value) -> Optional[str]:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10] if value else None


def _vaccination_status(expires_at: Optional[str], today: date) -> tuple[str, Optional[int]]:
    if not expires_at:
        return "none", None
    try:
        ends = datetime.strptime(expires_at[:10], "%Y-%m-%d").date()
    except ValueError:
        return "none", None
    days_left = (ends - today).days
    if days_left < 0:
        return "expired", days_left
    return ("soon" if days_left <= EXPIRY_SOON_DAYS else "valid"), days_left


def _weight(pet_id: str) -> Optional[dict]:
    cursor = app.db.events.find({"pet_id": pet_id, "type": "weight"}).sort("date_time", -1).limit(WEIGHT_POINTS * 3)
    points = []
    for record in cursor:
        value = (record.get("fields") or {}).get("weight")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        points.append({"date": _as_date_str(record.get("date_time")), "value": float(value)})
        if len(points) == WEIGHT_POINTS:
            break
    if not points:
        return None
    return {"latest": points[0], "series": list(reversed(points))}


def _intake_stats(med_ids: list[str]) -> dict[str, dict]:
    """Per course: doses given and skipped, and the days of the first and last given dose."""
    stats: dict[str, dict] = {}
    if not med_ids:
        return stats
    for intake in app.db.medication_intakes.find({"medication_id": {"$in": med_ids}}):
        row = stats.setdefault(intake["medication_id"], {"given": 0, "skipped": 0, "first": None, "last": None})
        if intake.get("skipped"):
            row["skipped"] += 1
            continue
        row["given"] += 1
        day = _as_date_str(intake.get("date_time"))
        if day:
            row["first"] = day if row["first"] is None or day < row["first"] else row["first"]
            row["last"] = day if row["last"] is None or day > row["last"] else row["last"]
    return stats


def _courses(pet_id: str, today: date) -> tuple[list[dict], list[dict]]:
    """``(current, past)``: the courses going on or still to begin, and the finished ones.

    A course made before dates existed has none stored: its start is then its
    first given dose (or the day it was added), and, once it is switched off,
    its end is the last given dose.
    """
    today_key = today.isoformat()
    meds = list(app.db.medications.find({"pet_id": pet_id}))
    stats = _intake_stats([str(m["_id"]) for m in meds])
    current, past = [], []
    for med in meds:
        status = course_status(med, today_key)
        stat = stats.get(str(med["_id"]), {"given": 0, "skipped": 0, "first": None, "last": None})
        started = _as_date_str(med.get("started_on")) or stat["first"] or _as_date_str(med.get("created_at"))
        ended = _as_date_str(med.get("ended_on")) or (stat["last"] if status == ENDED else None)
        unit = med.get("dose_unit") or ""
        dose = med.get("default_dose")
        item = {
            "id": str(med["_id"]),
            "name": med.get("name", ""),
            "type": med.get("type") or None,
            "strength": med.get("strength") or None,
            "dose_text": f"{_number(dose)} {unit}".strip() if dose else None,
            "schedule_text": schedule_text(med.get("schedule") or {}),
            "comment": med.get("comment") or None,
            "purpose": med.get("purpose") or None,
            "prescribed_by": med.get("prescribed_by") or None,
            "status": status,
            "started_on": started,
            "ended_on": ended,
            "given": stat["given"],
            "skipped": stat["skipped"],
        }
        (past if status == ENDED else current).append(item)
    current.sort(key=lambda c: (c["status"] != ACTIVE, c["name"].casefold()))
    # The latest finished first; one with no known end goes last.
    past.sort(key=lambda c: (c["ended_on"] or "", c["name"]), reverse=True)
    return current, past[:PAST_COURSES]


def _vaccinations(pet_id: str, today: date) -> list[dict]:
    result = []
    for doc in app.db.documents.find({"pet_id": pet_id, "category": "vaccination"}):
        expires = _as_date_str(doc.get("expires_at"))
        status, days_left = _vaccination_status(expires, today)
        result.append(
            {
                "id": str(doc["_id"]),
                "title": doc.get("title", ""),
                "expires_at": expires,
                "status": status,
                "days_left": days_left,
                "note": doc.get("note") or None,
            }
        )
    # The latest cover first (ISO dates sort as text); the ones with no end date last.
    dated = sorted((v for v in result if v["expires_at"]), key=lambda v: v["expires_at"], reverse=True)
    return dated + [v for v in result if not v["expires_at"]]


def _recent_documents(pet_id: str) -> list[dict]:
    cursor = (
        app.db.documents.find({"pet_id": pet_id, "category": {"$in": list(RECENT_DOCUMENT_CATEGORIES)}})
        .sort("created_at", -1)
        .limit(RECENT_DOCUMENTS)
    )
    return [
        {
            "id": str(doc["_id"]),
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "added": _as_date_str(doc.get("created_at")) or "",
        }
        for doc in cursor
    ]


def _profile(pet: dict) -> dict:
    """The stored profile as the API shows it; an empty one when nothing is filled in."""
    stored = pet.get("medical_profile") or {}
    try:
        return MedicalProfileOut.model_validate(stored).model_dump()
    except Exception:  # a hand-edited or half-written document must not take the card down
        app.logger.warning(f"Unreadable medical_profile on pet {pet.get('_id')}")
        return MedicalProfileOut().model_dump()


def build_medical_card(pet: dict, username: str, today: date) -> dict:
    pet_id = str(pet["_id"])
    birth = _as_date_str(pet.get("birth_date"))
    current_courses, past_courses = _courses(pet_id, today)
    return {
        "pet": {
            "name": pet.get("name", ""),
            "species": SPECIES_LABELS.get(pet.get("species"), pet.get("species")) or None,
            "breed": pet.get("breed") or None,
            "birth_date": birth,
            "age_text": age_text(birth, today),
            "gender": GENDER_LABELS.get(pet.get("gender"), pet.get("gender")) or None,
            "neutered_text": neutered_text(pet.get("is_neutered"), pet.get("gender")),
            "health_notes": (pet.get("health_notes") or "").strip() or None,
        },
        "profile": _profile(pet),
        "weight": _weight(pet_id),
        "medications": current_courses,
        "past_courses": past_courses,
        "vaccinations": _vaccinations(pet_id, today),
        "documents": _recent_documents(pet_id),
        "generated_at": today.isoformat(),
        "can_edit": pet.get("owner") == username,
    }


def _card_for(pet_id: str):
    """``(card, None)`` for a pet the user may see, else ``(None, error)``."""
    username, _ = get_current_user()
    pet, access_error = get_pet_and_validate(pet_id, username, require_owner=False)
    if access_error:
        return None, access_error
    query = request.context.query  # type: ignore[attr-defined]
    return build_medical_card(pet, username, _today(query.tz)), None


@medical_card_bp.route("/api/pets/<pet_id>/medical-card", methods=["GET"])
@login_required
@api.validate(
    query=MedicalCardQuery,
    resp=Response(HTTP_200=MedicalCardResponse, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["pets"],
)
def get_medical_card(pet_id):
    """The pet's medical card: profile, weight, medications, vaccinations, recent results."""
    card, error = _card_for(pet_id)
    if error:
        return error[0], error[1]
    response = jsonify({"card": card})
    response.headers["Cache-Control"] = "private, no-store"
    return response


@medical_card_bp.route("/api/pets/<pet_id>/medical-card/pdf", methods=["GET"])
@login_required
@api.validate(
    query=MedicalCardQuery,
    resp=Response(HTTP_200=None, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse),
    tags=["pets"],
)
def get_medical_card_pdf(pet_id):
    """The same card as a PDF, to hand to a vet."""
    from web.medical_card_pdf import render_medical_card_pdf

    card, error = _card_for(pet_id)
    if error:
        return error[0], error[1]
    try:
        content = render_medical_card_pdf(card)
    except Exception as e:  # a font or layout failure must not be a bare 500 page
        app.logger.error(f"Medical card PDF failed: pet_id={pet_id}, error={e}", exc_info=True)
        return error_response("internal_error")
    name = "".join(c for c in card["pet"]["name"] if c.isalnum() or c in " -_").strip().replace(" ", "_") or "pet"
    filename = f"медкарта_{name}_{card['generated_at'].replace('-', '')}.pdf"
    response = make_response(content)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@medical_card_bp.route("/api/pets/<pet_id>/medical-profile", methods=["PUT"])
@login_required
@api.validate(
    body=Request(MedicalProfile),
    resp=Response(
        HTTP_200=MedicalProfileResponse, HTTP_403=ErrorResponse, HTTP_404=ErrorResponse, HTTP_422=ErrorResponse
    ),
    tags=["pets"],
)
def put_medical_profile(pet_id):
    """Replace the pet's medical profile (allergies, conditions, chip, blood type, clinic).

    Anyone with access to the pet may: it is the household's shared knowledge
    about the animal, like its weight and medicines, not the owner's setting.
    Unlike the pet card, which only the owner edits.
    """
    username, _ = get_current_user()
    pet, access_error = get_pet_and_validate(pet_id, username, require_owner=False)
    if access_error:
        return access_error[0], access_error[1]

    data = request.context.body  # type: ignore[attr-defined]
    profile = data.model_dump()
    # No author is stored: the field would outlive the account it names.
    profile["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    app.db.pets.update_one({"_id": pet["_id"]}, {"$set": {"medical_profile": profile}})
    app.logger.info(f"Medical profile updated: pet_id={pet_id}, user={username}")
    return jsonify({"profile": profile})
