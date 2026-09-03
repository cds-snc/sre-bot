"""Unit tests for the relocated pure Calendar-availability helpers."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
import pytz
from packages.incident.scheduling import availability


@pytest.fixture
def est_timezone():
    return pytz.timezone("US/Eastern")


@pytest.fixture
def fixed_utc_now():
    # This is a Monday
    return datetime(2023, 4, 10, 12, 0)


@pytest.fixture
def mock_year():
    return 2024


@pytest.fixture
def time_range():
    """Fixture providing standard time range for tests."""
    return {
        "time_min": "2023-04-01T00:00:00Z",
        "time_max": "2023-05-01T00:00:00Z",
    }


@patch("packages.incident.scheduling.availability.get_federal_holidays")
@patch("packages.incident.scheduling.availability.datetime")
def test_available_slot_on_first_weekday(mock_datetime, mock_federal_holidays, fixed_utc_now, mock_year, est_timezone):
    mock_datetime.utcnow.return_value = fixed_utc_now
    mock_datetime.return_value.year = mock_year
    mock_datetime.fromisoformat.side_effect = lambda d: datetime.fromisoformat(d[:-1])
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    {
                        "start": "2023-04-10T17:00:000Z",
                        "end": "2023-04-10T17:30:000Z",
                    }
                ]
            }
        }
    }
    mock_federal_holidays.return_value = {"holidays": [{"observedDate": "2024-01-01"}, {"observedDate": "2024-07-01"}]}

    expected_start_time = fixed_utc_now.replace(day=fixed_utc_now.day + 3, hour=17, minute=0, second=0, microsecond=0).astimezone(
        est_timezone
    )
    expected_end_time = expected_start_time + timedelta(minutes=30)

    actual_start, actual_end = availability.find_first_available_slot(
        freebusy_response, days_in_future=3, duration_minutes=30, search_days_limit=60
    )

    assert actual_start == expected_start_time
    assert actual_end == expected_end_time


@patch("packages.incident.scheduling.availability.get_federal_holidays")
@patch("packages.incident.scheduling.availability.datetime")
def test_opening_exists_after_busy_days(mock_datetime, mock_federal_holidays, fixed_utc_now, est_timezone):
    mock_datetime.utcnow.return_value = fixed_utc_now
    mock_datetime.return_value.year = 2024
    mock_datetime.fromisoformat.side_effect = lambda d: datetime.fromisoformat(d[:-1])
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    {"start": "2023-04-13T17:00:000Z", "end": "2023-04-13T19:00:000Z"},
                    {"start": "2023-04-14T17:00:000Z", "end": "2023-04-14T19:00:000Z"},
                    {"start": "2023-04-17T17:00:000Z", "end": "2023-04-17T19:00:000Z"},
                    {"start": "2023-04-18T17:00:000Z", "end": "2023-04-18T19:00:000Z"},
                ]
            }
        }
    }

    mock_federal_holidays.return_value = {"holidays": [{"observedDate": "2024-01-01"}, {"observedDate": "2024-07-01"}]}

    start, end = availability.find_first_available_slot(
        freebusy_response, days_in_future=3, duration_minutes=30, search_days_limit=60
    )
    expected_start = fixed_utc_now.replace(day=fixed_utc_now.day + 9, hour=17, minute=0, second=0, microsecond=0).astimezone(
        est_timezone
    )
    expected_end = expected_start + timedelta(minutes=30)

    assert start == expected_start and end == expected_end, "Expected to find an available slot correctly."


@patch("packages.incident.scheduling.availability.get_federal_holidays")
@patch("packages.incident.scheduling.availability.datetime")
def test_skipping_weekends(mock_datetime, mock_federal_holidays, fixed_utc_now, est_timezone):
    mock_datetime.utcnow.return_value = fixed_utc_now
    mock_datetime.fromisoformat.side_effect = lambda d: datetime.fromisoformat(d[:-1])
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    freebusy_response = {"calendars": {"primary": {"busy": []}}}

    mock_federal_holidays.return_value = {"holidays": [{"observedDate": "2024-01-01"}, {"observedDate": "2024-07-01"}]}

    start, end = availability.find_first_available_slot(
        freebusy_response, duration_minutes=30, days_in_future=1, search_days_limit=60
    )

    expected_start = fixed_utc_now.replace(day=fixed_utc_now.day + 1, hour=17, minute=0, second=0, microsecond=0).astimezone(
        est_timezone
    )
    expected_end = expected_start + timedelta(minutes=30)

    assert start == expected_start and end == expected_end, "Expected to find an available slot after skipping the weekend"


@patch("packages.incident.scheduling.availability.get_federal_holidays")
@patch("packages.incident.scheduling.availability.datetime")
def test_no_available_slots_within_search_limit(mock_datetime, mock_federal_holidays, fixed_utc_now, est_timezone):
    mock_datetime.utcnow.return_value = fixed_utc_now
    mock_datetime.fromisoformat.side_effect = lambda d: datetime.fromisoformat(d[:-1])
    mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    {"start": "2023-04-10T17:00:000Z", "end": "2023-08-13T19:00:000Z"},
                ]
            }
        }
    }

    mock_federal_holidays.return_value = {"holidays": [{"observedDate": "2024-01-01"}, {"observedDate": "2024-07-01"}]}

    start, end = availability.find_first_available_slot(
        freebusy_response, duration_minutes=30, days_in_future=3, search_days_limit=60
    )

    assert start is None and end is None, "Expected no available slots within the search limit"


def test_get_utc_hour_same_zone():
    """Test case for the same timezone (UTC)."""
    assert availability.get_utc_hour(13, 0, "UTC") == 13


def test_get_utc_hour_us_eastern_daylight_time_winter():
    """Test case for US Eastern Daylight Time during the winter."""
    tz_name = "US/Eastern"
    local_tz = pytz.timezone(tz_name)
    test_date = datetime(2023, 12, 1, 13, 0)
    localized_time = local_tz.localize(test_date)
    utc_time = localized_time.astimezone(pytz.utc).hour

    assert availability.get_utc_hour(13, 0, tz_name, test_date) == utc_time


def test_get_utc_hour_us_eastern_daylight_time_summer():
    """Test case for US Eastern Daylight Time (EDT, UTC-4) during the summer."""
    tz_name = "US/Eastern"
    local_tz = pytz.timezone(tz_name)
    test_date = datetime(2023, 8, 1, 13, 0)
    localized_time = local_tz.localize(test_date)
    utc_time = localized_time.astimezone(pytz.utc).hour

    assert availability.get_utc_hour(13, 0, tz_name, test_date) == utc_time


def test_get_utc_hour_pacific_time():
    """Test case for Pacific Standard Time (PST, UTC-8)."""
    test_date = datetime(2023, 12, 1, 13, 0)

    assert availability.get_utc_hour(13, 0, "US/Pacific", test_date) == 21


def test_get_utc_hour_with_invalid_timezone():
    """Test case for invalid timezone input."""
    with pytest.raises(pytz.UnknownTimeZoneError):
        availability.get_utc_hour(13, 0, "Invalid/Zone")


def test_get_utc_hour_midnight_transition():
    """Test case for midnight transition without having to change for DST."""
    tz = pytz.timezone("US/Eastern")
    local_dt = datetime.now(tz).replace(hour=23, minute=0, second=0, microsecond=0)
    expected_utc_hour = local_dt.astimezone(pytz.utc).hour

    assert availability.get_utc_hour(23, 0, "US/Eastern") == expected_utc_hour


def test_get_utc_hour_negative_hour():
    """Test case for invalid hour input."""
    with pytest.raises(ValueError):
        availability.get_utc_hour(-1, 0, "UTC")


def test_get_utc_hour_invalid_minute():
    """Test case for invalid minute input."""
    with pytest.raises(ValueError):
        availability.get_utc_hour(13, 60, "UTC")


def test_identify_unavailable_users_exact_match(time_range):
    """Test identifying users with busy periods exactly matching the search range."""
    freebusy_response = {
        "calendars": {
            "user1@example.com": {"busy": [{"start": time_range["time_min"], "end": time_range["time_max"]}]},
            "user2@example.com": {"busy": [{"start": "2023-04-05T00:00:00Z", "end": "2023-04-10T00:00:00Z"}]},
        }
    }

    result = availability.identify_unavailable_users(freebusy_response, time_range["time_min"], time_range["time_max"])

    assert result == ["user1@example.com"]


def test_identify_unavailable_users_within_threshold(time_range):
    """Test identifying users with busy periods just outside the 1-hour threshold for end time."""
    start_dt = datetime.fromisoformat(time_range["time_min"][:-1]).replace(tzinfo=UTC)
    end_dt = datetime.fromisoformat(time_range["time_max"][:-1]).replace(tzinfo=UTC)

    close_start = (start_dt + timedelta(minutes=30)).isoformat() + "Z"
    far_end = (end_dt - timedelta(minutes=61)).isoformat() + "Z"

    freebusy_response = {"calendars": {"user1@example.com": {"busy": [{"start": close_start, "end": far_end}]}}}

    result = availability.identify_unavailable_users(freebusy_response, time_range["time_min"], time_range["time_max"])

    assert result == []


def test_identify_unavailable_users_outside_threshold(time_range):
    """Test users with busy periods outside the 1-hour threshold."""
    start_dt = datetime.fromisoformat(time_range["time_min"][:-1]).replace(tzinfo=UTC)
    end_dt = datetime.fromisoformat(time_range["time_max"][:-1]).replace(tzinfo=UTC)

    far_start = (start_dt + timedelta(hours=2)).isoformat() + "Z"
    far_end = (end_dt - timedelta(hours=2)).isoformat() + "Z"

    freebusy_response = {"calendars": {"user1@example.com": {"busy": [{"start": far_start, "end": far_end}]}}}

    result = availability.identify_unavailable_users(freebusy_response, time_range["time_min"], time_range["time_max"])

    assert result == []


def test_identify_unavailable_users_multiple_busy_periods(time_range):
    """Test users with multiple busy periods are not identified."""
    freebusy_response = {
        "calendars": {
            "user1@example.com": {"busy": [{"start": time_range["time_min"], "end": time_range["time_max"]}]},
            "user2@example.com": {
                "busy": [
                    {"start": time_range["time_min"], "end": time_range["time_max"]},
                    {"start": "2023-04-05T00:00:00Z", "end": "2023-04-10T00:00:00Z"},
                ]
            },
        }
    }

    result = availability.identify_unavailable_users(freebusy_response, time_range["time_min"], time_range["time_max"])

    assert result == ["user1@example.com"]


def test_identify_unavailable_users_with_errors(time_range):
    """Test users with calendar errors are skipped."""
    freebusy_response = {
        "calendars": {
            "user1@example.com": {"errors": [{"domain": "global", "reason": "notFound"}]},
            "user2@example.com": {"busy": [{"start": time_range["time_min"], "end": time_range["time_max"]}]},
        }
    }

    result = availability.identify_unavailable_users(freebusy_response, time_range["time_min"], time_range["time_max"])

    assert result == ["user2@example.com"]


def test_identify_unavailable_users_no_busy_data(time_range):
    """Test users with no busy data are skipped."""
    freebusy_response = {
        "calendars": {
            "user1@example.com": {},
            "user2@example.com": {"busy": [{"start": time_range["time_min"], "end": time_range["time_max"]}]},
        }
    }

    result = availability.identify_unavailable_users(freebusy_response, time_range["time_min"], time_range["time_max"])

    assert result == ["user2@example.com"]


def test_identify_unavailable_users_empty_busy_list(time_range):
    """Test users with empty busy list are not identified."""
    freebusy_response = {
        "calendars": {
            "user1@example.com": {"busy": []},
            "user2@example.com": {"busy": [{"start": time_range["time_min"], "end": time_range["time_max"]}]},
        }
    }

    result = availability.identify_unavailable_users(freebusy_response, time_range["time_min"], time_range["time_max"])

    assert result == ["user2@example.com"]


def test_identify_unavailable_users_edge_case_threshold(time_range):
    """Test edge cases exactly at the 1-hour threshold."""
    start_dt = datetime.fromisoformat(time_range["time_min"][:-1]).replace(tzinfo=UTC)
    end_dt = datetime.fromisoformat(time_range["time_max"][:-1]).replace(tzinfo=UTC)

    threshold_start = (start_dt + timedelta(seconds=3599)).isoformat() + "Z"
    threshold_end = (end_dt - timedelta(seconds=3599)).isoformat() + "Z"

    freebusy_response = {"calendars": {"user1@example.com": {"busy": [{"start": threshold_start, "end": threshold_end}]}}}

    result = availability.identify_unavailable_users(freebusy_response, time_range["time_min"], time_range["time_max"])

    assert result == ["user1@example.com"]


def test_identify_unavailable_users_empty_response(time_range):
    """Test with empty response."""
    freebusy_response = {"calendars": {}}

    result = availability.identify_unavailable_users(freebusy_response, time_range["time_min"], time_range["time_max"])

    assert result == []
