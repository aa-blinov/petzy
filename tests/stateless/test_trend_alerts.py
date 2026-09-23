"""Tests for web.trend_alerts.detect_anomaly — pure Mongo-query logic,
no Flask request context needed."""

import pytest
from datetime import datetime, timezone

from web.trend_alerts import detect_anomaly, DEVIATION_THRESHOLD, MIN_HISTORY_FOR_BASELINE, ROLLING_WINDOW


def _insert_weight_events(mock_db, pet_id, values):
    """Oldest first in `values` — inserted with increasing date_time so
    "most recent N" (sort by date_time desc) matches "last N in the list"."""
    for i, v in enumerate(values):
        mock_db.events.insert_one(
            {
                "pet_id": pet_id,
                "type": "weight",
                "date_time": datetime(2024, 1, 1 + i, tzinfo=timezone.utc),
                "fields": {"weight": v},
            }
        )


@pytest.mark.unit
class TestDetectAnomaly:
    def test_not_enough_history_returns_none(self, mock_db):
        assert MIN_HISTORY_FOR_BASELINE == 3
        pet_id = "pet-1"
        _insert_weight_events(mock_db, pet_id, [5.0, 5.1])  # only 2, one short of the minimum

        assert detect_anomaly(mock_db, pet_id, "weight", "weight", 5.2) is None

    def test_value_within_threshold_returns_none(self, mock_db):
        pet_id = "pet-1"
        _insert_weight_events(mock_db, pet_id, [5.0, 5.1, 4.9, 5.0])  # average 5.0

        # 5.3 is 6% above the 5.0 average — comfortably under the 15% bound.
        assert detect_anomaly(mock_db, pet_id, "weight", "weight", 5.3) is None

    def test_value_above_threshold_flagged(self, mock_db):
        pet_id = "pet-1"
        _insert_weight_events(mock_db, pet_id, [5.0, 5.0, 5.0, 5.0])  # average 5.0

        result = detect_anomaly(mock_db, pet_id, "weight", "weight", 6.5)  # +30%

        assert result is not None
        assert result["average"] == 5.0
        assert result["deviation"] == pytest.approx(0.3, abs=1e-6)

    def test_value_below_threshold_on_the_low_side_flagged(self, mock_db):
        """A sharp drop matters as much as a sharp rise — both directions
        of deviation are checked via abs()."""
        pet_id = "pet-1"
        _insert_weight_events(mock_db, pet_id, [5.0, 5.0, 5.0, 5.0])

        result = detect_anomaly(mock_db, pet_id, "weight", "weight", 3.5)  # -30%

        assert result is not None
        assert result["deviation"] == pytest.approx(0.3, abs=1e-6)

    def test_exactly_at_threshold_is_flagged(self, mock_db):
        """The comparison is a strict `<` against the threshold, so a
        deviation of exactly DEVIATION_THRESHOLD (not one hair more) still
        counts as abnormal rather than slipping through as "normal" by an
        off-by-one on the boundary."""
        pet_id = "pet-1"
        _insert_weight_events(mock_db, pet_id, [5.0, 5.0, 5.0, 5.0])  # average 5.0

        assert DEVIATION_THRESHOLD == 0.15
        result = detect_anomaly(mock_db, pet_id, "weight", "weight", 5.75)  # exactly +15%

        assert result is not None
        assert result["deviation"] == pytest.approx(0.15, abs=1e-9)

    def test_only_recent_window_counts_not_all_history(self, mock_db):
        """A much older reading outside ROLLING_WINDOW must not drag the
        baseline — otherwise a pet that's been steadily gaining weight for
        months would keep comparing against a stale, now-irrelevant past."""
        pet_id = "pet-1"
        # 6 readings — one more than ROLLING_WINDOW (5). The oldest (10.0,
        # a wildly different value) must be excluded from the average.
        assert ROLLING_WINDOW == 5
        _insert_weight_events(mock_db, pet_id, [10.0, 5.0, 5.0, 5.0, 5.0, 5.0])

        # If the 10.0 outlier were included, the average would be ~5.83
        # and this wouldn't cross the 15% bound; excluded, average is 5.0
        # and it does.
        result = detect_anomaly(mock_db, pet_id, "weight", "weight", 6.0)

        assert result is not None
        assert result["average"] == 5.0

    def test_zero_average_does_not_divide_by_zero(self, mock_db):
        pet_id = "pet-1"
        _insert_weight_events(mock_db, pet_id, [0, 0, 0])

        assert detect_anomaly(mock_db, pet_id, "weight", "weight", 5.0) is None

    def test_non_numeric_history_values_are_ignored(self, mock_db):
        """A malformed/legacy record with a non-numeric value in the field
        (shouldn't normally happen given input validation, but history can
        predate a schema change) must not crash the average."""
        pet_id = "pet-1"
        mock_db.events.insert_one(
            {
                "pet_id": pet_id,
                "type": "weight",
                "date_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "fields": {"weight": "not-a-number"},
            }
        )
        _insert_weight_events(mock_db, pet_id, [5.0, 5.0, 5.0])

        # Only the 3 real numeric readings count toward MIN_HISTORY_FOR_BASELINE.
        result = detect_anomaly(mock_db, pet_id, "weight", "weight", 6.5)
        assert result is not None
        assert result["average"] == 5.0

    def test_different_pet_history_is_not_mixed_in(self, mock_db):
        _insert_weight_events(mock_db, "pet-1", [5.0, 5.0, 5.0])
        _insert_weight_events(mock_db, "pet-2", [50.0, 50.0, 50.0])

        result = detect_anomaly(mock_db, "pet-1", "weight", "weight", 6.5)

        assert result is not None
        assert result["average"] == 5.0  # not contaminated by pet-2's much larger values

    def test_negative_average_still_flags_a_large_swing(self, mock_db):
        """The deviation formula divides by abs(average), not the raw
        (possibly negative) average — otherwise a negative baseline flips
        the sign and the comparison against DEVIATION_THRESHOLD always
        looks "normal" no matter how far off the new value is."""
        pet_id = "pet-1"
        _insert_weight_events(mock_db, pet_id, [-2.0, -2.5, -2.0, -3.0])  # average -2.375

        result = detect_anomaly(mock_db, pet_id, "weight", "weight", -10.0)  # ~320% off

        assert result is not None
        assert result["average"] == -2.38
        assert result["deviation"] == pytest.approx(abs(-10.0 - (-2.375)) / abs(-2.375), abs=1e-6)

    def test_custom_deviation_threshold_overrides_the_module_default(self, mock_db):
        """A caller can pass a field's own declared sensitivity instead of
        the module-wide DEVIATION_THRESHOLD (e.g. a naturally noisy field
        that shouldn't fire at the default 15%)."""
        pet_id = "pet-1"
        _insert_weight_events(mock_db, pet_id, [5.0, 5.0, 5.0, 5.0])  # average 5.0

        # +30% would be flagged at the default threshold...
        assert detect_anomaly(mock_db, pet_id, "weight", "weight", 6.5) is not None
        # ...but not against an explicit, wider threshold.
        assert detect_anomaly(mock_db, pet_id, "weight", "weight", 6.5, deviation_threshold=0.35) is None

    def test_different_type_or_field_history_is_not_mixed_in(self, mock_db):
        pet_id = "pet-1"
        _insert_weight_events(mock_db, pet_id, [5.0, 5.0, 5.0])
        for i in range(3):
            mock_db.events.insert_one(
                {
                    "pet_id": pet_id,
                    "type": "feeding",
                    "date_time": datetime(2024, 2, 1 + i, tzinfo=timezone.utc),
                    "fields": {"food_weight": 300},
                }
            )

        result = detect_anomaly(mock_db, pet_id, "weight", "weight", 6.5)

        assert result is not None
        assert result["average"] == 5.0  # not contaminated by the feeding events
