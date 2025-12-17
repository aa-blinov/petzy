"""Pytest configuration and fixtures."""

import os
import bcrypt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import jwt
import pytest
from mongomock import MongoClient

# Set test environment variables before importing app
os.environ["FLASK_SECRET_KEY"] = "test-secret-key"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD_HASH"] = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
os.environ["MONGO_USER"] = "test_user"
os.environ["MONGO_PASS"] = "test_pass"
os.environ["MONGO_HOST"] = "localhost"
os.environ["MONGO_PORT"] = "27017"
os.environ["MONGO_DB"] = "test_db"
# Use memory storage for Flask-Limiter in tests
os.environ["RATELIMIT_STORAGE_URI"] = "memory://"

# Create mock database and patch before importing app
_mock_client = MongoClient()
_mock_db = _mock_client["test_db"]
# Patch db and GridFS before importing app so ensure_default_admin uses mock_db
with patch("web.db.db", _mock_db), patch("web.db.client", _mock_client), patch("gridfs.GridFS", MagicMock):
    from web.app import app
    from web.security import create_access_token


@pytest.fixture(scope="function")
def mock_db():
    """Create a mock MongoDB database for testing."""
    mock_client = MongoClient()
    mock_db = mock_client["test_db"]

    # Patch the db module and GridFS
    with patch("web.db.db", mock_db), patch("web.app.db", mock_db), patch("web.app.fs", MagicMock()):
        # Clear any existing data
        mock_db["users"].delete_many({})
        mock_db["pets"].delete_many({})
        mock_db["refresh_tokens"].delete_many({})
        mock_db["asthma_attacks"].delete_many({})
        mock_db["defecations"].delete_many({})
        mock_db["litter_changes"].delete_many({})
        mock_db["weights"].delete_many({})
        mock_db["feedings"].delete_many({})

        # Create default admin user
        admin_password_hash = os.environ["ADMIN_PASSWORD_HASH"]
        mock_db["users"].insert_one(
            {
                "username": "admin",
                "password_hash": admin_password_hash,
                "full_name": "Administrator",
                "email": "",
                "created_at": datetime.now(timezone.utc),
                "created_by": "system",
                "is_active": True,
            }
        )

        yield mock_db

        # Cleanup
        mock_client.drop_database("test_db")


@pytest.fixture(scope="function")
def client(mock_db):
    """Create a Flask test client."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        yield client


@pytest.fixture
def admin_token():
    """Create a valid access token for admin user."""
    return create_access_token("admin")


@pytest.fixture
def admin_refresh_token(mock_db):
    """Create a valid refresh token for admin user."""
    # Need to use mock_db context, so create token manually
    from web.security import JWT_SECRET_KEY, JWT_ALGORITHM, REFRESH_TOKEN_EXPIRE_DAYS

    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"username": "admin", "exp": expire, "type": "refresh"}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    # Store in database
    from web.app import db

    db["refresh_tokens"].insert_one(
        {"token": token, "username": "admin", "created_at": datetime.now(timezone.utc), "expires_at": expire}
    )

    return token


@pytest.fixture
def regular_user(mock_db):
    """Create a regular test user."""
    password_hash = bcrypt.hashpw("user123".encode(), bcrypt.gensalt()).decode()
    user_data = {
        "username": "testuser",
        "password_hash": password_hash,
        "full_name": "Test User",
        "email": "test@example.com",
        "created_at": datetime.now(timezone.utc),
        "created_by": "admin",
        "is_active": True,
    }
    mock_db["users"].insert_one(user_data)
    return user_data


@pytest.fixture
def regular_user_token(regular_user):
    """Create a valid access token for regular user."""
    return create_access_token(regular_user["username"])


@pytest.fixture
def test_pet(mock_db, regular_user):
    """Create a test pet owned by regular user."""
    pet_data = {
        "name": "Test Cat",
        "breed": "Persian",
        "birth_date": datetime(2020, 1, 1),
        "gender": "Male",
        "owner": regular_user["username"],
        "shared_with": [],
        "created_at": datetime.now(timezone.utc),
        "created_by": regular_user["username"],
    }
    result = mock_db["pets"].insert_one(pet_data)
    pet_data["_id"] = result.inserted_id
    return pet_data


@pytest.fixture
def admin_pet(mock_db):
    """Create a test pet owned by admin."""
    pet_data = {
        "name": "Admin Cat",
        "breed": "Siamese",
        "birth_date": datetime(2019, 5, 15),
        "gender": "Female",
        "owner": "admin",
        "shared_with": [],
        "created_at": datetime.now(timezone.utc),
        "created_by": "admin",
    }
    result = mock_db["pets"].insert_one(pet_data)
    pet_data["_id"] = result.inserted_id
    return pet_data


@pytest.fixture
def auth_headers(admin_token):
    """Create authorization headers with access token."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def auth_cookies(admin_token, admin_refresh_token):
    """Create cookies with access and refresh tokens."""
    return {"access_token": admin_token, "refresh_token": admin_refresh_token}
