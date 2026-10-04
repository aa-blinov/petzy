"""What a vaccine protects against, so that a change of brand is not a new vaccination.

A pet gets «Нобивак DHPPi» one year and «Эурикан DHPPi2» the next: the card must read the second as the repeat of the
first, not as another vaccine whose older entry stays overdue for ever. What counts is what the shot is *against*
(the protection group), not the name on the vial. A record keeps its group in ``protects``; one made before that, or
typed by hand, is read by its name here, so the old data is covered without a migration.

The catalogue is one place for the app: the search list of the form comes from it (``GET /api/vaccines/catalog``), and
the card's rule that a newer shot of the same group replaces an older one reads it too.
"""

from typing import Optional

from flask import Blueprint, jsonify
from flask_pydantic_spec import Response

from web.app import api
from web.schemas import ErrorResponse, VaccineCatalogResponse
from web.security import login_required

vaccines_bp = Blueprint("vaccines", __name__)

# (key, the short label, what it covers, the species it is offered to). Shots are listed as sold; a combined one belongs to the group its
# schedule follows (a dog's «комплексная», with or without leptospirosis, is one schedule for the card).
GROUPS: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("rabies", "Бешенство", "", ("dog", "cat", "rabbit", "other")),
    ("dhpp", "Комплексная для собак", "Чума, аденовирус, парвовирус, парагрипп", ("dog",)),
    ("lepto", "Лептоспироз", "", ("dog",)),
    ("kennel", "Питомниковый кашель", "Бордетеллёз и парагрипп", ("dog",)),
    ("fvrcp", "Комплексная для кошек", "Панлейкопения, ринотрахеит, калицивироз", ("cat",)),
    ("felv", "Лейкоз кошек", "", ("cat",)),
    ("myxo_rhd", "Миксоматоз и ВГБК", "Миксоматоз и вирусная геморрагическая болезнь кроликов", ("rabbit",)),
]
GROUP_KEYS = tuple(key for key, _, _, _ in GROUPS)
GROUP_LABELS = {key: label for key, label, _, _ in GROUPS}

# (the name shown, the species, the group). The name is also what is looked for in a typed one (a start of it, lower case).
PRODUCTS: list[tuple[str, tuple[str, ...], str]] = [
    ("Нобивак Rabies", ("dog", "cat", "rabbit", "other"), "rabies"),
    ("Рабизин", ("dog", "cat", "other"), "rabies"),
    ("Рабикан", ("dog", "cat", "other"), "rabies"),
    ("Дефенсор 3", ("dog", "cat"), "rabies"),
    ("Биокан R", ("dog",), "rabies"),
    ("Бешенство", ("dog", "cat", "rabbit", "other"), "rabies"),
    ("Нобивак DHPPi", ("dog",), "dhpp"),
    ("Нобивак DHP", ("dog",), "dhpp"),
    ("Эурикан DHPPi2", ("dog",), "dhpp"),
    ("Эурикан DHPPi2-L", ("dog",), "dhpp"),
    ("Эурикан DAPPi-Lmulti", ("dog",), "dhpp"),
    ("Мультикан-4", ("dog",), "dhpp"),
    ("Мультикан-6", ("dog",), "dhpp"),
    ("Мультикан-8", ("dog",), "dhpp"),
    ("Биокан DHPPi", ("dog",), "dhpp"),
    ("Вангард Plus 5", ("dog",), "dhpp"),
    ("Комплексная прививка", ("dog",), "dhpp"),
    ("Нобивак Lepto", ("dog",), "lepto"),
    ("Биокан L", ("dog",), "lepto"),
    ("Нобивак KC", ("dog",), "kennel"),
    ("Нобивак Tricat Trio", ("cat",), "fvrcp"),
    ("Фелоцел CVR", ("cat",), "fvrcp"),
    ("Пуревакс RCP", ("cat",), "fvrcp"),
    ("Пуревакс RCPCh", ("cat",), "fvrcp"),
    ("Мультифел-4", ("cat",), "fvrcp"),
    ("Фелиген CRP", ("cat",), "fvrcp"),
    ("Комплексная прививка", ("cat",), "fvrcp"),
    ("Пуревакс FeLV", ("cat",), "felv"),
    ("Леукоген", ("cat",), "felv"),
    ("Нобивак Myxo-RHD", ("rabbit",), "myxo_rhd"),
    ("Рабивак-V", ("rabbit",), "myxo_rhd"),
]


def _norm(text: str) -> str:
    return " ".join((text or "").casefold().split())


# Longest names first, so that «нобивак dhppi» is not taken for the shorter «нобивак dhp».
_BY_NAME = sorted(
    ((_norm(name), key) for name, _, key in PRODUCTS if name != "Комплексная прививка"), key=lambda p: -len(p[0])
)


def infer_protects(title: str) -> Optional[str]:
    """The group of a typed name that is one of the known (a start of it, so that «Нобивак DHPPi (2025)» is read too)."""
    name = _norm(title)
    if not name:
        return None
    for known, key in _BY_NAME:
        if name == known or name.startswith(known + " ") or name.startswith(known + "("):
            return key
    return None


def effective_protects(record: dict) -> Optional[str]:
    """What a vaccination is against: the group it was given, else the one its name says, else nothing known."""
    if record.get("kind") != "vaccination":
        return None
    kept = record.get("protects")
    return kept if kept in GROUP_KEYS else infer_protects(record.get("title", ""))


@vaccines_bp.route("/api/vaccines/catalog", methods=["GET"])
@login_required
@api.validate(resp=Response(HTTP_200=VaccineCatalogResponse, HTTP_401=ErrorResponse), tags=["medical-records"])
def get_catalog():
    """The vaccines the form offers to search, each with what it protects against."""
    response = jsonify(
        {
            "groups": [
                {"key": key, "label": label, "detail": detail, "species": list(species)}
                for key, label, detail, species in GROUPS
            ],
            "products": [{"name": name, "species": list(species), "protects": key} for name, species, key in PRODUCTS],
        }
    )
    response.headers["Cache-Control"] = "private, max-age=3600"
    return response
