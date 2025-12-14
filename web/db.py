"""Database interaction module for the web application."""

import os
from urllib.parse import quote_plus

from pymongo import MongoClient


def get_env(name: str, default: str = None) -> str:
    """Get environment variable with optional default."""
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Environment variable '{name}' is not set!")
    return value


# MongoDB connection settings
MONGO_USER = get_env("MONGO_USER")
MONGO_PASS = get_env("MONGO_PASS")
MONGO_HOST = get_env("MONGO_HOST", "db")
MONGO_PORT = get_env("MONGO_PORT", "27017")
MONGO_DB = get_env("MONGO_DB")

# Build MongoDB URI
mongo_user = quote_plus(MONGO_USER)
mongo_pass = quote_plus(MONGO_PASS)
mongo_uri: str = f"mongodb://{mongo_user}:{mongo_pass}@{MONGO_HOST}:{MONGO_PORT}/{MONGO_DB}?authSource=admin"

# Create MongoDB client and database connection
client: MongoClient = MongoClient(mongo_uri)
db = client[MONGO_DB]

# Export mongo_uri for use in Flask-Limiter
__all__ = ['db', 'client', 'mongo_uri']
