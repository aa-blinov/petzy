"""Fill the medical card of the demo pets, through the public API, to try everything by hand.

Run it after scripts/seed_demo.py on the local Docker stack (it signs in as the demo account of that script):

    .venv/bin/python scripts/seed_medical.py                 # http://localhost:3000
    .venv/bin/python scripts/seed_medical.py --base http://localhost:5173

It can be run again: the medical records of the pets it fills are removed first and made anew, with dates counted
from today, so what is «overdue» or «soon» stays so.

What each pet is for:
  Рекс    a full card: allergies, conditions, three clinics with their doctors, vaccinations (one overdue, one
          valid), treatments (one due within a week), visits with a complaint, procedures, «К приёму», a finished
          course of a medicine, a lab result linked to a visit.
  Мурзик  a card half filled in: one next step («Обработка от паразитов»), the certificate in the documents that
          still has to be made a record.
  Пустик  a new pet with nothing: the empty states.

Local and demo use only.
"""

import argparse
import sys
import time
from datetime import date, timedelta

from seed_demo import DEMO_LOGIN, DEMO_PASSWORD, Api, _pdf

TODAY = date.today()


class PatientApi(Api):
    """The same client that tries again when gunicorn is changing a worker (nginx answers 502 for a moment)."""

    def call(self, method, path, body=None, files=None, ok=(200, 201)):
        for attempt in range(4):
            try:
                return super().call(method, path, body, files, ok)
            except SystemExit as e:
                if "-> 502" not in str(e) or attempt == 3:
                    raise
                time.sleep(2)


def day(offset: int) -> str:
    """A date offset days from today (negative: in the past)."""
    return (TODAY + timedelta(days=offset)).isoformat()


def pet_id(api: Api, name: str):
    for pet in api.call("GET", "/api/pets")["pets"]:
        if pet["name"] == name:
            return pet["_id"]
    return None


def clear_records(api: Api, pid: str) -> None:
    for record in api.call("GET", f"/api/medical-records?pet_id={pid}")["records"]:
        api.call("DELETE", f"/api/medical-records/{record['_id']}", ok=(200, 204))


def record(api: Api, pid: str, kind: str, title: str, offset: int, **extra) -> str:
    body = {"pet_id": pid, "kind": kind, "title": title, "date": day(offset), **extra}
    api.call("POST", "/api/medical-records", body)
    records = api.call("GET", f"/api/medical-records?pet_id={pid}&kind={kind}")["records"]
    return next(r["_id"] for r in records if r["title"] == title and r["date"] == day(offset))


def _add_course(api: Api, rex: str) -> None:
    api.call(
        "POST",
        "/api/medications",
        {
            "pet_id": rex,
            "name": "Артрафлекс",
            "type": "Таблетка",
            "form_factor": "tablet",
            "strength": "500 мг",
            "dose_unit": "таб",
            "default_dose": 1,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["09:00"]},
            "started_on": day(-110),
            "ended_on": day(-80),
            "purpose": "Дисплазия, поддержка суставов",
            "prescribed_by": "Каримов Д.",
        },
        ok=(200, 201),
    )


