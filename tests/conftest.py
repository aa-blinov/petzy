"""Pytest configuration and fixtures."""

import os
import bcrypt
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from uuid import uuid4

import boto3
import jwt
import pytest
from moto import mock_aws
from mongomock import MongoClient

from web.builtin_event_types import seed_builtin_event_types

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
# Object storage: every test runs against moto's in-memory S3 (the
# s3_storage fixture below). An amazonaws endpoint so moto intercepts it;
# dummy credentials so nothing can reach a real bucket.
os.environ["S3_ENDPOINT"] = "https://s3.us-east-1.amazonaws.com"
os.environ["S3_REGION"] = "us-east-1"
os.environ["S3_BUCKET"] = "petzy-test"
os.environ["S3_KEY_ID"] = "testing"
os.environ["S3_SECRET_KEY"] = "testing"
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"

# Create mock database and patch before importing app
_mock_client = MongoClient()
_mock_db = _mock_client["test_db"]
# The import itself reaches for S3: web.app sets the bucket's CORS rules at startup, and it runs before any fixture. Without
# the mock around this import that call went to the real amazonaws.com with the dummy key, failed, and botocore retried it
# with pauses: a warning in every run, seconds of waiting, and a test suite that hangs on a machine without a network. The
# mock ends with the import; the per-test fixture below takes over from there.
with patch("web.db.db", _mock_db), patch("web.db.client", _mock_client), patch("gridfs.GridFS", MagicMock):
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=os.environ["S3_BUCKET"])
        from web.app import app
        from web.security import create_access_token


@pytest.fixture(autouse=True)
def s3_storage():
    """A fresh, empty in-memory bucket for every test."""
    import boto3
    from moto import mock_aws

    from web import storage

    with mock_aws():
        storage.reset_client()
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=os.environ["S3_BUCKET"])
        yield s3
    storage.reset_client()


@pytest.fixture(scope="function")
def mock_db():
    """Create a mock MongoDB database for testing."""
    mock_client = MongoClient()
    mock_db = mock_client["test_db"]

    # Patch the db module and GridFS
    with (
        patch("web.db.db", mock_db),
        patch("web.app.db", mock_db),
        patch("web.security.db", mock_db),
        patch("web.app.fs", MagicMock()),
    ):
        # Clear any existing data
        mock_db["users"].delete_many({})
        mock_db["pets"].delete_many({})
        mock_db["refresh_tokens"].delete_many({})
        mock_db["asthma_attacks"].delete_many({})
        mock_db["defecations"].delete_many({})
        mock_db["litter_changes"].delete_many({})
        mock_db["weights"].delete_many({})
        mock_db["feedings"].delete_many({})
        mock_db["medications"].delete_many({})
        mock_db["medication_intakes"].delete_many({})
        mock_db["eye_drops"].delete_many({})
        mock_db["ear_cleaning"].delete_many({})
        mock_db["tooth_brushing"].delete_many({})
        mock_db["events"].delete_many({})
        mock_db["event_types"].delete_many({})

        # Populate the event-type registry the same way production does at
        # startup, so every test sees the eight builtin types available.
        seed_builtin_event_types(mock_db)

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
    from web.security import JWT_SECRET_KEY, REFRESH_TOKEN_EXPIRE_DAYS

    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    jti = uuid4().hex
    payload = {"username": "admin", "exp": expire, "type": "refresh", "jti": jti}
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm="HS256")

    # Store in database
    from web.app import db

    db["refresh_tokens"].insert_one(
        {
            "jti": jti,
            "token": token,
            "username": "admin",
            "created_at": datetime.now(timezone.utc),
            "expires_at": expire,
        }
    )

    return token


_PASSWORD_HASHES: dict[bytes, str] = {}


def password_hash_for(password: bytes) -> str:
    """A bcrypt hash for a user document a test puts into the database.

    One hash per password, not one per test: bcrypt costs 0.18s, and nothing here
    checks that two users with the same password got different salts. A test that
    needs a fresh hash for a real security reason should say so and compute it.
    """
    if password not in _PASSWORD_HASHES:
        _PASSWORD_HASHES[password] = bcrypt.hashpw(password, bcrypt.gensalt()).decode()
    return _PASSWORD_HASHES[password]


_TEST_PASSWORD_HASH = bcrypt.hashpw("user123".encode(), bcrypt.gensalt()).decode()


@pytest.fixture
def regular_user(mock_db):
    """Create a regular test user."""
    password_hash = _TEST_PASSWORD_HASH
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
