
import pytest
from flask import Flask, g, jsonify, request
from bson import ObjectId
from web.decorators import require_pet_access, require_record_access
from web.errors import error_response

# Mock app and db setup for testing
@pytest.fixture
def test_app_with_decorators(mock_db):
    app = Flask(__name__)
    app.db = mock_db
    
    # Mock get_current_user to return a test user
    # We'll patch this inside the tests or use a context manager if possible,
    # but since decorators import it, we might need to mock where it's imported in decorators.py
    return app

@pytest.fixture(autouse=True)
def mock_login_required(monkeypatch):
    """Mock login_required to pass through."""
    def _mock_login_required(f):
        return f
    monkeypatch.setattr("web.decorators.login_required", _mock_login_required)

@pytest.fixture
def client(test_app_with_decorators):
    return test_app_with_decorators.test_client()

@pytest.fixture
def mock_auth(monkeypatch):
    """Mock authentication to return a specific user."""
    def _mock_auth(username="testuser", error=None):
        def mock_get_current_user():
            return username, error
        monkeypatch.setattr("web.decorators.get_current_user", mock_get_current_user)
    return _mock_auth

@pytest.fixture
def mock_validate_access(monkeypatch):
    """Mock validate_pet_access."""
    def _mock_validate(success=True, error=None):
        def mock_validate_pet_access(pet_id, username):
            return success, error
        monkeypatch.setattr("web.decorators.validate_pet_access", mock_validate_pet_access)
    return _mock_validate

@pytest.fixture
def mock_record_access(monkeypatch):
    """Mock get_record_and_validate_access."""
    def _mock_record_access(record=None, pet_id="123", error=None):
        def mock_func(record_id, collection, username):
            return record, pet_id, error
        monkeypatch.setattr("web.decorators.get_record_and_validate_access", mock_func)
    return _mock_record_access


def test_require_pet_access_success(test_app_with_decorators, mock_auth, mock_validate_access):
    """Test @require_pet_access allows access when validation succeeds."""
    mock_auth(username="testuser")
    mock_validate_access(success=True)

    @test_app_with_decorators.route("/test_pet_access", methods=["GET"])
    @require_pet_access
    def test_route():
        return jsonify({"user": g.username, "pet": g.pet_id})

    client = test_app_with_decorators.test_client()
    response = client.get("/test_pet_access?pet_id=123")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"] == "testuser"
    assert data["pet"] == "123"

def test_require_pet_access_no_auth(test_app_with_decorators, mock_auth):
    """Test @require_pet_access fails when user not authenticated."""
    with test_app_with_decorators.app_context():
        mock_auth(username=None, error=(jsonify({"error": "unauthorized"}), 401))

        @test_app_with_decorators.route("/test_no_auth", methods=["GET"])
        @require_pet_access
        def test_route():
            return "Allowed"

        client = test_app_with_decorators.test_client()
        response = client.get("/test_no_auth?pet_id=123")
        
        assert response.status_code == 401

def test_require_pet_access_denied(test_app_with_decorators, mock_auth, mock_validate_access):
    """Test @require_pet_access fails when validate_pet_access returns error."""
    with test_app_with_decorators.app_context():
        mock_auth(username="testuser")
        mock_validate_access(success=False, error=(jsonify({"error": "forbidden"}), 403))

        @test_app_with_decorators.route("/test_denied", methods=["GET"])
        @require_pet_access
        def test_route():
            return "Allowed"

        client = test_app_with_decorators.test_client()
        response = client.get("/test_denied?pet_id=123")
        
        assert response.status_code == 403

def test_require_record_access_success(test_app_with_decorators, mock_auth, mock_record_access):
    """Test @require_record_access allows access when validation succeeds."""
    mock_auth(username="testuser")
    mock_record = {"_id": ObjectId(), "data": "test"}
    mock_record_access(record=mock_record, pet_id="123")

    @test_app_with_decorators.route("/test_record/<record_id>", methods=["GET"])
    @require_record_access("test_collection")
    def test_route(record_id):
        # Need to ensure we are in a request context to access g
        return jsonify({"user": g.username, "pet": g.pet_id, "record_id": str(g.record["_id"])})

    client = test_app_with_decorators.test_client()
    response = client.get("/test_record/abc")
    
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"] == "testuser"
    assert data["pet"] == "123"
    assert data["record_id"] == str(mock_record["_id"])

def test_require_record_access_denied(test_app_with_decorators, mock_auth, mock_record_access):
    """Test @require_record_access fails when access denied."""
    with test_app_with_decorators.app_context():
        mock_auth(username="testuser")
        mock_record_access(error=(jsonify({"error": "not found"}), 404))

        @test_app_with_decorators.route("/test_record_denied/<record_id>", methods=["GET"])
        @require_record_access("test_collection")
        def test_route(record_id):
            return "Allowed"

        client = test_app_with_decorators.test_client()
        response = client.get("/test_record_denied/abc")
        
        assert response.status_code == 404
