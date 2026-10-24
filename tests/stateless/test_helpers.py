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
        assert data["error"] == "Не удалось определить питомца"

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
        assert "Не удалось определить питомца" in data["error"]

    def test_validate_pet_access_no_access(self, client, mock_db, regular_user_token, admin_pet):
        """validate_pet_access should fail when user has no access to pet."""
        from web.app import app
        from web.helpers import validate_pet_access

        # admin_pet belongs to 'admin', regular_user_token belongs to 'testuser'
        with app.app_context():
            success, error_response = validate_pet_access(str(admin_pet["_id"]), "testuser")

        assert success is False
        response, status = error_response
        assert status == 404
        data = response.get_json()
        assert data["code"] == "pet_not_found"

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
        assert "Неверный формат даты или времени" in data["error"]
        assert data["code"] == "validation_error"

    def test_parse_event_datetime_safe_half_given_is_refused(self, client, mock_db, regular_user_token, test_pet):
        """A date without a time (or the reverse) is refused: it used to become «now» and drop what was typed."""
        from web.app import app
        from web.helpers import parse_event_datetime_safe

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with app.app_context():
            for date_str, time_str in ((today, None), (today, ""), (None, "10:00"), ("", "10:00")):
                event_dt, error = parse_event_datetime_safe(date_str, time_str, "ctx", str(test_pet["_id"]), "u")
                assert event_dt is None
                assert error[1] == 422

    def test_parse_event_datetime_safe_neither_is_now_to_the_minute(self, mock_db):
        from web.app import app
        from web.helpers import parse_event_datetime_safe

        with app.app_context():
            event_dt, error = parse_event_datetime_safe("", "")
            assert error is None
            assert event_dt.second == 0 and event_dt.microsecond == 0

            event_dt, error = parse_event_datetime_safe("", "", allow_now=False)
            assert event_dt is None and error[1] == 422

    def test_non_padded_date_or_time_is_refused(self, mock_db):
        from web.app import app
        from web.helpers import parse_event_datetime_safe

        with app.app_context():
            for date_str, time_str in (("2026-1-5", "10:00"), ("2026-01-05", "8:5")):
                event_dt, error = parse_event_datetime_safe(date_str, time_str)
                assert event_dt is None and error[1] == 422


class TestParseEventDatetime:
    """parse_event_datetime (the raising variant, distinct from
    parse_event_datetime_safe's tuple-returning contract used by
    events.py) isn't currently called from any route, but it's a real,
    reachable function with its own contract worth verifying directly.
    """

    def test_both_present_parses_combined_datetime(self):
        from web.helpers import parse_event_datetime

        result = parse_event_datetime("2024-01-15", "14:30")
        assert result.hour == 14
        assert result.minute == 30

    def test_neither_present_returns_now(self):
        from web.helpers import parse_event_datetime
        from datetime import datetime, timedelta

        before = datetime.now().replace(second=0, microsecond=0)
        result = parse_event_datetime("", "")
        after = datetime.now()
        assert before <= result <= after + timedelta(seconds=1)
        assert result.second == 0 and result.microsecond == 0

    def test_only_date_present_raises(self):
        from web.helpers import parse_event_datetime

        with pytest.raises(ValueError, match="вместе"):
            parse_event_datetime("2024-01-15", "")

    def test_only_time_present_raises(self):
        from web.helpers import parse_event_datetime

        with pytest.raises(ValueError, match="вместе"):
            parse_event_datetime("", "14:30")


class TestGetRecordAndValidateAccessMalformedRecord:
    def test_record_without_pet_id_is_rejected(self, client, mock_db):
        from web.helpers import get_record_and_validate_access
        from bson import ObjectId
        from web.app import app as flask_app

        record_id = ObjectId()
        mock_db["medications"].insert_one({"_id": record_id, "name": "orphaned, no pet_id"})

        with flask_app.test_request_context("/"):
            record, pet_id, error = get_record_and_validate_access(str(record_id), "medications", "testuser")

        assert record is None
        assert pet_id is None
        assert error is not None


class TestOptimizeImagePaletteMode:
    def test_palette_mode_image_converts_correctly(self):
        import io
        from PIL import Image
        from web.helpers import optimize_image
        from werkzeug.datastructures import FileStorage

        buf = io.BytesIO()
        # A "P" (palette) mode image, as produced by e.g. a GIF or an
        # indexed-color PNG.
        img = Image.new("RGB", (10, 10), (200, 50, 50)).convert("P")
        img.save(buf, format="PNG")
        buf.seek(0)
        file_storage = FileStorage(stream=buf, filename="palette.png")

        result = optimize_image(file_storage)

        assert result is not None
        output, content_type = result
        assert content_type == "image/webp"
        assert Image.open(output).format == "WEBP"

    def test_grayscale_mode_image_converts_to_rgb(self):
        import io
        from PIL import Image
        from web.helpers import optimize_image
        from werkzeug.datastructures import FileStorage

        buf = io.BytesIO()
        img = Image.new("L", (10, 10), 128)  # grayscale — neither RGBA/LA/P nor RGB
        img.save(buf, format="PNG")
        buf.seek(0)
        file_storage = FileStorage(stream=buf, filename="gray.png")

        result = optimize_image(file_storage)

        assert result is not None
        output, content_type = result
        assert content_type == "image/webp"
