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
from unittest.mock import MagicMock

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dev_local")


def _patch_with_mongomock() -> None:
    """Replace pymongo with mongomock before web.db is imported."""
    import mongomock

    mock_client = mongomock.MongoClient()
    mock_db = mock_client["petzy_dev"]

    # Patch pymongo.MongoClient so `from pymongo import MongoClient` works.
    import pymongo

    pymongo.MongoClient = lambda *a, **kw: mock_client  # type: ignore[assignment]

    # gridfs.GridFS rejects mongomock databases — we don't need real photo
    # storage for the smoke UI test, so mock it out before web.app imports it.
    sys.modules.setdefault("gridfs", type(sys)("gridfs"))
    sys.modules["gridfs"].GridFS = MagicMock()  # type: ignore[attr-defined]

    # Now import the app — web.db will pick up our patched client.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import web.db as _web_db

    _web_db.client = mock_client
    _web_db.db = mock_db


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

    _patch_with_mongomock()

    import bcrypt
    # Pin the admin password hash for the local dev runner so the seed
    # user is deterministic and we know the credentials at the UI.
    os.environ["ADMIN_PASSWORD_HASH"] = bcrypt.hashpw(
        b"test1234", bcrypt.gensalt()
    ).decode()

    from web.app import app
    from web.security import ensure_default_admin

    ensure_default_admin()

    # Also seed a couple of pets and a record so the UI isn't empty.
    from web.db import db

    from bson import ObjectId
    from datetime import datetime, timezone

    pet_id = ObjectId()
    db.pets.insert_one(
        {
            "_id": pet_id,
            "name": "Барсик",
            "species": "cat",
            "owner": "admin",
            "shared_with": [],
            "photo_file_id": None,
            "tiles_settings": {
                "order": [
                    "feeding",
                    "asthma",
                    "defecation",
                    "weight",
                    "litter",
                    "eye_drops",
                    "ear_cleaning",
                    "tooth_brushing",
                    "medications",
                ],
                "visible": {
                    "feeding": True,
                    "asthma": True,
                    "defecation": True,
                    "weight": True,
                    "litter": True,
                    "eye_drops": True,
                    "ear_cleaning": True,
                    "tooth_brushing": True,
                    "medications": True,
                },
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    db.feedings.insert_many(
        [
            {
                "pet_id": str(pet_id),
                "date_time": datetime(2026, 9, 18, 8, 0),
                "food_weight": 50,
                "comment": "",
                "username": "admin",
            },
            {
                "pet_id": str(pet_id),
                "date_time": datetime(2026, 9, 18, 19, 0),
                "food_weight": 50,
                "comment": "",
                "username": "admin",
            },
            {
                "pet_id": str(pet_id),
                "date_time": datetime(2026, 9, 19, 8, 0),
                "food_weight": 50,
                "comment": "",
                "username": "admin",
            },
        ]
    )
    db.weights.insert_one(
        {
            "pet_id": str(pet_id),
            "date_time": datetime(2026, 9, 15, 10, 0),
            "weight": 4.5,
            "food": "Сухой корм",
            "comment": "",
            "username": "admin",
        }
    )

    logger.info("Seeded admin/admin, pet Барсик (%s), and a few records.", pet_id)
    logger.info("Listening on http://0.0.0.0:5001")
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()