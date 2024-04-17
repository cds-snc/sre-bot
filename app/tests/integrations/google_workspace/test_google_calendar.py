"""Unit tests for google_calendar module."""

import json
from unittest.mock import patch, MagicMock
from datetime import datetime
import pytest
import pytz
from integrations.google_workspace import google_calendar


# Fixture to mock the event details JSON string
@pytest.fixture
def event_details():
    return json.dumps(
        {
            "emails": ["user1@example.com", "user2@example.com"],
            "topic": "Incident Response Meeting",
        }
    )


# Fixture to mock the calendar service object
@pytest.fixture
def calendar_service_mock():
    # Mock for the Google Calendar service object
    service_mock = MagicMock()

    # Properly set the return value for the execute method to return the expected dictionary directly
    service_mock.events.return_value.insert.return_value.execute.return_value = {
        "htmlLink": "https://calendar.google.com/event_link"
    }

    return service_mock


# Fixture to mock the timezone
@pytest.fixture
def est_timezone():
    return pytz.timezone("US/Eastern")


# Fixture to mock the datetime.now() function
@pytest.fixture
def mock_datetime_now(est_timezone):
    """Fixture to mock datetime.now() to return a specific time in the EST timezone."""
    # Mocking the specific date we want to consider as "now"
    specific_now = datetime(
        2023, 4, 10, 10, 0, tzinfo=est_timezone
    )  # Assuming April 10, 2023, is a Monday

    with patch(
        "integrations.google_workspace.google_calendar.datetime"
    ) as mock_datetime:
        mock_datetime.now.return_value = specific_now
        mock_datetime.strptime.side_effect = lambda *args, **kw: datetime.strptime(
            *args, **kw
        )
        yield mock_datetime


# Fixture to mock the list of calendars
@pytest.fixture
def items():
    return [{"id": "calendar1"}, {"id": "calendar2"}]


@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
def test_get_freebusy_required_args_only(mock_execute_google_api_call, items):
    mock_execute_google_api_call.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"

    google_calendar.get_freebusy(time_min, time_max, items)

    mock_execute_google_api_call.assert_called_once_with(
        "calendar",
        "v3",
        "freebusy",
        "query",
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "calendar1"}, {"id": "calendar2"}],
        },
    )


@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
def test_get_freebusy_optional_args(mock_execute_google_api_call, items):
    mock_execute_google_api_call.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"
    time_zone = "America/Los_Angeles"
    calendar_expansion_max = 20
    group_expansion_max = 30

    google_calendar.get_freebusy(
        time_min,
        time_max,
        items,
        time_zone=time_zone,
        calendar_expansion_max=calendar_expansion_max,
        group_expansion_max=group_expansion_max,
    )

    mock_execute_google_api_call.assert_called_once_with(
        "calendar",
        "v3",
        "freebusy",
        "query",
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "calendar1"}, {"id": "calendar2"}],
            "timeZone": "America/Los_Angeles",
            "calendarExpansionMax": 20,
            "groupExpansionMax": 30,
        },
    )


@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
def test_get_freebusy_returns_object(mock_execute):
    mock_execute.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"
    items = ["calendar1", "calendar2"]

    result = google_calendar.get_freebusy(time_min, time_max, items)

    assert isinstance(result, dict)


@patch("os.environ.get", return_value="test_email")
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
@patch("integrations.google_workspace.google_calendar.convert_to_camel_case")
def test_insert_event_no_kwargs_no_delegated_email(
    mock_convert, mock_execute, mock_get
):
    mock_execute.return_value = {"htmlLink": "test_link"}
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    result = google_calendar.insert_event(start, end, emails, title)
    assert result == "test_link"
    mock_execute.assert_called_once_with(
        "calendar",
        "v3",
        "events",
        "insert",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        delegated_user_email="test_email",
        body={
            "start": {"dateTime": start.isoformat(), "timeZone": "America/New_York"},
            "end": {"dateTime": end.isoformat(), "timeZone": "America/New_York"},
            "attendees": [{"email": email.strip()} for email in emails],
            "summary": title,
        },
        calendarId="primary",
    )
    assert not mock_convert.called
    assert mock_get.called_once_with("SRE_BOT_EMAIL")


@patch("os.environ.get", return_value="test_email")
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
@patch("integrations.google_workspace.google_calendar.convert_to_camel_case")
def test_insert_event_with_kwargs(mock_convert, mock_execute, mock_get):
    mock_execute.return_value = {"htmlLink": "test_link"}
    mock_convert.side_effect = lambda x: x  # just return the same value
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    kwargs = {
        "location": "Test Location",
        "description": "Test Description",
        "delegated_user_email": "test_custom_email",
    }
    result = google_calendar.insert_event(start, end, emails, title, **kwargs)
    assert result == "test_link"
    mock_execute.assert_called_once_with(
        "calendar",
        "v3",
        "events",
        "insert",
        scopes=["https://www.googleapis.com/auth/calendar.events"],
        delegated_user_email="test_custom_email",
        body={
            "start": {"dateTime": start.isoformat(), "timeZone": "America/New_York"},
            "end": {"dateTime": end.isoformat(), "timeZone": "America/New_York"},
            "attendees": [{"email": email.strip()} for email in emails],
            "summary": title,
            **kwargs,
        },
        calendarId="primary",
    )
    for key in kwargs:
        mock_convert.assert_any_call(key)

    assert not mock_get.called


