"""Tests for working hours service."""
import pytest
from unittest.mock import patch
import datetime
from zoneinfo import ZoneInfo

from services.working_hours_service import (
    is_within_working_hours,
    get_next_working_hours_start,
    get_off_hours_message
)


class TestIsWithinWorkingHours:
    """Tests for is_within_working_hours function."""

    @pytest.mark.asyncio
    async def test_working_hours_disabled(self):
        """Test that function returns True when working hours are disabled."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.ENABLE_WORKING_HOURS = False
            
            result = is_within_working_hours()
            assert result is True

    @pytest.mark.asyncio
    async def test_within_working_hours_weekday(self):
        """Test that function returns True during working hours on weekday."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.ENABLE_WORKING_HOURS = True
            mock_settings.SUPPORT_HOURS_START = 9
            mock_settings.SUPPORT_HOURS_END = 18
            mock_settings.SUPPORT_TIMEZONE = "UTC"
            
            # Mock datetime to be Tuesday 12:00
            mock_now = datetime.datetime(2024, 1, 2, 12, 0, 0, tzinfo=ZoneInfo("UTC"))  # Tuesday
            with patch("services.working_hours_service.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = mock_now
                
                result = is_within_working_hours()
                assert result is True

    @pytest.mark.asyncio
    async def test_outside_working_hours_before(self):
        """Test that function returns False before working hours."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.ENABLE_WORKING_HOURS = True
            mock_settings.SUPPORT_HOURS_START = 9
            mock_settings.SUPPORT_HOURS_END = 18
            mock_settings.SUPPORT_TIMEZONE = "UTC"
            
            # Mock datetime to be Tuesday 08:00
            mock_now = datetime.datetime(2024, 1, 2, 8, 0, 0, tzinfo=ZoneInfo("UTC"))  # Tuesday
            with patch("services.working_hours_service.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = mock_now
                
                result = is_within_working_hours()
                assert result is False

    @pytest.mark.asyncio
    async def test_outside_working_hours_after(self):
        """Test that function returns False after working hours."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.ENABLE_WORKING_HOURS = True
            mock_settings.SUPPORT_HOURS_START = 9
            mock_settings.SUPPORT_HOURS_END = 18
            mock_settings.SUPPORT_TIMEZONE = "UTC"
            
            # Mock datetime to be Tuesday 19:00
            mock_now = datetime.datetime(2024, 1, 2, 19, 0, 0, tzinfo=ZoneInfo("UTC"))  # Tuesday
            with patch("services.working_hours_service.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = mock_now
                
                result = is_within_working_hours()
                assert result is False

    @pytest.mark.asyncio
    async def test_weekend_not_working(self):
        """Test that function returns False on weekends."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.ENABLE_WORKING_HOURS = True
            mock_settings.SUPPORT_HOURS_START = 9
            mock_settings.SUPPORT_HOURS_END = 18
            mock_settings.SUPPORT_TIMEZONE = "UTC"
            
            # Mock datetime to be Saturday 12:00
            mock_now = datetime.datetime(2024, 1, 6, 12, 0, 0, tzinfo=ZoneInfo("UTC"))  # Saturday
            with patch("services.working_hours_service.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = mock_now
                
                result = is_within_working_hours()
                assert result is False

    @pytest.mark.asyncio
    async def test_invalid_timezone_fallback(self):
        """Test that invalid timezone falls back to UTC."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.ENABLE_WORKING_HOURS = True
            mock_settings.SUPPORT_HOURS_START = 9
            mock_settings.SUPPORT_HOURS_END = 18
            mock_settings.SUPPORT_TIMEZONE = "Invalid/Timezone"
            
            # Should not raise exception
            result = is_within_working_hours()
            assert isinstance(result, bool)


class TestGetNextWorkingHoursStart:
    """Tests for get_next_working_hours_start function."""

    @pytest.mark.asyncio
    async def test_today_before_start(self):
        """Test returns 'today' when before working hours on weekday."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.SUPPORT_HOURS_START = 9
            mock_settings.SUPPORT_TIMEZONE = "UTC"
            
            # Tuesday 07:00
            mock_now = datetime.datetime(2024, 1, 2, 7, 0, 0, tzinfo=ZoneInfo("UTC"))
            with patch("services.working_hours_service.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = mock_now
                mock_dt.timedelta = datetime.timedelta
                
                result = get_next_working_hours_start()
                assert "сегодня" in result

    @pytest.mark.asyncio
    async def test_tomorrow(self):
        """Test returns 'tomorrow' when after working hours on weekday."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.SUPPORT_HOURS_START = 9
            mock_settings.SUPPORT_TIMEZONE = "UTC"
            
            # Tuesday 19:00
            mock_now = datetime.datetime(2024, 1, 2, 19, 0, 0, tzinfo=ZoneInfo("UTC"))
            with patch("services.working_hours_service.datetime") as mock_dt:
                mock_dt.datetime.now.return_value = mock_now
                mock_dt.timedelta = datetime.timedelta
                
                result = get_next_working_hours_start()
                assert "завтра" in result


class TestGetOffHoursMessage:
    """Tests for get_off_hours_message function."""

    @pytest.mark.asyncio
    async def test_message_contains_hours(self):
        """Test that off-hours message contains working hours."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.SUPPORT_HOURS_START = 9
            mock_settings.SUPPORT_HOURS_END = 18
            mock_settings.SUPPORT_TIMEZONE = "UTC"
            
            with patch("services.working_hours_service.get_next_working_hours_start", return_value="завтра в 9:00"):
                result = get_off_hours_message()
                
                assert "9:00" in result
                assert "18:00" in result
                assert "нерабочее время" in result

    @pytest.mark.asyncio
    async def test_message_contains_next_time(self):
        """Test that off-hours message contains next available time."""
        with patch("services.working_hours_service.settings") as mock_settings:
            mock_settings.SUPPORT_HOURS_START = 9
            mock_settings.SUPPORT_HOURS_END = 18
            mock_settings.SUPPORT_TIMEZONE = "UTC"
            
            with patch("services.working_hours_service.get_next_working_hours_start", return_value="в понедельник в 9:00"):
                result = get_off_hours_message()
                
                assert "понедельник" in result
