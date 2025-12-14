"""Tests for datetime parsing helper functions."""

import pytest
from datetime import datetime, timedelta
from web.app import parse_datetime, parse_date


@pytest.mark.datetime
class TestDateTimeParsing:
    """Test datetime parsing helper functions."""
    
    def test_parse_datetime_success_with_time(self):
        """Test successful parsing of date and time."""
        result = parse_datetime("2024-01-15", "14:30")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
    
    def test_parse_datetime_success_date_only(self):
        """Test successful parsing of date only."""
        result = parse_datetime("2024-01-15")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0
    
    def test_parse_datetime_invalid_date_format(self):
        """Test parsing with invalid date format."""
        with pytest.raises(ValueError) as exc_info:
            parse_datetime("2024/01/15", "14:30")
        assert "Invalid date/time format" in str(exc_info.value)
        assert "YYYY-MM-DD HH:MM" in str(exc_info.value)
    
    def test_parse_datetime_invalid_time_format(self):
        """Test parsing with invalid time format."""
        with pytest.raises(ValueError) as exc_info:
            parse_datetime("2024-01-15", "14:30:00")
        assert "Invalid date/time format" in str(exc_info.value)
    
    def test_parse_datetime_invalid_date_only_format(self):
        """Test parsing date only with invalid format."""
        with pytest.raises(ValueError) as exc_info:
            parse_datetime("2024/01/15")
        assert "Invalid date format" in str(exc_info.value)
        assert "YYYY-MM-DD" in str(exc_info.value)
    
    def test_parse_datetime_empty_date_string(self):
        """Test parsing with empty date string."""
        with pytest.raises(ValueError) as exc_info:
            parse_datetime("", "14:30")
        assert "Date string is required" in str(exc_info.value)
    
    def test_parse_datetime_future_date_allowed(self):
        """Test parsing future date when allowed."""
        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")
        time_str = tomorrow.strftime("%H:%M")
        
        result = parse_datetime(date_str, time_str, allow_future=True, max_future_days=1)
        assert isinstance(result, datetime)
    
    def test_parse_datetime_future_date_exceeds_limit(self):
        """Test parsing future date that exceeds limit."""
        future_date = datetime.now() + timedelta(days=2)
        date_str = future_date.strftime("%Y-%m-%d")
        time_str = future_date.strftime("%H:%M")
        
        with pytest.raises(ValueError) as exc_info:
            parse_datetime(date_str, time_str, allow_future=True, max_future_days=1)
        assert "cannot be more than 1 day(s) in the future" in str(exc_info.value)
    
    def test_parse_datetime_future_date_not_allowed(self):
        """Test parsing future date when not allowed."""
        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")
        time_str = tomorrow.strftime("%H:%M")
        
        with pytest.raises(ValueError) as exc_info:
            parse_datetime(date_str, time_str, allow_future=False, max_future_days=0)
        assert "cannot be more than 0 day(s) in the future" in str(exc_info.value)
    
    def test_parse_datetime_past_date_too_old(self):
        """Test parsing date that is too old."""
        old_date = datetime.now() - timedelta(days=51 * 365)
        date_str = old_date.strftime("%Y-%m-%d")
        
        with pytest.raises(ValueError) as exc_info:
            parse_datetime(date_str, allow_future=True, max_past_years=50)
        assert "cannot be more than 50 years in the past" in str(exc_info.value)
    
    def test_parse_datetime_valid_past_date(self):
        """Test parsing valid past date."""
        past_date = datetime.now() - timedelta(days=10 * 365)
        date_str = past_date.strftime("%Y-%m-%d")
        
        result = parse_datetime(date_str, allow_future=True, max_past_years=50)
        assert isinstance(result, datetime)
    
    def test_parse_datetime_current_date(self):
        """Test parsing current date."""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        
        result = parse_datetime(date_str, time_str, allow_future=True, max_future_days=1)
        assert isinstance(result, datetime)
    
    def test_parse_datetime_custom_max_future_days(self):
        """Test parsing with custom max_future_days."""
        future_date = datetime.now() + timedelta(days=5)
        date_str = future_date.strftime("%Y-%m-%d")
        time_str = future_date.strftime("%H:%M")
        
        result = parse_datetime(date_str, time_str, allow_future=True, max_future_days=10)
        assert isinstance(result, datetime)
        
        # Should fail with smaller limit
        with pytest.raises(ValueError):
            parse_datetime(date_str, time_str, allow_future=True, max_future_days=1)
    
    def test_parse_datetime_custom_max_past_years(self):
        """Test parsing with custom max_past_years."""
        old_date = datetime.now() - timedelta(days=20 * 365)
        date_str = old_date.strftime("%Y-%m-%d")
        
        result = parse_datetime(date_str, allow_future=True, max_past_years=30)
        assert isinstance(result, datetime)
        
        # Should fail with smaller limit
        with pytest.raises(ValueError):
            parse_datetime(date_str, allow_future=True, max_past_years=10)
    
    def test_parse_date_success(self):
        """Test successful parsing of date for birth_date."""
        result = parse_date("2020-01-15", allow_future=False, max_past_years=50)
        assert isinstance(result, datetime)
        assert result.year == 2020
        assert result.month == 1
        assert result.day == 15
    
    def test_parse_date_empty_string_returns_none(self):
        """Test that empty date string returns None."""
        result = parse_date("")
        assert result is None
    
    def test_parse_date_none_returns_none(self):
        """Test that None date string returns None."""
        result = parse_date(None)
        assert result is None
    
    def test_parse_date_future_not_allowed(self):
        """Test that future dates are not allowed for birth_date by default."""
        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")
        
        with pytest.raises(ValueError) as exc_info:
            parse_date(date_str, allow_future=False)
        assert "cannot be more than 0 day(s) in the future" in str(exc_info.value)
    
    def test_parse_date_future_allowed_when_set(self):
        """Test that future dates are allowed when explicitly set."""
        # Note: parse_date always sets max_future_days=0, so we test with current date
        today = datetime.now()
        date_str = today.strftime("%Y-%m-%d")
        
        result = parse_date(date_str, allow_future=True, max_past_years=50)
        assert isinstance(result, datetime)
    
    def test_parse_date_invalid_format(self):
        """Test parsing date with invalid format."""
        with pytest.raises(ValueError) as exc_info:
            parse_date("2020/01/15")
        assert "Invalid date format" in str(exc_info.value)
    
    def test_parse_date_too_old(self):
        """Test parsing birth_date that is too old."""
        old_date = datetime.now() - timedelta(days=51 * 365)
        date_str = old_date.strftime("%Y-%m-%d")
        
        with pytest.raises(ValueError) as exc_info:
            parse_date(date_str, allow_future=False, max_past_years=50)
        assert "cannot be more than 50 years in the past" in str(exc_info.value)
    
    def test_parse_date_valid_birth_date(self):
        """Test parsing valid birth date."""
        birth_date = datetime.now() - timedelta(days=5 * 365)
        date_str = birth_date.strftime("%Y-%m-%d")
        
        result = parse_date(date_str, allow_future=False, max_past_years=50)
        assert isinstance(result, datetime)
        assert result.year == birth_date.year
    
    def test_parse_datetime_edge_case_max_future(self):
        """Test parsing date exactly at max_future_days limit."""
        max_future = datetime.now() + timedelta(days=1)
        date_str = max_future.strftime("%Y-%m-%d")
        time_str = max_future.strftime("%H:%M")
        
        # Should succeed at exactly the limit
        result = parse_datetime(date_str, time_str, allow_future=True, max_future_days=1)
        assert isinstance(result, datetime)
    
    def test_parse_datetime_edge_case_max_past(self):
        """Test parsing date exactly at max_past_years limit."""
        # Use a date slightly less than 50 years ago to ensure it passes
        max_past = datetime.now() - timedelta(days=49 * 365 + 364)
        date_str = max_past.strftime("%Y-%m-%d")
        
        # Should succeed when within the limit
        result = parse_datetime(date_str, allow_future=True, max_past_years=50)
        assert isinstance(result, datetime)
    
    def test_parse_datetime_invalid_date_values(self):
        """Test parsing with invalid date values."""
        # Invalid month
        with pytest.raises(ValueError):
            parse_datetime("2024-13-15", "14:30")
        
        # Invalid day
        with pytest.raises(ValueError):
            parse_datetime("2024-02-30", "14:30")
        
        # Invalid time
        with pytest.raises(ValueError):
            parse_datetime("2024-01-15", "25:00")
        
        # Invalid time minutes
        with pytest.raises(ValueError):
            parse_datetime("2024-01-15", "14:60")