@patch("integrations.google_workspace.google_service.handle_google_api_errors")
@patch("os.environ.get", return_value="test_email")
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
@patch("integrations.google_workspace.google_calendar.convert_to_camel_case")
def test_insert_event_api_call_error(
    mock_convert, mock_execute, mock_get, mock_handle_errors, caplog
):
    mock_execute.side_effect = Exception("API call error")
    start = datetime.now()
    end = start
    emails = ["test1@test.com", "test2@test.com"]
    title = "Test Event"
    google_calendar.insert_event(start, end, emails, title)
    assert (
        "An unexpected error occurred in function 'insert_event': API call error"
        in caplog.text
    )


# Test out the find_first_available_slot function on the first available weekday
def test_available_slot_on_first_weekday(mock_datetime_now, est_timezone):
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    # Assuming the provided busy time is on April 10, 2023, from 1 PM to 1:30 PM UTC (9 AM to 9:30 AM EST)
                    {
                        "start": "2023-04-10T17:00:00Z",
                        "end": "2023-04-10T17:30:00Z",
                    }  # Busy at 1 PM to 1:30 PM EST on April 10
                ]
            }
        }
    }

    start, end = google_calendar.find_first_available_slot(
        freebusy_response, duration_minutes=30, days_in_future=3, search_days_limit=60
    )

    # Since April 10 is the "current" day and we start searching from 3 days in the future (April 13),
    # we expect the function to find the first available slot on April 13 between 1 PM and 3 PM EST.
    expected_start = datetime(
        2023, 4, 13, 13, 0, tzinfo=est_timezone
    )  # Expected start time in EST
    expected_end = datetime(
        2023, 4, 13, 13, 30, tzinfo=est_timezone
    )  # Expected end time in EST

    assert (
        start == expected_start and end == expected_end
    ), "The function should find the first available slot on April 13, 2023, from 1 PM to 1:30 PM EST."


# Test out the find_first_available_slot function when multiple busy days
def test_opening_exists_after_busy_days(mock_datetime_now, est_timezone):
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    {"start": "2023-04-13T17:00:00Z", "end": "2023-04-13T19:00:00Z"},
                    {"start": "2023-04-14T17:00:00Z", "end": "2023-04-14T19:00:00Z"},
                    {"start": "2023-04-17T17:00:00Z", "end": "2023-04-17T19:00:00Z"},
                    {"start": "2023-04-18T17:00:00Z", "end": "2023-04-18T19:00:00Z"},
                ]
            }
        }
    }

    start, end = google_calendar.find_first_available_slot(
        freebusy_response, duration_minutes=30, days_in_future=3, search_days_limit=60
    )

    expected_start = datetime(
        2023, 4, 13, 14, 30, tzinfo=est_timezone
    )  # Expected start time in EST
    expected_end = datetime(
        2023, 4, 13, 15, 0, tzinfo=est_timezone
    )  # Expected end time in EST

    assert (
        start == expected_start and end == expected_end
    ), "Expected to find an available slot correctly."


# Test that weekends are skipped when searching for available slots
def test_skipping_weekends(mock_datetime_now, est_timezone):
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    # Assuming weekdays are busy, but we expect the function to skip weekends automatically
                ]
            }
        }
    }

    # For this test, ensure the mocked 'now' falls before a weekend, and verify that the function skips to the next weekday
    start, end = google_calendar.find_first_available_slot(
        freebusy_response, duration_minutes=30, days_in_future=1, search_days_limit=60
    )

    # Adjust these expected values based on the specific 'now' being mocked
    expected_start = datetime(2023, 4, 11, 13, 0, tzinfo=est_timezone)
    expected_end = datetime(2023, 4, 11, 13, 30, tzinfo=est_timezone)

    assert (
        start == expected_start and end == expected_end
    ), "Expected to find an available slot after skipping the weekend"


# Test that no available slots are found within the search limit
def test_no_available_slots_within_search_limit(mock_datetime_now):
    freebusy_response = {
        "calendars": {
            "primary": {
                "busy": [
                    # Simulate a scenario where every eligible day within the search window is fully booked
                    # For simplicity, let's assume a pattern that covers the search hours for the next 60 days
                    {"start": "2023-04-10T17:00:00Z", "end": "2023-08-13T19:00:00Z"},
                ]
            }
        }
    }

    start, end = google_calendar.find_first_available_slot(
        freebusy_response, duration_minutes=30, days_in_future=3, search_days_limit=60
    )

    assert (
        start is None and end is None
    ), "Expected no available slots within the search limit"
