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

# MongoDB connection pool settings
MONGO_POOL_CONFIG = {
    "maxPoolSize": 50,           # Maximum number of connections in the pool
    "minPoolSize": 5,            # Minimum number of connections to maintain
    "maxIdleTimeMS": 30000,      # Close idle connections after 30 seconds
    "serverSelectionTimeoutMS": 5000,  # Timeout for server selection (5 seconds)
    "connectTimeoutMS": 10000,   # Timeout for initial connection (10 seconds)
    "socketTimeoutMS": 30000,    # Timeout for socket operations (30 seconds)
    "retryWrites": True,         # Enable automatic retry for write operations
    "retryReads": True,          # Enable automatic retry for read operations
}

# Create MongoDB client and database connection with pool configuration
client: MongoClient = MongoClient(mongo_uri, **MONGO_POOL_CONFIG)
db = client[MONGO_DB]

# Export mongo_uri for use in Flask-Limiter
__all__ = ["db", "client", "mongo_uri"]
