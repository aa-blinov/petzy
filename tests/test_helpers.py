"""Edge-case tests for helper functions (access and datetime helpers)."""

import pytest
from datetime import datetime, timezone


@pytest.mark.unit
class TestAccessHelpers:
    """Tests for validate_pet_access and check_pet_access edge cases."""

    def test_validate_pet_access_missing_pet_id(self, client, mock_db, regular_user_token):
        """validate_pet_access should fail when pet_id is missing."""
        from web.app import app
        from web.helpers import validate_pet_access

        with app.app_context():
            success, error_response = validate_pet_access(None, "testuser")

        assert success is False
        assert error_response is not None
        response, status = error_response
        assert status == 422
        data = response.get_json()
        assert "error" in data
        assert "pet_id" in data["error"]

    def test_validate_pet_access_invalid_pet_id_format(self, client, mock_db, regular_user_token):
        """validate_pet_access should fail on invalid pet_id format."""
        from web.app import app
        from web.helpers import validate_pet_access

        with app.app_context():
            success, error_response = validate_pet_access("not-an-object-id", "testuser")

        assert success is False
        response, status = error_response
        assert status == 422
        data = response.get_json()
        assert "Неверный формат pet_id" in data["error"]

    def test_validate_pet_access_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """validate_pet_access should fail when user has no access to pet."""
        from web.app import app
        from web.helpers import validate_pet_access

        # admin_pet belongs to 'admin', regular_user_token belongs to 'testuser'
        with app.app_context():
            success, error_response = validate_pet_access(str(admin_pet["_id"]), "testuser")

        assert success is False
        response, status = error_response
        assert status == 403
        data = response.get_json()
        assert "Нет доступа к этому животному" in data["error"]

    def test_validate_pet_access_success_owner(self, client, mock_db, regular_user, test_pet):
        """validate_pet_access should succeed for pet owner."""
        from web.app import app
        from web.helpers import validate_pet_access

        with app.app_context():
            success, error_response = validate_pet_access(str(test_pet["_id"]), regular_user["username"])

        assert success is True
        assert error_response is None

    def test_check_pet_access_invalid_pet_id(self, client, mock_db):
        """check_pet_access should return False for invalid pet_id format."""
        from web.helpers import check_pet_access

        assert check_pet_access("not-an-object-id", "user") is False

    def test_check_pet_access_pet_not_found(self, client, mock_db):
        """check_pet_access should return False when pet does not exist."""
        from web.helpers import check_pet_access
        from bson import ObjectId

        fake_id = str(ObjectId())
        assert check_pet_access(fake_id, "user") is False

    def test_check_pet_access_owner(self, client, mock_db, regular_user, test_pet):
        """check_pet_access should return True for pet owner."""
        from web.helpers import check_pet_access

        assert check_pet_access(str(test_pet["_id"]), regular_user["username"]) is True

    def test_check_pet_access_shared_user(self, client, mock_db, regular_user, test_pet):
        """check_pet_access should return True for user in shared_with."""
        from web.helpers import check_pet_access
        from web.db import db

        # Share pet with another user
        db["pets"].update_one({"_id": test_pet["_id"]}, {"$addToSet": {"shared_with": "shareduser"}})

        assert check_pet_access(str(test_pet["_id"]), "shareduser") is True


@pytest.mark.datetime
class TestParseEventDateTimeSafe:
    """Additional edge-case tests for parse_event_datetime_safe."""

    def test_parse_event_datetime_safe_valid_values(self, client, mock_db, regular_user_token, test_pet):
        """Should return parsed datetime when both date and time are valid."""
        from web.helpers import parse_event_datetime_safe

        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")

        event_dt, error_response = parse_event_datetime_safe(
            date_str, time_str, "test-context", str(test_pet["_id"]), "testuser"
        )

        assert error_response is None
        assert isinstance(event_dt, datetime)

    def test_parse_event_datetime_safe_invalid_values(self, client, mock_db, regular_user_token, test_pet):
        """Should return error_response with 400 for invalid date/time."""
        from web.app import app
        from web.helpers import parse_event_datetime_safe

        with app.app_context():
            event_dt, error_response = parse_event_datetime_safe(
                "invalid-date", "invalid-time", "test-context", str(test_pet["_id"]), "testuser"
            )

        assert event_dt is None
        assert error_response is not None
        response, status = error_response
        assert status == 422
        data = response.get_json()
        assert data["error"] == "Неверные данные"
        assert data["code"] == "validation_error"

    def test_parse_event_datetime_safe_missing_date_or_time(self, client, mock_db, regular_user_token, test_pet):
        """When date or time is missing, should return current datetime without error."""
        from web.helpers import parse_event_datetime_safe

        # Missing time
        event_dt1, error_response1 = parse_event_datetime_safe(
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            None,
            "test-context",
            str(test_pet["_id"]),
            "testuser",
        )

        # Missing date
        event_dt2, error_response2 = parse_event_datetime_safe(
            None,
            datetime.now(timezone.utc).strftime("%H:%M"),
            "test-context",
            str(test_pet["_id"]),
            "testuser",
        )

        assert error_response1 is None
        assert error_response2 is None
        assert isinstance(event_dt1, datetime)
        assert isinstance(event_dt2, datetime)
