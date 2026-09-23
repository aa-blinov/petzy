"""Run the Flask backend locally with mongomock for UI testing.

Patches ``web.db`` before importing the app so any code path that does
``import web.db`` (or ``from web import db``) gets a mongomock client
instead of a real MongoDB connection.

Usage:
    python scripts/dev_local.py

Listens on 0.0.0.0:5001 — matches the vite proxy in frontend/vite.config.ts.
"""

import logging
import os
import sys

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dev_local")


class _InMemoryGridOut:
    """The subset of GridFS's GridOut the app actually reads."""

    def __init__(self, data: bytes, content_type: str | None):
        self._data = data
        self.content_type = content_type

    def read(self) -> bytes:
        return self._data


class _InMemoryGridFS:
    """A tiny stand-in for gridfs.GridFS, since real GridFS rejects
    mongomock databases. Real file bytes in, real file bytes out — good
    enough for local pet-photo uploads and demo seeding; not a real
    GridFS implementation (no chunking, no metadata queries)."""

    def __init__(self):
        self._store: dict = {}

    def put(self, data, filename=None, content_type=None):
        from bson import ObjectId

        if hasattr(data, "read"):
            data = data.read()
        file_id = ObjectId()
        self._store[file_id] = (data, content_type)
        return file_id

    def get(self, file_id):
        data, content_type = self._store[file_id]
        return _InMemoryGridOut(data, content_type)

    def delete(self, file_id):
        self._store.pop(file_id, None)


def _patch_with_mongomock() -> None:
    """Replace pymongo with mongomock before web.db is imported."""
    import mongomock

    mock_client = mongomock.MongoClient()
    mock_db = mock_client["petzy_dev"]

    # Patch pymongo.MongoClient so `from pymongo import MongoClient` works.
    import pymongo

    pymongo.MongoClient = lambda *a, **kw: mock_client  # type: ignore[assignment]

    # gridfs.GridFS rejects mongomock databases, so swap in a minimal
    # working stand-in before web.app imports it — pet photo upload and
    # the demo seed's own photos need it to actually store bytes.
    sys.modules.setdefault("gridfs", type(sys)("gridfs"))
    sys.modules["gridfs"].GridFS = lambda *_a, **_kw: _InMemoryGridFS()  # type: ignore[attr-defined]

    # Now import the app — web.db will pick up our patched client.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import web.db as _web_db

    _web_db.client = mock_client
    _web_db.db = mock_db


