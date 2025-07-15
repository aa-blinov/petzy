"""Configuration for the bot, including environment variable management."""

import os


def get_env(name: str) -> str:
    """Get environment variable and raise error if not set."""
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Environment variable '{name}' is not set!")
    return value


MONGO_USER = get_env("MONGO_USER")
MONGO_PASS = get_env("MONGO_PASS")
MONGO_HOST = get_env("MONGO_HOST")
MONGO_PORT = get_env("MONGO_PORT")
MONGO_DB = get_env("MONGO_DB")
TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")
