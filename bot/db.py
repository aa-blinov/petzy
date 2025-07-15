"Database interaction module for the Telegram bot application."

import os
from datetime import datetime
from typing import Any, Dict
from urllib.parse import quote_plus

from pymongo import MongoClient

from bot.config import MONGO_DB, MONGO_HOST, MONGO_PASS, MONGO_PORT, MONGO_USER

mongo_user = quote_plus(MONGO_USER)
mongo_pass = quote_plus(MONGO_PASS)
mongo_uri: str = f"mongodb://{mongo_user}:{mongo_pass}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}?authSource=admin"
client: MongoClient = MongoClient(mongo_uri)
db = client[MONGO_DB]
user_context = db["user_context"]
whitelist = db["whitelist_users"]
asthma = db["asthma_attacks"]
defecations = db["defecations"]


def save_user_context(user_id: int, key: str, value: Any) -> None:
    """Save user context data."""
    user_context.update_one({"user_id": user_id}, {"$set": {key: value}}, upsert=True)


def get_user_context(user_id: int) -> Dict[str, Any]:
    """Get user context data."""
    result = user_context.find_one({"user_id": user_id})
    return result or {}


def clear_user_context(user_id: int) -> None:
    """Clear user context data."""
    user_context.delete_one({"user_id": user_id})


def is_whitelisted(user_id: int) -> bool:
    """Check if user is whitelisted."""
    return whitelist.find_one({"telegram_id": user_id}) is not None


def save_asthma_attack(user_id: int, data: Dict[str, Any]) -> None:
    """Save asthma attack event."""
    event_time = data.get("date_time", datetime.now())
    asthma.insert_one({"user_id": user_id, **data, "date_time": event_time})


def save_defecation(user_id: int, data: Dict[str, Any]) -> None:
    """Save defecation event."""
    event_time = data.get("date_time", datetime.now())
    defecations.insert_one({"user_id": user_id, **data, "date_time": event_time})


def init_db() -> None:
    """Add users from whitelist.txt to whitelist collection if not present."""
    whitelist_path: str = os.path.join(os.path.dirname(__file__), "whitelist.txt")
    if not os.path.exists(whitelist_path):
        return
    with open(whitelist_path, "r", encoding="utf-8") as f:
        for line in f:
            user_id: str = line.strip()
            if user_id and not whitelist.find_one({"telegram_id": int(user_id)}):
                whitelist.insert_one({"telegram_id": int(user_id)})