def _seed_demo_photo(fs, filename: str) -> "object | None":
    """Load one of scripts/demo_photos/*.jpg into fs, return its file id.

    Returns None (no photo, falls back to the species icon) if the file
    is missing — the demo still works without it.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_photos", filename)
    if not os.path.exists(path):
        logger.warning("Demo photo not found, skipping: %s", path)
        return None
    with open(path, "rb") as f:
        return fs.put(f.read(), filename=filename, content_type="image/jpeg")


def _seed_demo_data(db, fs) -> None:
    """Populate ~2 months of realistic-looking history for two pets.

    Deterministic (fixed random seed) so re-running this script always
    produces the same-looking demo data, but varied enough (feeding
    weights jitter, a slow weight trend, occasional non-default stool
    type, a resolved eye-drops course, a couple of asthma attacks) to
    show off charts, filters and the timeline instead of a flat wall of
    identical rows.
    """
    import random
    from datetime import datetime, timedelta, timezone

    from bson import ObjectId

    rng = random.Random(42)
    now = datetime.now(timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    def days_ago(n: int, hour: int = 12, minute: int = 0) -> datetime:
        return today - timedelta(days=n) + timedelta(hours=hour, minutes=minute)

    def tiles_settings(visible_keys: list[str]) -> dict:
        order = [
            "feeding",
            "asthma",
            "defecation",
            "weight",
            "litter",
            "eye_drops",
            "ear_cleaning",
            "tooth_brushing",
            "medications",
        ]
        return {
            "order": order,
            "visible": {key: key in visible_keys for key in order},
        }

    # --- Pet 1: Барсик, cat, ~60 days of rich multi-type history -----
    cat_photo_id = _seed_demo_photo(fs, "cat.jpg")
    cat_id = ObjectId()
    db.pets.insert_one(
        {
            "_id": cat_id,
            "name": "Барсик",
            "species": "cat",
            "breed": "Британская короткошерстная",
            "birth_date": datetime(2022, 4, 12),
            "gender": "Мужской",
            "is_neutered": True,
            "health_notes": "Лёгкая астма — приступы редкие, под контролем.",
            "owner": "admin",
            "shared_with": [],
            "photo_file_id": str(cat_photo_id) if cat_photo_id else None,
            "tiles_settings": tiles_settings(
                [
                    "feeding",
                    "asthma",
                    "defecation",
                    "weight",
                    "litter",
                    "eye_drops",
                    "ear_cleaning",
                    "tooth_brushing",
                    "medications",
                ]
            ),
            "created_at": days_ago(60, 9, 0),
            "updated_at": now,
        }
    )

    cat_events: list[dict] = []

    def add_cat_event(day: int, hour: int, minute: int, type_: str, fields: dict, comment: str = "") -> None:
        cat_events.append(
            {
                "pet_id": str(cat_id),
                "type": type_,
                "date_time": days_ago(day, hour, minute),
                "fields": fields,
                "comment": comment,
                "username": "admin",
            }
        )

    foods = ["Сухой корм", "Royal Canin Fibre Response", "Purina Pro Plan"]

    for day in range(60, -1, -1):
        # Feeding — twice a day, weight jitters a little.
        add_cat_event(day, 8, rng.randint(0, 20), "feeding", {"food_weight": rng.randint(45, 55)})
        add_cat_event(day, 19, rng.randint(0, 25), "feeding", {"food_weight": rng.randint(45, 55)})

        # Weight — once a week, slow realistic gain from 4.3 to 4.6 kg.
        if day % 7 == 0:
            progress = (60 - day) / 60
            weight = round(4.3 + progress * 0.3 + rng.uniform(-0.05, 0.05), 1)
            add_cat_event(day, 10, 0, "weight", {"weight": weight, "food": rng.choice(foods)})

        # Defecation — most days, mostly normal.
        if rng.random() < 0.85:
            stool_type = rng.choices(["Обычный", "Твердый", "Жидкий"], weights=[85, 10, 5])[0]
            color = rng.choices(["Коричневый", "Темно-коричневый", "Светло-коричневый"], weights=[70, 20, 10])[0]
            add_cat_event(
                day, rng.randint(7, 21), rng.randint(0, 59), "defecation", {"stool_type": stool_type, "color": color}
            )

        # Litter change — every 3 days.
        if day % 3 == 0:
            add_cat_event(day, 20, 0, "litter", {})

        # Tooth brushing — twice a week.
        if day % 4 == 0:
            add_cat_event(day, 21, 0, "tooth_brushing", {"brushing_type": "Щетка"})

        # Ear cleaning — every 12 days.
        if day % 12 == 0:
            add_cat_event(day, 18, 30, "ear_cleaning", {"cleaning_type": "Салфетка/Марля"})

    # Resolved eye-drops course — a conjunctivitis flare-up 3 weeks ago.
    for day in range(21, 16, -1):
        add_cat_event(day, 9, 0, "eye_drops", {"drops_type": "Гелевые"})
        add_cat_event(day, 21, 0, "eye_drops", {"drops_type": "Гелевые"})

    # A couple of mild, manageable asthma attacks.
    add_cat_event(38, 14, 20, "asthma", {"duration": "Короткий", "inhalation": "false", "reason": "Пыль после уборки"})
    add_cat_event(9, 7, 45, "asthma", {"duration": "Короткий", "inhalation": "true", "reason": "Стресс — визит гостей"})

    db.events.insert_many(cat_events)

    # Ongoing daily vitamin course, partially used up, mostly-taken log.
    vitamins_id = ObjectId()
    db.medications.insert_one(
        {
            "_id": vitamins_id,
            "pet_id": str(cat_id),
            "name": "Beaphar Kitty's Mix",
            "type": "Таблетка",
            "form_factor": "tablet",
            "strength": None,
            "dosage": None,
            "unit": None,
            "dose_unit": "таб",
            "default_dose": 1.0,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["08:30"]},
            "inventory_enabled": True,
            "inventory_total": 60.0,
            "inventory_current": 60.0 - 18,
            "inventory_warning_threshold": 10.0,
            "is_active": True,
            "comment": "Для шерсти и когтей",
            "username": "admin",
            "created_at": days_ago(18, 8, 0),
        }
    )
    intakes = []
    for day in range(17, 0, -1):
        # Realistic adherence — the occasional missed day.
        if rng.random() < 0.9:
            intakes.append(
                {
                    "medication_id": str(vitamins_id),
                    "pet_id": str(cat_id),
                    "date_time": days_ago(day, 8, rng.randint(20, 40)),
                    "dose_taken": 1.0,
                    "comment": "",
                    "username": "admin",
                    "created_at": days_ago(day, 8, 40),
                }
            )
    db.medication_intakes.insert_many(intakes)

    # A short, already-finished antibiotic course from the ear-cleaning-
    # heavy period, showing what a completed treatment looks like.
    antibiotic_id = ObjectId()
    db.medications.insert_one(
        {
            "_id": antibiotic_id,
            "pet_id": str(cat_id),
            "name": "Синулокс",
            "type": "Таблетка",
            "form_factor": "tablet",
            "strength": "50 мг",
            "dosage": None,
            "unit": None,
            "dose_unit": "таб",
            "default_dose": 1.0,
            "schedule": {"days": [0, 1, 2, 3, 4, 5, 6], "times": ["09:00", "21:00"]},
            "inventory_enabled": False,
            "inventory_total": None,
            "inventory_current": None,
            "inventory_warning_threshold": None,
            "is_active": False,
            "comment": "Курс от отита, пройден полностью",
            "username": "admin",
            "created_at": days_ago(35, 9, 0),
        }
    )
    antibiotic_intakes = []
    for day in range(35, 28, -1):
        for hour, minute in ((9, 0), (21, 0)):
            antibiotic_intakes.append(
                {
                    "medication_id": str(antibiotic_id),
                    "pet_id": str(cat_id),
                    "date_time": days_ago(day, hour, minute),
                    "dose_taken": 1.0,
                    "comment": "",
                    "username": "admin",
                    "created_at": days_ago(day, hour, minute),
                }
            )
    db.medication_intakes.insert_many(antibiotic_intakes)

    # --- Pet 2: Рекс, dog, lighter ~2-week history for the pet switcher --
    dog_photo_id = _seed_demo_photo(fs, "dog.jpg")
    dog_id = ObjectId()
    db.pets.insert_one(
        {
            "_id": dog_id,
            "name": "Рекс",
            "species": "dog",
            "breed": "Лабрадор-ретривер",
            "birth_date": datetime(2020, 6, 1),
            "gender": "Мужской",
            "is_neutered": False,
            "health_notes": "",
            "owner": "admin",
            "shared_with": [],
            "photo_file_id": str(dog_photo_id) if dog_photo_id else None,
            "tiles_settings": tiles_settings(["feeding", "defecation", "weight", "tooth_brushing", "medications"]),
            "created_at": days_ago(14, 9, 0),
            "updated_at": now,
        }
    )

    dog_events: list[dict] = []
    for day in range(14, -1, -1):
        dog_events.append(
            {
                "pet_id": str(dog_id),
                "type": "feeding",
                "date_time": days_ago(day, 8, 0),
                "fields": {"food_weight": rng.randint(280, 320)},
                "comment": "",
                "username": "admin",
            }
        )
        dog_events.append(
            {
                "pet_id": str(dog_id),
                "type": "feeding",
                "date_time": days_ago(day, 18, 30),
                "fields": {"food_weight": rng.randint(280, 320)},
                "comment": "",
                "username": "admin",
            }
        )
        if day % 7 == 0:
            dog_events.append(
                {
                    "pet_id": str(dog_id),
                    "type": "weight",
                    "date_time": days_ago(day, 10, 0),
                    "fields": {"weight": round(28.5 + rng.uniform(-0.3, 0.3), 1), "food": "Acana Adult Dog"},
                    "comment": "",
                    "username": "admin",
                }
            )
        if rng.random() < 0.7:
            dog_events.append(
                {
                    "pet_id": str(dog_id),
                    "type": "defecation",
                    "date_time": days_ago(day, rng.randint(7, 20), rng.randint(0, 59)),
                    "fields": {"stool_type": "Обычный", "color": "Коричневый"},
                    "comment": "",
                    "username": "admin",
                }
            )
        if day % 3 == 0:
            dog_events.append(
                {
                    "pet_id": str(dog_id),
                    "type": "tooth_brushing",
                    "date_time": days_ago(day, 20, 0),
                    "fields": {"brushing_type": "Игрушка"},
                    "comment": "",
                    "username": "admin",
                }
            )
    db.events.insert_many(dog_events)

    logger.info(
        "Seeded admin/test1234, pets Барсик (%s, %d events) and Рекс (%s, %d events).",
        cat_id,
        len(cat_events),
        dog_id,
        len(dog_events),
    )


def main() -> None:
    # Env defaults that mirror docker-compose for parity.
    os.environ.setdefault("MONGO_USER", "admin")
    os.environ.setdefault("MONGO_PASS", "admin")
    os.environ.setdefault("MONGO_HOST", "localhost")
    os.environ.setdefault("MONGO_PORT", "27017")
    os.environ.setdefault("MONGO_DB", "petzy_dev")
    os.environ.setdefault("FLASK_SECRET_KEY", "dev-local-secret")
    os.environ.setdefault("JWT_SECRET_KEY", "dev-local-jwt-secret")
    os.environ.setdefault("ADMIN_USERNAME", "admin")
    os.environ.setdefault("RATELIMIT_STORAGE_URI", "memory://")

    # Fixed dev-only VAPID pair (generated once via
    # `python -m scripts.generate_vapid_keys`) so a browser subscription
    # survives across dev-server restarts instead of needing to
    # re-subscribe every time. Never used outside this local runner.
    os.environ.setdefault(
        "VAPID_PUBLIC_KEY",
        "BEAFT_kVkSueKANpSxD1htnxIIKLln9mYnYUPHqF1LkASgjesy5mQzNdPKdlrd5gdf2KENSuqrpT_2WfqMpLxuY",
    )
    os.environ.setdefault("VAPID_PRIVATE_KEY", "ay_H1xDEhyWhfOJ1rEF67WpPjJdX7z9CpsgQjvyP3zo")
    os.environ.setdefault("VAPID_CLAIMS_EMAIL", "dev@example.com")

    _patch_with_mongomock()

    import bcrypt

    # Pin the admin password hash for the local dev runner so the seed
    # user is deterministic and we know the credentials at the UI.
    os.environ["ADMIN_PASSWORD_HASH"] = bcrypt.hashpw(b"test1234", bcrypt.gensalt()).decode()

    from web.app import app, fs
    from web.security import ensure_default_admin

    ensure_default_admin()

    # Also seed a couple of pets and ~2 months of realistic history so
    # the UI has something worth demoing instead of an empty state.
    from web.db import db

    _seed_demo_data(db, fs)

    # Run the reminder sender in-process on a background thread — only
    # safe here because dev_local.py is single-process. In production
    # this is its own container (docker-compose's `reminders` service)
    # specifically because gunicorn runs several worker processes, and
    # an in-process thread there would send every reminder once per
    # worker. A short 20s interval (vs. production's 60s) just makes
    # manual testing faster, not more correct.
    import threading
    import time
    from datetime import datetime, timezone

    from scripts.send_medication_reminders import send_reminders

    def _reminder_loop():
        vapid_claims = {"sub": f"mailto:{os.environ['VAPID_CLAIMS_EMAIL']}"}
        while True:
            try:
                sent = send_reminders(db, datetime.now(timezone.utc), os.environ["VAPID_PRIVATE_KEY"], vapid_claims)
                if sent:
                    logger.info(f"[reminders] sent {sent} notification(s)")
            except Exception:
                logger.exception("[reminders] tick failed")
            time.sleep(20)

    threading.Thread(target=_reminder_loop, daemon=True).start()

    logger.info("Listening on http://0.0.0.0:5001")
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