def seed(base: str) -> None:
    api = PatientApi(base)
    api.token = api.call("POST", "/api/auth/login", {"username": DEMO_LOGIN, "password": DEMO_PASSWORD})["access_token"]

    rex = pet_id(api, "Рекс")
    murzik = pet_id(api, "Мурзик")
    if not rex or not murzik:
        raise SystemExit("Рекс and Мурзик are not here: run scripts/seed_demo.py on an empty database first")

    # ---------------------------------------------------------------- Рекс
    clear_records(api, rex)
    api.call(
        "PUT",
        f"/api/pets/{rex}/medical-profile",
        {
            "chip_number": "643094100200311",
            "blood_type": "DEA 1.1+",
            "allergies": [
                {"substance": "Курица", "reaction": "зуд, покраснение ушей"},
                {"substance": "Амоксициллин", "reaction": "сыпь"},
            ],
            "conditions": [
                {"name": "Дисплазия тазобедренных суставов", "since_year": 2023, "note": "обострения после нагрузки"},
                {"name": "Хронический гастрит", "since_year": 2024},
            ],
            "diet": "Сухой корм Royal Canin Sensitivity, два раза в день",
            "living": "Квартира, выгул три раза в день, дома живёт кошка Мурзик",
            "clinics": [
                {
                    "name": "Вет-клиника Друг",
                    "phone": "+7 701 555 01 02",
                    "doctors": [
                        {"name": "Иванова А. П.", "specialty": "терапевт"},
                        {"name": "Петров С. И.", "specialty": "кардиолог"},
                    ],
                },
                {
                    "name": "Зубастик",
                    "phone": "+7 702 555 03 04",
                    "doctors": [{"name": "Сидорова Н.", "specialty": "стоматолог"}],
                },
                {
                    "name": "Ортовет",
                    "phone": "+7 727 555 05 06",
                    "doctors": [{"name": "Каримов Д.", "specialty": "хирург-ортопед"}],
                },
            ],
        },
    )

    # A yearly vaccine: the last one is overdue by 35 days, the earlier ones are history.
    for k in range(4, 0, -1):
        record(
            api,
            rex,
            "vaccination",
            "Нобивак DHPPi",
            -400 - 365 * k,
            next_due=day(-400 - 365 * k + 365),
            clinic="Вет-клиника Друг",
            vet="Иванова А. П.",
        )
    record(
        api,
        rex,
        "vaccination",
        "Нобивак DHPPi",
        -400,
        next_due=day(-35),
        batch="B-4471",
        clinic="Вет-клиника Друг",
        vet="Иванова А. П.",
    )
    record(api, rex, "vaccination", "Нобивак Rabies", -530, next_due=day(-165), clinic="Вет-клиника Друг")
    record(
        api,
        rex,
        "vaccination",
        "Нобивак Rabies",
        -165,
        next_due=day(200),
        batch="R-2210",
        clinic="Вет-клиника Друг",
        vet="Иванова А. П.",
    )
    record(
        api, rex, "vaccination", "Нобивак KC", -20, next_due=day(345), clinic="Вет-клиника Друг", vet="Иванова А. П."
    )
    # Treatments: one is due within a week, one is fine.
    record(api, rex, "parasite", "Бравекто", -174, target="both", next_due=day(-84))
    record(api, rex, "parasite", "Бравекто", -84, target="both", next_due=day(6))
    record(api, rex, "parasite", "Дронтал Плюс", -60, target="worms", next_due=day(30))

    # The lab result a visit points at: made once, found again on the next run.
    def find(path: str, key: str, title: str):
        listing = api.call("GET", path)
        return next((x for x in listing[key] if x.get("title", x.get("name")) == title), None)

    document = find(f"/api/documents?pet_id={rex}", "documents", "Анализ крови")
    if not document:
        api.call(
            "POST",
            "/api/documents",
            {"pet_id": rex, "category": "lab_result", "title": "Анализ крови", "note": "Биохимия, общий"},
            files={"file": ("blood-rex.pdf", _pdf("Blood test - Rex"), "application/pdf")},
        )
        document = find(f"/api/documents?pet_id={rex}", "documents", "Анализ крови")
    doc_id = document["_id"] if document else None

    record(
        api,
        rex,
        "visit",
        "Плановый осмотр",
        -9,
        complaint="Чаще пьёт воду",
        diagnosis="Без патологии",
        recommendations="Повторить анализы через три месяца",
        clinic="Вет-клиника Друг",
        vet="Иванова А. П.",
        document_ids=[doc_id] if doc_id else [],
    )
    record(
        api,
        rex,
        "visit",
        "Хромота на левую заднюю",
        -120,
        complaint="Хромает после прогулок",
        diagnosis="Дисплазия тазобедренных суставов, 1 степень",
        recommendations="Ограничить прыжки, курс хондропротекторов",
        clinic="Ортовет",
        vet="Каримов Д.",
    )
    record(
        api,
        rex,
        "visit",
        "Консультация кардиолога",
        -300,
        complaint="Одышка при нагрузке",
        diagnosis="Функциональный шум, норма",
        note="ЭхоКГ без изменений",
        clinic="Вет-клиника Друг",
        vet="Петров С. И.",
    )
    record(
        api,
        rex,
        "procedure",
        "Чистка зубов",
        -200,
        note="Под седацией, без осложнений",
        clinic="Зубастик",
        vet="Сидорова Н.",
    )
    record(api, rex, "procedure", "УЗИ брюшной полости", -9, clinic="Вет-клиника Друг", vet="Иванова А. П.")
    record(api, rex, "procedure", "Кастрация", -1700, clinic="Вет-клиника Друг")

    api.call(
        "PUT",
        f"/api/pets/{rex}/visit-prep",
        {
            "complaint": "Стал меньше гулять, хромает после вчерашней пробежки",
            "checks": {"appetite": "normal", "thirst": "changed", "stool": "normal", "activity": "changed"},
        },
    )
    # A course that is over: it stays on the card with what it was for.
    if not find(f"/api/medications?pet_id={rex}", "medications", "Артрафлекс"):
        _add_course(api, rex)
    print("Рекс: a full card, a vaccination overdue by 35 days, a treatment due in 6 days, «К приёму» filled in")

    # -------------------------------------------------------------- Мурзик
    clear_records(api, murzik)
    api.call(
        "PUT",
        f"/api/pets/{murzik}/medical-profile",
        {
            "allergies_none_known": True,
            "diet": "Влажный корм, три раза в день",
            "clinics": [
                {
                    "name": "Вет-клиника Друг",
                    "phone": "+7 701 555 01 02",
                    "doctors": [{"name": "Иванова А. П.", "specialty": "терапевт"}],
                }
            ],
        },
    )
    record(
        api,
        murzik,
        "vaccination",
        "Нобивак Tricat Trio",
        -340,
        next_due=day(25),
        batch="T-9002",
        clinic="Вет-клиника Друг",
        vet="Иванова А. П.",
    )
    api.call("PUT", f"/api/pets/{murzik}/visit-prep", {"complaint": None, "checks": {}})
    print("Мурзик: half filled in (the next step is the treatment), a certificate waiting in the Documents")

    # -------------------------------------------------------------- Пустик
    if not pet_id(api, "Пустик"):
        api.call("POST", "/api/pets", {"name": "Пустик", "species": "cat"})
    print("Пустик: a new pet with an empty card")
    print()
    print(f"Done. Sign in at {base} as «{DEMO_LOGIN}» (password of scripts/seed_demo.py); «family» sees Мурзик.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="http://localhost:3000", help="the app's address (nginx)")
    seed(parser.parse_args().base)


if __name__ == "__main__":
    sys.exit(main())
