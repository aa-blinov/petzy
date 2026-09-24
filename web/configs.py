"""Application configuration loaded from environment variables and JSON defaults."""

import json
import os
from typing import Dict, Any
from urllib.parse import quote_plus


def load_config() -> Dict[str, Any]:
    """
    Load application configuration from environment variables.
    Returns a dictionary with all configuration settings.
    """
    # MongoDB configuration (matching db.py format)
    mongo_user = os.getenv("MONGO_USER", "admin")
    mongo_pass = os.getenv("MONGO_PASS", "password")
    mongo_host = os.getenv("MONGO_HOST", "localhost")
    mongo_port = os.getenv("MONGO_PORT", "27017")
    mongo_db = os.getenv("MONGO_DB", "cat_health")
    # Use quote_plus to properly encode credentials (matching db.py)
    mongo_user_encoded = quote_plus(mongo_user)
    mongo_pass_encoded = quote_plus(mongo_pass)
    mongo_uri = (
        f"mongodb://{mongo_user_encoded}:{mongo_pass_encoded}@{mongo_host}:{mongo_port}/{mongo_db}?authSource=admin"
    )

    # CORS allowed origins (comma-separated). Empty list → reflect the
    # request Origin (safe with cookies only when front and back share an origin).
    cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
    cors_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

    # Base configuration structure
    config = {
        # Flask settings
        "flask": {
            "secret_key": os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production"),
            "debug": os.getenv("FLASK_DEBUG", "False").lower() == "true",
            "jsonify_prettyprint_regular": False,
            "json_as_ascii": False,
            "cookie_secure": os.getenv("COOKIE_SECURE", "false").lower() == "true",
            "cookie_samesite": os.getenv("COOKIE_SAMESITE", "Lax"),
        },
        # JWT settings
        "jwt": {
            "secret_key": os.getenv(
                "JWT_SECRET_KEY", os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
            ),
            "algorithm": "HS256",
            "access_token_expire_minutes": 15,
            "refresh_token_expire_days": 7,
        },
        # Rate limiting settings. Override any of these via env in
        # production or dev:
        #   RATE_LIMIT_LOGIN        — per-IP cap on /api/auth/login
        #   RATE_LIMIT_DEFAULT      — global fallback for everything else
        # Default values are chosen to be friendly to real users (forgot
        # password retry, slow phone, etc.) while still blocking brute
        # force — 5 logins per minute is ~1 attempt every 12 s, well
        # above human typing speed but well below any brute-force loop.
        "rate_limit": {
            "storage_uri": os.getenv("RATELIMIT_STORAGE_URI", mongo_uri),
            "default_limits": [],
            "strategy": "fixed-window",
            "login_limit": os.getenv("RATE_LIMIT_LOGIN", "5 per minute"),
        },
        # Logging settings
        "logging": {
            "level": os.getenv("LOG_LEVEL", "INFO").upper(),
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        # CORS settings
        "cors": {
            "allowed_origins": cors_origins,
        },
        # Admin settings
        "admin": {
            "username": os.getenv("ADMIN_USERNAME", "admin"),
            "password_hash": os.getenv("ADMIN_PASSWORD_HASH"),
        },
        # Web Push (VAPID). All optional — an unset VAPID_PUBLIC_KEY means
        # push notifications are simply unavailable (GET /api/push/
        # vapid-public-key returns push_not_configured) rather than a
        # startup failure, since not every deployment needs this feature.
        "push": {
            "vapid_public_key": os.getenv("VAPID_PUBLIC_KEY"),
            "vapid_private_key": os.getenv("VAPID_PRIVATE_KEY"),
            "vapid_claims_email": os.getenv("VAPID_CLAIMS_EMAIL", "admin@example.com"),
        },
        # MongoDB settings
        "mongodb": {
            "user": mongo_user,
            "pass": mongo_pass,
            "host": mongo_host,
            "port": mongo_port,
            "db": mongo_db,
            "uri": mongo_uri,
        },
    }

    return config


def get_config_json() -> str:
    """
    Get configuration as JSON string (for reference/documentation).
    Note: Sensitive values (passwords, secrets) are masked.
    """
    config = load_config()
    # Create a safe copy for JSON export (mask sensitive data)
    safe_config = json.loads(json.dumps(config))
    if safe_config["admin"]["password_hash"]:
        safe_config["admin"]["password_hash"] = "***MASKED***"
    if (
        safe_config["flask"]["secret_key"]
        and safe_config["flask"]["secret_key"] != "dev-secret-key-change-in-production"
    ):
        safe_config["flask"]["secret_key"] = "***MASKED***"
    if safe_config["jwt"]["secret_key"] and safe_config["jwt"]["secret_key"] != "dev-secret-key-change-in-production":
        safe_config["jwt"]["secret_key"] = "***MASKED***"
    if safe_config["mongodb"]["pass"]:
        safe_config["mongodb"]["pass"] = "***MASKED***"
    if safe_config["push"]["vapid_private_key"]:
        safe_config["push"]["vapid_private_key"] = "***MASKED***"

    return json.dumps(safe_config, indent=2, ensure_ascii=False)


# Load configuration on module import
_config = load_config()

# Export individual config sections for easy access
FLASK_CONFIG = _config["flask"]
JWT_CONFIG = _config["jwt"]
RATE_LIMIT_CONFIG = _config["rate_limit"]
LOGGING_CONFIG = _config["logging"]
ADMIN_CONFIG = _config["admin"]
PUSH_CONFIG = _config["push"]
MONGODB_CONFIG = _config["mongodb"]
CORS_CONFIG = _config["cors"]
