"""Direct unit tests for schema-level validators in web.schemas.

validate_date_logic is shared by PetCreate/PetUpdate/HealthRecordBase/
HealthRecordUpdateBase, but no existing test exercises it directly —
route-level date tests go through web.helpers.parse_date/parse_datetime
instead, a separate implementation with the same rules (see the
"combined datetime" tests in test_events.py for why these two exist
side by side). Testing this one directly is the reliable way to hit
every one of its branches without needing to find a route where it's
the specific thing that fires first.
"""

from datetime import datetime, timedelta

import pytest


@pytest.mark.unit
class TestValidateDateLogic:
    def test_empty_value_passes_through(self):
        from web.schemas import validate_date_logic

        assert validate_date_logic("", allow_future=True) == ""

    def test_invalid_format_rejected(self):
        from web.schemas import validate_date_logic

        with pytest.raises(ValueError, match="формат"):
            validate_date_logic("15/01/2024", allow_future=True)

    def test_future_rejected_when_not_allowed(self):
        from web.schemas import validate_date_logic

        tomorrow = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        with pytest.raises(ValueError, match="будущем"):
            validate_date_logic(tomorrow, allow_future=False)

    def test_future_beyond_max_future_days_rejected(self):
        from web.schemas import validate_date_logic

        too_far = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        with pytest.raises(ValueError, match="будущем"):
            validate_date_logic(too_far, allow_future=True, max_future_days=1)

    def test_past_beyond_max_past_years_rejected(self):
        from web.schemas import validate_date_logic

        too_old = (datetime.now() - timedelta(days=366 * 60)).strftime("%Y-%m-%d")
        with pytest.raises(ValueError, match="прошлом"):
            validate_date_logic(too_old, allow_future=True, max_past_years=50)

    def test_valid_date_within_bounds_returned_unchanged(self):
        from web.schemas import validate_date_logic

        assert validate_date_logic("2024-06-15", allow_future=True) == "2024-06-15"


@pytest.mark.unit
class TestHealthRecordTimeAndDateEdgeCases:
    """HealthRecordBase.time technically allows an empty string to skip
    format validation entirely (short-circuited before strptime runs) —
    documenting that as intentional-or-not, it's the current behavior."""

    def test_health_record_base_accepts_empty_time_without_format_check(self):
        from web.schemas import HealthRecordBase

        instance = HealthRecordBase(pet_id="507f1f77bcf86cd799439011", date="2024-01-01", time="")
        assert instance.time == ""

    def test_health_record_update_base_accepts_empty_date_and_time(self):
        from web.schemas import HealthRecordUpdateBase

        instance = HealthRecordUpdateBase(date="", time="")
        assert instance.date == ""
        assert instance.time == ""

    def test_health_record_update_base_still_validates_non_empty_date(self):
        from web.schemas import HealthRecordUpdateBase
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            HealthRecordUpdateBase(date="not-a-date")

    def test_health_record_update_base_rejects_malformed_non_empty_time(self):
        from web.schemas import HealthRecordUpdateBase
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="времени"):
            HealthRecordUpdateBase(time="25:99")


@pytest.mark.unit
class TestEventTypeFieldAndChartValidators:
    def test_event_type_field_rejects_unknown_type(self):
        from web.schemas import EventTypeField
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Тип поля"):
            EventTypeField(name="x", label="X", type="not_a_real_type")

    def test_event_chart_config_rejects_unknown_kind(self):
        from web.schemas import EventChartConfig
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="kind"):
            EventChartConfig(kind="not_count_or_value")

    def test_number_field_with_no_explicit_min_defaults_to_zero(self):
        """There's no UI for a custom event type to declare a
        negative-capable numeric field, so "no min given" must not mean
        "no floor at all" — it means 0, decided once here rather than by
        every consumer of the field def."""
        from web.schemas import EventTypeField

        field = EventTypeField(name="distance_km", label="Дистанция", type="number")

        assert field.min == 0.0

    def test_number_field_with_explicit_min_keeps_it(self):
        from web.schemas import EventTypeField

        field = EventTypeField(name="temp_delta", label="Дельта температуры", type="number", min=-10)

        assert field.min == -10

    def test_non_number_field_is_not_given_a_min(self):
        from web.schemas import EventTypeField

        field = EventTypeField(name="note", label="Заметка", type="text")

        assert field.min is None

    def test_deviation_threshold_must_be_a_fraction(self):
        from web.schemas import EventTypeField
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            EventTypeField(name="x", label="X", type="number", deviation_threshold=1.5)
