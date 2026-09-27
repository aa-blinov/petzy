"""Fill a running Petzy with demo data, through its public API.

Made for the local Docker stack (docker-compose.local.yml), so every call
goes through nginx and the real API, like the app's own:

    .venv/bin/python scripts/seed_demo.py                 # http://localhost:3000
    .venv/bin/python scripts/seed_demo.py --base http://localhost:5173

Creates two accounts (DEMO_LOGIN owns the pets, FAMILY_LOGIN is invited to
one and has accepted), two pets with photos, two months of records, a custom
event type, medications with stock and doses (one skipped), documents (one
expiring soon), form defaults and a confirmed email. Run it on an empty
database: the accounts must not exist yet. Local and demo use only.
"""

import argparse
import io
import json
import os
import random
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta

# Demo accounts of a local stack, printed at the end.
DEMO_LOGIN = "demo"
FAMILY_LOGIN = "family"
DEMO_PASSWORD = "petzy-demo-2026"

HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(7)  # the same demo every time


class Api:
    """A native-style client: no Origin header, so tokens come in the body."""

    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token = None

    def call(self, method: str, path: str, body=None, files=None, ok=(200, 201)):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if files is not None:
            boundary = uuid.uuid4().hex
            data = _multipart(boundary, body or {}, files)
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        payload = json.loads(raw) if raw and raw[:1] in (b"{", b"[") else raw
        if status not in ok:
            raise SystemExit(f"{method} {path} -> {status}: {payload}")
        return payload

    def sign_up(self, username: str, full_name: str, email: str = ""):
        body = {"username": username, "password": DEMO_PASSWORD, "full_name": full_name}
        if email:
            body["email"] = email
        self.token = self.call("POST", "/api/auth/register", body)["access_token"]


