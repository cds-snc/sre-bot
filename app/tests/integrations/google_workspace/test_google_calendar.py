"""Unit tests for google_calendar module."""

import json
from unittest.mock import ANY, patch, MagicMock
from datetime import datetime, timedelta
import pytest
import pytz
from integrations.google_workspace import google_calendar

# Mocked dependencies
SRE_BOT_EMAIL = "sre-bot@cds-snc.ca"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


# Fixture to mock the event details JSON string
@pytest.fixture
def event_details():
    return json.dumps(
        {
            "emails": ["user1@example.com", "user2@example.com"],
            "topic": "Incident Response Meeting",
        }
    )


# # Fixture to mock the Google service object
# @pytest.fixture
# def google_service_mock():
#     service = MagicMock()
#     service.freebusy().query().execute.return_value = "Mocked FreeBusy Query Result"
#     return service


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


@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
def test_get_freebusy_required_args_only(mock_execute):
    mock_execute.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"
    items = ["calendar1", "calendar2"]

    google_calendar.get_freebusy(time_min, time_max, items)

    mock_execute.assert_called_once_with(
        "calendar",
        "v3",
        "freebusy",
        "query",
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": items,
        },
    )


@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
def test_get_freebusy_optional_args(mock_execute):
    mock_execute.return_value = {}
    time_min = "2022-01-01T00:00:00Z"
    time_max = "2022-01-02T00:00:00Z"
    items = ["calendar1", "calendar2"]
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

    mock_execute.assert_called_once_with(
        "calendar",
        "v3",
        "freebusy",
        "query",
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": items,
            "timeZone": time_zone,
            "calendarExpansionMax": calendar_expansion_max,
            "groupExpansionMax": group_expansion_max,
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


# Test out the schedule_event function is successful
@patch("integrations.google_workspace.google_calendar.get_freebusy")
@patch("integrations.google_workspace.google_calendar.find_first_available_slot")
@patch("integrations.google_workspace.google_calendar.insert_event")
def test_schedule_event_successful(
    insert_event_mock,
    find_first_available_slot_mock,
    get_freebusy_mock,
    event_details,
):
    # Set up the mock return values
    get_freebusy_mock.return_value = {
        "result": "Mocked FreeBusy Query Result"
    }
    find_first_available_slot_mock.return_value = (
        datetime.utcnow().isoformat(),
        (datetime.utcnow() + timedelta(hours=1)).isoformat(),
    )
    insert_event_mock.return_value = "https://calendar.link"
    mock_days = 1

    # Parse event details
    event_details_dict = json.loads(event_details)
    emails = event_details_dict["emails"]
    topic = event_details_dict["topic"]

    # Call the function under test
    event_link = google_calendar.schedule_event(event_details, mock_days)

    # Assertions
    get_freebusy_mock.assert_called_once_with(
        ANY,  # Replace with expected arguments
        ANY,  # Replace with expected arguments
        ANY,  # Replace with expected arguments
    )
    find_first_available_slot_mock.assert_called_once_with(
        {"result": "Mocked FreeBusy Query Result"}, mock_days
    )
    insert_event_mock.assert_called_once_with(
        find_first_available_slot_mock.return_value[0],
        find_first_available_slot_mock.return_value[1],
        emails,
        topic,
    )

    assert event_link == "https://calendar.link"


# Test out the schedule_event function when no available slots are found
@patch("integrations.google_workspace.google_calendar.execute_google_api_call")
@patch("integrations.google_workspace.google_calendar.find_first_available_slot")
@patch("integrations.google_workspace.google_calendar.insert_event")
def test_schedule_event_no_available_slots(
    insert_event_mock,
    find_first_available_slot_mock,
    execute_google_api_call_mock,
    event_details,
):
    # Set up the mock return values
    find_first_available_slot_mock.return_value = (None, None)
    mock_days = 1

    # Call the function under test
    event_link = google_calendar.schedule_event(event_details, mock_days)

    # Assertions
    assert event_link is None
    insert_event_mock.assert_not_called()
    execute_google_api_call_mock.assert_called_once()


# Test out the book_calendar_event function is successful
def test_book_calendar_event_success(calendar_service_mock):
    start = datetime.utcnow()
    end = start + timedelta(hours=1)
    emails = ["user1@example.com", "user2@example.com"]
    incident_name = "Network Outage"

    event_link = google_calendar.book_calendar_event(
        calendar_service_mock, start, end, emails, incident_name
    )

    assert event_link == "https://calendar.google.com/event_link"
    calendar_service_mock.events().insert.assert_called_once()
    assert (
        calendar_service_mock.events().insert.call_args[1]["body"]["summary"]
        == "Retro Network Outage"
    )
    assert calendar_service_mock.events().insert.call_args[1]["sendUpdates"] == "all"


# Test out the book_calendar_event function with empty emails
def test_book_calendar_event_with_empty_emails(calendar_service_mock):
    start = datetime.utcnow()
    end = start + timedelta(hours=1)
    emails = []
    incident_name = "System Upgrade"

    event_link = google_calendar.book_calendar_event(
        calendar_service_mock, start, end, emails, incident_name
    )

    assert event_link == "https://calendar.google.com/event_link"
    assert (
        len(calendar_service_mock.events().insert.call_args[1]["body"]["attendees"])
        == 0
    )


# Test out the book_calendar_event function with no conference data
def test_book_calendar_event_with_no_conference_data(calendar_service_mock):
    start = datetime.utcnow()
    end = start + timedelta(hours=1)
    emails = ["user1@example.com"]
    incident_name = "Database Migration"

    # Simulate behavior when conference data is not provided by the API response
    calendar_service_mock.events().insert().execute.return_value = {
        "htmlLink": "https://calendar.google.com/event_link",
        "conferenceData": None,
    }

    event_link = google_calendar.book_calendar_event(
        calendar_service_mock, start, end, emails, incident_name
    )

    assert event_link == "https://calendar.google.com/event_link"
    assert (
        "conferenceData" in calendar_service_mock.events().insert.call_args[1]["body"]
    )


# Test out the book_calendar_event function with no HTML link
def test_book_calendar_event_no_html_link(calendar_service_mock):
    # Adjust the mock to not include 'htmlLink' in the response.
    calendar_service_mock.events.return_value.insert.return_value.execute.return_value = (
        {}
    )
    start = datetime.utcnow()
    end = start + timedelta(hours=1)
    emails = ["user@example.com"]
    incident_name = "No Link Incident"

    event_link = google_calendar.book_calendar_event(
        calendar_service_mock, start, end, emails, incident_name
    )

    # Assert that the function handles the missing 'htmlLink' gracefully.
    assert event_link is None


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