def _multipart(boundary: str, fields: dict, files: dict) -> bytes:
    out = io.BytesIO()
    for name, value in fields.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, (filename, content, content_type) in files.items():
        out.write(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n".encode()
        )
        out.write(content)
        out.write(b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue()


def _pdf(title: str) -> bytes:
    """A small but real one-page PDF, so the document opens in a viewer."""
    text = title.encode("ascii", "replace").decode()
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + obj + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return out.getvalue()


def _photo(name: str) -> tuple:
    with open(os.path.join(HERE, "demo_photos", name), "rb") as f:
        return (name, f.read(), "image/jpeg")


def _day(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _time(hour: int, minute: int, jitter: int = 20) -> str:
    total = max(0, min(23 * 60 + 59, hour * 60 + minute + random.randint(-jitter, jitter)))
    return f"{total // 60:02d}:{total % 60:02d}"


def _past(days_ago: int, hhmm: str) -> bool:
    """Not in the future: the API refuses records from later today."""
    when = datetime.combine(date.today() - timedelta(days=days_ago), datetime.strptime(hhmm, "%H:%M").time())
    return when <= datetime.now()


def _event(api: Api, pet_id: str, kind: str, days_ago: int, hhmm: str, fields=None, comment="") -> None:
    if not _past(days_ago, hhmm):
        return
    body = {"pet_id": pet_id, "type": kind, "date": _day(days_ago), "time": hhmm, "fields": fields or {}}
    if comment:
        body["comment"] = comment
    api.call("POST", "/api/events", body)


def seed(base: str) -> None:
    demo = Api(base)
    if demo.call("GET", "/api/auth/registration")["open"] is not True:
        raise SystemExit("Sign-up is closed on this server (REGISTRATION_ENABLED)")
    demo.sign_up(DEMO_LOGIN, "Анна", email="demo@example.com")
    family = Api(base)
    family.sign_up(FAMILY_LOGIN, "Иван")
    print(f"accounts: {DEMO_LOGIN}, {FAMILY_LOGIN}")

    # Confirm the demo email from the local outbox (MAIL_OUTBOX=memory).
    letters = demo.call("GET", "/api/dev/outbox", ok=(200, 404))
    if isinstance(letters, dict):
        for letter in reversed(letters.get("letters", [])):
            if "verify-email?token=" in letter["text"]:
                token = letter["text"].split("verify-email?token=", 1)[1].split()[0]
                demo.call("POST", "/api/auth/email/verify", {"token": token})
                print("email: demo@example.com confirmed")
                break

    dog_tiles = json.dumps(
        {
            "order": [],
            "visible": {
                "feeding": True,
                "weight": True,
                "defecation": True,
                "eye_drops": True,
                "ear_cleaning": True,
                "tooth_brushing": True,
                "litter": False,
                "asthma": False,
            },
        }
    )
    cat = demo.call(
        "POST",
        "/api/pets",
        {
            "name": "Мурзик",
            "species": "cat",
            "breed": "Британская короткошёрстная",
            "birth_date": "2019-04-12",
            "gender": "male",
            "is_neutered": "true",
            "health_notes": "Чувствительный желудок, корм только гипоаллергенный",
        },
        files={"photo_file": _photo("cat.jpg")},
    )["pet"]["_id"]
    dog = demo.call(
        "POST",
        "/api/pets",
        {
            "name": "Рекс",
            "species": "dog",
            "breed": "Лабрадор",
            "birth_date": "2021-08-01",
            "gender": "male",
            "tiles_settings": dog_tiles,
        },
        files={"photo_file": _photo("dog.jpg")},
    )["pet"]["_id"]
    print("pets: Мурзик, Рекс")

    walk = demo.call(
        "POST",
        "/api/event-types",
        {
            "label": "Прогулка",
            "icon": "paw",
            "color": "green",
            "fields": [
                {"name": "minutes", "label": "Длительность (мин)", "type": "number", "required": True, "min": 0}
            ],
            "chart": {"kind": "value", "value_field": "minutes", "value_label": "Минуты"},
        },
    )["key"]

    for d in range(60, -1, -1):
        # Мурзик: two meals, litter every 3 days, weight weekly (slowly down
        # on the diet), eye drops during a ten-day course, daily toilet.
        _event(demo, cat, "feeding", d, _time(8, 10), {"food_weight": random.randint(52, 64)})
        _event(demo, cat, "feeding", d, _time(19, 30), {"food_weight": random.randint(44, 56)})
        if d % 3 == 0:
            _event(demo, cat, "litter", d, _time(21, 0))
        if d % 7 == 0:
            weight = round(4.95 - (60 - d) * 0.006 + random.uniform(-0.04, 0.04), 2)
            _event(demo, cat, "weight", d, _time(9, 0, 5), {"weight": weight, "food": "Royal Canin Sensitivity"})
        stool = "Жидкий" if d in (41, 40) else "Обычный"
        _event(demo, cat, "defecation", d, _time(10, 0, 60), {"stool_type": stool, "color": "Коричневый"})
        if 30 <= d <= 40:
            for hour in (9, 21):
                _event(demo, cat, "eye_drops", d, _time(hour, 0, 10), {"drops_type": "Обычные"})
        # Рекс: meals, two walks, teeth weekly, ears every two weeks.
        _event(demo, dog, "feeding", d, _time(7, 30), {"food_weight": random.randint(180, 220)})
        _event(demo, dog, "feeding", d, _time(18, 30), {"food_weight": random.randint(180, 220)})
        _event(demo, dog, walk, d, _time(7, 0), {"minutes": random.choice([30, 35, 40, 45])})
        _event(demo, dog, walk, d, _time(20, 0), {"minutes": random.choice([40, 50, 60])})
        if d % 7 == 3:
            _event(demo, dog, "tooth_brushing", d, _time(21, 30), {"brushing_type": "Щетка"})
        if d % 14 == 5:
            _event(demo, dog, "ear_cleaning", d, _time(12, 0), {"cleaning_type": "Капли"})
        if d % 14 == 0:
            _event(demo, dog, "weight", d, _time(11, 0, 5), {"weight": round(28.4 + (60 - d) * 0.012, 1)})
    _event(
        demo, cat, "asthma", 18, "03:40", {"duration": "Короткий", "inhalation": "true", "reason": "Пыль после уборки"}
    )
    print("records: two months for both")

    every_day = [0, 1, 2, 3, 4, 5, 6]
    gaba = demo.call(
        "POST",
        "/api/medications",
        {
            "pet_id": cat,
            "name": "Габапентин",
            "type": "Капсула",
            "form_factor": "tablet",
            "strength": "50 мг",
            "dose_unit": "капс",
            "default_dose": 1,
            "schedule": {"days": every_day, "times": ["08:00", "20:00"]},
            "inventory_enabled": True,
            "inventory_total": 30,
            "inventory_current": 35,
            "inventory_warning_days": 3,
            "comment": "Перед едой",
        },
    )["id"]
    omega = demo.call(
        "POST",
        "/api/medications",
        {
            "pet_id": cat,
            "name": "Омега-3",
            "type": "Капсула",
            "form_factor": "tablet",
            "dose_unit": "капс",
            "default_dose": 1,
            "schedule": {"days": every_day, "times": ["09:00"]},
            "inventory_enabled": True,
            "inventory_total": 60,
            "inventory_current": 20,
        },
    )["id"]
    sinulox = demo.call(
        "POST",
        "/api/medications",
        {
            "pet_id": cat,
            "name": "Синулокс",
            "type": "Таблетка",
            "form_factor": "tablet",
            "strength": "50 мг",
            "dose_unit": "таб",
            "default_dose": 0.5,
            "schedule": {"days": every_day, "times": ["08:00", "20:00"]},
            "is_active": True,
            "comment": "Курс антибиотика на 7 дней",
        },
    )["id"]
    drontal = demo.call(
        "POST",
        "/api/medications",
        {
            "pet_id": dog,
            "name": "Дронтал Плюс",
            "type": "Таблетка",
            "form_factor": "tablet",
            "dose_unit": "таб",
            "default_dose": 1,
            "schedule": {"days": [5], "times": ["10:00"]},
            "inventory_enabled": True,
            "inventory_current": 2,
        },
    )["id"]

    def dose(med_id: str, days_ago: int, hhmm: str, skipped: bool = False) -> None:
        if _past(days_ago, hhmm):
            demo.call(
                "POST",
                f"/api/medications/{med_id}/log",
                {"date": _day(days_ago), "time": hhmm, "skipped": skipped},
            )

    for d in range(14, -1, -1):
        dose(gaba, d, _time(8, 5, 10), skipped=(d == 5))
        dose(gaba, d, _time(20, 10, 10))
        dose(omega, d, _time(9, 5, 10))
    for d in range(26, 19, -1):  # a finished course, now in the archive
        dose(sinulox, d, _time(8, 5, 10))
        dose(sinulox, d, _time(20, 5, 10))
    demo.call("PUT", f"/api/medications/{sinulox}", {"is_active": False})
    for d in range(56, -1, -7):
        dose(drontal, d, "10:00")
    # Габапентин: 35 at the start, about 29 doses given: three days left,
    # so the course shows «Заканчивается».
    print("medications: Габапентин, Омега-3, Синулокс (archive), Дронтал Плюс")

    soon = (date.today() + timedelta(days=10)).isoformat()
    demo.call(
        "POST",
        "/api/documents",
        {
            "pet_id": cat,
            "category": "vaccination",
            "title": "Прививка от бешенства",
            "expires_at": soon,
            "note": "Ветклиника «Айболит», ревакцинация через год",
        },
        files={"file": ("rabies.pdf", _pdf("Rabies vaccination - Murzik"), "application/pdf")},
    )
    demo.call(
        "POST",
        "/api/documents",
        {"pet_id": cat, "category": "lab_result", "title": "Общий анализ крови", "note": "Всё в норме"},
        files={"file": ("blood.pdf", _pdf("Blood test - Murzik"), "application/pdf")},
    )
    demo.call(
        "POST",
        "/api/documents",
        {"pet_id": cat, "category": "other", "title": "Фото с приёма"},
        files={"file": _photo("cat.jpg")},
    )
    demo.call(
        "POST",
        "/api/documents",
        {
            "pet_id": dog,
            "category": "insurance",
            "title": "Страховка на год",
            "expires_at": (date.today() + timedelta(days=200)).isoformat(),
        },
        files={"file": ("insurance.pdf", _pdf("Insurance - Rex"), "application/pdf")},
    )
    print("documents: 4, one expiring in 10 days")

    # The family: invited to Мурзик, accepted, and logged tonight's meal.
    demo.call("POST", f"/api/pets/{cat}/share", {"username": FAMILY_LOGIN})
    family.call("POST", f"/api/pets/{cat}/invite/accept")
    now = datetime.now()
    family.call(
        "POST",
        "/api/events",
        {
            "pet_id": cat,
            "type": "feeding",
            "date": now.date().isoformat(),
            "time": now.strftime("%H:%M"),
            "fields": {"food_weight": 30},
            "comment": "Дал немного, доест позже",
        },
    )
    # And Рекс is offered to them but not answered yet: an invitation to see.
    demo.call("POST", f"/api/pets/{dog}/share", {"username": FAMILY_LOGIN})
    print(f"sharing: Мурзик shared with {FAMILY_LOGIN}, Рекс invited")

    demo.call(
        "PUT",
        "/api/me/form-defaults",
        {
            "form_defaults": {
                "weight": {"food": "Royal Canin Sensitivity"},
                "defecation": {"food": "Royal Canin Sensitivity"},
            }
        },
    )

    print()
    print(f"Done. Sign in at {base} as «{DEMO_LOGIN}» (owner) or «{FAMILY_LOGIN}», password: {DEMO_PASSWORD}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="http://localhost:3000", help="the app's address (nginx)")
    seed(parser.parse_args().base)


if __name__ == "__main__":
    sys.exit(main())
